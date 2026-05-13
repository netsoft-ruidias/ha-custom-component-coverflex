"""DataUpdateCoordinator for the Coverflex integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CoverflexAPI
from .exceptions import CoverflexAPIError
from .interfaces import Card, Pocket, Transaction
from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    CONF_USER_AGENT_TOKEN,
    CONF_REFRESH_TOKEN,
    DEFAULT_TRANSACTIONS_COUNT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoverflexData:
    """Data returned by a single coordinator refresh."""

    card: Card
    pockets: list[Pocket]
    transactions: dict[str, list[Transaction]]  # keyed by pocket_id


class CoverflexCoordinator(DataUpdateCoordinator[CoverflexData]):
    """Coordinator that manages all Coverflex API calls.

    Token strategy (in order of priority):
    1. Renew access_token via refresh_token (no credentials needed).
       On success, persist the new refresh_token immediately.
    2. Login with credentials + user_agent_token (no OTP needed).
    3. All else fails → trigger a reauth flow so the user can re-enter credentials / OTP.

    The access_token is kept in memory only (_access_token).
    The refresh_token and user_agent_token are persisted in config_entry.data.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CoverflexAPI,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._entry = entry
        self._api = api
        self._access_token: str | None = None
        # Cache: pocket_id → last known balance (to detect changes)
        self._last_balances: dict[str, float] = {}
        # Cache: pocket_id → last fetched transactions list
        self._cached_transactions: dict[str, list[Transaction]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _async_obtain_access_token(self) -> str:
        """Return a valid access_token, trying each authentication level in order."""
        data = self._entry.data

        # Level 1 — silent renewal via refresh_token
        refresh_token: str | None = data.get(CONF_REFRESH_TOKEN)
        if refresh_token:
            renewed = await self._api.refresh_access_token(refresh_token)
            if renewed and renewed.get("access_token"):
                _LOGGER.debug("Access token renewed via refresh_token.")
                # Persist the new (rotated) refresh_token immediately
                await self._async_save_tokens(
                    refresh_token=renewed["refresh_token"],
                    user_agent_token=data.get(CONF_USER_AGENT_TOKEN),
                )
                return renewed["access_token"]
            _LOGGER.debug("refresh_token expired or invalid, falling back to login.")

        # Level 2 — login with credentials + user_agent_token (skip OTP)
        user_agent_token: str | None = data.get(CONF_USER_AGENT_TOKEN)
        username: str = data[CONF_USERNAME]
        password: str = data[CONF_PASSWORD]

        try:
            token = await self._api.login(username, password, user_agent_token=user_agent_token)
            if token:
                _LOGGER.debug("Logged in via user_agent_token.")
                return token
        except Exception:
            pass

        # Level 3 — all fallbacks exhausted → request reauth from the user
        _LOGGER.warning(
            "All authentication methods failed. Requesting reauth for entry %s.",
            self._entry.entry_id,
        )
        raise ConfigEntryAuthFailed("All Coverflex authentication methods failed.")

    async def _async_save_tokens(
        self,
        refresh_token: str | None,
        user_agent_token: str | None,
    ) -> None:
        """Persist updated tokens into config_entry.data without triggering a reload."""
        new_data = {
            **self._entry.data,
            **(
                {CONF_REFRESH_TOKEN: refresh_token}
                if refresh_token is not None
                else {}
            ),
            **(
                {CONF_USER_AGENT_TOKEN: user_agent_token}
                if user_agent_token is not None
                else {}
            ),
        }
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

    # ------------------------------------------------------------------
    # DataUpdateCoordinator protocol
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> CoverflexData:
        """Fetch the latest data from the Coverflex API."""
        try:
            self._access_token = await self._async_obtain_access_token()

            card = await self._api.get_card(self._access_token)
            pockets = await self._api.get_balances(self._access_token)

            if card is None or pockets is None:
                raise UpdateFailed("Coverflex API returned incomplete data.")

            # Fetch transactions only for pockets whose balance changed (or first run)
            for pocket in pockets:
                previous = self._last_balances.get(pocket.id)
                if previous is None or previous != pocket.balance:
                    _LOGGER.debug(
                        "Balance changed for pocket %s (%.2f → %.2f), fetching transactions.",
                        pocket.type,
                        previous if previous is not None else 0.0,
                        pocket.balance,
                    )
                    movements = await self._api.get_movements(
                        self._access_token, pocket.id, DEFAULT_TRANSACTIONS_COUNT
                    )
                    self._cached_transactions[pocket.id] = movements or []
                    self._last_balances[pocket.id] = pocket.balance
                else:
                    _LOGGER.debug(
                        "Balance unchanged for pocket %s (%.2f), reusing cached transactions.",
                        pocket.type,
                        pocket.balance,
                    )

            return CoverflexData(card=card, pockets=pockets, transactions=self._cached_transactions)

        except ConfigEntryAuthFailed:
            # Let HA handle the reauth flow — do not wrap in UpdateFailed
            raise
        except CoverflexAPIError as err:
            raise UpdateFailed(f"Coverflex API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error communicating with Coverflex: {err}") from err

    # ------------------------------------------------------------------
    # Public helpers (called by config_flow after reauth)
    # ------------------------------------------------------------------

    async def async_update_trust_tokens(
        self,
        refresh_token: str,
        user_agent_token: str,
    ) -> None:
        """Called by the reauth flow after a successful OTP login to persist new tokens."""
        await self._async_save_tokens(refresh_token, user_agent_token)

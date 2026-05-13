"""Config flow for Coverflex integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoverflexAPI
from .exceptions import OTPRequiredException, AuthenticationError
from .const import DOMAIN, CONF_USER_AGENT_TOKEN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

_SCHEMA_OTP = vol.Schema(
    {
        vol.Required("otp"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Multi-step config flow for Coverflex.

    Step 1 (user):  Username + Password
      → success without OTP  → get_trust_token → create entry
      → OTPRequiredException  → show step 2
      → auth failure          → show error, repeat step 1

    Step 2 (otp):  6-digit OTP code
      → success  → get_trust_token → create entry
      → failure  → show error, repeat step 2
    """

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._otp_channel: str = ""
        self._phone_last_digits: str = ""

    # ------------------------------------------------------------------
    # Step 1 — Credentials
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip().lower()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            api = CoverflexAPI(async_get_clientsession(self.hass))

            try:
                token = await api.login(username, password)
                # Direct success (no OTP required)
                trust = await api.get_trust_token(token)
                return self._async_create_entry(
                    username=username,
                    password=password,
                    trust=trust,
                )

            except OTPRequiredException as exc:
                # Store state for the OTP step
                self._username = username
                self._password = password
                self._otp_channel = exc.otp_channel
                self._phone_last_digits = exc.phone_last_digits
                return await self.async_step_otp()

            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Coverflex login")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=_SCHEMA_USER,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2 — OTP
    # ------------------------------------------------------------------

    async def async_step_otp(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle the OTP verification step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = CoverflexAPI(async_get_clientsession(self.hass))
            otp_code = user_input["otp"].strip()

            try:
                token = await api.login_with_otp(self._username, self._password, otp_code)
                if not token:
                    errors["base"] = "invalid_otp"
                else:
                    trust = await api.get_trust_token(token)
                    return self._async_create_entry(
                        username=self._username,
                        password=self._password,
                        trust=trust,
                    )
            except Exception:
                _LOGGER.exception("Unexpected error during Coverflex OTP verification")
                errors["base"] = "invalid_otp"

        return self.async_show_form(
            step_id="otp",
            data_schema=_SCHEMA_OTP,
            errors=errors,
            description_placeholders={
                "otp_channel": self._otp_channel,
                "phone_last_digits": self._phone_last_digits,
            },
        )

    # ------------------------------------------------------------------
    # Reauth flow — triggered by the coordinator when all tokens expire
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict
    ) -> config_entries.FlowResult:
        """Start the reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle reauth: same as step_user but updates the existing entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            api = CoverflexAPI(async_get_clientsession(self.hass))

            try:
                token = await api.login(username, password)
                trust = await api.get_trust_token(token)
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_PASSWORD: password,
                        CONF_USER_AGENT_TOKEN: trust.get(CONF_USER_AGENT_TOKEN, ""),
                        CONF_REFRESH_TOKEN: trust.get(CONF_REFRESH_TOKEN, ""),
                    },
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except OTPRequiredException as exc:
                self._username = username
                self._password = password
                self._otp_channel = exc.otp_channel
                self._phone_last_digits = exc.phone_last_digits
                return await self.async_step_reauth_otp()

            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Coverflex reauth")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
        )

    async def async_step_reauth_otp(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle OTP verification during reauth."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            api = CoverflexAPI(async_get_clientsession(self.hass))
            otp_code = user_input["otp"].strip()

            try:
                token = await api.login_with_otp(self._username, self._password, otp_code)
                if not token:
                    errors["base"] = "invalid_otp"
                else:
                    trust = await api.get_trust_token(token)
                    self.hass.config_entries.async_update_entry(
                        reauth_entry,
                        data={
                            **reauth_entry.data,
                            CONF_PASSWORD: self._password,
                            CONF_USER_AGENT_TOKEN: trust.get(CONF_USER_AGENT_TOKEN, ""),
                            CONF_REFRESH_TOKEN: trust.get(CONF_REFRESH_TOKEN, ""),
                        },
                    )
                    await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            except Exception:
                _LOGGER.exception("Unexpected error during Coverflex reauth OTP")
                errors["base"] = "invalid_otp"

        return self.async_show_form(
            step_id="reauth_otp",
            data_schema=_SCHEMA_OTP,
            errors=errors,
            description_placeholders={
                "otp_channel": self._otp_channel,
                "phone_last_digits": self._phone_last_digits,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _async_create_entry(
        self, username: str, password: str, trust: dict | None
    ) -> config_entries.FlowResult:
        """Build the config entry data dict and create the entry."""
        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_USER_AGENT_TOKEN: trust.get("user_agent_token", "") if trust else "",
            CONF_REFRESH_TOKEN: trust.get("refresh_token", "") if trust else "",
        }
        return self.async_create_entry(
            title=f"Coverflex ({username})",
            data=data,
        )

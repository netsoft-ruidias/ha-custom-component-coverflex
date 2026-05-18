"""Sensor platform for the Coverflex integration."""
from __future__ import annotations

import logging
from typing import Any

from babel.dates import format_date as babel_format_date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_local

from .const import DOMAIN, ATTRIBUTION, DEFAULT_ICON
from .coordinator import CoverflexCoordinator
from .interfaces import Pocket

_LOGGER = logging.getLogger(__name__)

_MONTH_ABBR_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _format_transaction_date(dt_obj, lang: str) -> str:
    """Return a locale-aware date string in 'dd Mmm - HH:MM' format."""
    local_dt = as_local(dt_obj)
    try:
        month = babel_format_date(local_dt, format="MMM", locale=lang).capitalize()
    except Exception:  # noqa: BLE001
        month = _MONTH_ABBR_EN[local_dt.month - 1]
    return f"{local_dt.day:02d} {month} - {local_dt.strftime('%H:%M')}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Coverflex sensors from a config entry."""
    coordinator: CoverflexCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        CoverflexPocketSensor(coordinator, entry, pocket)
        for pocket in coordinator.data.pockets
    )


class CoverflexPocketSensor(CoordinatorEntity[CoverflexCoordinator], SensorEntity):
    """Sensor representing a single Coverflex pocket balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_attribution = ATTRIBUTION
    _attr_icon = DEFAULT_ICON
    _attr_entity_picture = "/coverflex-brand/icon.png"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoverflexCoordinator,
        entry: ConfigEntry,
        pocket: Pocket,
    ) -> None:
        super().__init__(coordinator)
        self._pocket_id = pocket.id
        self._pocket_type = pocket.type
        self._attr_unique_id = f"{entry.unique_id}_{pocket.type}"
        self._attr_name = pocket.type.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=f"Coverflex ({entry.data[CONF_USERNAME]})",
            manufacturer="Coverflex",
            entry_type=DeviceEntryType.SERVICE,
        )

    # ------------------------------------------------------------------
    # State / attributes derived from coordinator data
    # ------------------------------------------------------------------

    @property
    def _pocket(self) -> Pocket | None:
        """Return the current pocket data from the coordinator."""
        for p in self.coordinator.data.pockets:
            if p.id == self._pocket_id:
                return p
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current balance."""
        pocket = self._pocket
        return pocket.balance if pocket else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency from the API response."""
        pocket = self._pocket
        return pocket.currency if pocket else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        card = self.coordinator.data.card
        pocket = self._pocket
        raw_transactions = self.coordinator.data.transactions.get(self._pocket_id, [])
        lang = self.hass.config.language
        transactions = [
            {
                "date": _format_transaction_date(t.date, lang),
                "description": t.description,
                "amount": f"{t.amount:.2f}",
                "currency": t.currency,
            }
            for t in raw_transactions
        ]
        return {
            "pocket_id": self._pocket_id,
            "pocket_type": self._pocket_type,
            "card_holder": card.holder_name if card else None,
            "card_company": card.holder_company_name if card else None,
            "card_status": card.status if card else None,
            "card_last_digits": card.pan_last_digits if card else None,
            "card_expiration": card.expiration_date if card else None,
            "transactions": transactions,
        }

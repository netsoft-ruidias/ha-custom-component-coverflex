"""The Coverflex integration."""
from __future__ import annotations
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoverflexAPI
from .coordinator import CoverflexCoordinator
from .const import DOMAIN, SERVICE_REFRESH

__version__ = "2.0.0"
_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

_SERVICE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coverflex from a config entry."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/coverflex-brand",
            str(Path(__file__).parent / "brand"),
            cache_headers=True,
        )
    ])

    api = CoverflexAPI(async_get_clientsession(hass))
    coordinator = CoverflexCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the domain service only once (first entry setup)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def handle_refresh(call: ServiceCall) -> None:
            """Handle the coverflex.refresh service call."""
            entry_id: str | None = call.data.get("config_entry_id")
            coordinators: dict[str, CoverflexCoordinator] = hass.data.get(DOMAIN, {})

            if entry_id:
                target = coordinators.get(entry_id)
                if target is None:
                    raise ServiceValidationError(
                        f"No Coverflex entry found with config_entry_id '{entry_id}'."
                    )
                await target.async_force_refresh()
            else:
                for coord in coordinators.values():
                    await coord.async_force_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            handle_refresh,
            schema=_SERVICE_REFRESH_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove the domain service when the last entry is unloaded
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unloaded
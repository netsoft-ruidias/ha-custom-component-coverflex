"""The Coverflex integration."""
from __future__ import annotations
import logging
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoverflexAPI
from .coordinator import CoverflexCoordinator
from .const import DOMAIN

__version__ = "2.0.0"
_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
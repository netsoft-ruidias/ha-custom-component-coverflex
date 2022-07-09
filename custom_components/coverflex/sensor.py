"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
import aiohttp
import logging

from datetime import timedelta
from typing import Any, Callable, Dict

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD
)

from .api import CoverflexAPI
from .interfaces import Card
from .const import (
    DOMAIN,
    DEFAULT_ICON,
    UNIT_OF_MEASUREMENT,
    ATTRIBUTION,
    CONF_TRANSACTIONS
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

# Time between updating data from API
SCAN_INTERVAL = timedelta(minutes=60)

async def async_setup_entry(hass: HomeAssistant, 
                            config_entry: ConfigEntry, 
                            async_add_entities: Callable):
    """Setup sensor platform."""
    session = async_get_clientsession(hass, True)
    api = CoverflexAPI(session)

    config = config_entry.data
    token = await api.login(config[CONF_USERNAME], config[CONF_PASSWORD])

    if (token):
        card = await api.getCard(token)
        sensors = [CoverflexSensor(card, api, config)]
        async_add_entities(sensors, update_before_add=True)


class CoverflexSensor(SensorEntity):
    """Representation of a Coverflex Card (Sensor)."""

    def __init__(self, card: Card, api: CoverflexAPI, config: Any):
        super().__init__()
        self._card = card
        self._api = api
        self._config = config
        self._transactions = None
        self._currency = None

        self._icon = DEFAULT_ICON
        self._unit_of_measurement = UNIT_OF_MEASUREMENT
        self._device_class = SensorDeviceClass.MONETARY
        self._state_class = SensorStateClass.TOTAL
        self._state = None
        self._available = True
        
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Coverflex Card {self._card.holder_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{DOMAIN}-{self._card.id}".lower()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> float:
        return self._state

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        return self._state_class

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        return self._icon

    @property
    def attribution(self):
        return ATTRIBUTION

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {
            "activated_at": self._card.activated_at,
            "expiration_date": self._card.expiration_date,
            "holder_company_name": self._card.holder_company_name,
            "holder_name": self._card.holder_name,
            "pan_last_digits": self._card.pan_last_digits,
            "status": self._card.status,
            "currency": self._currency,
            "transactions": self._transactions
        }

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.
           This is the only method that should fetch new data for Home Assistant.
        """
        api = self._api
        config = self._config
        
        try:
            token = await api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
            if (token):
                pocket = await api.getBalance(token)
                self._state = pocket.balance
                self._currency = pocket.currency

                qtd = int(config[CONF_TRANSACTIONS])
                if (qtd > 0):
                    movements = await api.getMovements(token, pocket.id, qtd)
                    list = []
                    [list.append({
                        "date": t.date,
                        "description": t.description,
                        "amount": t.amount,
                        "currency": t.currency
                    }) for t in movements]
                    self._transactions = list



        except aiohttp.ClientError as err:
            self._available = False
            _LOGGER.exception("Error updating data from Coverflex API. %s", err)
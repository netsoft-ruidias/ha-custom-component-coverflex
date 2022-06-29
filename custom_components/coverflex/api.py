"""API to COVERFLEX."""
import aiohttp
import logging

from .interfaces import Card, Pocket
from .const import (
    API_LOGIN_URL,
    API_CARD_URL,
    API_POCKETS_URL
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class CoverflexAPI:
    """Interfaces to https://my.coverflex.com/"""

    def __init__(self, websession):
        self.websession = websession
        self.json = None

    async def login(self, username, password):
        """Issue LOGIN request."""
        try:
            _LOGGER.debug("Logging in...")
            async with self.websession.post(
                API_LOGIN_URL, 
                headers = { "Content-Type": "application/json" },
                json={"email":username,"password":password}
            ) as res:
                if res.status == 201 and res.content_type == "application/json":
                    json = await res.json()
                    return json['token']
                raise Exception("Could not retrieve token for user, login failed")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def getCard(self, token) -> Card:
        """Issue CARD requests."""
        try:
            _LOGGER.debug("Getting the card details...")
            async with self.websession.get(
                API_CARD_URL, 
                headers = { 
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}" }
            ) as res:
                if res.status == 200 and res.content_type == "application/json":
                    json = await res.json()
                    return Card(json['card'])
                raise Exception("Could not fetch the card details from API")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def getBalance(self, token) -> Pocket:
        """Issue CARD requests."""
        try:
            _LOGGER.debug("Getting the card details...")
            async with self.websession.get(
                API_POCKETS_URL, 
                headers = { 
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}" }
            ) as res:
                if res.status == 200 and res.content_type == "application/json":
                    json = await res.json()
                    return Pocket(json['pockets'][0])
                raise Exception("Could not fetch the card balance from API")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)
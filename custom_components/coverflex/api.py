"""API to COVERFLEX."""
import uuid
import aiohttp
import logging

from .exceptions import OTPRequiredException
from .interfaces import Card, Pocket, Transaction
from .const import (
    API_LOGIN_URL,
    API_CARD_URL,
    API_POCKETS_URL,
    API_MOVEMENTS_URL,
    API_TRUST_USER_AGENT_URL,
    API_RENEW_URL,
    API_CHANNEL,
    API_LANGUAGE,
    API_VERSION,
)


_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class CoverflexAPI:
    """Interfaces to https://my.coverflex.com/"""

    def __init__(self, websession):
        self.websession = websession
        self.json = None
        self._rum_session_id = str(uuid.uuid4())

    def _base_headers(self):
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "x-coverflex-channel": API_CHANNEL,
            "x-coverflex-language": API_LANGUAGE,
            "x-coverflex-version": API_VERSION,
            "x-coverflex-rum-session-id": self._rum_session_id,
        }

    async def login(self, username, password, user_agent_token=None):
        """Issue LOGIN request.

        Returns the token on success (HTTP 201).
        Raises OTPRequiredException when the server requires SMS/email verification (HTTP 202).
        Pass user_agent_token to skip OTP on a known device.
        """
        try:
            _LOGGER.debug("Logging in...")
            body = {"email": username, "password": password}
            if user_agent_token:
                body["user_agent_token"] = user_agent_token
            async with self.websession.post(
                API_LOGIN_URL,
                headers=self._base_headers(),
                json=body
            ) as res:
                if res.status == 201 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("Login successful, token received.")
                    return json['token']
                if res.status == 202 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("OTP verification required: %s", json)
                    raise OTPRequiredException(
                        otp_channel=json.get("otp_channel", "sms"),
                        phone_last_digits=json.get("phone_last_digits", ""),
                    )
                raise Exception(f"Login failed (HTTP {res.status})")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def login_with_otp(self, username, password, otp_code):
        """Complete login with OTP verification code.

        Call this after login() raises OTPRequiredException.
        Returns the token on success (HTTP 201).
        """
        try:
            _LOGGER.debug("Verifying OTP...")
            async with self.websession.post(
                API_LOGIN_URL,
                headers=self._base_headers(),
                json={"email": username, "password": password, "otp": otp_code}
            ) as res:
                if res.status == 201 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("OTP verification successful, token received.")
                    return json['token']
                raise Exception(f"OTP verification failed (HTTP {res.status})")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def get_trust_token(self, token) -> dict | None:
        """Obtain trust tokens to skip OTP on future logins.

        Call this once after a successful OTP login.
        Returns a dict with keys: access_token, refresh_token, user_agent_token.
        Store all three persistently and pass user_agent_token to login() next time.
        """
        try:
            _LOGGER.debug("Requesting device trust token...")
            headers = {**self._base_headers(), "Authorization": f"Bearer {token}"}
            async with self.websession.post(
                API_TRUST_USER_AGENT_URL,
                headers=headers,
                json=None
            ) as res:
                if res.status in (200, 201) and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("Trust token received")
                    return {
                        "access_token": json.get("token"),
                        "refresh_token": json.get("refresh_token"),
                        "user_agent_token": json.get("user_agent_token"),
                    }
                _LOGGER.warning("Trust token request returned HTTP %s", res.status)
                return None
        except aiohttp.ClientError as err:
            _LOGGER.error(err)
            return None

    async def refresh_access_token(self, refresh_token: str) -> dict | None:
        """Refresh the access token using the refresh token.

        Returns a dict with keys: access_token, refresh_token.
        Call this before making API requests when the current access token may be expired.
        If this fails (e.g. refresh token expired), fall back to login() with user_agent_token.
        """
        try:
            _LOGGER.debug("Refreshing access token...")
            headers = {**self._base_headers(), "Authorization": f"Bearer {refresh_token}"}
            async with self.websession.post(
                API_RENEW_URL,
                headers=headers,
                json=None
            ) as res:
                if res.status in (200, 201) and res.content_type == "application/json":
                    json = await res.json()
                    data = json.get("data", json)
                    _LOGGER.debug("Access token refreshed successfully")
                    return {
                        "access_token": data.get("access_token"),
                        "refresh_token": data.get("refresh_token"),
                    }
                _LOGGER.warning("Token refresh returned HTTP %s", res.status)
                return None
        except aiohttp.ClientError as err:
            _LOGGER.error(err)
            return None

    async def get_card(self, token) -> Card | None:
        """Issue CARD requests."""
        try:
            _LOGGER.debug("Getting the card details...")
            headers = {**self._base_headers(), "Authorization": f"Bearer {token}"}
            async with self.websession.get(
                API_CARD_URL,
                headers=headers
            ) as res:
                if res.status == 200 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("Fetched card details: %s", json)
                    return Card(json['card'])
                raise Exception("Could not fetch the card details from API")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def get_balances(self, token):
        """Issue POCKETS requests."""
        try:
            _LOGGER.debug("Getting the balances...")
            headers = {**self._base_headers(), "Authorization": f"Bearer {token}"}
            async with self.websession.get(
                API_POCKETS_URL,
                headers=headers
            ) as res:
                if res.status == 200 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("Fetched balances: %s", json)
                    pockets = map(lambda x: Pocket(x), json['pockets'])
                    return  list(pockets)
                raise Exception("Could not fetch the card balance from API")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)

    async def get_movements(self, token, pocketId, movementCount: int):
        """Issue MOVEMENTS requests."""
        try:
            _LOGGER.debug("Getting the card movements...")
            headers = {**self._base_headers(), "Authorization": f"Bearer {token}"}
            async with self.websession.get(
                API_MOVEMENTS_URL,
                params={"pocket_id": pocketId, "per_page": movementCount},
                headers=headers
            ) as res:
                if res.status == 200 and res.content_type == "application/json":
                    json = await res.json()
                    _LOGGER.debug("Fetched movements: %s", json)
                    return [
                        Transaction(data) for data in json['movements']['list']
                    ]
                raise Exception("Could not fetch the card movements from API")
        except aiohttp.ClientError as err:
            _LOGGER.error(err)            
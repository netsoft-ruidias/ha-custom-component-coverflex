"""Card Class."""

from datetime import datetime, timezone
from homeassistant.util import dt

class Card:
    """Represents a Coverflex card."""

    def __init__(self, data):
        self._data = data
        
    @property
    def id(self):
        return self._data["id"]

    @property
    def activated_at(self) -> datetime:
        raw = self._data.get("activated_at")
        return dt.parse_datetime(raw).astimezone(timezone.utc) if raw else None

    @property
    def expiration_date(self) -> datetime:
        raw = self._data.get("expiration_date")
        return dt.parse_datetime(raw).astimezone(timezone.utc) if raw else None

    @property
    def holder_company_name(self) -> str:
        return self._data["holder_company_name"]

    @property
    def holder_name(self) -> str:
        return self._data["holder_name"]

    @property
    def pan_last_digits(self) -> str:
        return self._data["pan_last_digits"]

    @property
    def status(self):
        return self._data["status"]

    def __repr__(self):
        return f"Card({self._data.get('holder_name')} [{self._data.get('status')}] pan=****{self._data.get('pan_last_digits')})"


class Pocket:
    """Represents a Coverflex Pocket."""

    def __init__(self, data):
        self._data = data
        
    @property
    def id(self):
        return self._data["id"]

    @property
    def balance(self) -> float:
        return float(self._data["balance"]["amount"]) / 100

    @property
    def currency(self) -> str:
        return self._data["balance"]["currency"]

    @property
    def type(self):
        return self._data["type"]


class Transaction:
    """Represents a Coverflex Transaction."""

    def __init__(self, data):
        self._data = data
        
    @property
    def date(self) -> datetime:
        return dt.parse_datetime(self._data["executed_at"]).astimezone(timezone.utc)

    @property
    def description(self) -> str:
        return self._data["description"]


    @property
    def amount(self) -> float:
        if (self._data["is_debit"]):
            return 0 - float(self._data["amount"]["amount"]) / 100
        else:
            return float(self._data["amount"]["amount"]) / 100

    @property
    def currency(self) -> str:
        return self._data["amount"]["currency"]
"""Card Class."""

class Card:
    """Represents a Coverflex card."""

    def __init__(self, data):
        self._data = data
        
    @property
    def id(self):
        return self._data["id"]

    @property
    def activated_at(self):
        return self._data["activated_at"]

    @property
    def expiration_date(self):
        return self._data["expiration_date"]

    @property
    def holder_company_name(self):
        return self._data["holder_company_name"]

    @property
    def holder_name(self):
        return self._data["holder_name"]

    @property
    def pan_last_digits(self):
        return self._data["pan_last_digits"]

    @property
    def status(self):
        return self._data["status"]

class Pocket:
    """Represents a Coverflex Pocket."""

    def __init__(self, data):
        self._data = data
        
    @property
    def id(self):
        return self._data["id"]

    @property
    def balance(self) -> float:
        return float(self._data["balance"]["amount"])

    @property
    def currency(self):
        return self._data["balance"]["currency"]
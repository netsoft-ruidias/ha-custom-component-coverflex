"""Exceptions for the Coverflex API."""


class CoverflexAPIError(Exception):
    """Raised when the Coverflex API returns an unexpected error."""


class AuthenticationError(CoverflexAPIError):
    """Raised when authentication fails (invalid credentials)."""


class OTPRequiredException(Exception):
    """Raised when the API requires an OTP verification step."""

    def __init__(self, otp_channel: str, phone_last_digits: str):
        self.otp_channel = otp_channel
        self.phone_last_digits = phone_last_digits
        super().__init__(f"OTP required via {otp_channel} (****{phone_last_digits})")

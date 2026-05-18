"""Constants for the Coverflex integration."""

from datetime import timedelta

DOMAIN = "coverflex"
PLATFORM = "sensor"

ATTRIBUTION = "Data provided by https://www.coverflex.com/"

DEFAULT_ICON = "mdi:credit-card"

API_BASE_URL = "https://menhir-api.coverflex.com/api/employee"
API_LOGIN_URL = f"{API_BASE_URL}/sessions"
API_CARD_URL = f"{API_BASE_URL}/card"
API_POCKETS_URL = f"{API_BASE_URL}/pockets"
API_MOVEMENTS_URL = f"{API_BASE_URL}/movements"
API_TRUST_USER_AGENT_URL = f"{API_BASE_URL}/sessions/trust-user-agent"
API_RENEW_URL = f"{API_BASE_URL}/sessions/renew"

API_CHANNEL = "web"
API_LANGUAGE = "en-GB"
API_VERSION = "1.462.0"

CONF_USER_AGENT_TOKEN = "user_agent_token"
CONF_REFRESH_TOKEN = "refresh_token"

UPDATE_INTERVAL = timedelta(minutes=30)

# Maximum number of transactions to fetch and expose per pocket
DEFAULT_TRANSACTIONS_COUNT = 20

# Service names
SERVICE_REFRESH = "refresh"

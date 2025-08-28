"""Constants for the Laddel integration."""
from typing import Final

DOMAIN: Final = "laddel"

CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_TOKEN_TYPE: Final = "token_type"
CONF_EXPIRES_IN: Final = "expires_in"

DEFAULT_NAME: Final = "Laddel EV Charging"
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes

# API endpoints
BASE_URL: Final = "https://api.laddel.no/v1"
AUTH_URL: Final = "https://id.laddel.no/realms/laddel-app-prod"
SUBSCRIPTION_ENDPOINT: Final = "/api/facility/subscription"
NOTIFICATION_SYNC_ENDPOINT: Final = "/api/notification/synchronize-token"
CURRENT_SESSION_ENDPOINT: Final = "/api/session/get-current-session"
CHARGER_OPERATING_MODE_ENDPOINT: Final = "/api/charger/operating-mode"
FACILITY_INFO_ENDPOINT: Final = "/api/facility/information"

# OAuth2 endpoints
OAUTH2_AUTHORIZE: Final = f"{AUTH_URL}/protocol/openid-connect/auth"
OAUTH2_TOKEN: Final = f"{AUTH_URL}/protocol/openid-connect/token"
OAUTH2_CLIENT_ID: Final = "laddel-app-prod"
OAUTH2_SCOPE: Final = "openid profile email offline_access"
OAUTH2_REDIRECT_URI: Final = "laddel://oauth/callback"

# User agent to match the app
USER_AGENT: Final = "Dart/3.7 (dart:io)"
APP_HEADER: Final = "Laddel_1.23.2+10230201"

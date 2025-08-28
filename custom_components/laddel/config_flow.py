"""Config flow for Laddel integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, CONF_REFRESH_TOKEN
from .oauth2 import LaddelDirectOAuth2FlowHandler

_LOGGER = logging.getLogger(__name__)


class LaddelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laddel."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            auth_method = user_input.get("auth_method")
            
            if auth_method == "oauth":
                # Start direct OAuth flow
                return await self.async_step_oauth()
            elif auth_method == "refresh_token":
                # Handle refresh token input
                if CONF_REFRESH_TOKEN in user_input and user_input[CONF_REFRESH_TOKEN]:
                    return self.async_create_entry(
                        title="Laddel EV Charging",
                        data={
                            CONF_REFRESH_TOKEN: user_input[CONF_REFRESH_TOKEN],
                        },
                    )
                else:
                    errors["base"] = "refresh_token_required"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("auth_method"): vol.In({
                        "oauth": "OAuth2 with PKCE (Recommended - Login with Laddel account)",
                        "refresh_token": "Manual Refresh Token (Advanced users)"
                    }),
                }
            ),
            errors=errors,
        )

    async def async_step_oauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle OAuth2 authentication."""
        # Use the direct OAuth2 flow handler
        oauth_handler = LaddelDirectOAuth2FlowHandler()
        oauth_handler.hass = self.hass
        oauth_handler.flow_id = self.flow_id
        oauth_handler.context = self.context
        
        # Start the OAuth flow
        return await oauth_handler.async_step_user()

    async def async_step_refresh_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle refresh token input."""
        errors = {}

        if user_input is not None:
            if CONF_REFRESH_TOKEN in user_input and user_input[CONF_REFRESH_TOKEN]:
                return self.async_create_entry(
                    title="Laddel EV Charging",
                    data={
                        CONF_REFRESH_TOKEN: user_input[CONF_REFRESH_TOKEN],
                    },
                )
            else:
                errors["base"] = "refresh_token_required"

        return self.async_show_form(
            step_id="refresh_token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_info)

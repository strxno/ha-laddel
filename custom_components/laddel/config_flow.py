"""Config flow for Laddel integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
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
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            
            if username and password:
                # Use the OAuth2 flow handler to authenticate and get tokens
                try:
                    oauth_handler = LaddelDirectOAuth2FlowHandler()
                    oauth_handler.hass = self.hass
                    oauth_handler.flow_id = self.flow_id
                    oauth_handler.context = self.context
                    oauth_handler.flow_context = {"username": username, "password": password}
                    
                    # Authenticate and get tokens
                    result = await oauth_handler.async_step_authenticate()
                    return result
                    
                except Exception as e:
                    _LOGGER.error("Authentication failed: %s", e)
                    errors["base"] = "auth_failed"
            else:
                errors["base"] = "missing_credentials"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )



    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_info)

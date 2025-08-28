"""Data coordinator for Laddel integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AUTH_URL,
    BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_TOKEN_TYPE,
    CONF_EXPIRES_IN,
    DEFAULT_SCAN_INTERVAL,
    SUBSCRIPTION_ENDPOINT,
    NOTIFICATION_SYNC_ENDPOINT,
    CURRENT_SESSION_ENDPOINT,
    CHARGER_OPERATING_MODE_ENDPOINT,
    USER_AGENT,
    APP_HEADER,
)

_LOGGER = logging.getLogger(__name__)


class LaddelDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Laddel data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
        self.access_token = entry.data.get(CONF_ACCESS_TOKEN)
        self.token_expires = None
        
        # Calculate token expiration if we have an access token
        if self.access_token and CONF_EXPIRES_IN in entry.data:
            expires_in = entry.data.get(CONF_EXPIRES_IN, 3600)
            self.token_expires = datetime.now() + timedelta(seconds=expires_in)

        super().__init__(
            hass,
            _LOGGER,
            name="Laddel",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Laddel API."""
        try:
            # Ensure we have a valid access token
            if not self.access_token or (
                self.token_expires and datetime.now() >= self.token_expires
            ):
                await self._refresh_access_token()

            # Fetch all available data
            data = {}
            
            # Fetch subscription data
            try:
                subscription_data = await self._fetch_subscription_data()
                data["subscription"] = subscription_data
            except Exception as e:
                _LOGGER.warning("Failed to fetch subscription data: %s", e)
                data["subscription"] = None

            # Fetch current charging session
            try:
                session_data = await self._fetch_current_session()
                data["current_session"] = session_data
            except Exception as e:
                _LOGGER.warning("Failed to fetch current session: %s", e)
                data["current_session"] = None

            # Fetch charger operating mode if we have a charger ID
            if data.get("current_session") and data["current_session"].get("chargerId"):
                try:
                    charger_id = data["current_session"]["chargerId"]
                    charger_data = await self._fetch_charger_operating_mode(charger_id)
                    data["charger_operating_mode"] = charger_data
                except Exception as e:
                    _LOGGER.warning("Failed to fetch charger operating mode: %s", e)
                    data["charger_operating_mode"] = None

            data["last_update"] = datetime.now().isoformat()
            return data

        except Exception as err:
            _LOGGER.error("Error updating Laddel data: %s", err)
            raise UpdateFailed(f"Error updating Laddel data: {err}") from err

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise UpdateFailed("No refresh token available")

        token_url = f"{AUTH_URL}/protocol/openid-connect/token"
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": "laddel-app-prod",
            "scope": "openid profile email offline_access",
        }

        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("Failed to refresh token: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to refresh access token")

                token_data = await response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)

                # Update the refresh token if a new one was provided
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]
                    # Update the config entry with the new tokens
                    hass = self.hass
                    hass.config_entries.async_update_entry(
                        self.entry,
                        data={
                            **self.entry.data,
                            CONF_REFRESH_TOKEN: self.refresh_token,
                            CONF_ACCESS_TOKEN: self.access_token,
                            CONF_EXPIRES_IN: expires_in,
                        }
                    )

    async def _fetch_subscription_data(self) -> dict[str, Any]:
        """Fetch subscription data from Laddel API."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{SUBSCRIPTION_ENDPOINT}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("Failed to fetch subscription data: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch subscription data")

                return await response.json()

    async def _fetch_current_session(self) -> dict[str, Any]:
        """Fetch current charging session from Laddel API."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{CURRENT_SESSION_ENDPOINT}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("Failed to fetch current session: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch current session")

                return await response.json()

    async def _fetch_charger_operating_mode(self, charger_id: str) -> dict[str, Any]:
        """Fetch charger operating mode from Laddel API."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{CHARGER_OPERATING_MODE_ENDPOINT}?chargerId={charger_id}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("Failed to fetch charger operating mode: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch charger operating mode")

                return await response.json()

    async def sync_notification_token(self, fcm_token: str, installation_id: str) -> bool:
        """Sync notification token with Laddel API."""
        if not self.access_token:
            _LOGGER.error("No access token available for notification sync")
            return False

        url = f"{BASE_URL}{NOTIFICATION_SYNC_ENDPOINT}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        data = {
            "fcmToken": fcm_token,
            "installationId": installation_id,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        _LOGGER.error("Failed to sync notification token: %s - %s", response.status, text)
                        return False
                    
                    _LOGGER.info("Notification token synced successfully")
                    return True
        except Exception as e:
            _LOGGER.error("Error syncing notification token: %s", e)
            return False

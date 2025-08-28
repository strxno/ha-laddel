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
    CHARGING_SCAN_INTERVAL,
    SUBSCRIPTION_ENDPOINT,
    NOTIFICATION_SYNC_ENDPOINT,
    CURRENT_SESSION_ENDPOINT,
    CHARGER_OPERATING_MODE_ENDPOINT,
    FACILITY_INFO_ENDPOINT,
    HISTORY_SESSIONS_ENDPOINT,
    STOP_SESSION_ENDPOINT,
    START_SESSION_ENDPOINT,
    LATEST_CHARGERS_ENDPOINT,
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
        
        # Device information
        self.device_info = None
        
        # Charging state for dynamic polling
        self._is_charging = False
        self._last_session_id = None
        self._latest_charger_id = None
        
        # Cache for infrequent data to reduce API calls
        self._facility_cache = {}
        self._facility_cache_time = None
        self._latest_chargers_cache = None
        self._latest_chargers_cache_time = None
        self._subscription_cache = None
        self._subscription_cache_time = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Laddel API."""
        try:
            # Ensure we have a valid access token with buffer time
            if self._token_needs_refresh():
                await self._refresh_access_token()

            # Fetch all available data
            data = {}
            
            # Fetch current charging session first (contains facility ID)
            try:
                session_data = await self._fetch_current_session()
                data["current_session"] = session_data
                
                # Check if charging status changed for dynamic polling
                await self._update_charging_state(session_data)
                
            except Exception as e:
                _LOGGER.warning("Failed to fetch current session: %s", e)
                data["current_session"] = None
                # Reset charging state if we can't fetch session data
                await self._update_charging_state(None)

            # Get facility ID from session data or subscription data
            facility_id = None
            if data.get("current_session"):
                facility_id = data["current_session"].get("facilityId")

            # Fetch subscription data (cached for 24 hours - rarely changes)
            try:
                subscription_data = await self._fetch_subscription_data_cached()
                data["subscription"] = subscription_data
                
                # If we don't have facility ID from session, get it from subscription
                if not facility_id and subscription_data and subscription_data.get("activeSubscriptions"):
                    facility_id = subscription_data["activeSubscriptions"][0].get("facilityId")
                    
            except Exception as e:
                _LOGGER.warning("Failed to fetch subscription data: %s", e)
                data["subscription"] = None

            # Fetch facility information using the facility ID (cached)
            try:
                if facility_id:
                    facility_data = await self._fetch_facility_info_cached(str(facility_id))
                    data["facility"] = facility_data
                    
                    # Create device info from facility data
                    if facility_data:
                        facility_name = facility_data.get("facilityName", "Laddel Account")
                        self.device_info = {
                            "identifiers": {("laddel", str(facility_id))},
                            "name": facility_name,
                            "manufacturer": "Laddel",
                            "model": "EV Charging Facility",
                            "sw_version": "1.0",
                        }
            except Exception as e:
                _LOGGER.warning("Failed to fetch facility info: %s", e)
                data["facility"] = None

            # Fetch latest used chargers (cached)
            try:
                latest_chargers = await self._fetch_latest_chargers_cached()
                data["latest_chargers"] = latest_chargers
                
                # Store the latest charger ID for controls
                if latest_chargers and latest_chargers.get("chargers"):
                    self._latest_charger_id = latest_chargers["chargers"][0].get("chargerId")
            except Exception as e:
                _LOGGER.warning("Failed to fetch latest chargers: %s", e)
                data["latest_chargers"] = None

            # Fetch charger operating mode for current session charger or latest charger
            charger_id = None
            if data.get("current_session") and data["current_session"].get("chargerId"):
                charger_id = data["current_session"]["chargerId"]
            elif self._latest_charger_id:
                charger_id = self._latest_charger_id
                
            if charger_id:
                try:
                    charger_data = await self._fetch_charger_operating_mode(charger_id)
                    data["charger_operating_mode"] = charger_data
                except Exception as e:
                    _LOGGER.warning("Failed to fetch charger operating mode: %s", e)
                    data["charger_operating_mode"] = None

            # Fetch recent charging sessions for cost tracking
            try:
                recent_sessions = await self._fetch_recent_sessions()
                data["recent_sessions"] = recent_sessions
            except Exception as e:
                _LOGGER.warning("Failed to fetch recent sessions: %s", e)
                data["recent_sessions"] = None

            data["last_update"] = datetime.now().isoformat()
            return data

        except Exception as err:
            _LOGGER.error("Error updating Laddel data: %s", err)
            raise UpdateFailed(f"Error updating Laddel data: {err}") from err

    def _token_needs_refresh(self) -> bool:
        """Check if access token needs refresh with buffer time."""
        if not self.access_token:
            _LOGGER.debug("No access token - refresh needed")
            return True
        
        if not self.token_expires:
            _LOGGER.debug("No token expiry info - refresh needed")
            return True
        
        # Refresh 30 seconds before expiry to avoid race conditions
        buffer_time = timedelta(seconds=30)
        needs_refresh = datetime.now() >= (self.token_expires - buffer_time)
        
        if needs_refresh:
            _LOGGER.debug("Access token expires soon - refresh needed")
        
        return needs_refresh

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
                expires_in = token_data.get("expires_in", 300)  # Default 5 minutes
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)

                _LOGGER.debug("Access token refreshed - expires in %d seconds", expires_in)

                # Update the refresh token if a new one was provided
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]
                    _LOGGER.debug("Refresh token updated")
                    
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

    async def _fetch_facility_info(self, facility_id: str) -> dict[str, Any]:
        """Fetch facility information from Laddel API."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{FACILITY_INFO_ENDPOINT}?id={facility_id}"
        
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
                    _LOGGER.error("Failed to fetch facility info: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch facility info")

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

    async def _update_charging_state(self, session_data: dict[str, Any] | None):
        """Update charging state and adjust polling interval."""
        current_charging = False
        current_session_id = None
        
        if session_data:
            session_type = session_data.get("type", "").upper()
            charger_mode = session_data.get("chargerOperatingMode", "")
            current_charging = (session_type == "ACTIVE" and charger_mode == "CHARGING")
            current_session_id = session_data.get("sessionId")
        
        # Check if charging state changed
        if current_charging != self._is_charging:
            self._is_charging = current_charging
            
            # Adjust polling interval
            new_interval = CHARGING_SCAN_INTERVAL if current_charging else DEFAULT_SCAN_INTERVAL
            self.update_interval = timedelta(seconds=new_interval)
            
            _LOGGER.info(
                "Charging state changed to %s, polling interval set to %d seconds",
                "CHARGING" if current_charging else "NOT CHARGING",
                new_interval
            )
        
        # Track session changes for cost updates
        if current_session_id != self._last_session_id:
            self._last_session_id = current_session_id
            if current_session_id:
                _LOGGER.info("New charging session started: %s", current_session_id)
            elif self._last_session_id:
                _LOGGER.info("Charging session ended: %s", self._last_session_id)

    async def _fetch_recent_sessions(self, page: int = 0) -> dict[str, Any]:
        """Fetch recent charging sessions for cost tracking."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{HISTORY_SESSIONS_ENDPOINT}?page={page}"
        
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
                    _LOGGER.error("Failed to fetch recent sessions: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch recent sessions")

                return await response.json()

    async def stop_charging_session(self, session_id: str) -> bool:
        """Stop an active charging session."""
        if not self.access_token:
            _LOGGER.error("No access token available for stopping session")
            return False

        url = f"{BASE_URL}{STOP_SESSION_ENDPOINT}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        data = {"sessionId": session_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status in [200, 204]:
                        _LOGGER.info("Successfully scheduled stop for session: %s", session_id)
                        return True
                    else:
                        text = await response.text()
                        _LOGGER.error("Failed to stop session: %s - %s", response.status, text)
                        return False
        except Exception as e:
            _LOGGER.error("Error stopping charging session: %s", e)
            return False

    async def _fetch_latest_chargers(self) -> dict[str, Any]:
        """Fetch latest used chargers."""
        if not self.access_token:
            raise UpdateFailed("No access token available")

        url = f"{BASE_URL}{LATEST_CHARGERS_ENDPOINT}"
        
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
                    _LOGGER.error("Failed to fetch latest chargers: %s - %s", response.status, text)
                    raise UpdateFailed("Failed to fetch latest chargers")

                return await response.json()

    async def start_charging_session(
        self, 
        charger_id: str | None = None,
        scheduled_start_time: str | None = None,
        scheduled_end_time: str | None = None,
        registration_number: str | None = None,
        request_private_session: bool = False
    ) -> bool:
        """Start a charging session."""
        if not self.access_token:
            _LOGGER.error("No access token available for starting session")
            return False

        # Use latest charger if no specific charger provided
        if not charger_id:
            charger_id = self._latest_charger_id
            
        if not charger_id:
            _LOGGER.error("No charger ID available for starting session")
            return False

        url = f"{BASE_URL}{START_SESSION_ENDPOINT}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "x-app": APP_HEADER,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Host": "api.laddel.no",
        }

        data = {
            "chargerId": charger_id,
            "scheduledStartTime": scheduled_start_time,
            "scheduledEndTime": scheduled_end_time,
            "registrationNumber": registration_number,
            "requestPrivateSession": request_private_session,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status in [200, 204]:
                        _LOGGER.info("Successfully scheduled start for charger: %s", charger_id)
                        return True
                    else:
                        text = await response.text()
                        _LOGGER.error("Failed to start session: %s - %s", response.status, text)
                        return False
        except Exception as e:
            _LOGGER.error("Error starting charging session: %s", e)
            return False

    async def _fetch_facility_info_cached(self, facility_id: str) -> dict[str, Any]:
        """Fetch facility information with caching (facility info rarely changes)."""
        now = datetime.now()
        cache_duration = timedelta(hours=1)  # Cache facility info for 1 hour
        
        # Check if we have valid cached data
        if (facility_id in self._facility_cache and 
            self._facility_cache_time and 
            now - self._facility_cache_time < cache_duration):
            _LOGGER.debug("Using cached facility info for ID: %s", facility_id)
            return self._facility_cache[facility_id]
        
        # Fetch fresh data
        _LOGGER.debug("Fetching fresh facility info for ID: %s", facility_id)
        try:
            facility_data = await self._fetch_facility_info(facility_id)
            
            # Cache the result
            self._facility_cache[facility_id] = facility_data
            self._facility_cache_time = now
            
            return facility_data
        except Exception as e:
            # Return cached data if available, even if expired
            if facility_id in self._facility_cache:
                _LOGGER.warning("Using stale facility cache due to error: %s", e)
                return self._facility_cache[facility_id]
            raise

    async def _fetch_latest_chargers_cached(self) -> dict[str, Any]:
        """Fetch latest chargers with caching (charger list changes infrequently)."""
        now = datetime.now()
        cache_duration = timedelta(minutes=15)  # Cache chargers for 15 minutes
        
        # Check if we have valid cached data
        if (self._latest_chargers_cache and 
            self._latest_chargers_cache_time and 
            now - self._latest_chargers_cache_time < cache_duration):
            _LOGGER.debug("Using cached latest chargers")
            return self._latest_chargers_cache
        
        # Fetch fresh data
        _LOGGER.debug("Fetching fresh latest chargers")
        try:
            chargers_data = await self._fetch_latest_chargers()
            
            # Cache the result
            self._latest_chargers_cache = chargers_data
            self._latest_chargers_cache_time = now
            
            return chargers_data
        except Exception as e:
            # Return cached data if available, even if expired
            if self._latest_chargers_cache:
                _LOGGER.warning("Using stale chargers cache due to error: %s", e)
                return self._latest_chargers_cache
            raise

    async def _fetch_subscription_data_cached(self) -> dict[str, Any]:
        """Fetch subscription data with caching (subscriptions auto-renew, rarely change)."""
        now = datetime.now()
        cache_duration = timedelta(hours=24)  # Cache subscription for 24 hours
        
        # Check if we have valid cached data
        if (self._subscription_cache and 
            self._subscription_cache_time and 
            now - self._subscription_cache_time < cache_duration):
            _LOGGER.debug("Using cached subscription data")
            return self._subscription_cache
        
        # Fetch fresh data
        _LOGGER.debug("Fetching fresh subscription data")
        try:
            subscription_data = await self._fetch_subscription_data()
            
            # Cache the result
            self._subscription_cache = subscription_data
            self._subscription_cache_time = now
            
            return subscription_data
        except Exception as e:
            # Return cached data if available, even if expired
            if self._subscription_cache:
                _LOGGER.warning("Using stale subscription cache due to error: %s", e)
                return self._subscription_cache
            raise

"""Button platform for Laddel integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaddelDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Laddel button based on a config entry."""
    coordinator: LaddelDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add charging control buttons
    entities.append(LaddelStartChargingButton(coordinator, entry))
    entities.append(LaddelStopChargingButton(coordinator, entry))

    async_add_entities(entities)


class LaddelButton(ButtonEntity):
    """Base class for Laddel buttons."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        self.coordinator = coordinator
        self.entry = entry
        self._attr_attribution = "Data provided by Laddel"
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info


class LaddelStartChargingButton(LaddelButton):
    """Button to start charging session."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Start Charging"
        self._attr_unique_id = f"{entry.entry_id}_start_charging"
        self._attr_icon = "mdi:play-circle"

    @property
    def available(self) -> bool:
        """Return True if button is available for use."""
        if not super().available:
            return False
        
        # Only available if no active session and car is connected
        session_data = self.coordinator.data.get("current_session")
        charger_data = self.coordinator.data.get("charger_operating_mode")
        
        # No active session
        has_active_session = (
            session_data and 
            not session_data.get("errorKey") == "noSession" and
            session_data.get("type", "").upper() == "ACTIVE"
        )
        
        # Car is connected
        car_connected = False
        if charger_data:
            operating_mode = charger_data.get("operatingMode", "")
            car_connected = operating_mode in ["CAR_CONNECTED", "IDLE"]
        
        return not has_active_session and car_connected

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Start charging button pressed")
        
        # Get the charger ID from current session or latest used charger
        charger_id = None
        
        # First try current session
        session_data = self.coordinator.data.get("current_session")
        if session_data and not session_data.get("errorKey"):
            charger_id = session_data.get("chargerId")
        
        # Then try latest used charger
        if not charger_id and self.coordinator._latest_charger_id:
            charger_id = self.coordinator._latest_charger_id
        
        # Finally try charger operating mode data
        if not charger_id:
            charger_data = self.coordinator.data.get("charger_operating_mode")
            if charger_data:
                charger_id = charger_data.get("chargerId")
        
        if not charger_id:
            _LOGGER.error("No charger ID available to start charging")
            return
        
        # Start the charging session
        success = await self.coordinator.start_charging_session(
            charger_id=charger_id,
            scheduled_start_time=None,
            scheduled_end_time=None,
            registration_number=None,
            request_private_session=False
        )
        
        if success:
            _LOGGER.info("Charging session started successfully")
            # Trigger immediate data refresh
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to start charging session")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {}
        
        # Add charger info if available
        if self.coordinator._latest_charger_id:
            attributes["target_charger_id"] = self.coordinator._latest_charger_id
        
        # Add car connection status
        charger_data = self.coordinator.data.get("charger_operating_mode")
        if charger_data:
            attributes["charger_operating_mode"] = charger_data.get("operatingMode")
        
        return attributes


class LaddelStopChargingButton(LaddelButton):
    """Button to stop charging session."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self._attr_name = "Stop Charging"
        self._attr_unique_id = f"{entry.entry_id}_stop_charging"
        self._attr_icon = "mdi:stop-circle"

    @property
    def available(self) -> bool:
        """Return True if button is available for use."""
        if not super().available:
            return False
        
        # Only available if there's an active charging session
        session_data = self.coordinator.data.get("current_session")
        
        return (
            session_data and 
            not session_data.get("errorKey") == "noSession" and
            session_data.get("type", "").upper() == "ACTIVE"
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Stop charging button pressed")
        
        # Get the session ID from current session
        session_data = self.coordinator.data.get("current_session")
        if not session_data or session_data.get("errorKey") == "noSession":
            _LOGGER.error("No active session to stop")
            return
        
        session_id = session_data.get("sessionId")
        if not session_id:
            _LOGGER.error("No session ID available to stop charging")
            return
        
        # Stop the charging session
        success = await self.coordinator.stop_charging_session(session_id)
        
        if success:
            _LOGGER.info("Charging session stopped successfully")
            # Trigger immediate data refresh
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to stop charging session")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {}
        
        # Add current session info
        session_data = self.coordinator.data.get("current_session")
        if session_data and not session_data.get("errorKey"):
            attributes.update({
                "session_id": session_data.get("sessionId"),
                "charger_id": session_data.get("chargerId"),
                "session_type": session_data.get("type"),
                "charger_operating_mode": session_data.get("chargerOperatingMode"),
                "energy_consumed": session_data.get("charged"),
                "start_time": session_data.get("startTime"),
            })
        
        return attributes

"""Binary sensor platform for Laddel integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaddelDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Laddel binary sensor based on a config entry."""
    coordinator: LaddelDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add active subscription binary sensor
    entities.append(LaddelActiveSubscriptionBinarySensor(coordinator, entry))
    
    # Add active charging session binary sensor
    entities.append(LaddelActiveChargingSessionBinarySensor(coordinator, entry))

    async_add_entities(entities)


class LaddelBinarySensor(BinarySensorEntity):
    """Base class for Laddel binary sensors."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self._attr_attribution = "Data provided by Laddel"
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success


class LaddelActiveSubscriptionBinarySensor(LaddelBinarySensor):
    """Binary sensor for active subscription status."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Active Subscription"
        self._attr_unique_id = f"{entry.entry_id}_active_subscription"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return None
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        return len(active_subs) > 0 and any(
            sub.get("status") == "ACTIVE" for sub in active_subs
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return {}
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if not active_subs:
            return {}
        
        # Return info about all active subscriptions
        return {
            "active_subscriptions_count": len(active_subs),
            "subscriptions": [
                {
                    "facility_id": sub.get("facilityId"),
                    "facility_name": sub.get("facilityName"),
                    "status": sub.get("status"),
                    "monthly_fee": sub.get("monthlyFee"),
                    "currency": sub.get("monthlyFeeCurrency"),
                    "activation_date": sub.get("activationDate"),
                    "expiration_date": sub.get("expirationDate"),
                }
                for sub in active_subs
            ]
        }


class LaddelActiveChargingSessionBinarySensor(LaddelBinarySensor):
    """Binary sensor for active charging session."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Active Charging Session"
        self._attr_unique_id = f"{entry.entry_id}_active_charging_session"

    @property
    def is_on(self) -> bool | None:
        """Return true if there's an active charging session."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return False
        
        return session_data.get("isActive", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return {}
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return {}
        
        return {
            "charger_id": session_data.get("chargerId"),
            "charger_name": session_data.get("chargerName"),
            "start_time": session_data.get("startTime"),
            "end_time": session_data.get("endTime"),
            "energy_consumed": session_data.get("energyConsumed"),
            "current_power": session_data.get("currentPower"),
            "is_completed": session_data.get("isCompleted", False),
            "is_cancelled": session_data.get("isCancelled", False),
        }

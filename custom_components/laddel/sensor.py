"""Sensor platform for Laddel integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CURRENCY_EURO, UnitOfPower, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULT_NAME
from .coordinator import LaddelDataUpdateCoordinator

ATTR_FACILITY_ID = "facility_id"
ATTR_FACILITY_NAME = "facility_name"
ATTR_ACTIVATION_DATE = "activation_date"
ATTR_EXPIRATION_DATE = "expiration_date"
ATTR_STATUS = "status"
ATTR_MONTHLY_FEE = "monthly_fee"
ATTR_MONTHLY_FEE_CURRENCY = "monthly_fee_currency"

# Charging session attributes
ATTR_CHARGER_ID = "charger_id"
ATTR_CHARGER_NAME = "charger_name"
ATTR_SESSION_START = "session_start"
ATTR_SESSION_END = "session_end"
ATTR_ENERGY_CONSUMED = "energy_consumed"
ATTR_POWER = "power"
ATTR_DURATION = "duration"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Laddel sensor based on a config entry."""
    coordinator: LaddelDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add subscription status sensor
    entities.append(LaddelSubscriptionStatusSensor(coordinator, entry))
    
    # Add monthly fee sensor
    entities.append(LaddelMonthlyFeeSensor(coordinator, entry))
    
    # Add facility name sensor
    entities.append(LaddelFacilityNameSensor(coordinator, entry))
    
    # Add days remaining sensor
    entities.append(LaddelDaysRemainingSensor(coordinator, entry))

    # Add charging session sensors
    entities.append(LaddelChargingSessionStatusSensor(coordinator, entry))
    entities.append(LaddelChargingPowerSensor(coordinator, entry))
    entities.append(LaddelEnergyConsumedSensor(coordinator, entry))
    entities.append(LaddelChargingDurationSensor(coordinator, entry))
    entities.append(LaddelChargerIdSensor(coordinator, entry))
    
    # Add facility sensors
    entities.append(LaddelElectricityPriceSensor(coordinator, entry))
    entities.append(LaddelFacilityAddressSensor(coordinator, entry))

    async_add_entities(entities)


class LaddelSensor(SensorEntity):
    """Base class for Laddel sensors."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
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


class LaddelSubscriptionStatusSensor(LaddelSensor):
    """Sensor for subscription status."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Subscription Status"
        self._attr_unique_id = f"{entry.entry_id}_subscription_status"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return None
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if active_subs:
            return active_subs[0].get("status", "Unknown")
        return "No Active Subscription"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return {}
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if not active_subs:
            return {}
        
        sub = active_subs[0]
        return {
            ATTR_FACILITY_ID: sub.get("facilityId"),
            ATTR_FACILITY_NAME: sub.get("facilityName"),
            ATTR_ACTIVATION_DATE: sub.get("activationDate"),
            ATTR_EXPIRATION_DATE: sub.get("expirationDate"),
            ATTR_MONTHLY_FEE: sub.get("monthlyFee"),
            ATTR_MONTHLY_FEE_CURRENCY: sub.get("monthlyFeeCurrency"),
        }


class LaddelMonthlyFeeSensor(LaddelSensor):
    """Sensor for monthly fee."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Monthly Fee"
        self._attr_unique_id = f"{entry.entry_id}_monthly_fee"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "NOK"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return None
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if active_subs:
            return active_subs[0].get("monthlyFee")
        return None


class LaddelFacilityNameSensor(LaddelSensor):
    """Sensor for facility name."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Facility Name"
        self._attr_unique_id = f"{entry.entry_id}_facility_name"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return None
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if active_subs:
            return active_subs[0].get("facilityName")
        return None


class LaddelDaysRemainingSensor(LaddelSensor):
    """Sensor for days remaining in subscription."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Days Remaining"
        self._attr_unique_id = f"{entry.entry_id}_days_remaining"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "subscription" not in self.coordinator.data:
            return None
        
        subscription_data = self.coordinator.data["subscription"]
        active_subs = subscription_data.get("activeSubscriptions", [])
        
        if not active_subs:
            return None
        
        expiration_date_str = active_subs[0].get("expirationDate")
        if not expiration_date_str:
            return None
        
        try:
            expiration_date = datetime.fromisoformat(expiration_date_str.replace('Z', '+00:00'))
            now = dt_util.now()
            delta = expiration_date - now
            return max(0, delta.days)
        except (ValueError, TypeError):
            return None


class LaddelChargingSessionStatusSensor(LaddelSensor):
    """Sensor for charging session status."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Charging Session Status"
        self._attr_unique_id = f"{entry.entry_id}_charging_session_status"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return "No Active Session"
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return "No Active Session"
        
        # Check session type and status from real API response
        session_type = session_data.get("type", "").upper()
        if session_type == "ACTIVE":
            charger_mode = session_data.get("chargerOperatingMode", "")
            if charger_mode == "CHARGING":
                return "Charging"
            elif charger_mode == "IDLE":
                return "Connected"
            else:
                return "Active"
        elif session_type == "COMPLETED":
            return "Completed"
        elif session_type == "CANCELLED":
            return "Cancelled"
        else:
            return session_type if session_type else "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return {}
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return {}
        
        return {
            ATTR_CHARGER_ID: session_data.get("chargerId"),
            ATTR_CHARGER_NAME: session_data.get("chargerName"),
            ATTR_SESSION_START: session_data.get("startTime"),
            ATTR_SESSION_END: session_data.get("endTime"),
            ATTR_ENERGY_CONSUMED: session_data.get("energyConsumed"),
            ATTR_POWER: session_data.get("currentPower"),
            "isActive": session_data.get("isActive"),
            "isCompleted": session_data.get("isCompleted"),
            "isCancelled": session_data.get("isCancelled"),
        }


class LaddelChargingPowerSensor(LaddelSensor):
    """Sensor for current charging power."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Charging Power"
        self._attr_unique_id = f"{entry.entry_id}_charging_power"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return None
        
        power = session_data.get("currentPower")
        if power is not None:
            # Convert to kW if the value is in W
            if power > 1000:
                return round(power / 1000, 2)
            return power
        return None


class LaddelEnergyConsumedSensor(LaddelSensor):
    """Sensor for energy consumed in current session."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Energy Consumed"
        self._attr_unique_id = f"{entry.entry_id}_energy_consumed"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return None
        
        # The API returns "charged" field with energy in kWh
        energy = session_data.get("charged")
        if energy is not None:
            return round(float(energy), 3)  # Keep 3 decimal places for precision
        return None


class LaddelChargingDurationSensor(LaddelSensor):
    """Sensor for charging session duration."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Charging Duration"
        self._attr_unique_id = f"{entry.entry_id}_charging_duration"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return None
        
        start_time = session_data.get("startTime")
        if not start_time:
            return None
        
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            now = dt_util.now()
            duration = now - start_dt
            return int(duration.total_seconds() / 60)  # Convert to minutes
        except (ValueError, TypeError):
            return None


class LaddelChargerIdSensor(LaddelSensor):
    """Sensor for charger ID."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Charger ID"
        self._attr_unique_id = f"{entry.entry_id}_charger_id"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data:
            return None
        
        return session_data.get("chargerId")


class LaddelElectricityPriceSensor(LaddelSensor):
    """Sensor for current electricity price."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Electricity Price"
        self._attr_unique_id = f"{entry.entry_id}_electricity_price"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "NOK/kWh"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "facility" not in self.coordinator.data:
            return None
        
        facility_data = self.coordinator.data["facility"]
        if not facility_data:
            return None
        
        # Return the total price from facility info
        total_price = facility_data.get("total")
        if total_price is not None:
            return round(float(total_price), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "facility" not in self.coordinator.data:
            return {}
        
        facility_data = self.coordinator.data["facility"]
        if not facility_data:
            return {}
        
        return {
            "average_electricity_price": facility_data.get("averageElectricityPriceAndDeliveryFee"),
            "average_surcharge": facility_data.get("averageSurCharge"),
            "markup": facility_data.get("markup"),
            "price_type": facility_data.get("priceType"),
        }


class LaddelFacilityAddressSensor(LaddelSensor):
    """Sensor for facility address."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Facility Address"
        self._attr_unique_id = f"{entry.entry_id}_facility_address"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "facility" not in self.coordinator.data:
            return None
        
        facility_data = self.coordinator.data["facility"]
        if not facility_data:
            return None
        
        # Build full address
        address_parts = []
        if facility_data.get("address"):
            address_parts.append(facility_data["address"])
        if facility_data.get("postalCode"):
            address_parts.append(facility_data["postalCode"])
        if facility_data.get("city"):
            address_parts.append(facility_data["city"])
        
        return ", ".join(address_parts) if address_parts else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "facility" not in self.coordinator.data:
            return {}
        
        facility_data = self.coordinator.data["facility"]
        if not facility_data:
            return {}
        
        return {
            "latitude": facility_data.get("latitude"),
            "longitude": facility_data.get("longitude"),
            "country": facility_data.get("country"),
            "county": facility_data.get("county"),
            "charger_count": len(facility_data.get("chargers", [])),
            "kw_effect": facility_data.get("kweffect"),
        }

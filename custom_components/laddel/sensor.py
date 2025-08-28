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

    # Priority 1: Current charging session (most important)
    entities.append(LaddelChargingSessionStatusSensor(coordinator, entry))
    entities.append(LaddelEnergyConsumedSensor(coordinator, entry))
    entities.append(LaddelChargingPowerSensor(coordinator, entry))  # Real calculated power
    entities.append(LaddelChargingDurationSensor(coordinator, entry))
    
    # Priority 2: Charger and facility status
    entities.append(LaddelChargerStatusSensor(coordinator, entry))
    entities.append(LaddelChargerIdSensor(coordinator, entry))
    entities.append(LaddelElectricityPriceSensor(coordinator, entry))
    
    # Priority 3: Cost tracking (financial info)
    entities.append(LaddelLastSessionCostSensor(coordinator, entry))
    entities.append(LaddelMonthlyCostSensor(coordinator, entry))
    entities.append(LaddelSessionCountSensor(coordinator, entry))
    
    # Priority 4: Facility information
    entities.append(LaddelFacilityNameSensor(coordinator, entry))
    entities.append(LaddelFacilityAddressSensor(coordinator, entry))
    entities.append(LaddelMaxChargingCapacitySensor(coordinator, entry))  # Max 22kW capacity
    
    # Priority 5: Subscription info (least important for daily use)
    entities.append(LaddelMonthlyFeeSensor(coordinator, entry))
    entities.append(LaddelSessionIdSensor(coordinator, entry))  # Replace useless sensors with Session ID

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
        if not subscription_data:
            return None
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
        if not subscription_data:
            return {}
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
        if not subscription_data:
            return None
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
        if not subscription_data:
            return None
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
        if not subscription_data:
            return None
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
            # Check for "noSession" error
            error_key = session_data.get("errorKey") if session_data else None
            if error_key == "noSession":
                return "No Session"
            return "No Active Session"
        
        # Check session type and charger operating mode from real API response
        session_type = session_data.get("type", "").upper()
        charger_mode = session_data.get("chargerOperatingMode", "")
        error_key = session_data.get("errorKey")
        
        # Handle error states
        if error_key == "noSession":
            return "No Session"
        elif error_key:
            return f"Error: {error_key}"
        
        # Handle active sessions with different operating modes
        if session_type == "ACTIVE":
            if charger_mode == "CHARGING":
                return "Charging"
            elif charger_mode == "COMPLETED":
                return "Session Complete"
            elif charger_mode == "IDLE":
                return "Connected"
            else:
                return f"Active ({charger_mode})"
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
            ATTR_SESSION_START: session_data.get("startTime"),
            ATTR_SESSION_END: session_data.get("endTime"),
            ATTR_ENERGY_CONSUMED: session_data.get("charged"),  # Real API field
            "session_id": session_data.get("sessionId"),
            "facility_id": session_data.get("facilityId"),
            "latitude": session_data.get("latitude"),
            "longitude": session_data.get("longitude"),
            "vehicle": session_data.get("vehicle"),
            "charging_privately": session_data.get("chargingPrivately"),
            "session_type": session_data.get("type"),
            "charger_operating_mode": session_data.get("chargerOperatingMode"),
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
        if not session_data or session_data.get("errorKey") == "noSession":
            return None
        
        session_type = session_data.get("type", "").upper()
        charger_mode = session_data.get("chargerOperatingMode", "")
        
        # Only calculate power during active charging
        if session_type != "ACTIVE" or charger_mode != "CHARGING":
            return 0.0
        
        # Calculate real charging power from energy consumed over time
        energy_kwh = session_data.get("charged")  # kWh consumed
        start_time_str = session_data.get("startTime")
        
        if not start_time_str:
            return 0.0
            
        # If no energy consumed yet (very new session), estimate power
        if not energy_kwh or energy_kwh <= 0:
            # For very new sessions, use a reasonable estimate
            return 11.0  # Typical charging rate
        
        try:
            from datetime import datetime
            from homeassistant.util import dt as dt_util
            
            # Parse start time
            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            now = dt_util.now()
            duration_hours = (now - start_dt).total_seconds() / 3600
            
            if duration_hours <= 0:
                return 0.0
            
            # Calculate average power: kWh / hours = kW
            average_power = energy_kwh / duration_hours
            
            # Cap at facility max power (sanity check)
            max_power = 22.0  # Default max
            if (self.coordinator.data.get("facility") and 
                self.coordinator.data["facility"].get("kweffect")):
                max_power = self.coordinator.data["facility"]["kweffect"]
            
            return min(round(average_power, 2), max_power)
            
        except (ValueError, TypeError) as e:
            _LOGGER.debug("Error calculating charging power: %s", e)
            return 0.0


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
        if not session_data or session_data.get("errorKey") == "noSession":
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
        if not session_data or session_data.get("errorKey") == "noSession":
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
        if not session_data or session_data.get("errorKey") == "noSession":
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


class LaddelLastSessionCostSensor(LaddelSensor):
    """Sensor for the cost of the last charging session."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Last Session Cost"
        self._attr_unique_id = f"{entry.entry_id}_last_session_cost"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "NOK"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return None
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("receipts"):
            return None
        
        # Get the most recent session cost
        latest_receipt = recent_data["receipts"][0]
        cost = latest_receipt.get("totalAmount")
        if cost is not None:
            return round(float(cost), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return {}
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("receipts"):
            return {}
        
        latest_receipt = recent_data["receipts"][0]
        return {
            "session_start": latest_receipt.get("sessionStart"),
            "session_end": latest_receipt.get("sessionEnd"),
            "charger_name": latest_receipt.get("chargerName"),
            "facility_name": latest_receipt.get("facilityName"),
            "power_consumption": latest_receipt.get("powerConsumption"),
            "payment_status": latest_receipt.get("paymentStatus"),
            "currency": latest_receipt.get("currency"),
            "total_excl_vat": latest_receipt.get("totalPriceExclVat"),
            "total_vat": latest_receipt.get("totalVat"),
        }


class LaddelMonthlyCostSensor(LaddelSensor):
    """Sensor for monthly charging costs."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Monthly Charging Cost"
        self._attr_unique_id = f"{entry.entry_id}_monthly_cost"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "NOK"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return None
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("monthlySummaries"):
            return None
        
        # Get current month's total
        current_month = datetime.now().strftime("%Y-%m")
        for summary in recent_data["monthlySummaries"]:
            if summary.get("month") == current_month:
                total_amount = summary.get("totalAmount")
                if total_amount is not None:
                    return round(float(total_amount), 2)
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return {}
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("monthlySummaries"):
            return {}
        
        # Return all monthly summaries
        monthly_data = {}
        for summary in recent_data["monthlySummaries"]:
            month = summary.get("month")
            if month:
                monthly_data[month] = {
                    "total_amount": summary.get("totalAmount"),
                    "session_count": summary.get("sessionCount"),
                }
        
        return {"monthly_summaries": monthly_data}


class LaddelSessionCountSensor(LaddelSensor):
    """Sensor for monthly session count."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Monthly Session Count"
        self._attr_unique_id = f"{entry.entry_id}_session_count"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return None
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("monthlySummaries"):
            return None
        
        # Get current month's session count
        current_month = datetime.now().strftime("%Y-%m")
        for summary in recent_data["monthlySummaries"]:
            if summary.get("month") == current_month:
                session_count = summary.get("sessionCount")
                if session_count is not None:
                    return int(session_count)
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "recent_sessions" not in self.coordinator.data:
            return {}
        
        recent_data = self.coordinator.data["recent_sessions"]
        if not recent_data or not recent_data.get("receipts"):
            return {}
        
        # Count sessions by payment status
        payment_statuses = {}
        for receipt in recent_data["receipts"]:
            status = receipt.get("paymentStatus", "unknown")
            payment_statuses[status] = payment_statuses.get(status, 0) + 1
        
        return {
            "payment_status_breakdown": payment_statuses,
            "total_sessions": len(recent_data["receipts"]),
        }


class LaddelChargerStatusSensor(LaddelSensor):
    """Sensor for charger operating mode and car connection status."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Charger Status"
        self._attr_unique_id = f"{entry.entry_id}_charger_status"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "charger_operating_mode" not in self.coordinator.data:
            return "Unknown"
        
        charger_data = self.coordinator.data["charger_operating_mode"]
        if not charger_data:
            return "Unknown"
        
        operating_mode = charger_data.get("operatingMode", "")
        
        # Map operating modes to user-friendly states
        mode_mapping = {
            "CAR_CONNECTED": "Car Connected",
            "DISCONNECTED": "Disconnected",
            "AVAILABLE": "Available", 
            "CHARGING": "Charging",
            "IDLE": "Idle",
            "OCCUPIED": "Occupied",
            "OUT_OF_ORDER": "Out of Order",
            "OFFLINE": "Offline",
        }
        
        return mode_mapping.get(operating_mode, operating_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "charger_operating_mode" not in self.coordinator.data:
            return {}
        
        charger_data = self.coordinator.data["charger_operating_mode"]
        if not charger_data:
            return {}
        
        attributes = {
            "charger_id": charger_data.get("chargerId"),
            "operating_mode": charger_data.get("operatingMode"),
            "error_key": charger_data.get("errorKey"),
        }
        
        # Add latest charger info if available
        if self.coordinator.data.get("latest_chargers"):
            latest_data = self.coordinator.data["latest_chargers"]
            if latest_data.get("chargers"):
                latest_charger = latest_data["chargers"][0]
                attributes.update({
                    "latest_charger_name": latest_charger.get("chargerName"),
                    "latest_facility_name": latest_charger.get("facilityName"),
                    "is_latest_charger": latest_charger.get("chargerId") == charger_data.get("chargerId"),
                })
        
        return attributes


class LaddelSessionIdSensor(LaddelSensor):
    """Sensor for current charging session ID."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Session ID"
        self._attr_unique_id = f"{entry.entry_id}_session_id"
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return None
        
        session_data = self.coordinator.data["current_session"]
        if not session_data or session_data.get("errorKey") == "noSession":
            return None
        
        return session_data.get("sessionId")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data or "current_session" not in self.coordinator.data:
            return {}
        
        session_data = self.coordinator.data["current_session"]
        if not session_data or session_data.get("errorKey") == "noSession":
            return {}
        
        return {
            "facility_id": session_data.get("facilityId"),
            "start_time": session_data.get("startTime"),
            "session_type": session_data.get("type"),
            "charging_privately": session_data.get("chargingPrivately"),
        }


class LaddelMaxChargingCapacitySensor(LaddelSensor):
    """Sensor for maximum charging capacity of the charger."""

    def __init__(self, coordinator: LaddelDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = "Max Charging Capacity"
        self._attr_unique_id = f"{entry.entry_id}_max_charging_capacity"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        # Get max power from facility data
        if (self.coordinator.data and 
            self.coordinator.data.get("facility") and 
            self.coordinator.data["facility"].get("kweffect")):
            return self.coordinator.data["facility"]["kweffect"]
        
        # Default fallback for typical Norwegian chargers
        return 22.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {}
        
        if (self.coordinator.data and 
            self.coordinator.data.get("facility")):
            facility_data = self.coordinator.data["facility"]
            attributes.update({
                "facility_name": facility_data.get("facilityName"),
                "charger_count": len(facility_data.get("chargers", [])),
                "price_type": facility_data.get("priceType"),
                "charging_fee": facility_data.get("chargingFeeIncludingVAT", 0),
            })
        
        return attributes

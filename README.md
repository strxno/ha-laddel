# Laddel EV Charging Integration for Home Assistant
Version 1.0.0
_Unofficial community integration to monitor your Laddel EV charging sessions in Home Assistant._

**⚠️ This is a community-developed integration and is not officially supported by Laddel.**

## About

[Laddel](https://laddel.no) is a Norwegian EV charging service provider. This integration allows you to monitor your charging sessions and subscription status directly in Home Assistant.

## Features

This integration provides comprehensive monitoring of your Laddel charging infrastructure directly in Home Assistant:

### Subscription Monitoring
- **Subscription Status**: Track your subscription status (ACTIVE, EXPIRED, etc.)
- **Monthly Fee**: Monitor your monthly subscription costs in NOK
- **Facility Information**: View your charging facility name and details
- **Days Remaining**: See how many days are left in your current subscription period
- **Active Subscription Indicator**: Binary sensor for active subscription status

### Real-time Charging Session Monitoring
- **Session Status**: Monitor current charging session state (Charging, Completed, Cancelled)
- **Live Power Monitoring**: Real-time charging power in kW
- **Energy Consumption**: Track energy consumed in the current session (kWh)
- **Session Duration**: Monitor how long your current charging session has been running
- **Charger Information**: View which charger you're using and its operating mode
- **Active Session Indicator**: Binary sensor for active charging sessions

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the "+" button to add a repository
4. Search for "Laddel" and install it
5. Restart Home Assistant

### Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`)
2. If you do not have a `custom_components` directory (folder) there, you need to create it
3. In the `custom_components` directory (folder) create a new folder called `laddel`
4. Download _all_ the files from the `custom_components/laddel/` directory (folder) in this repository
5. Place the files you downloaded in the new directory (folder) you created
6. Restart Home Assistant

## Configuration

The integration can be configured through the Home Assistant UI:

**Settings** → **Devices & Services** → **Add Integration** → **Laddel EV Charging**

### Authentication Options

#### OAuth2 with PKCE (Recommended)
Simply enter your Laddel account email and password. The integration will:
- Automatically handle OAuth2 authentication using PKCE (Proof Key for Code Exchange)
- Securely obtain and manage access tokens
- Automatically refresh tokens when needed
- Follow OAuth2 security best practices

#### Manual Refresh Token (Advanced)
For advanced users who prefer to extract refresh tokens manually from the Laddel mobile app.

## Entities

Once configured, the integration will create the following entities:

### Sensors
| Entity | Description | Unit |
|--------|-------------|------|
| `sensor.laddel_subscription_status` | Current subscription status | - |
| `sensor.laddel_monthly_fee` | Monthly subscription fee | NOK |
| `sensor.laddel_facility_name` | Name of your charging facility | - |
| `sensor.laddel_days_remaining` | Days remaining in subscription | days |
| `sensor.laddel_charging_session_status` | Current charging session status | - |
| `sensor.laddel_charging_power` | Real-time charging power | kW |
| `sensor.laddel_energy_consumed` | Energy consumed in current session | kWh |
| `sensor.laddel_charging_duration` | Duration of current session | minutes |
| `sensor.laddel_charger_id` | ID of the charger being used | - |

### Binary Sensors
| Entity | Description |
|--------|-------------|
| `binary_sensor.laddel_active_subscription` | Active subscription indicator |
| `binary_sensor.laddel_active_charging_session` | Active charging session indicator |

## Automation Examples

### Notify When Charging Starts
```yaml
automation:
  - alias: "Notify when EV charging starts"
    trigger:
      platform: state
      entity_id: binary_sensor.laddel_active_charging_session
      to: "on"
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "EV charging has started at {{ state_attr('sensor.laddel_facility_name', 'facility_name') }}"
```

### Notify When Subscription Expires Soon
```yaml
automation:
  - alias: "Subscription expiring soon"
    trigger:
      platform: numeric_state
      entity_id: sensor.laddel_days_remaining
      below: 7
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "Your Laddel subscription expires in {{ states('sensor.laddel_days_remaining') }} days"
```

### Track Monthly Charging Costs
```yaml
automation:
  - alias: "Log monthly charging costs"
    trigger:
      platform: state
      entity_id: sensor.laddel_monthly_fee
    action:
      service: logbook.log
      data:
        name: "Laddel Charging"
        message: "Monthly fee updated to {{ states('sensor.laddel_monthly_fee') }} NOK"
```

## API Endpoints

This integration connects to the following Laddel API endpoints:

- **Authentication**: `https://id.laddel.no/realms/laddel-app-prod/protocol/openid-connect/`
- **Subscription Data**: `https://api.laddel.no/v1/api/facility/subscription`
- **Current Session**: `https://api.laddel.no/v1/api/session/get-current-session`
- **Charger Operating Mode**: `https://api.laddel.no/v1/api/charger/operating-mode`

The integration automatically handles:
- OAuth2 authentication with PKCE security
- Token refresh and management
- API authentication and headers
- Data polling every 5 minutes
- Error handling and retry logic

## Troubleshooting

### Authentication Issues
If you experience authentication problems:
1. Verify your Laddel account credentials are correct
2. Check that your account has an active subscription
3. Try removing and re-adding the integration

### Missing Data
If some sensors show "Unknown" or "Unavailable":
- Ensure you have an active Laddel subscription
- Check if you have any active charging sessions
- Verify your account has access to the charging facilities

### API Rate Limits
The integration polls data every 5 minutes to respect API limits.

## Support

This is a community addon with support available only through GitHub issues. 

## Disclaimer

This integration is not officially endorsed by Laddel. It uses the same APIs as the official Laddel mobile application.

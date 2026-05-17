# Baxi HybridApp Home

Custom integration for [Home Assistant](https://home-assistant.io) to monitor and control your Baxi system via the HybridApp cloud API.

## Features

🌡️ **Temperature Sensors**
- External Temperature, Internal Temperature
- Boiler Flow Temperature, PDC Exit / Return Temperature
- DHW Storage Temperature, DHW Auxiliary Storage Temperature
- Sanitary Setpoints (Instantaneous, Comfort, Eco)

💧 **Pressure Sensor**
- Water Pressure (bar)

⚡ **Power Sensors**
- Boiler Instantaneous Power, PDC Instantaneous Power

🧭 **Mode / Status Sensors**
- System Mode, System Operation Mode, Season Mode
- Sanitary On, Flame Status, Scheduler Status

⚡ **Energy Sensors** _(disabled by default, compatible with HA Energy dashboard)_
- Total and partial energy for PDC, boiler, and electric resistances

🔔 **Alert Monitoring**
- Binary sensors for active FAILURE and WARNING alerts
- FAILURE count (last 24h / last 7 days)
- Event `baxi_hybridapp_alert` on the HA bus for automations
- Blueprint included for push notifications to the HA mobile app

🛁 **Water Heater Entities**
- Adjustable Comfort and Eco DHW setpoints (30–52 °C)

Data is fetched from the Baxi cloud every **10 minutes** via polling.

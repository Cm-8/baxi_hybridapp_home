# Baxi HybridApp Home

**Unofficial integration for Baxi HybridApp in Home Assistant**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/Cm-8/baxi_hybridapp_home.svg)](https://github.com/Cm-8/baxi_hybridapp_home/releases)

> **Disclaimer:** This is an unofficial integration and is not affiliated with or endorsed by Baxi in any way.

Custom integration for Home Assistant to monitor data from your Baxi system through the **HybridApp** cloud API.

---

## Features

This integration provides the following sensors:

🌡️ Temperature Sensors
- External Temperature
- Internal Temperature
- Boiler Flow Temperature
- DHW Storage Temperature
- DHW Auxiliary Storage Temperature
- PDC Exit Temperature
- PDC Return Temperature
- Sanitary Setpoint Instantaneous
- Sanitary Setpoint Comfort
- Sanitary Setpoint Eco

🧭 Mode / Status Sensors
- System Mode
- Season Mode
- Sanitary Mode On

💧 Pressure Sensor
- Water Pressure

Data is fetched from the Baxi cloud every 5 minutes via polling.

---

## Requirements

- A valid account for the [Baxi HybridApp](https://play.google.com/store/apps/details?id=it.baxi.HybridApp)  
- Home Assistant version >= 2023.0

---

## Installation

### Manual

1. Copy the `baxi_hybridapp_home` folder into your `custom_components` directory.
2. Restart Home Assistant.

### Via HACS (Custom Repository)

1. In HACS, go to **Integrations** > **Custom Repositories**.
2. Add `https://github.com/Cm-8/baxi_hybridapp_home` as a new repository.
3. Search for **Baxi HybridApp Home** and install it.

---

## Configuration

After installation, configure the integration via the Home Assistant UI:

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for `Baxi HybridApp Home`.
3. Enter your Baxi app credentials (email and password).

---

## Limitations

- This is a cloud polling integration and requires an internet connection.
- Currently, only one Baxi system is supported per configuration entry.

---

## Contributing

Contributions are welcome! If you find a bug or want to request a feature:

- [Open an issue here](https://github.com/Cm-8/baxi_hybridapp_home/issues)

---

## Author

[@Cm-8](https://github.com/Cm-8)

---

**Disclaimer:** This integration is not affiliated with or endorsed by Baxi.

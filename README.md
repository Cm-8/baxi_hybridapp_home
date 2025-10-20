# Baxi HybridApp Home

**Unofficial integration for Baxi HybridApp in Home Assistant**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/Cm-8/baxi_hybridapp_home.svg?style=for-the-badge&color=blue)](https://github.com/Cm-8/baxi_hybridapp_home/releases)
[![Integration Usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&style=for-the-badge&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$['baxi_hybridapp_home'].total)](https://analytics.home-assistant.io/)

> **Disclaimer:** This is an unofficial integration and is not affiliated with or endorsed by Baxi in any way.

Custom integration for Home Assistant to monitor data from your Baxi system through the **HybridApp** cloud API.


## References

<img src="https://raw.githubusercontent.com/Cm-8/baxi_hybridapp_home/main/assets/pannello-di-controllo-wi-fi-da-esterno.png" alt="Pannello Controllo Wifi Esterno" width="250" height="auto" align="right">

This extension is only compatible with devices:
- [CSI IN Alya / Auriga H WI-FI (Baxi website)](https://www.baxi.it/prodotti/pompe-di-calore/sistemi-ad-incasso-in-pompa-di-calore-con-integrazione-solo-elettrica/csi-in-auriga-e-wi-fi)
- [Baxi HybridApp (Baxi website)](https://www.baxi.it/news/baxi-hybrid-app)
- [Cronotermostato modulante - Kit pannello di controllo wi fi da esterno (Baxi website)](https://www.youtube.com/redirect?event=video_description&redir_token=QUFFLUhqa2tDRmdtdDdKWFViSkpSbkViWmtqUldxX2o3UXxBQ3Jtc0tsZ0VnT0hxN2ZhUEk0MkVMU1ZvOE5fMVhDZEZnalkwNFhCRHBYU2lFQ2ljZnRFQ3JtdmFjcnRfZWtNYXNQVC1FOEx3SEwyd00zRUVGVzlTMDU2Ym1KR29SdjNvMWxsTlIzNlB6eU9ZcFNPbEZ4MHQzTQ&q=https%3A%2F%2Fwww.baxi.it%2Fprodotti%2Fdigital%2Fkit-pannello-di-controllo-wi-fi-da-esterno&v=RW-ZO0UKzrE)
- [Pannello di controllo WI-FI - (Youtube video)](https://www.youtube.com/watch?v=RW-ZO0UKzrE)


---

## Features

This integration provides the following sensors:

**🌡️ Temperature Sensors**
- **External Temperature** — ambient outdoor temperature
- **Internal Temperature** — indoor room temperature (if available)
- **Boiler Flow Temperature** — heating circuit flow temperature
- **Boiler Return Temperature** — heating circuit return temperature
- **DHW Storage Temperature** — domestic hot water storage temperature
- **DHW Auxiliary Storage Temperature** — auxiliary tank temperature
- **PDC Exit Temperature** — heat pump outlet temperature
- **PDC Return Temperature** — heat pump return temperature
- **Sanitary Setpoint Instantaneous** — current target DHW temperature
- **Sanitary Setpoint Comfort** — comfort mode setpoint
- **Sanitary Setpoint Eco** — eco mode setpoint

**🧭 Mode / Status Sensors**
- **System Mode** — current system state (e.g., Standby, Heating, Cooling)
- **Season Mode** — current seasonal configuration (Winter, Summer)
- **Sanitary Mode On** — indicates if sanitary mode is active
- **Scheduler Status** — indicates if DHW scheduler is active or in error
- **Scheduler Raw JSON** — raw data used for diagnostic and automation parsing
- **Flame Status** — shows if boiler flame is currently active
- **Compressor Status** — shows if heat pump compressor is running

**💧 Pressure Sensor**
- **Water Pressure** — hydraulic circuit pressure (in bar)

**🔘 Control Entities**
- **Water Heater – Comfort Setpoint** — adjustable DHW comfort temperature
- **Water Heater – Eco Setpoint** — adjustable DHW eco temperature
- **Buttons / Actions** — triggerable service calls:
  - **set_comfort** — set new comfort temperature
  - **set_eco** — set new eco temperature

**⚙️ Coordinator & Update**
- Data is fetched from the Baxi Servitly Cloud API every **10 minutes** via polling
- Smart error handling and logging for unavailable data
- Async-compatible API layer (BaxiHybridAppAPI) with rate-limit protection
- Data is fetched from the Baxi cloud every 10 minutes via polling.

**🧩 Planned / Experimental**
- Support for **Heating/Cooling** setpoints (climate entity)

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

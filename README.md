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

### 🌡️ Temperature Sensors
- **External Temperature** — ambient outdoor temperature
- **Internal Temperature** — indoor room temperature (if available)
- **Boiler Flow Temperature** — heating circuit flow temperature
- **DHW Storage Temperature** — domestic hot water storage temperature
- **DHW Auxiliary Storage Temperature** — auxiliary tank temperature
- **PDC Exit Temperature** — heat pump outlet temperature
- **PDC Return Temperature** — heat pump return temperature
- **Sanitary Setpoint Instantaneous** — current target DHW temperature
- **Sanitary Setpoint Comfort** — comfort mode setpoint
- **Sanitary Setpoint Eco** — eco mode setpoint

### 💧 Pressure Sensor
- **Water Pressure** — hydraulic circuit pressure (bar)

### ⚡ Power Sensors
- **Boiler Instantaneous Power** — current boiler power output
- **PDC Instantaneous Power** — current heat pump power output

### 🧭 Mode / Status Sensors
- **System Mode** — current operating mode (Automatico, Standby, Solo Sanitario)
- **System Operation Mode** — firmware-level operating mode (Automatico, Standby)
- **Season Mode** — current seasonal configuration (Winter, Summer, Auto)
- **Sanitary On** — whether sanitary mode is active (On / Off)
- **Sanitary Request Status** — DHW request status code
- **Scheduler Status** — DHW scheduler state (active, off, or error)
- **Flame Status** — whether the boiler flame is currently active (On / Off)
- **System Operation Icon** — icon code from the Baxi cloud status

### ⚡ Energy Sensors
All energy sensors are disabled by default and use `TOTAL_INCREASING` state class (compatible with the HA Energy dashboard).

- **Energia totale PDC** — total heat pump energy consumption (kWh)
- **Energia totale caldaia** — total boiler energy consumption (kWh)
- **Energia totale resistenze** — total electric resistance energy (kWh)
- **Energia totale globale** — total system energy (kWh)
- **Energia totale globale per day** — daily total system energy (kWh)
- **Energia parziale caldaia** — partial boiler energy (kWh)
- **Energia parziale PDC** — partial heat pump energy (kWh)
- **Energia parziale resistenze** — partial electric resistance energy (kWh)

### 🔔 Alert Monitoring
The integration polls the Baxi cloud for historical FAILURE and WARNING alerts and exposes them as diagnostic entities.

- **Failure** — binary sensor (Problem / OK); active when a FAILURE alert is open
- **Warning** — binary sensor (Problem / OK); active when a WARNING alert is open (disabled by default)
- **Failure ultime 24h** — count of FAILURE alerts in the last 24 hours
- **Failure ultimi 7g** — count of FAILURE alerts in the last 7 days

Each new alert fires a `baxi_hybridapp_alert` event on the Home Assistant event bus, which can be used as a trigger for automations. The event payload includes `severity`, `code`, `description`, `title`, `start_ts`, and `end_ts`.

A ready-made **blueprint** for push notifications is included — see [blueprints/automation/baxi_hybridapp_home/notifica_avvisi.yaml](blueprints/automation/baxi_hybridapp_home/notifica_avvisi.yaml).

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FCm-8%2Fbaxi_hybridapp_home%2Fmain%2Fblueprints%2Fautomation%2Fbaxi_hybridapp_home%2Fnotifica_avvisi.yaml)

### 🛁 Water Heater Entities
- **Sanitario Comfort** — adjustable DHW comfort temperature setpoint (30–52 °C)
- **Sanitario Eco** — adjustable DHW eco temperature setpoint (30–52 °C)

### 🔘 Diagnostic Entities
- **Aggiorna dati** — button to manually trigger a data refresh

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

## Push Notification Blueprint

To receive push notifications on your phone when a Baxi alert is detected:

Click the button below to import the blueprint directly into your Home Assistant:

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FCm-8%2Fbaxi_hybridapp_home%2Fmain%2Fblueprints%2Fautomation%2Fbaxi_hybridapp_home%2Fnotifica_avvisi.yaml)

Or manually: **Settings** > **Automations & Scenes** > **Blueprints** > **Import Blueprint** and paste:
```
https://raw.githubusercontent.com/Cm-8/baxi_hybridapp_home/main/blueprints/automation/baxi_hybridapp_home/notifica_avvisi.yaml
```

Then create an automation from the blueprint, select your mobile notify service and the desired severity filter.

---

## Limitations

- This is a cloud polling integration and requires an internet connection.
- Data is refreshed every 10 minutes.
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

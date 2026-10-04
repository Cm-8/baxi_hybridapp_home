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

Other systems supported by the Baxi HybridApp, **not yet tested** with this integration:
- Artemis systems
- Luna OpenTherm built-in systems

Readings may partly work; the controls use model-specific commands and may not. If you own one of these systems, please [open an issue](https://github.com/Cm-8/baxi_hybridapp_home/issues) and attach the diagnostics (see [Troubleshooting](#troubleshooting)).


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
- **Cooling Setpoint** — cooling flow setpoint (7–30 °C, disabled by default)

### 💧 Pressure Sensor
- **Water Pressure** — hydraulic circuit pressure (bar)

### ⚡ Power Sensors
- **Boiler Instantaneous Power** — current boiler power output
- **PDC Instantaneous Power** — current heat pump power output

### 🧭 Mode / Status Sensors
- **System Mode** — current operating mode (Automatico, Standby, Solo Sanitario)
- **System Operation Mode** — firmware-level operating mode (Automatico, Standby, Solo Sanitario)
- **Season Mode** — current seasonal configuration (Estate, Inverno, Estate/Inverno automatico, Estate/Inverno remoto)
- **Sanitary On** — whether sanitary mode is active (On / Off)
- **Scheduler Status** — DHW scheduler state (active, off, or error)
- **Flame Status** — whether the boiler flame is currently active (On / Off)
- **Boiler Status** — boiler state (On / Off)
- **PDC Status** — heat pump state (On / Avvio / Off; "Avvio" is the short start-up phase)
- **Holiday Mode** — whether holiday mode is active (On / Off)
- **Holiday Mode End** — end date/time of the active holiday period (unknown while holiday mode is off)
- **System Operation Icon** — icon code from the Baxi cloud status (disabled by default)

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

### 🎛️ Operating Mode Control
- **Modo Impianto** — select entity to switch between **Automatico**, **Solo Sanitario** and **Standby**; sends the command to the Baxi cloud instantly and refreshes the state
- **Modo Stagione** — select entity to switch the season mode between **Estate**, **Inverno**, **Estate/Inverno automatico** and **Estate/Inverno remoto**

### 🛁 Water Heater Entities
- **Sanitario Comfort** — adjustable DHW comfort temperature setpoint (30–52 °C)
- **Sanitario Eco** — adjustable DHW eco temperature setpoint (30–52 °C)

### 🏖️ Holiday Mode Control
Mirrors the Baxi app's on/off flag, avoiding accidental sends. Both entities are **disabled by default** — enable them if you use holiday mode:
- **Modo Vacanza Fine** — datetime entity for the end date/time. When holiday mode is **off**, setting it only *stages* the value locally (nothing is sent) — you apply it with the switch. When holiday mode is already **on**, changing it is sent immediately (extend/shorten the period).
- **Modo Vacanza** — switch: turning it **on** sends the staged end date and activates holiday mode; turning it **off** disables it. Set the date first, then flip the switch.

### ❄️ Cooling Control
- **Setpoint Raffrescamento** — adjustable cooling flow setpoint (7–30 °C, number entity, disabled by default); automatable via the native `number.set_value` service (e.g. lower it when you have photovoltaic surplus)

### 🔘 Diagnostic Entities
- **Aggiorna** — button to manually trigger a data refresh
- **Test Failure** — button to simulate a FAILURE alert (only available with debug logging enabled)

### 🩺 Diagnostics
From the integration page (**⋮** > **Download diagnostics**) you can download a JSON report with the current sensor values and the full catalog of commands, configuration parameters and metrics supported by your device model. Credentials and serial number are redacted. Attach it when opening an issue — it makes troubleshooting much faster, especially for device models not yet fully supported.

---

## Requirements

- A valid account for the [Baxi HybridApp](https://play.google.com/store/apps/details?id=it.baxi.HybridApp)
- Home Assistant version >= 2025.1.0

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

Credentials are validated against the Baxi cloud before the integration is created: if the login fails, the form shows a specific error (invalid credentials, connection problem, or unknown error).

If your password changes later, Home Assistant will automatically ask you to re-authenticate — just enter the new password, no need to remove and re-add the integration.

To update the credentials yourself at any time, open the integration and select **⋮** > **Reconfigure**. The account must stay the same: to add a different Baxi system, add a new integration.

Entity names and messages follow the Home Assistant language (Italian or English) and are shown with the device name in front, as usual in Home Assistant (for example *Baxi HybridApp Home Temp. Esterna*).

### Update interval

Data is read from the Baxi cloud every **5 minutes**. To change it, open the integration and select **Configure**: you can choose 2, 5 (recommended) or 10 minutes. The new interval applies right away, without restarting and without entering the password again. Shorter intervals mean more requests to the Baxi cloud.

For a custom schedule (for example every 2 minutes only during the day), use an automation with the `homeassistant.update_entity` action. **Updating a single entity of the integration updates all the others too**, so one entity is enough. Example every 2 minutes (replace the `entity_id` with the real one of your *External Temperature* sensor, from **Settings** > **Devices & Services** > **Entities**):

```yaml
- alias: "Baxi: aggiornamento ogni 2 minuti"
  triggers:
    - trigger: time_pattern
      minutes: "/2"
  actions:
    - action: homeassistant.update_entity
      target:
        entity_id: sensor.baxi_temperatura_esterna
```

Use an entity that is enabled (not, for example, an energy sensor disabled by default). Updates closer than 10 seconds are merged into one. If you want only the automation to decide when to update, disable the automatic updates in the integration's **⋮** > **System options**.

---

## Service actions

| Action | Description |
|---|---|
| `baxi_hybridapp_home.set_comfort` | Sets the DHW **Comfort** setpoint (`value`: 30–52 °C) |
| `baxi_hybridapp_home.set_eco` | Sets the DHW **Eco** setpoint (`value`: 30–52 °C) |

```yaml
action: baxi_hybridapp_home.set_comfort
data:
  value: 45
```

The same actions are available as device actions in the automation editor. Like the controls, they show an error if the Baxi cloud rejects the request; the new value is confirmed from the cloud about 30 seconds later.

---

## Removal

1. Go to **Settings** > **Devices & Services**, open **Baxi HybridApp Home** and select **⋮** > **Delete**.
2. If you installed it via HACS, remove it from HACS; if you installed it manually, delete the `custom_components/baxi_hybridapp_home` folder.
3. Restart Home Assistant.

Removing the integration changes nothing on your Baxi system or in the Baxi app.

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

## Troubleshooting

- **All entities unavailable** — no request to the Baxi cloud succeeded: the entities recover by themselves at the next successful refresh. Check that the Baxi app works.
- **A single entity unavailable** — your system may not provide that measurement (for example, flame status on an all-electric system).
- **"Sconosciuto (…)" value** — the cloud sent a code the integration does not know yet: open an issue saying which mode the system was in.
- **Debug logs** — add to `configuration.yaml` and restart:
  ```yaml
  logger:
    logs:
      custom_components.baxi_hybridapp_home: debug
  ```
- **Diagnostics** — integration page > **⋮** > **Download diagnostics**, then attach the file to the issue (credentials and serial number are redacted).

---

## Limitations

- This is a cloud polling integration and requires an internet connection.
- Data is refreshed every 5 minutes by default (2, 5 or 10 minutes from **Configure**, see [Update interval](#update-interval)).
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

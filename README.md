# Baxi HybridApp Home

Baxi HybridApp integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/Cm-8/baxi_hybridapp_home.svg)](https://github.com/Cm-8/baxi_hybridapp_home/releases)

Custom integration for Home Assistant to monitor data from your Baxi system through the **HybridApp** cloud API.

## Features

This integration provides the following sensors:

- External temperature
- Internal temperature (Zone 1)
- System water pressure
- Boiler flow temperature
- DHW storage temperature

Data is fetched from the Baxi cloud every 5 minutes via polling.

## Requirements

- A valid account for the [Baxi HybridApp](https://play.google.com/store/apps/details?id=it.baxi.HybridApp)
- Home Assistant >= 2023.0

## Installation

### Manual

1. Copy the `baxi_hybridapp_home` folder into your `custom_components` directory.
2. Restart Home Assistant.

### Via HACS (Custom Repository)

1. In HACS, go to **Integrations** > **Custom Repositories**.
2. Add `https://github.com/Cm-8/baxi_hybridapp_home` as a new repository.
3. Search for "Baxi HybridApp Home" and install it.

## Configuration

After installation, set up the integration through the Home Assistant UI:

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for `Baxi HybridApp Home`.
3. Enter your Baxi app credentials.

## Debugging and Logs

To enable debug logs:

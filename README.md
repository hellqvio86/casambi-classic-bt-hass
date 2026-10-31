# Home Assistant Integration for Casambi Classic (Bluetooth)

[![HACS](https://img.shields.io/badge/HACS-Custom%20Repository-orange.svg)](https://hacs.xyz/)
[![Firmware](https://img.shields.io/badge/firmware-Classic%20Casambi-orange.svg)](https://casambi.com)
[![Focus](https://img.shields.io/badge/focus-Classic%20Bluetooth%20Mesh-green.svg)](#why-this-fork-classic-vs-evolution)

A custom integration for [Home Assistant](https://www.home-assistant.io/) to control **Casambi Classic** lighting networks locally via Bluetooth Low Energy (BLE).

> [!IMPORTANT]
> **Fork & Firmware Focus Notice**  
> This project is a specialized fork of [lkempf/casambi-bt-hass](https://github.com/lkempf/casambi-bt-hass) dedicated specifically to **Casambi Classic** firmware networks.
>
> Upstream `casambi-bt-hass` primarily targets modern **Evolution** firmware. This fork focuses on legacy **Classic** installations, introducing offline key cache support, robust auto-reconnection backoff logic, and domain naming (`casambi_classic_bt`) to avoid conflicts with Evolution-based components.

---

## Why This Fork? (Classic vs. Evolution)

Casambi networks run on either **Classic** or **Evolution** firmware:

- **Evolution Networks:** Newer Casambi installations use the Evolution profile. If your network runs Evolution firmware, you should use upstream [lkempf/casambi-bt-hass](https://github.com/lkempf/casambi-bt-hass).
- **Classic Networks (This Fork's Focus):** Many existing fixtures and installations run on Classic firmware. This fork provides:
  - Compatibility with Classic Bluetooth mesh characteristics and GATT services (`0000fe4d-...`).
  - Offline mode operation using pre-cached network credentials.
  - Resilient reconnection with exponential backoff if Bluetooth signal is temporarily lost.
  - Independent domain (`casambi_classic_bt`) so it can coexist smoothly.

> [!TIP]
> **Which integration should you use?**
> - For **Classic** firmware networks: **Use this integration (`casambi-classic-bt-hass`)**.
> - For **Evolution** firmware networks: Use [lkempf/casambi-bt-hass](https://github.com/lkempf/casambi-bt-hass).
> - For **Cloud API Gateway** setups: Consider [hellqvio86/home_assistant_casambi](https://github.com/hellqvio86/home_assistant_casambi).

---

## Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the three dots in the top right corner and choose **Custom repositories**.
4. Enter repository URL: `https://github.com/hellqvio86/casambi-classic-bt-hass`
5. Select category: **Integration**.
6. Click **Add**, search for **Casambi Classic Bluetooth**, and click **Download**.
7. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release from the repository.
2. Copy the `custom_components/casambi_classic_bt` folder into your Home Assistant `<config>/custom_components/` directory:
   ```
   <config>/custom_components/casambi_classic_bt/
   ```
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Integrations**.
2. Click **Add Integration** and search for **Casambi Classic Bluetooth**.
3. Follow the config flow to discover your local Classic network adapter and enter your network credentials.

### Enabling Debug Logging

If you encounter connection or discovery issues, enable debug logging by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    casambi_classic_ble: debug
    custom_components.casambi_classic_bt: debug
```

---

## Features

- 💡 **Lights:** On/Off, Brightness dimming.
- 🎨 **Color & White:** RGB, RGBW, and Kelvin Color Temperature.
- 👥 **Groups & Scenes:** Group control and Casambi scene activation.
- 🔄 **Resilient Reconnection:** Background reconnection task with backoff.
- 📴 **Offline Support:** Ability to connect and operate with cached network identifiers without continuous internet access.

---

## Development

This repository uses [`uv`](https://docs.astral.sh/uv/) and [`ruff`](https://docs.astral.sh/ruff/) for dependency management and linting.

```bash
# Setup environment and git commit hooks
make setup

# Or install git hooks directly
make hooks

# Run linting and code formatting checks
make lint

# Automatically format code with ruff
make format
```

## Credits

- Forked from [lkempf/casambi-bt-hass](https://github.com/lkempf/casambi-bt-hass) by Lukas Kempf.
- Maintained by [Olof Hellqvist](https://github.com/hellqvio86).

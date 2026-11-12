# Home Assistant Integration for Casambi Classic (Bluetooth)

[![HACS](https://img.shields.io/badge/HACS-Custom%20Repository-orange.svg)](https://hacs.xyz/)
[![Firmware](https://img.shields.io/badge/firmware-Classic%20Casambi-orange.svg)](https://casambi.com)
[![Focus](https://img.shields.io/badge/focus-Classic%20Bluetooth%20Mesh-green.svg)](#why-this-fork-classic-vs-evolution)
[![CI](https://github.com/hellqvio86/casambi-classic-bt-hass/actions/workflows/ci.yml/badge.svg)](https://github.com/hellqvio86/casambi-classic-bt-hass/actions/workflows/ci.yml)
[![Coverage](coverage.svg)](https://github.com/hellqvio86/casambi-classic-bt-hass/actions/workflows/ci.yml)

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

## Operational Limitations & Hardware Compatibility

- **Reverse-Engineered Protocol Scope:** Casambi does not publish an official specification for the Classic BLE GATT protocol. This integration and its underlying library ([`casambi-classic-ble`](https://github.com/hellqvio86/casambi-classic-ble)) implement behavior observed and verified against real Classic firmware fixtures:
  - **Vadsbo LD220WCM** (Trailing-edge phase-cut dimmer, Classic FW `26.x`)
  - **Vadsbo LD220WCM_onoff** (On/off relay module, Classic FW `26.x`)
  - **Casambi CBU-PWM4 RGBW** (4-channel PWM dimmer, Classic FW `26.x`)
  - **AIMOTION GLOW** (Pendant luminaire, Classic FW `26.x`)
  - **EnOcean PTM215B** (4-button kinetic BLE switch, Classic FW `20.x`–`26.x`)
- **Single Active BLE Connection Limit:** Casambi mesh nodes accept only **one active Bluetooth Low Energy GATT connection** at a time. If the official Casambi mobile app (iOS or Android) is open in the foreground or background on a smartphone or tablet in range, it will hold the GATT connection and cause Home Assistant connection attempts to time out. Force-close the mobile app before setting up or reconnecting in Home Assistant.
- **Local BLE Control vs. Initial Cloud Topology Discovery:**
  - Real-time light control, scene switching, and state updates run locally over BLE GATT.
  - Initial setup and password changes (re-authentication) contact the Casambi API once to fetch the network's topology (unit names, groups, scenes, fixture profiles, and Visitor/Manager signing keys) and cache them under `<config>/.storage/casambi_classic_bt/<uuid>/`.
- **What "Offline Support" Means:**
  - Once a network has been set up online and cached in `<config>/.storage/casambi_classic_bt/`, subsequent Home Assistant restarts can connect and authenticate over BLE completely offline using the cached topology and signing keys.
  - First-time setup, password changes, or newly added fixtures/groups/scenes cannot be discovered offline and require internet access during setup/reload.

---

## Safe Troubleshooting & Diagnostics

- **Close the Casambi App:** If setup fails with `Failed to connect` or `Connection timed out`, verify that no phone or tablet has the official Casambi app open.
- **Bluetooth Adapter / ESPHome Proxy Range:** Ensure your Home Assistant Bluetooth adapter (BlueZ `>= 5.64`) or ESPHome Bluetooth proxy has `connectable: true` enabled and adequate signal (`RSSI > -80 dBm`) to at least one mesh unit.
- **Never Share Secrets or Unredacted Identifiers:**
  - When opening an issue or sharing logs, **never publish your network password, cached `.storage/casambi_classic_bt/` JSON files (`casambi_lookup.json`, `casambi_session.json`), raw packet captures, or real Bluetooth MAC addresses**.
  - At standard `INFO` log level, MAC addresses (`AA:**:**:**:**:FF`) and credentials are automatically masked. When `debug` logging is enabled, sanitize any real MAC addresses (`AA:BB:CC:DD:EE:FF`) before posting logs publicly.

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

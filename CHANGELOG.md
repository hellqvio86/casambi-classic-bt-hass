# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] - 2026-11-01

### Changed
- Bumped integration version to `0.5.1` and updated minimum library requirement to `casambi-classic-ble>=0.5.1`.
- Modernized integration API calls to use snake_case keyword-only methods (`turn_on`, `turn_off`, `set_level`, `set_color`, `set_temperature`, `set_white`, `switch_to_scene`, `set_vertical`, `set_unit_state`).
- Updated exception imports directly from `casambi_classic_ble` root namespace, eliminating deprecation warnings.
- Switched to snake_case properties `network_id` and `network_name`.

## [0.4.0] - 2026-11-01

### Changed
- Bumped integration version to `0.4.0` and updated minimum library requirement to `casambi-classic-ble>=0.4.0`.
- Ensured clean background task cancellation and cleanup on disconnect/reconnect cycles.
- Added cross-platform file/directory permissions abstraction (`utils.permissions`) and sensitive logging sanitization (`utils.mask`).
- Migrated legacy cache files to JSON (`casambi_session.json`, `casambi_types.json`, `casambi_network_id.txt`).
- Fixed advertisement frame duplicate suppression and color temperature clamping.

## [0.3.6] - 2026-11-01

### Changed
- Bumped integration version to `0.3.6` and updated minimum library requirement to `casambi-classic-ble>=0.3.6`.
- Includes validated status opcode parsing (`0x03`) and enhanced beacon address matching and normalization.

## [0.3.5] - 2026-11-01

### Changed
- Bumped integration version to `0.3.5` and updated minimum library requirement to `casambi-classic-ble>=0.3.5`.
- Updated key storage backend to use `casambi_lookup.json` with seamless migration from legacy cache.
- Dispatched GATT notifications to unified device state subscribers with per-unit deduplication.

## [0.3.4] - 2026-11-01

### Changed
- Bumped integration version to `0.3.4` and updated minimum library requirement to `casambi-classic-ble>=0.3.4`.

## [0.3.3] - 2026-10-31

### Changed
- Bumped integration version to `0.3.3` and updated minimum library requirement to `casambi-classic-ble>=0.3.3`.

## [0.3.2] - 2026-10-31

### Added
- Automated CI/CD release workflow for HACS (Ruff linting, HACS action validation, Home Assistant hassfest validation).
- Automated HACS release packaging (`casambi_classic_bt.zip`) and GitHub release drafting on version bumps.
- Dependabot configuration with 2-day cooldown and assigned maintainer (`hellqvio86`).
- Pre-commit git hook and Makefile automation targets (`make lint`, `make format`, `make package`).

### Changed
- Bumped integration version to `0.3.2`.

## [0.3.1] - 2026-10-31

### Added
- Offline key cache directory support for seamless offline reconnection.
- Resilient connection backoff logic with exponential step delays.
- Dutch (`nl`) and German (`de`) translations.

### Changed
- Fork rebranded to `casambi_classic_bt` domain dedicated to Casambi Classic firmware networks.

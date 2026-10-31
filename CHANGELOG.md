# Changelog

All notable changes to this project will be documented in this file.

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

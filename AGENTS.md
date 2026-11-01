# AGENTS.md

Guidelines and operational knowledge for AI coding assistants (Antigravity Agent, Claude Code, Cursor, Copilot, etc.) and contributors working in this repository.

---

## 💡 What This Project Is

`casambi-classic-bt-hass` is a Home Assistant custom integration for controlling Casambi lighting networks running **Classic firmware** over **Bluetooth Low Energy (BLE)**.

- **Upstream Origin & Fork Focus:** Specialized standalone fork of [`lkempf/casambi-bt-hass`](https://github.com/lkempf/casambi-bt-hass). While upstream focuses primarily on modern **Evolution** firmware, this integration is dedicated exclusively to **Casambi Classic** firmware networks.
- **Core Library Dependency:** [`casambi-classic-ble`](https://github.com/hellqvio86/casambi-classic-ble) (PyPI: `casambi-classic-ble>=0.3.0`), which provides both the modern Classic BLE engine and the compatibility layer. **Do not use upstream `casambi-bt`**.
- **Downstream Consumer:** Home Assistant installations via HACS or automated homelab deployment pipelines.
- **Integration Domain:** `casambi_classic_bt` (renamed from `casambi_bt` to avoid conflicts with Evolution-based components).
- **Target Python Version:** `>= 3.12`.
- **Packaging & Dependency Management:** Managed with [`uv`](https://docs.astral.sh/uv/) and standard `pyproject.toml`.

---

## 📁 Repository Layout

```
casambi-classic-bt-hass/
├── custom_components/
│   └── casambi_classic_bt/     # Core Home Assistant custom integration
│       ├── __init__.py         # Integration lifecycle, CasambiApi coordinator & proxy
│       ├── binary_sensor.py    # Connectivity & network status binary sensors
│       ├── config_flow.py      # Config & reauth flow (Bluetooth discovery & cache)
│       ├── const.py            # Integration constants, backoff steps, domain
│       ├── entities.py         # Base entity models (unit, group, network)
│       ├── light.py            # Light platform (dimming, RGB, RGBW, Kelvin temp)
│       ├── number.py           # Number platform (vertical light / tilt control)
│       ├── scene.py            # Scene platform (Casambi scene activation)
│       ├── manifest.json       # Home Assistant integration manifest
│       ├── strings.json        # Base translations & configuration strings
│       └── translations/       # Localized strings (en, de, nl)
├── .github/
│   ├── workflows/
│   │   └── ci.yml              # CI/CD pipeline (Ruff, Hassfest, HACS, Draft Release)
│   └── dependabot.yml          # Dependabot configuration (2-day cooldown, hellqvio86 assignee)
├── .githooks/                  # Git commit hooks (pre-commit lint & format runner)
├── Makefile                    # Developer convenience targets
├── hacs.json                   # HACS repository metadata
├── pyproject.toml              # Build config, dependencies, Ruff configurations
└── uv.lock                     # Deterministic dependency lockfile
```

---

## 🔒 Strict Security & Privacy Mandate (Zero PII / Zero Hardware Identifiers)

**NEVER COMMIT CREDENTIALS, REAL MAC ADDRESSES, NETWORK KEYS, DEVICE IDENTIFIERS, OR ANY PII (Personally Identifiable Information).**

1. **No Real Hardware Identifiers or PII:**
   - Never commit actual Bluetooth MAC addresses, device IDs, network addresses, or real device names (e.g. custom home tags).
   - In all unit tests, docstrings, examples, and fixtures, **always use standardized or generic mock placeholders**:
     - Example MAC addresses: `AA:BB:CC:DD:EE:FF` or `00:11:22:33:44:55`.
     - Example device names: `MockDevice` or `Test Light`.
     - Example hex payloads: `aabbccddeeff...`.
2. **No Hardware Scripts with Personal Data:**
   - Never commit personal hardware diagnostic scripts, hardcoded MAC triggers, or local network dumps into the repository.
3. **No Credentials:**
   - Never commit API keys, user passwords, network passwords, email addresses, or tokens.
   - Any local configuration files containing credentials (like `casambi.yaml`, `.env`) are strictly gitignored and must never be tracked or staged.
4. **Mandatory Secret Scanning:**
   - TruffleHog secret scanning is mandatory and enforced locally on every commit via `.githooks/pre-commit` and in CI.

---

## 🐍 Code Style & Home Assistant Pythonista Standards

Write clean, idiomatic, and modern Python (Python `>= 3.12`):

1. **Modern Python Syntax (>= 3.12):**
   - Use built-in generic types (`list[str]`, `dict[str, Any]`, `tuple[int, ...]`) instead of `typing.List` or `typing.Dict`.
   - Use pipe union types (`str | None`, `int | float`) instead of `Optional[...]` or `Union[...]`.
   - Prefer `enum.StrEnum` or `enum.IntEnum` for constants.
   - Use `@dataclass(kw_only=True)` for entity description models.

2. **Full Type Annotations:**
   - Every function, method signature, parameter, and return value must have explicit type annotations.
   - Use precise Home Assistant typing (`HomeAssistant`, `ConfigEntry`, `AddEntitiesCallback`, `FlowResult`).

3. **Home Assistant Logging Standards:**
   - Use `_LOGGER = logging.getLogger(__name__)`.
   - Standard logging calls must use `%s` placeholder formatting (e.g. `_LOGGER.debug("Connecting to %s", self.address)`), **never f-strings** inside logger calls.
   - The underlying BLE driver root logger is `casambi_classic_ble`. In `README.md` and user documentation, specify:
     ```yaml
     logger:
       default: info
       logs:
         casambi_classic_ble: debug
         custom_components.casambi_classic_bt: debug
     ```

4. **Resource Safety & Background Tasks:**
   - Manage Home Assistant background tasks with `config_entry.async_create_background_task(hass, ...)`.
   - Clean up event listeners, periodic timers, and Bluetooth advertisement callbacks when entries unload (`async_unload_entry`).
   - **Never use bare `except:` clauses.** Always catch explicit exception types and **always name exception variables `err`** (`except ... as err:`). Never use `e` or `exc`.

5. **Manifest Rules & Invariants:**
   - Keys in [`custom_components/casambi_classic_bt/manifest.json`](custom_components/casambi_classic_bt/manifest.json) must be sorted in exact alphabetical order: `domain`, `name`, then `bluetooth`, `codeowners`, `config_flow`, `dependencies`, `documentation`, `integration_type`, `iot_class`, `issue_tracker`, `requirements`, `version`.
   - Strict `continue-on-error: false` is enforced on Hassfest and HACS validations.
   - Requirement must point to `casambi-classic-ble` (e.g. `"casambi-classic-ble>=0.3.0"`), **never `casambi-bt`**.

---

## 🛠️ Verification & Development Commands

Always run these before completing any changes or committing:

```bash
# Set up development environment (installs dev dependencies and hooks)
uv sync

# Run Ruff linter and formatter checks
uv run ruff check custom_components/
uv run ruff format --check custom_components/

# Build HACS release zip archive locally
make package
```

Convenience `Makefile` targets:
```bash
make setup      # Sets up virtualenv, installs dependencies and git hooks
make lint       # Runs ruff linter and formatting check
make format     # Formats code and auto-fixes lint issues with ruff
make package    # Packages custom_components/casambi_classic_bt into casambi_classic_bt.zip
make clean      # Cleans test cache, build artifacts, and pycache
```

---

## 🚀 Release Flow (CI/CD to GitHub Releases)

This project uses an automated GitHub Actions workflow configured in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. **Version Change Detection:**
   - On every push to `main`, CI checks the `version` field in `custom_components/casambi_classic_bt/manifest.json` and `pyproject.toml`.
2. **Strict Validations:**
   - `lint`: Ruff formatting and lint rules.
   - `validate-hassfest`: Official Home Assistant Hassfest validation action.
   - `validate-hacs`: HACS action validation with `category: integration` and `ignore: brands`.
   - All validation jobs run with `continue-on-error: false`.
3. **Draft Release & Asset Packaging:**
   - When a version bump is detected and all checks pass, CI tags the commit (`v<version>`), creates a release zip (`casambi_classic_bt.zip`), computes its SHA256 checksum, generates changelog notes, and drafts a GitHub release.
4. **Publish Release:**
   - Review and publish the draft release on GitHub. Downstream automation downloads `casambi_classic_bt.zip` with cryptographic checksum verification.

---

## 🔀 Branching, Pull Requests & Human Approval Mandate

- **Always Use Pull Requests:** All changes (features, fixes, refactoring, dependency bumps, docs) must be developed on a dedicated feature or fix branch and submitted via a Pull Request.
- **Never Push Directly to `main`:** Direct pushes to `main` by automated agents or assistants are strictly forbidden.
- **Only Humans Can Merge to `main`:** Merging pull requests to `main` is strictly reserved for human maintainers. Never use `gh pr merge`, automerge, or scripts to merge a PR to `main`.

---

## 📝 Commit Conventions

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat:` New features, capabilities, or Home Assistant platform support
  - `fix:` Bug fixes or Home Assistant deprecation mitigations
  - `docs:` Documentation improvements or logging guide updates
  - `ci:` GitHub Actions, HACS, or Hassfest workflow modifications
  - `chore:` Dependency bumps, repo maintenance, or configuration

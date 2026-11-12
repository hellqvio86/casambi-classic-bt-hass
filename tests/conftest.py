"""Pytest fixtures and lightweight Home Assistant test stubs for casambi_classic_bt tests."""

import asyncio
import sys
import types
from enum import IntFlag, StrEnum
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure homeassistant mock stubs are injected if real HomeAssistant is not installed in the dev environment.
if "homeassistant" not in sys.modules:
    try:
        import homeassistant  # noqa: F401
    except ImportError:
        ha_mod = types.ModuleType("homeassistant")
        sys.modules["homeassistant"] = ha_mod

        # homeassistant.const
        ha_const = types.ModuleType("homeassistant.const")
        ha_const.CONF_ADDRESS = "address"
        ha_const.CONF_PASSWORD = "password"

        class Platform(StrEnum):
            BINARY_SENSOR = "binary_sensor"
            LIGHT = "light"
            SCENE = "scene"
            NUMBER = "number"

        ha_const.Platform = Platform
        sys.modules["homeassistant.const"] = ha_const

        # homeassistant.core
        ha_core = types.ModuleType("homeassistant.core")

        class HomeAssistant:
            """Stub HomeAssistant."""

            def __init__(self) -> None:
                self.config = MagicMock()
                self.config_entries = MagicMock()
                self.data = {}

        def callback(func: Any) -> Any:
            return func

        ha_core.HomeAssistant = HomeAssistant
        ha_core.callback = callback
        sys.modules["homeassistant.core"] = ha_core

        # homeassistant.data_entry_flow
        ha_flow = types.ModuleType("homeassistant.data_entry_flow")

        class FlowResultType(StrEnum):
            FORM = "form"
            CREATE_ENTRY = "create_entry"
            ABORT = "abort"

        ha_flow.FlowResultType = FlowResultType
        ha_flow.FlowResult = dict[str, Any]
        sys.modules["homeassistant.data_entry_flow"] = ha_flow

        # homeassistant.config_entries
        ha_entries = types.ModuleType("homeassistant.config_entries")

        class ConfigEntry:
            def __init__(self, entry_id: str = "test_entry_id", data: dict[str, Any] | None = None):
                self.entry_id = entry_id
                self.data = data or {}

            def async_create_background_task(
                self, hass: Any, target: Any, name: str | None = None
            ) -> asyncio.Task:
                return asyncio.create_task(target, name=name)

        class ConfigFlow:
            VERSION = 1

            def __init_subclass__(cls, **kwargs: Any) -> None:
                super().__init_subclass__()

            def __init__(self) -> None:
                self.hass: Any = None
                self.context: dict[str, Any] = {}

            async def async_set_unique_id(self, unique_id: str) -> Any:
                return None

            def _abort_if_unique_id_configured(self) -> None:
                pass

            def async_show_form(
                self,
                *,
                step_id: str,
                data_schema: Any = None,
                errors: dict[str, str] | None = None,
            ) -> dict[str, Any]:
                return {
                    "type": FlowResultType.FORM,
                    "step_id": step_id,
                    "data_schema": data_schema,
                    "errors": errors or {},
                }

            async def _async_create_casa_entry(
                self, title: str, id: str, data: dict[str, Any]
            ) -> dict[str, Any]:
                return self.async_create_entry(title=title, data=data)

            def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
                return {
                    "type": FlowResultType.CREATE_ENTRY,
                    "title": title,
                    "data": data,
                }

            def async_abort(self, *, reason: str) -> dict[str, Any]:
                return {
                    "type": FlowResultType.ABORT,
                    "reason": reason,
                }

            def add_suggested_values_to_schema(self, schema: Any, suggested_values: Any) -> Any:
                return schema

        ha_entries.ConfigEntry = ConfigEntry
        ha_entries.ConfigFlow = ConfigFlow
        sys.modules["homeassistant.config_entries"] = ha_entries

        # homeassistant.components
        sys.modules["homeassistant.components"] = types.ModuleType("homeassistant.components")

        # homeassistant.components.bluetooth
        ha_bt = types.ModuleType("homeassistant.components.bluetooth")
        ha_bt.async_ble_device_from_address = MagicMock()
        ha_bt.async_scanner_count = MagicMock(return_value=1)
        ha_bt.async_register_callback = MagicMock()
        ha_bt.BluetoothScanningMode = MagicMock()
        ha_bt.BluetoothChange = MagicMock()
        ha_bt.BluetoothServiceInfoBleak = MagicMock
        sys.modules["homeassistant.components.bluetooth"] = ha_bt

        # homeassistant.components.bluetooth.models
        ha_bt_models = types.ModuleType("homeassistant.components.bluetooth.models")

        class BluetoothServiceInfoBleak:
            def __init__(self, **kwargs: Any) -> None:
                for k, v in kwargs.items():
                    setattr(self, k, v)

        ha_bt_models.BluetoothServiceInfoBleak = BluetoothServiceInfoBleak
        sys.modules["homeassistant.components.bluetooth.models"] = ha_bt_models

        # homeassistant.helpers
        sys.modules["homeassistant.helpers"] = types.ModuleType("homeassistant.helpers")

        # homeassistant.helpers.config_validation
        ha_cv = types.ModuleType("homeassistant.helpers.config_validation")
        ha_cv.string = str
        ha_cv.boolean = bool
        sys.modules["homeassistant.helpers.config_validation"] = ha_cv

        # homeassistant.helpers.device_registry
        ha_dr = types.ModuleType("homeassistant.helpers.device_registry")

        def format_mac(mac: str) -> str:
            cleaned = mac.replace("-", ":").upper()
            return cleaned

        ha_dr.format_mac = format_mac
        ha_dr.DeviceEntry = MagicMock
        ha_dr.CONNECTION_BLUETOOTH = "bluetooth"
        ha_dr.async_get_device_id_by_identifier = MagicMock(return_value="dev-1")
        sys.modules["homeassistant.helpers.device_registry"] = ha_dr

        # homeassistant.helpers.httpx_client
        ha_httpx = types.ModuleType("homeassistant.helpers.httpx_client")
        ha_httpx.get_async_client = MagicMock()
        sys.modules["homeassistant.helpers.httpx_client"] = ha_httpx

        # homeassistant.helpers.event
        ha_event = types.ModuleType("homeassistant.helpers.event")
        ha_event.async_track_time_interval = MagicMock()
        sys.modules["homeassistant.helpers.event"] = ha_event

        # homeassistant.helpers.entity
        ha_entity = types.ModuleType("homeassistant.helpers.entity")

        class Entity:
            def __init__(self) -> None:
                self.hass: Any = None
                self.entity_id: str = ""

            def async_write_ha_state(self) -> None:
                pass

            def schedule_update_ha_state(self, force_refresh: bool = False) -> None:
                pass

        from dataclasses import dataclass

        class EntityCategory(StrEnum):
            DIAGNOSTIC = "diagnostic"
            CONFIG = "config"

        @dataclass(kw_only=True)
        class EntityDescription:
            key: str = ""
            name: str | None = None
            device_class: Any = None
            entity_category: Any = None

        class DeviceInfo(dict):
            pass

        ha_entity.Entity = Entity
        ha_entity.EntityCategory = EntityCategory
        ha_entity.EntityDescription = EntityDescription
        ha_entity.DeviceInfo = DeviceInfo
        sys.modules["homeassistant.helpers.entity"] = ha_entity

        # homeassistant.components.binary_sensor
        ha_bs = types.ModuleType("homeassistant.components.binary_sensor")

        class BinarySensorDeviceClass(StrEnum):
            CONNECTIVITY = "connectivity"

        @dataclass(kw_only=True)
        class BinarySensorEntityDescription(EntityDescription):
            pass

        class BinarySensorEntity(Entity):
            pass

        ha_bs.BinarySensorDeviceClass = BinarySensorDeviceClass
        ha_bs.BinarySensorEntityDescription = BinarySensorEntityDescription
        ha_bs.BinarySensorEntity = BinarySensorEntity
        sys.modules["homeassistant.components.binary_sensor"] = ha_bs

        # homeassistant.components.number
        ha_num = types.ModuleType("homeassistant.components.number")

        class NumberDeviceClass(StrEnum):
            ILLUMINANCE = "illuminance"

        @dataclass(kw_only=True)
        class NumberEntityDescription(EntityDescription):
            pass

        class NumberEntity(Entity):
            pass

        ha_num.NumberDeviceClass = NumberDeviceClass
        ha_num.NumberEntityDescription = NumberEntityDescription
        ha_num.NumberEntity = NumberEntity
        sys.modules["homeassistant.components.number"] = ha_num

        # homeassistant.components.scene
        ha_scene = types.ModuleType("homeassistant.components.scene")

        class Scene(Entity):
            @property
            def name(self) -> str | None:
                return getattr(self.entity_description, "name", None)

        ha_scene.Scene = Scene
        sys.modules["homeassistant.components.scene"] = ha_scene

        # homeassistant.helpers.entity_platform
        ha_platform = types.ModuleType("homeassistant.helpers.entity_platform")
        ha_platform.AddEntitiesCallback = Any
        sys.modules["homeassistant.helpers.entity_platform"] = ha_platform

        # homeassistant.components.light
        ha_light = types.ModuleType("homeassistant.components.light")
        ha_light.ATTR_BRIGHTNESS = "brightness"
        ha_light.ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
        ha_light.ATTR_RGB_COLOR = "rgb_color"
        ha_light.ATTR_RGBW_COLOR = "rgbw_color"
        ha_light.ATTR_XY_COLOR = "xy_color"

        class ColorMode(StrEnum):
            UNKNOWN = "unknown"
            ONOFF = "onoff"
            BRIGHTNESS = "brightness"
            COLOR_TEMP = "color_temp"
            RGB = "rgb"
            RGBW = "rgbw"
            XY = "xy"

        class LightEntityFeature(IntFlag):
            EFFECT = 1

        class LightEntity(Entity):
            @property
            def supported_color_modes(self) -> set[ColorMode] | None:
                return getattr(self, "_attr_supported_color_modes", None)

            @property
            def color_mode(self) -> ColorMode | None:
                return getattr(self, "_attr_color_mode", None)

            @property
            def brightness(self) -> int | None:
                return getattr(self, "_attr_brightness", None)

            @property
            def is_on(self) -> bool | None:
                return getattr(self, "_attr_is_on", None)

        ha_light.ColorMode = ColorMode
        ha_light.LightEntityFeature = LightEntityFeature
        ha_light.LightEntity = LightEntity
        sys.modules["homeassistant.components.light"] = ha_light

        # homeassistant.exceptions
        ha_exc = types.ModuleType("homeassistant.exceptions")
        ha_exc.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
        ha_exc.ConfigEntryError = type("ConfigEntryError", (Exception,), {})
        ha_exc.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})
        sys.modules["homeassistant.exceptions"] = ha_exc

from bleak.backends.device import BLEDevice  # noqa: E402
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402

from custom_components.casambi_classic_bt.const import CONF_IMPORT_GROUPS  # noqa: E402

MOCK_MAC = "AA:BB:CC:DD:EE:FF"
MOCK_PASSWORD = "test-password"


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Return a mock BLEDevice with standardized placeholder address."""
    device = MagicMock(spec=BLEDevice)
    device.address = MOCK_MAC
    device.name = "Casambi Light"
    device.rssi = -60
    return device


@pytest.fixture
def mock_hass(tmp_path: Path) -> HomeAssistant:
    """Return a mocked HomeAssistant instance."""
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    hass.data = {}
    hass.is_stopping = False

    async def _async_add_executor_job(target: Any, *args: Any, **kwargs: Any) -> Any:
        return target(*args, **kwargs)

    hass.async_add_executor_job = AsyncMock(side_effect=_async_add_executor_job)
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.config_entries.async_get_entry = MagicMock()
    hass.config_entries.async_update_entry = MagicMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.async_create_task = MagicMock(side_effect=lambda task: task)

    return hass


@pytest.fixture
def valid_user_input() -> dict[str, str | bool]:
    """Return valid user input payload for config flow."""
    return {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_IMPORT_GROUPS: True,
    }

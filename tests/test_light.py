"""Unit tests for Casambi light entities, state consolidation, and availability separation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from casambi_classic_ble import (
    Group,
    Unit,
    UnitControl,
    UnitControlType,
    UnitState,
    UnitType,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
)

from custom_components.casambi_classic_bt.light import CasambiLightGroup, CasambiLightUnit


def _make_unit(
    *,
    device_id: int = 1,
    online: bool = True,
    dimmer: int | None = 128,
    rgb: tuple[int, int, int] | None = (255, 100, 50),
    white: int | None = 64,
    temperature: int | None = 3000,
    controls: list[UnitControlType] | None = None,
) -> Unit:
    ctrl_types = (
        controls
        if controls is not None
        else [
            UnitControlType.DIMMER,
            UnitControlType.RGB,
            UnitControlType.WHITE,
            UnitControlType.TEMPERATURE,
        ]
    )
    unit_controls = [
        UnitControl(
            type=ct,
            offset=idx * 8,
            length=8,
            default=0,
            readonly=False,
            min=2200 if ct == UnitControlType.TEMPERATURE else 0,
            max=6000 if ct == UnitControlType.TEMPERATURE else 255,
        )
        for idx, ct in enumerate(ctrl_types)
    ]
    ut = UnitType(
        id=10,
        model="CBU-PWM4",
        manufacturer="Casambi",
        mode="RGBW",
        stateLength=8,
        controls=unit_controls,
    )
    st = UnitState()
    st.dimmer = dimmer
    st.rgb = rgb
    st.white = white
    st.temperature = temperature
    return Unit(
        _typeId=10,
        deviceId=device_id,
        uuid=f"unit-uuid-{device_id}",
        address="AA:BB:CC:DD:EE:FF",
        name=f"Light {device_id}",
        firmwareVersion="26.2",
        unitType=ut,
        _state=st,
        _online=online,
        _on=bool(dimmer and dimmer > 0),
    )


def test_light_unit_available_vs_off_state_separation() -> None:
    """Verify unavailable unit never reports is_on=False or brightness=0."""
    api = MagicMock()
    api.available = True
    api.casa.network_id = "net-1"
    api.casa.network_name = "Test Mesh"

    # Case 1: Online and turned off (dimmer = 0)
    unit_off = _make_unit(device_id=1, online=True, dimmer=0)
    entity_off = CasambiLightUnit(api, unit_off)
    assert entity_off.available is True
    assert entity_off.is_on is False
    assert entity_off.brightness == 0

    # Case 2: Unit goes offline -> available is False, is_on is None, brightness is None
    unit_off._online = False
    assert entity_off.available is False
    assert entity_off.is_on is None
    assert entity_off.brightness is None

    # Case 3: Unit is online, but controller/BLE session is disconnected -> unavailable
    unit_on = _make_unit(device_id=2, online=True, dimmer=200)
    entity_on = CasambiLightUnit(api, unit_on)
    assert entity_on.available is True
    assert entity_on.is_on is True
    assert entity_on.brightness == 200

    api.available = False
    assert entity_on.available is False
    assert entity_on.is_on is None
    assert entity_on.brightness is None


@pytest.mark.asyncio
async def test_light_unit_turn_on_and_off_and_updates() -> None:
    """Verify CasambiLightUnit controls and single-dispatch state updates."""
    api = MagicMock()
    api.available = True
    api.casa.network_id = "net-1"
    api.casa.network_name = "Test Mesh"
    api.casa.set_unit_state = AsyncMock()
    api.casa.turn_on = AsyncMock()
    api.casa.turn_off = AsyncMock()

    unit = _make_unit(device_id=1, online=True, dimmer=100)
    entity = CasambiLightUnit(api, unit)
    entity.schedule_update_ha_state = MagicMock()

    assert ColorMode.RGBW in entity.supported_color_modes
    assert ColorMode.COLOR_TEMP in entity.supported_color_modes
    assert entity.rgb_color == (255, 100, 50)
    assert entity.rgbw_color == (255, 100, 50, 64)
    assert entity.color_temp_kelvin == 3000

    await entity.async_turn_on()
    api.casa.turn_on.assert_awaited_once_with(target=unit)

    await entity.async_turn_on(
        **{
            ATTR_BRIGHTNESS: 180,
            ATTR_RGBW_COLOR: (10, 20, 30, 40),
            ATTR_COLOR_TEMP_KELVIN: 4000,
        }
    )
    api.casa.set_unit_state.assert_awaited_once()

    await entity.async_turn_off()
    api.casa.turn_off.assert_awaited_once_with(target=unit)

    # State callback updates entity and schedules HA state update once
    updated_unit = _make_unit(device_id=1, online=True, dimmer=250)
    entity._change_callback(updated_unit)
    assert entity.brightness == 250
    entity.schedule_update_ha_state.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_light_group_availability_and_controls() -> None:
    """Verify CasambiLightGroup availability, state aggregation, and group commands."""
    api = MagicMock()
    api.available = True
    api.casa.network_id = "net-1"
    api.casa.network_name = "Test Mesh"
    api.casa.set_level = AsyncMock()
    api.casa.set_temperature = AsyncMock()
    api.casa.set_color = AsyncMock()
    api.casa.set_white = AsyncMock()
    api.casa.turn_on = AsyncMock()
    api.casa.turn_off = AsyncMock()

    u1 = _make_unit(device_id=1, online=False, dimmer=200)
    u2 = _make_unit(device_id=2, online=True, dimmer=0)
    group = Group(group_id=5, name="Living Room", units=[u1, u2])

    group_entity = CasambiLightGroup(api, group)
    group_entity.schedule_update_ha_state = MagicMock()

    # u1 is offline (even though its last dimmer was 200), u2 is online with dimmer=0
    assert group_entity.available is True
    assert group_entity.is_on is False
    assert group_entity.brightness == 0

    # Both units offline -> group is unavailable, is_on is None, brightness is None
    u2._online = False
    assert group_entity.available is False
    assert group_entity.is_on is None
    assert group_entity.brightness is None

    # Bring u2 back online with brightness 150
    u2._online = True
    u2._on = True
    assert u2.state is not None
    u2.state.dimmer = 150
    assert group_entity.available is True
    assert group_entity.is_on is True
    assert group_entity.brightness == 150

    await group_entity.async_turn_on(**{ATTR_BRIGHTNESS: 220, ATTR_RGB_COLOR: (1, 2, 3)})
    api.casa.set_level.assert_awaited_once_with(target=group, level=220)
    api.casa.set_color.assert_awaited_once_with(target=group, rgb_color=(1, 2, 3))

    await group_entity.async_turn_on(
        **{ATTR_RGBW_COLOR: (10, 20, 30, 40), ATTR_COLOR_TEMP_KELVIN: 3500}
    )
    api.casa.set_white.assert_awaited_once_with(target=group, level=40)
    api.casa.set_temperature.assert_awaited_once_with(target=group, temperature=3500)

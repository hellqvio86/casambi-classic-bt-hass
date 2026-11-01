"""Unit tests for Casambi light entities and control methods."""

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
)

from custom_components.casambi_classic_bt import CasambiApi
from custom_components.casambi_classic_bt.light import (
    CasambiLightGroup,
    CasambiLightUnit,
)


@pytest.fixture
def dummy_unit() -> Unit:
    """Return a mock Unit with DIMMER, RGB, and TEMPERATURE controls."""
    ctrl_dimmer = UnitControl(
        type=UnitControlType.DIMMER,
        offset=0,
        length=8,
        default=0,
        readonly=False,
    )
    ctrl_rgb = UnitControl(
        type=UnitControlType.RGB,
        offset=8,
        length=24,
        default=0,
        readonly=False,
    )
    ctrl_temp = UnitControl(
        type=UnitControlType.TEMPERATURE,
        offset=32,
        length=16,
        default=2700,
        readonly=False,
        min=2200,
        max=6500,
    )
    ut = UnitType(
        id=1,
        model="TestModel",
        manufacturer="Casambi",
        mode="DIM",
        stateLength=6,
        controls=[ctrl_dimmer, ctrl_rgb, ctrl_temp],
    )
    unit = Unit(
        _typeId=1,
        deviceId=1,
        uuid="unit-uuid-1",
        address="AA:BB:CC:DD:EE:01",
        name="Living Room Light",
        firmwareVersion="1.0",
        unitType=ut,
    )
    return unit


@pytest.fixture
def mock_api() -> MagicMock:
    """Return a mocked CasambiApi with async casa methods."""
    api = MagicMock(spec=CasambiApi)
    api.available = True
    api.network_id = "test-net-id"

    casa = MagicMock()
    casa.set_unit_state = AsyncMock()
    casa.turn_on = AsyncMock()
    casa.turn_off = AsyncMock()
    casa.set_level = AsyncMock()
    casa.set_color = AsyncMock()
    casa.set_white = AsyncMock()
    casa.set_temperature = AsyncMock()

    api.casa = casa
    return api


@pytest.mark.asyncio
async def test_unit_turn_on_with_brightness_calls_set_unit_state(
    mock_api: MagicMock, dummy_unit: Unit
) -> None:
    """Verify dimming a unit calls set_unit_state(target=unit, state=state) without TypeError."""
    light = CasambiLightUnit(api=mock_api, unit=dummy_unit)

    # Dim to 128
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 128})

    mock_api.casa.set_unit_state.assert_awaited_once()
    call_kwargs = mock_api.casa.set_unit_state.call_args.kwargs
    assert call_kwargs["target"] == dummy_unit
    assert isinstance(call_kwargs["state"], UnitState)
    assert call_kwargs["state"].dimmer == 128


@pytest.mark.asyncio
async def test_unit_turn_on_without_kwargs_calls_turn_on(
    mock_api: MagicMock, dummy_unit: Unit
) -> None:
    """Verify turning on without attributes calls turn_on(target=unit)."""
    light = CasambiLightUnit(api=mock_api, unit=dummy_unit)

    await light.async_turn_on()

    mock_api.casa.turn_on.assert_awaited_once_with(target=dummy_unit)
    mock_api.casa.set_unit_state.assert_not_called()


@pytest.mark.asyncio
async def test_unit_turn_off_calls_turn_off(mock_api: MagicMock, dummy_unit: Unit) -> None:
    """Verify turning off calls turn_off(target=unit)."""
    light = CasambiLightUnit(api=mock_api, unit=dummy_unit)

    await light.async_turn_off()

    mock_api.casa.turn_off.assert_awaited_once_with(target=dummy_unit)


@pytest.mark.asyncio
async def test_group_turn_on_with_brightness_and_colors(
    mock_api: MagicMock, dummy_unit: Unit
) -> None:
    """Verify group dimming and color control calls match expected keyword arguments."""
    group = Group(group_id=1, name="Living Room Group", units=[dummy_unit])
    light_group = CasambiLightGroup(api=mock_api, group=group)

    # 1. Dimming
    await light_group.async_turn_on(**{ATTR_BRIGHTNESS: 200})
    mock_api.casa.set_level.assert_awaited_with(target=group, level=200)

    # 2. Color temp
    await light_group.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 3500})
    mock_api.casa.set_temperature.assert_awaited_with(target=group, temperature=3500)

    # 3. RGB color
    await light_group.async_turn_on(**{ATTR_RGB_COLOR: (255, 100, 50)})
    mock_api.casa.set_color.assert_awaited_with(target=group, rgb_color=(255, 100, 50))

    # 4. RGBW color
    await light_group.async_turn_on(**{ATTR_RGBW_COLOR: (255, 100, 50, 150)})
    mock_api.casa.set_color.assert_awaited_with(target=group, rgb_color=(255, 100, 50))
    mock_api.casa.set_white.assert_awaited_with(target=group, level=150)

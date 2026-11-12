"""Unit tests for binary_sensor, number, scene, light setup, and entity base classes."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from casambi_classic_ble import (
    Group,
    Scene,
    Unit,
    UnitControl,
    UnitControlType,
    UnitState,
    UnitType,
)

from custom_components.casambi_classic_bt.binary_sensor import (
    NETWORK_SENSORS,
    CasambiBinarySensorEntity,
)
from custom_components.casambi_classic_bt.binary_sensor import (
    async_setup_entry as setup_binary_sensor,
)
from custom_components.casambi_classic_bt.binary_sensor import (
    async_unload_entry as unload_binary_sensor,
)
from custom_components.casambi_classic_bt.const import CONF_IMPORT_GROUPS, DOMAIN
from custom_components.casambi_classic_bt.light import async_setup_entry as setup_light
from custom_components.casambi_classic_bt.number import (
    CasambiVerticalNumberGroup,
    CasambiVerticalNumberUnit,
)
from custom_components.casambi_classic_bt.number import (
    async_setup_entry as setup_number,
)
from custom_components.casambi_classic_bt.scene import (
    CasambiScene,
)
from custom_components.casambi_classic_bt.scene import (
    async_setup_entry as setup_scene,
)


def _make_unit(
    *,
    device_id: int = 1,
    online: bool = True,
    vertical: int | None = 128,
    controls: list[UnitControlType] | None = None,
) -> Unit:
    ctrl_types = (
        controls
        if controls is not None
        else [
            UnitControlType.DIMMER,
            UnitControlType.VERTICAL,
            UnitControlType.ONOFF,
        ]
    )
    unit_controls = [
        UnitControl(
            type=ct,
            offset=idx * 8,
            length=8,
            default=0,
            readonly=False,
            min=0,
            max=255,
        )
        for idx, ct in enumerate(ctrl_types)
    ]
    ut = UnitType(
        id=10,
        model="CBU-TED",
        manufacturer="Casambi",
        mode="Vertical",
        stateLength=8,
        controls=unit_controls,
    )
    st = UnitState()
    st.dimmer = 100
    st.vertical = vertical
    return Unit(
        _typeId=10,
        deviceId=device_id,
        uuid=f"unit-uuid-{device_id}",
        address="AA:BB:CC:DD:EE:FF",
        name=f"Unit {device_id}",
        firmwareVersion="26.2",
        unitType=ut,
        _state=st,
        _online=online,
        _on=True,
    )


@pytest.mark.asyncio
async def test_binary_sensor_platform() -> None:
    """Test binary_sensor setup, unload, and entity properties."""
    api = MagicMock()
    api.available = True
    api.address = "AA:BB:CC:DD:EE:FF"
    api.casa.network_id = "net-1"
    api.casa.network_name = "Home Mesh"

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    hass.data = {DOMAIN: {"entry-1": api}}

    added: list[CasambiBinarySensorEntity] = []
    await setup_binary_sensor(hass, entry, added.extend)
    assert len(added) == len(NETWORK_SENSORS)

    sensor = added[0]
    assert sensor.is_on is True
    assert sensor.available is True
    assert sensor.unique_id == "net-1-status"
    assert sensor.device_info["name"] == "Home Mesh"

    api.available = False
    assert sensor.is_on is False
    assert sensor.available is True

    assert await unload_binary_sensor(hass, entry) is True


@pytest.mark.asyncio
async def test_scene_platform() -> None:
    """Test scene setup and activation."""
    api = MagicMock()
    api.available = True
    api.address = "AA:BB:CC:DD:EE:FF"
    api.casa.network_id = "net-1"
    api.casa.network_name = "Home Mesh"
    api.casa.switch_to_scene = AsyncMock()

    s1 = Scene(name="Evening", scene_id=3)
    api.get_scenes.return_value = [s1]

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    hass.data = {DOMAIN: {"entry-1": api}}

    added: list[CasambiScene] = []
    await setup_scene(hass, entry, added.extend)
    assert len(added) == 1

    scene_entity = added[0]
    assert scene_entity.unique_id == "net-1-scene-3"
    await scene_entity.async_activate(brightness=120)
    api.casa.switch_to_scene.assert_awaited_once_with(target=s1, level=120)


@pytest.mark.asyncio
async def test_number_platform_unit_and_group() -> None:
    """Test vertical number entities for both unit and group."""
    api = MagicMock()
    api.available = True
    api.address = "AA:BB:CC:DD:EE:FF"
    api.casa.network_id = "net-1"
    api.casa.network_name = "Home Mesh"
    api.casa.set_vertical = AsyncMock()
    api.conf_entry.entry_id = "entry-1"

    u1 = _make_unit(device_id=1, vertical=80)
    u2 = _make_unit(device_id=2, vertical=160)
    group = Group(group_id=10, name="Blinds", units=[u1, u2])

    api.get_units.return_value = [u1, u2]
    api.get_groups.return_value = [group]

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.data = {CONF_IMPORT_GROUPS: True}
    hass.data = {DOMAIN: {"entry-1": api}}

    added: list[CasambiVerticalNumberUnit | CasambiVerticalNumberGroup] = []
    await setup_number(hass, entry, added.extend)
    assert len(added) == 3

    unit_entity = added[0]
    assert isinstance(unit_entity, CasambiVerticalNumberUnit)
    assert unit_entity.native_value == 80.0
    assert unit_entity.unique_id == "net-1-unit-unit-uuid-1-vertical"
    await unit_entity.async_set_native_value(200.0)
    api.casa.set_vertical.assert_awaited_once_with(target=u1, vertical=200)

    # Test None state on unit
    u1._state = None
    assert unit_entity.native_value is None
    u1._state = UnitState()
    u1._state.vertical = 80

    group_entity = added[2]
    assert isinstance(group_entity, CasambiVerticalNumberGroup)
    assert group_entity.native_value == 120.0
    assert group_entity.unique_id == "net-1-group-10"

    # Lifecycle hooks on unit and group
    await unit_entity.async_added_to_hass()
    api.register_unit_updates.assert_called_with(u1, unit_entity._change_callback)
    await unit_entity.async_will_remove_from_hass()
    api.unregister_unit_updates.assert_called_with(u1, unit_entity._change_callback)

    await group_entity.async_added_to_hass()
    await group_entity.async_will_remove_from_hass()

    # Callback with no state on unit and group
    unit_entity.schedule_update_ha_state = MagicMock()
    u1_no_state = _make_unit(device_id=1, online=False)
    u1_no_state._state = None
    unit_entity._change_callback(u1_no_state)

    group_entity.schedule_update_ha_state = MagicMock()
    group_entity._change_callback(u1_no_state)
    u1_with_state = _make_unit(device_id=1, online=True, vertical=50)
    group_entity._change_callback(u1_with_state)


@pytest.mark.asyncio
async def test_light_setup_entry() -> None:
    """Test light async_setup_entry with groups enabled."""
    api = MagicMock()
    api.available = True
    api.casa.network_id = "net-1"
    api.casa.network_name = "Home Mesh"

    u1 = _make_unit(device_id=1, controls=[UnitControlType.ONOFF])
    group = Group(group_id=2, name="Hallway", units=[u1])
    api.get_units.return_value = [u1]
    api.get_groups.return_value = [group]

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.data = {CONF_IMPORT_GROUPS: True}
    hass.data = {DOMAIN: {"entry-1": api}}

    added = []
    await setup_light(hass, entry, added.extend)
    assert len(added) == 2

    # Group turn off
    api.casa.turn_off = AsyncMock()
    api.casa.turn_on = AsyncMock()
    grp_light = added[1]
    await grp_light.async_turn_on()
    api.casa.turn_on.assert_awaited_once_with(target=group)
    await grp_light.async_turn_off()
    api.casa.turn_off.assert_awaited_once_with(target=group)

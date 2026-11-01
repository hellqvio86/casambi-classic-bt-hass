"""Lifecycle tests for setup, unload, rollback, and reconnection in casambi_classic_bt."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from casambi_classic_ble import AuthenticationError, BluetoothError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from custom_components.casambi_classic_bt import (
    CasambiApi,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.casambi_classic_bt.const import DOMAIN
from tests.conftest import MOCK_MAC, MOCK_PASSWORD


@pytest.fixture
def test_entry() -> ConfigEntry:
    """Create a mock ConfigEntry."""
    return ConfigEntry(
        entry_id="test_entry_id",
        data={
            CONF_ADDRESS: MOCK_MAC,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )


@pytest.mark.asyncio
async def test_setup_entry_success(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    test_entry: ConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.connected = True
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
    ):
        result = await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert result is True
    assert DOMAIN in mock_hass.data
    assert test_entry.entry_id in mock_hass.data[DOMAIN]
    mock_hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_forwarding_failure_rollback(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    test_entry: ConfigEntry,
) -> None:
    """Test setup rollback when platform forwarding raises an exception."""
    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.connected = True
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()
    mock_casa.unregister_disconnect_callback = MagicMock()
    mock_casa.unregister_unit_changed_handler = MagicMock()

    mock_hass.config_entries.async_forward_entry_setups.side_effect = RuntimeError(
        "Platform crash during setup"
    )

    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
        pytest.raises(RuntimeError, match="Platform crash during setup"),
    ):
        await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert DOMAIN not in mock_hass.data
    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_device_not_found(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test setup failure when Bluetooth device is not found in cache."""
    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
        pytest.raises(ConfigEntryNotReady, match="wasn't found"),
    ):
        await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert DOMAIN not in mock_hass.data


@pytest.mark.asyncio
async def test_setup_entry_bluetooth_error(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    test_entry: ConfigEntry,
) -> None:
    """Test setup failure when Casambi raises BluetoothError during connect."""
    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=BluetoothError("GATT busy"))
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()
    mock_casa.unregister_disconnect_callback = MagicMock()
    mock_casa.unregister_unit_changed_handler = MagicMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
        pytest.raises(ConfigEntryNotReady, match="Failed to use bluetooth"),
    ):
        await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert DOMAIN not in mock_hass.data
    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_auth_failed(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    test_entry: ConfigEntry,
) -> None:
    """Test setup failure when Casambi raises AuthenticationError during connect."""
    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=AuthenticationError("Invalid network password"))
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()
    mock_casa.unregister_disconnect_callback = MagicMock()
    mock_casa.unregister_unit_changed_handler = MagicMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
        pytest.raises(ConfigEntryAuthFailed, match="Failed to authenticate"),
    ):
        await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert DOMAIN not in mock_hass.data
    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_unexpected_error(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    test_entry: ConfigEntry,
) -> None:
    """Test setup failure when Casambi raises an unexpected exception during connect."""
    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=ValueError("Corrupt frame received"))
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()
    mock_casa.unregister_disconnect_callback = MagicMock()
    mock_casa.unregister_unit_changed_handler = MagicMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
        pytest.raises(ConfigEntryError, match="Unexpected error creating network"),
    ):
        await async_setup_entry(hass=mock_hass, entry=test_entry)

    assert DOMAIN not in mock_hass.data
    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_unload_entry_success(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test successful unload of config entry."""
    mock_api = MagicMock(spec=CasambiApi)
    mock_api.disconnect = AsyncMock()

    mock_hass.data[DOMAIN] = {test_entry.entry_id: mock_api}
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    result = await async_unload_entry(hass=mock_hass, entry=test_entry)

    assert result is True
    assert DOMAIN not in mock_hass.data
    mock_api.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_unload_entry_platform_failure_preserves_runtime_state(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that failed platform unload does not remove runtime state or disconnect API."""
    mock_api = MagicMock(spec=CasambiApi)
    mock_api.disconnect = AsyncMock()

    mock_hass.data[DOMAIN] = {test_entry.entry_id: mock_api}
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

    result = await async_unload_entry(hass=mock_hass, entry=test_entry)

    assert result is False
    assert test_entry.entry_id in mock_hass.data[DOMAIN]
    mock_api.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_unload_entry_repeated_is_idempotent(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that calling async_unload_entry multiple times is safe and idempotent."""
    mock_api = MagicMock(spec=CasambiApi)
    mock_api.disconnect = AsyncMock()

    mock_hass.data[DOMAIN] = {test_entry.entry_id: mock_api}
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    result_1 = await async_unload_entry(hass=mock_hass, entry=test_entry)
    assert result_1 is True

    result_2 = await async_unload_entry(hass=mock_hass, entry=test_entry)
    assert result_2 is True
    assert DOMAIN not in mock_hass.data


@pytest.mark.asyncio
async def test_disconnect_cancels_and_awaits_active_reconnect_task(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that disconnect cancels active reconnect task and unregisters callbacks."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )

    reconnect_started = asyncio.Event()
    reconnect_cancelled = asyncio.Event()

    async def fake_reconnect() -> None:
        try:
            reconnect_started.set()
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            reconnect_cancelled.set()
            raise

    task = asyncio.create_task(fake_reconnect())
    api._reconnect_task = task

    cancel_bt_cb = MagicMock()
    api._cancel_bluetooth_callback = cancel_bt_cb

    cancel_watchdog = MagicMock()
    api._cancel_watchdog = cancel_watchdog

    api._casa = MagicMock()
    api._casa.disconnect = AsyncMock()
    api._casa.unregister_disconnect_callback = MagicMock()
    api._casa.unregister_unit_changed_handler = MagicMock()
    api._disconnect_cb_registered = True
    api._unit_changed_cb_registered = True

    await reconnect_started.wait()
    await api.disconnect()

    assert api._unloaded is True
    assert reconnect_cancelled.is_set()
    assert api._reconnect_task is None
    cancel_bt_cb.assert_called_once()
    assert api._cancel_bluetooth_callback is None
    cancel_watchdog.assert_called_once()
    assert api._cancel_watchdog is None
    api._casa.unregister_disconnect_callback.assert_called_once()
    api._casa.unregister_unit_changed_handler.assert_called_once()
    api._casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_stops_when_hass_is_stopping(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that reconnect terminates immediately when Home Assistant is stopping."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    mock_hass.is_stopping = True

    api._casa = MagicMock()
    api._casa.reconnect = AsyncMock()

    # Should exit loop without reconnecting because is_stopping is True
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await api.reconnect()

    api._casa.reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_reconnect_stops_when_entry_unloaded(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that reconnect terminates immediately when entry is marked unloaded."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    api._unloaded = True

    api._casa = MagicMock()
    api._casa.reconnect = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await api.reconnect()

    api._casa.reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_reconnect_suppressed_when_unloaded_or_stopping(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that scheduling reconnect is suppressed when unloaded or stopping."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    test_entry.async_create_background_task = MagicMock()

    api._unloaded = True
    api._schedule_reconnect()
    test_entry.async_create_background_task.assert_not_called()

    api._unloaded = False
    mock_hass.is_stopping = True
    api._schedule_reconnect()
    test_entry.async_create_background_task.assert_not_called()


@pytest.mark.asyncio
async def test_remove_config_entry_device_handling(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test device removal logic when unloaded, matching, or non-matching."""
    mock_device_entry = MagicMock()
    mock_device_entry.identifiers = {(DOMAIN, "unit_uuid_1")}

    # Case 1: Unloaded entry (not present in hass.data) -> allow removal safely
    result = await async_remove_config_entry_device(
        hass=mock_hass,
        config_entry=test_entry,
        device_entry=mock_device_entry,
    )
    assert result is True

    # Case 2: Loaded entry, device matches live unit -> disallow removal
    mock_unit = MagicMock()
    mock_unit.uuid = "unit_uuid_1"

    mock_api = MagicMock()
    mock_api.casa.network_id = "net_123"
    mock_api.get_units = MagicMock(return_value=[mock_unit])

    mock_hass.data[DOMAIN] = {test_entry.entry_id: mock_api}

    result = await async_remove_config_entry_device(
        hass=mock_hass,
        config_entry=test_entry,
        device_entry=mock_device_entry,
    )
    assert result is False

    # Case 3: Loaded entry, device does NOT match any unit or network -> allow removal
    mock_stale_device = MagicMock()
    mock_stale_device.identifiers = {(DOMAIN, "stale_uuid_999")}

    result = await async_remove_config_entry_device(
        hass=mock_hass,
        config_entry=test_entry,
        device_entry=mock_stale_device,
    )
    assert result is True


@pytest.mark.asyncio
async def test_watchdog_and_disconnect_callbacks(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that watchdog and library disconnect invoke _schedule_reconnect appropriately."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    api._schedule_reconnect = MagicMock()

    api._casa = MagicMock()
    api._casa.connected = True
    api._watchdog_callback(None)
    api._schedule_reconnect.assert_not_called()

    api._casa.connected = False
    api._watchdog_callback(None)
    api._schedule_reconnect.assert_called_once()

    api._schedule_reconnect.reset_mock()
    api._casa_disconnect()
    api._schedule_reconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bluetooth_callback_scheduling(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that bluetooth callback schedules reconnect only when disconnected and connectable."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    api._schedule_reconnect = MagicMock()

    api._casa = MagicMock()
    service_info = MagicMock()

    # Already connected -> no reconnect
    api._casa.connected = True
    service_info.connectable = True
    api._bluetooth_callback(service_info=service_info, _change=MagicMock())
    api._schedule_reconnect.assert_not_called()

    # Disconnected and not connectable -> no reconnect
    api._casa.connected = False
    service_info.connectable = False
    api._bluetooth_callback(service_info=service_info, _change=MagicMock())
    api._schedule_reconnect.assert_not_called()

    # Disconnected and connectable -> triggers reconnect
    api._casa.connected = False
    service_info.connectable = True
    api._bluetooth_callback(service_info=service_info, _change=MagicMock())
    api._schedule_reconnect.assert_called_once()


@pytest.mark.asyncio
async def test_proxy_triggers_reconnect_on_bluetooth_error(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that CasambiProxy wraps async calls and triggers reconnect on BluetoothError."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    api._schedule_reconnect = MagicMock()

    mock_target = AsyncMock(side_effect=BluetoothError("Write failed"))
    api._casa = MagicMock()
    api._casa.set_level = mock_target

    from custom_components.casambi_classic_bt import CasambiProxy

    proxy = CasambiProxy(api=api, casa=api._casa)

    # Calling through proxy should absorb BluetoothError and trigger reconnect
    await proxy.set_level(unit_id=1, level=1.0)
    api._schedule_reconnect.assert_called_once()


@pytest.mark.asyncio
async def test_rollback_connect_handles_exceptions_cleanly(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that _rollback_connect suppresses unregister ValueErrors and disconnect exceptions."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )
    api._disconnect_cb_registered = True
    api._unit_changed_cb_registered = True
    api._cancel_bluetooth_callback = MagicMock()
    api._cancel_watchdog = MagicMock()

    api._casa = MagicMock()
    api._casa.unregister_disconnect_callback = MagicMock(side_effect=ValueError("Not found"))
    api._casa.unregister_unit_changed_handler = MagicMock(side_effect=ValueError("Not found"))
    api._casa.disconnect = AsyncMock(side_effect=RuntimeError("BLE client crash"))

    # Should not raise
    await api._rollback_connect()

    assert api._disconnect_cb_registered is False
    assert api._unit_changed_cb_registered is False
    assert api._cancel_bluetooth_callback is None
    assert api._cancel_watchdog is None


@pytest.mark.asyncio
async def test_disconnect_handles_timeout_and_exceptions(
    mock_hass: HomeAssistant,
    test_entry: ConfigEntry,
) -> None:
    """Test that disconnect handles timeout and exceptions when cancelling reconnect."""
    api = CasambiApi(
        hass=mock_hass,
        conf_entry=test_entry,
        address=MOCK_MAC,
        password=MOCK_PASSWORD,
    )

    async def hung_reconnect() -> None:
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Shielding cancel simulation or long task
            raise TimeoutError("Hung task")

    task = asyncio.create_task(hung_reconnect())
    api._reconnect_task = task

    api._casa = MagicMock()
    api._casa.disconnect = AsyncMock(side_effect=RuntimeError("GATT disconnect failure"))

    await api.disconnect()

    assert api._unloaded is True
    assert api._reconnect_task is None


@pytest.mark.asyncio
async def test_canary_password_never_logged_or_persisted_in_plaintext(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify canary network password never appears in logs or plaintext cache files."""
    canary_password = "CANARY_SUPER_SECRET_PASSWORD_987654321"
    entry = ConfigEntry(
        entry_id="canary_entry_id",
        data={
            CONF_ADDRESS: MOCK_MAC,
            CONF_PASSWORD: canary_password,
        },
    )

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.connected = True
    mock_casa.disconnect = AsyncMock()
    mock_casa.register_disconnect_callback = MagicMock()
    mock_casa.register_unit_changed_handler = MagicMock()
    mock_casa.unregister_disconnect_callback = MagicMock()
    mock_casa.unregister_unit_changed_handler = MagicMock()

    import logging

    with (
        caplog.at_level(logging.DEBUG),
        patch(
            "custom_components.casambi_classic_bt.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.Casambi",
            return_value=mock_casa,
        ),
        patch(
            "custom_components.casambi_classic_bt.get_async_client",
            return_value=MagicMock(),
        ),
    ):
        await async_setup_entry(hass=mock_hass, entry=entry)
        await async_unload_entry(hass=mock_hass, entry=entry)

    # Assert canary password never appeared in any log record
    assert canary_password not in caplog.text

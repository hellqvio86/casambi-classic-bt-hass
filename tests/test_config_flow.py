"""Tests for Casambi Bluetooth integration config flow."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from casambi_classic_ble import AuthenticationError, NetworkNotFoundError
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.casambi_classic_bt.config_flow import ConfigFlow, _validate_input
from custom_components.casambi_classic_bt.const import CONF_IMPORT_GROUPS, DOMAIN
from tests.conftest import MOCK_MAC, MOCK_PASSWORD


@pytest.mark.asyncio
async def test_validate_input_online_success(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
) -> None:
    """Test successful online validation with no pre-existing cache."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
    }

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.disconnect = AsyncMock()
    mock_casa.invalidate_cache = AsyncMock()
    mock_casa.network_name = "Living Room Network"

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ) as mock_casa_cls,
    ):
        result = await _validate_input(mock_hass, data)

        # Invalidate cache must be called for online setup
        mock_casa.invalidate_cache.assert_awaited_once_with(uuid=MOCK_MAC)

        # Connect must be called with keyword arguments and force_offline=False
        mock_casa.connect.assert_awaited_once_with(
            address=mock_ble_device,
            password=MOCK_PASSWORD,
            force_offline=False,
        )

        # Disconnect must be awaited
        mock_casa.disconnect.assert_awaited_once()

        # Returned title must match network_name
        assert result == {"title": "Living Room Network", "id": MOCK_MAC}

        # Verify Casambi constructor called with keyword-only arguments
        assert mock_casa_cls.call_count == 1
        _, kwargs = mock_casa_cls.call_args
        assert "http_client" in kwargs
        assert "cache_path" in kwargs


@pytest.mark.asyncio
async def test_validate_input_offline_cache_success(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
    tmp_path: Path,
) -> None:
    """Test offline setup when cached network configuration exists."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
    }

    # Create fake networkid cache file on disk
    uuid_str = MOCK_MAC.replace(":", "").lower()
    net_id_file = tmp_path / ".storage" / DOMAIN / uuid_str / "networkid"
    net_id_file.parent.mkdir(parents=True, exist_ok=True)
    net_id_file.write_text("cached_network_id", encoding="utf-8")

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.disconnect = AsyncMock()
    mock_casa.invalidate_cache = AsyncMock()
    mock_casa.network_name = "Cached Network"

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ),
    ):
        result = await _validate_input(mock_hass, data)

        # Invalidate cache must NOT be called in offline cached mode
        mock_casa.invalidate_cache.assert_not_called()

        # Connect must be called with force_offline=True
        mock_casa.connect.assert_awaited_once_with(
            address=mock_ble_device,
            password=MOCK_PASSWORD,
            force_offline=True,
        )

        mock_casa.disconnect.assert_awaited_once()
        assert result == {"title": "Cached Network", "id": MOCK_MAC}


@pytest.mark.asyncio
async def test_validate_input_device_not_found(mock_hass: HomeAssistant) -> None:
    """Test NetworkNotFoundError when BLE device is not in range."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
    }

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(NetworkNotFoundError),
    ):
        await _validate_input(mock_hass, data)


@pytest.mark.asyncio
async def test_validate_input_auth_failure_guarantees_disconnect(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
) -> None:
    """Test that disconnect() is strictly called even when authentication fails."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: "wrong-password",
    }

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=AuthenticationError("Invalid credentials"))
    mock_casa.disconnect = AsyncMock()
    mock_casa.invalidate_cache = AsyncMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ),
        pytest.raises(AuthenticationError),
    ):
        await _validate_input(mock_hass, data)

    # Disconnect must be invoked via the finally block
    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_disconnect_failure_does_not_mask_error(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
) -> None:
    """Test that an error during disconnect does not swallow the original connect error."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: "wrong-password",
    }

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=AuthenticationError("Invalid credentials"))
    mock_casa.disconnect = AsyncMock(side_effect=RuntimeError("GATT disconnect failed"))
    mock_casa.invalidate_cache = AsyncMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ),
        pytest.raises(AuthenticationError),
    ):
        await _validate_input(mock_hass, data)

    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_disconnect_failure_on_success(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
) -> None:
    """Test that disconnect failure after successful connection does not fail config flow."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
    }

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock()
    mock_casa.disconnect = AsyncMock(side_effect=RuntimeError("GATT disconnect failed"))
    mock_casa.invalidate_cache = AsyncMock()
    mock_casa.network_name = "Living Room"

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ),
    ):
        result = await _validate_input(mock_hass, data)

    assert result == {"title": "Living Room", "id": MOCK_MAC}


@pytest.mark.asyncio
async def test_validate_input_cancellation_guarantees_disconnect(
    mock_hass: HomeAssistant,
    mock_ble_device: BLEDevice,
) -> None:
    """Test that task cancellation triggers disconnect in finally block."""
    data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: MOCK_PASSWORD,
    }

    mock_casa = MagicMock()
    mock_casa.connect = AsyncMock(side_effect=asyncio.CancelledError)
    mock_casa.disconnect = AsyncMock()
    mock_casa.invalidate_cache = AsyncMock()

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.get_async_client",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow.Casambi",
            return_value=mock_casa,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await _validate_input(mock_hass, data)

    mock_casa.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_config_flow_user_step_no_bluetooth(mock_hass: HomeAssistant) -> None:
    """Test user step when no connectable bluetooth scanner is present."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    with patch(
        "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
        return_value=0,
    ):
        result = await flow.async_step_user()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_error"


@pytest.mark.asyncio
async def test_config_flow_user_step_invalid_address(
    mock_hass: HomeAssistant,
    valid_user_input: dict[str, str | bool],
) -> None:
    """Test user step with invalid MAC address string format."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    user_input = {**valid_user_input, CONF_ADDRESS: "invalid-mac"}

    with patch(
        "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
        return_value=1,
    ):
        result = await flow.async_step_user(user_input=user_input)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_address"}


@pytest.mark.asyncio
async def test_config_flow_user_step_success(
    mock_hass: HomeAssistant,
    valid_user_input: dict[str, str | bool],
) -> None:
    """Test successful user step creating a new config entry."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow._validate_input",
            return_value={"title": "My Mesh", "id": MOCK_MAC},
        ),
        patch.object(flow, "async_set_unique_id", return_value=None),
    ):
        result = await flow.async_step_user(user_input=dict(valid_user_input))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My Mesh"
        assert result["data"][CONF_ADDRESS] == MOCK_MAC
        assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.asyncio
async def test_config_flow_user_step_auth_error(
    mock_hass: HomeAssistant,
    valid_user_input: dict[str, str | bool],
) -> None:
    """Test user step displaying invalid_auth on AuthenticationError."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow._validate_input",
            side_effect=AuthenticationError,
        ),
    ):
        result = await flow.async_step_user(user_input=dict(valid_user_input))
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_user_step_network_not_found(
    mock_hass: HomeAssistant,
    valid_user_input: dict[str, str | bool],
) -> None:
    """Test user step displaying cannot_connect on NetworkNotFoundError."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow._validate_input",
            side_effect=NetworkNotFoundError,
        ),
    ):
        result = await flow.async_step_user(user_input=dict(valid_user_input))
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_user_step_unexpected_error(
    mock_hass: HomeAssistant,
    valid_user_input: dict[str, str | bool],
) -> None:
    """Test user step displaying unknown error on unexpected exception."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.casambi_classic_bt.config_flow._validate_input",
            side_effect=RuntimeError("Unexpected BLE driver crash"),
        ),
    ):
        result = await flow.async_step_user(user_input=dict(valid_user_input))
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_config_flow_bluetooth_step(mock_hass: HomeAssistant) -> None:
    """Test discovery via bluetooth advertisement."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.connectable = True
    discovery_info.address = MOCK_MAC
    discovery_info.name = "Casambi Light"
    discovery_info.source = "hci0"
    discovery_info.advertisement = MagicMock()

    with (
        patch.object(flow, "async_set_unique_id", return_value=None),
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_step_bluetooth(discovery_info=discovery_info)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_bluetooth_step_unsuitable(mock_hass: HomeAssistant) -> None:
    """Test discovery rejection for non-connectable bluetooth advertisement."""
    flow = ConfigFlow()
    flow.hass = mock_hass

    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.connectable = False

    result = await flow.async_step_bluetooth(discovery_info=discovery_info)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "Unsuitable discovery."


@pytest.mark.asyncio
async def test_config_flow_reauth_step_success(mock_hass: HomeAssistant) -> None:
    """Test reauth flow success updating entry and reloading."""
    flow = ConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "test_entry_id"}

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: "old-password",
        CONF_IMPORT_GROUPS: True,
    }
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    with (
        patch(
            "custom_components.casambi_classic_bt.config_flow._validate_input",
            return_value={"title": "Updated Mesh", "id": MOCK_MAC},
        ),
        patch.object(
            flow,
            "async_abort",
            return_value={"type": FlowResultType.ABORT, "reason": "reauth_successful"},
        ),
    ):
        # Step reauth retrieves entry and routes to confirm
        result = await flow.async_step_reauth(mock_entry.data)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        # Submitting new password
        confirm_result = await flow.async_step_reauth_confirm(
            user_input={CONF_PASSWORD: "new-password"}
        )
        assert confirm_result["type"] == FlowResultType.ABORT
        assert confirm_result["reason"] == "reauth_successful"

        mock_hass.config_entries.async_update_entry.assert_called_once_with(
            mock_entry,
            data={
                CONF_ADDRESS: MOCK_MAC,
                CONF_PASSWORD: "new-password",
                CONF_IMPORT_GROUPS: True,
            },
        )
        mock_hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")


@pytest.mark.asyncio
async def test_config_flow_reauth_step_invalid_auth(mock_hass: HomeAssistant) -> None:
    """Test reauth flow error handling on invalid password."""
    flow = ConfigFlow()
    flow.hass = mock_hass
    flow.context = {"entry_id": "test_entry_id"}

    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_ADDRESS: MOCK_MAC,
        CONF_PASSWORD: "old-password",
    }
    flow.entry = mock_entry

    with patch(
        "custom_components.casambi_classic_bt.config_flow._validate_input",
        side_effect=AuthenticationError,
    ):
        result = await flow.async_step_reauth_confirm(user_input={CONF_PASSWORD: "wrong-password"})
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

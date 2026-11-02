"""Config flow for Casambi Bluetooth integration."""

import functools
import logging
from collections.abc import Mapping
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from casambi_classic_ble import (
    AuthenticationError,
    BluetoothDeviceNotFoundError,
    BluetoothError,
    Casambi,
    NetworkNotFoundError,
    ProtocolError,
    UnsupportedProtocolVersion,
    mask_mac,
)
from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_scanner_count,
)
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.httpx_client import get_async_client

from . import _CHECK_CACHED_NETWORK, get_cache_dir
from .const import CONF_IMPORT_GROUPS, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_IMPORT_GROUPS, default=True): cv.boolean,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def _fallback_clear_cached_session(*, cache_path: Any, address: str) -> None:
    """Clear cached session token when running against casambi-classic-ble < 0.8.5."""
    from casambi_classic_ble._constants import (
        LEGACY_SESSION_CACHE_FILE,
        SESSION_CACHE_FILE,
    )

    uuid = address.replace(":", "").lower()
    for name in (SESSION_CACHE_FILE, LEGACY_SESSION_CACHE_FILE):
        session_file = cache_path / uuid / name
        if session_file.exists():
            session_file.unlink()


_CLEAR_CACHED_SESSION = getattr(
    Casambi, "async_clear_cached_session", _fallback_clear_cached_session
)


async def _validate_input(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    *,
    force_online: bool = False,
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    address = str(data[CONF_ADDRESS])
    password = str(data[CONF_PASSWORD])
    client = get_async_client(hass)
    cache_dir = get_cache_dir(hass)
    casa = Casambi(http_client=client, cache_path=cache_dir)
    bt_device = async_ble_device_from_address(hass, address, connectable=True)

    if not bt_device:
        raise NetworkNotFoundError

    is_debug = _LOGGER.isEnabledFor(logging.DEBUG)
    masked_addr = mask_mac(bt_device.address, is_debug=is_debug)

    has_cache = False
    if force_online:
        await _CLEAR_CACHED_SESSION(cache_path=cache_dir, address=bt_device.address)
    else:
        has_cache = await hass.async_add_executor_job(
            functools.partial(
                _CHECK_CACHED_NETWORK,
                cache_path=cache_dir,
                address=bt_device.address,
            )
        )
        if not has_cache:
            await casa.invalidate_cache(uuid=bt_device.address)

    try:
        if has_cache:
            _LOGGER.info(
                "Using cached network configuration for %s (offline mode)",
                masked_addr,
            )
        await casa.connect(
            address=bt_device,
            password=password,
            force_offline=has_cache,
        )
        network_name = casa.network_name or address
    finally:
        # We need to disconnect again because otherwise setup will fail or leak BLE connection
        try:
            await casa.disconnect()
        except Exception as err:
            _LOGGER.debug(
                "Error disconnecting temporary session for %s: %s",
                masked_addr,
                err,
            )

    # Return info that you want to store in the config entry.
    return {"title": network_name, "id": address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Casambi Bluetooth."""

    discovery_info: BluetoothServiceInfoBleak | None = None

    VERSION = 1

    async def _async_create_casa_entry(
        self, title: str, id: str, data: dict[str, Any]
    ) -> FlowResult:
        existing_entry = await self.async_set_unique_id(id)

        if existing_entry:
            changed = self.hass.config_entries.async_update_entry(
                existing_entry, unique_id=id, title=title, data=data
            )

            if not changed:
                return self.async_abort(reason="already_configured")

            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=title, data=data)

    async def async_step_bluetooth_error(
        self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle bluetooth errors.

        The config flow can't proceed if there is a bluetooth error so this is the last step.
        """
        return self.async_abort(reason="bluetooth_error")

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        """Handle bluetooth discovery."""
        self.discovery_info = discovery_info

        if not discovery_info.connectable:
            return self.async_abort(reason="Unsuitable discovery.")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        is_debug = _LOGGER.isEnabledFor(logging.DEBUG)
        _LOGGER.debug(
            "Discovery: [%s] from %s.",
            mask_mac(discovery_info.address, is_debug=is_debug),
            discovery_info.source,
        )

        return self.async_show_form(step_id="user")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle entry of network information and attempt to connect."""

        suggested_input = {}
        if self.discovery_info:
            suggested_input[CONF_ADDRESS] = self.discovery_info.address

        if async_scanner_count(self.hass, connectable=True) < 1:
            return self.async_show_form(step_id="bluetooth_error")

        if user_input:
            errors = {}
            normalized_address = format_mac(user_input[CONF_ADDRESS]).upper()
            normalized_input = {
                **user_input,
                CONF_ADDRESS: normalized_address,
            }

            if len(normalized_address) == 17:
                try:
                    info = await _validate_input(self.hass, normalized_input)
                except (UnsupportedProtocolVersion, ProtocolError):
                    errors["base"] = "unsupported_firmware"
                except TimeoutError:
                    errors["base"] = "timeout"
                except (
                    NetworkNotFoundError,
                    BluetoothDeviceNotFoundError,
                    BluetoothError,
                ):
                    errors["base"] = "cannot_connect"
                except AuthenticationError:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return await self._async_create_casa_entry(
                        info["title"], info["id"], normalized_input
                    )
            else:
                errors["base"] = "invalid_address"

            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, normalized_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, suggested_input),
        )

    async def async_step_reauth(self, _entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with Casambi."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Casambi."""
        errors: dict[str, str] = {}
        assert self.entry is not None

        if user_input:
            data = {
                **self.entry.data,
                **user_input,
            }

            try:
                await _validate_input(self.hass, data, force_online=True)
            except (UnsupportedProtocolVersion, ProtocolError):
                errors["base"] = "unsupported_firmware"
            except TimeoutError:
                errors["base"] = "timeout"
            except (
                NetworkNotFoundError,
                BluetoothDeviceNotFoundError,
                BluetoothError,
            ):
                errors["base"] = "cannot_connect"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(REAUTH_SCHEMA, self.entry.data),
            errors=errors,
        )

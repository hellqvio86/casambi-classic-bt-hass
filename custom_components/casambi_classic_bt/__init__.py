"""The Casambi Bluetooth integration."""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any, Final, cast

from casambi_classic_ble import (
    AuthenticationError,
    BluetoothDeviceNotFoundError,
    BluetoothError,
    Casambi,
    Group,
    ProtocolError,
    Scene,
    Unit,
    UnitControlType,
    mask_mac,
)
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    DOMAIN,
    PLATFORMS,
    RECONNECT_BACKOFF_MAX,
    RECONNECT_BACKOFF_START,
    RECONNECT_BACKOFF_STEP,
)

_LOGGER: Final = logging.getLogger(__name__)


def _fallback_check_cached_network(*, cache_path: Path, address: str) -> bool:
    """Check cached network metadata when running against casambi-classic-ble < 0.8.5."""
    from casambi_classic_ble._constants import (
        LEGACY_NETWORK_ID_CACHE_FILE,
        NETWORK_ID_CACHE_FILE,
    )

    uuid = address.replace(":", "").lower()
    net_dir = cache_path / uuid
    return any(
        (net_dir / name).exists() for name in (NETWORK_ID_CACHE_FILE, LEGACY_NETWORK_ID_CACHE_FILE)
    )


_CHECK_CACHED_NETWORK = getattr(Casambi, "check_cached_network", _fallback_check_cached_network)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Casambi Bluetooth from a config entry."""
    api = CasambiApi(hass, entry, entry.data[CONF_ADDRESS], entry.data[CONF_PASSWORD])
    await api.connect()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        _LOGGER.error(
            "Failed to forward entry setups for %s: %s; rolling back setup",
            entry.entry_id,
            err,
        )
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
        await api.disconnect()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        casa_api: CasambiApi | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if casa_api is not None:
            await casa_api.disconnect()
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing a device that is no longer part of this Casambi network."""
    api: CasambiApi | None = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if api is None:
        return True
    live_identifiers: set[tuple[str, str]] = set()
    if api.casa and api.casa.network_id:
        live_identifiers.add((DOMAIN, str(api.casa.network_id)))
    for unit in api.get_units():
        live_identifiers.add((DOMAIN, str(unit.uuid)))

    return not bool(device_entry.identifiers & live_identifiers)


def get_cache_dir(hass: HomeAssistant) -> Path:
    """Return the cache dir that should be used by casambi_classic_ble."""
    conf_path = Path(hass.config.config_dir)
    return conf_path / ".storage" / DOMAIN


class CasambiApi:
    """Defines a Casambi API."""

    def __init__(
        self,
        hass: HomeAssistant,
        conf_entry: ConfigEntry,
        address: str,
        password: str,
    ) -> None:
        """Initialize a Casambi API."""

        self.hass = hass
        self.conf_entry = conf_entry
        self.address = address
        self.password = password
        self._casa = Casambi(
            http_client=get_async_client(hass),
            cache_path=get_cache_dir(hass),
        )
        self.casa = cast(Casambi, CasambiProxy(self, self._casa))

        self._callback_map: dict[int, list[Callable[[Unit], None]]] = {}
        self._cancel_bluetooth_callback: Callable[[], None] | None = None
        self._cancel_watchdog: Callable[[], None] | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._unloaded: bool = False
        self._disconnect_cb_registered: bool = False
        self._unit_changed_cb_registered: bool = False

    def _register_bluetooth_callback(self) -> None:
        self._cancel_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._bluetooth_callback,
            {"address": self.address, "connectable": True},
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

    async def connect(self) -> None:
        """Connect initially to the Casambi network."""
        try:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if not device:
                raise BluetoothDeviceNotFoundError  # noqa: TRY301

            if not self._disconnect_cb_registered:
                self._casa.register_disconnect_callback(callback=self._casa_disconnect)
                self._disconnect_cb_registered = True
            if not self._unit_changed_cb_registered:
                self._casa.register_unit_changed_handler(handler=self._unit_changed_handler)
                self._unit_changed_cb_registered = True

            force_offline = await self.hass.async_add_executor_job(
                functools.partial(
                    _CHECK_CACHED_NETWORK,
                    cache_path=get_cache_dir(self.hass),
                    address=self.address,
                )
            )
            if force_offline:
                _LOGGER.info(
                    "Connecting to %s in offline mode using pre-cached keys",
                    mask_mac(self.address, is_debug=_LOGGER.isEnabledFor(logging.DEBUG)),
                )

            await self._casa.connect(
                address=device, password=self.password, force_offline=force_offline
            )
        except BluetoothDeviceNotFoundError as err:
            await self._rollback_connect()
            raise ConfigEntryNotReady(f"Network with address {self.address} wasn't found") from err
        except BluetoothError as err:
            await self._rollback_connect()
            raise ConfigEntryNotReady("Failed to use bluetooth") from err
        except AuthenticationError as err:
            await self._rollback_connect()
            raise ConfigEntryAuthFailed(
                f"Failed to authenticate to network {self.address}"
            ) from err
        except Exception as err:  # pylint: disable=broad-except
            await self._rollback_connect()
            raise ConfigEntryError(f"Unexpected error creating network {self.address}") from err

        # Register bluetooth callback and periodic watchdog after connection.
        if not self._cancel_bluetooth_callback:
            self._register_bluetooth_callback()
        if not self._cancel_watchdog:
            self._cancel_watchdog = async_track_time_interval(
                self.hass,
                self._watchdog_callback,
                timedelta(seconds=60),
            )

    async def _rollback_connect(self) -> None:
        """Roll back partially initialized Casambi session after connect failure."""
        if self._disconnect_cb_registered:
            try:
                self._casa.unregister_disconnect_callback(callback=self._casa_disconnect)
            except ValueError:
                pass
            self._disconnect_cb_registered = False

        if self._unit_changed_cb_registered:
            try:
                self._casa.unregister_unit_changed_handler(handler=self._unit_changed_handler)
            except ValueError:
                pass
            self._unit_changed_cb_registered = False

        if self._cancel_bluetooth_callback is not None:
            self._cancel_bluetooth_callback()
            self._cancel_bluetooth_callback = None

        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None

        try:
            await self._casa.disconnect()
        except Exception as err:
            _LOGGER.debug("Error disconnecting Casambi library during setup rollback: %s", err)

    async def reconnect(self) -> None:
        """Start reconnection attempt to the Casambi network with resilient backoff."""
        _LOGGER.info("Starting reconnection attempt to Casambi network %s", self.address)
        # Yield briefly to let any pending disconnect handlers and BLE state settle
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            _LOGGER.debug("Casambi reconnect task cancelled during initial backoff.")
            return

        backoff = RECONNECT_BACKOFF_START
        while not self._unloaded and not (
            hasattr(self.hass, "is_stopping") and self.hass.is_stopping
        ):
            try:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                if not device:
                    raise BluetoothDeviceNotFoundError  # noqa: TRY301

                await self._casa.reconnect(address=device)
                if self._casa.connected:
                    _LOGGER.info("Successfully reconnected to Casambi network %s", self.address)
                    break
                _LOGGER.debug(
                    "Reconnect call completed but Casambi reports disconnected; retrying in %ds...",
                    backoff,
                )
            except BluetoothDeviceNotFoundError:
                _LOGGER.debug(
                    "Casambi device %s not found in Bluetooth cache. Retrying in %ds...",
                    self.address,
                    backoff,
                )
                backoff = max(backoff, 10)
            except BluetoothError as err:
                _LOGGER.debug(
                    "Connecting to %s failed due to bluetooth error: %s. Retrying in %ds...",
                    self.address,
                    err,
                    backoff,
                )
            except ProtocolError as err:
                _LOGGER.warning(
                    "Protocol error during Casambi reconnect to %s: %s. Retrying in %ds...",
                    self.address,
                    err,
                    backoff,
                )
            except AuthenticationError as err:
                _LOGGER.error(
                    "Authentication failed during Casambi reconnect to %s: %s. Retrying in 60s...",
                    self.address,
                    err,
                )
                backoff = max(backoff, 60)
            except asyncio.CancelledError:
                _LOGGER.debug("Casambi reconnect task cancelled.")
                break
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Unexpected error during Casambi reconnect to %s: %s. Retrying in %ds...",
                    self.address,
                    err,
                    backoff,
                )

            if self._unloaded or (hasattr(self.hass, "is_stopping") and self.hass.is_stopping):
                break

            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                _LOGGER.debug("Casambi reconnect task cancelled during backoff sleep.")
                break

            backoff = min(RECONNECT_BACKOFF_MAX, backoff * RECONNECT_BACKOFF_STEP)

    @property
    def available(self) -> bool:
        """Return True if the controller is available."""
        return self._casa.connected

    def get_units(self, control_types: list[UnitControlType] | None = None) -> Iterable[Unit]:
        """Return all units in the network optionally filtered by control type."""

        if not control_types:
            return self._casa.units

        control_values = {ct.value if hasattr(ct, "value") else ct for ct in control_types}
        return filter(
            lambda u: any(
                (uc.type.value if hasattr(uc.type, "value") else uc.type) in control_values
                for uc in u.unit_type.controls
            ),
            self._casa.units,
        )

    def get_groups(self) -> Iterable[Group]:
        """Return all groups in the network."""

        return self._casa.groups

    def get_scenes(self) -> Iterable[Scene]:
        """Return all scenes in the network."""

        return self._casa.scenes

    async def disconnect(self) -> None:
        """Disconnects from the controller and disables automatic reconnect."""
        self._unloaded = True

        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._reconnect_task), timeout=5)
            except (asyncio.CancelledError, TimeoutError):
                pass
            except Exception as err:
                _LOGGER.debug("Got exception when cancelling reconnect: %s", err, exc_info=True)
            finally:
                self._reconnect_task = None

        if self._cancel_bluetooth_callback is not None:
            self._cancel_bluetooth_callback()
            self._cancel_bluetooth_callback = None

        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None

        if self._disconnect_cb_registered:
            try:
                self._casa.unregister_disconnect_callback(callback=self._casa_disconnect)
            except ValueError:
                pass
            self._disconnect_cb_registered = False

        if self._unit_changed_cb_registered:
            try:
                self._casa.unregister_unit_changed_handler(handler=self._unit_changed_handler)
            except ValueError:
                pass
            self._unit_changed_cb_registered = False

        try:
            await self._casa.disconnect()
        except Exception as err:
            _LOGGER.exception("Error during disconnect: %s", err)

    @callback
    def _watchdog_callback(self, _now: Any) -> None:
        """Periodic watchdog verifying Bluetooth connection health."""
        if not self._casa.connected:
            _LOGGER.debug(
                "Casambi watchdog: mesh %s is disconnected; scheduling reconnect",
                self.address,
            )
            self._schedule_reconnect()

    @callback
    def _casa_disconnect(self) -> None:
        self._schedule_reconnect()

    def register_unit_updates(self, unit: Unit, c: Callable[[Unit], None]) -> None:
        """Register a callback for unit updates.

        :param unit: The unit for which changes should be reported.
        :param c: The callback.
        """
        callbacks = self._callback_map.setdefault(unit.device_id, [])
        if c not in callbacks:
            callbacks.append(c)

    def unregister_unit_updates(self, unit: Unit, c: Callable[[Unit], None]) -> None:
        """Unregister a callback for unit updates.

        :param unit: The unit for which changes should no longer be reported.
        :param c: The callback.
        """
        if unit.device_id in self._callback_map and c in self._callback_map[unit.device_id]:
            self._callback_map[unit.device_id].remove(c)

    @callback
    def _unit_changed_handler(self, unit: Unit) -> None:
        if unit.device_id not in self._callback_map:
            return
        for c in list(self._callback_map[unit.device_id]):
            c(unit)

    @callback
    def _bluetooth_callback(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        if not self._casa.connected and service_info.connectable:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._unloaded or (hasattr(self.hass, "is_stopping") and self.hass.is_stopping):
            _LOGGER.debug(
                "Skipping reconnect for %s: entry unloaded or Home Assistant stopping",
                self.address,
            )
            return

        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.conf_entry.async_create_background_task(
                self.hass, self.reconnect(), f"{DOMAIN}_{self.address}_reconnect"
            )


class CasambiProxy:
    """Proxy the write operations so that bluetooth errors automatically trigger a reconnect."""

    def __init__(self, api: CasambiApi, casa: Casambi) -> None:
        """Initialize a CasambiProxy."""
        self._api = api
        self._casa = casa

    def __getattr__(self, name: str) -> Any:
        """Wrap all async calls to drop BluetoothError and trigger a reconnect instead."""
        attr = getattr(self._casa, name)

        if inspect.iscoroutinefunction(attr):

            async def async_wrapper(*args, **kwargs):
                try:
                    return await attr(*args, **kwargs)
                except BluetoothError:
                    _LOGGER.debug("Bluetooth error during write.", exc_info=True)
                    _LOGGER.info("Triggering reconnect after write failed.")
                    self._api._schedule_reconnect()  # noqa: SLF001

            return async_wrapper

        return attr

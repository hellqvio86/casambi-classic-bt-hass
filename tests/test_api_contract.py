"""API contract and deprecation verification tests for casambi-classic-bt-hass."""

import ast
import inspect
from pathlib import Path

import casambi_classic_ble
from casambi_classic_ble import Casambi


def test_casambi_classic_ble_minimum_version() -> None:
    """Verify that installed casambi-classic-ble satisfies declared minimum >=0.8.1."""
    from packaging.version import Version

    version = getattr(casambi_classic_ble, "__version__", None)
    assert version is not None, "casambi_classic_ble must declare __version__"
    assert Version(version) >= Version("0.8.1")


def test_casambi_public_api_signatures() -> None:
    """Verify canonical method signatures on Casambi match integration expectations."""
    # connect
    connect_sig = inspect.signature(Casambi.connect)
    assert "address" in connect_sig.parameters
    assert "password" in connect_sig.parameters
    assert "force_offline" in connect_sig.parameters

    # invalidate_cache
    inv_sig = inspect.signature(Casambi.invalidate_cache)
    assert "uuid" in inv_sig.parameters

    # reconnect
    rec_sig = inspect.signature(Casambi.reconnect)
    assert "address" in rec_sig.parameters

    # disconnect
    assert callable(getattr(Casambi, "disconnect", None))

    # control methods
    for method_name in (
        "set_unit_state",
        "set_level",
        "set_temperature",
        "set_color",
        "set_white",
        "set_vertical",
        "turn_on",
        "turn_off",
        "switch_to_scene",
    ):
        sig = inspect.signature(getattr(Casambi, method_name))
        assert "target" in sig.parameters or "unit" in sig.parameters

    # properties and public cache boundary helpers
    from packaging.version import Version

    assert isinstance(inspect.getattr_static(Casambi, "network_name"), property)
    assert isinstance(inspect.getattr_static(Casambi, "network_id"), property)
    if Version(casambi_classic_ble.__version__) >= Version("0.8.5"):
        assert callable(getattr(Casambi, "has_cached_network", None))
        assert callable(getattr(Casambi, "check_cached_network", None))
        assert callable(getattr(Casambi, "async_has_cached_network", None))
        assert callable(getattr(Casambi, "clear_cached_session", None))
        assert callable(getattr(Casambi, "async_clear_cached_session", None))


def test_integration_calls_bind_to_library_signatures() -> None:
    """Static AST check verifying that all Casambi method invocations match library signatures."""
    cc_dir = Path(__file__).resolve().parent.parent / "custom_components" / "casambi_classic_bt"
    call_count = 0

    for py_file in cc_dir.glob("**/*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue

            # Identify calls to casa.<method> or self._api.casa.<method> or api.casa.<method>
            func_name = node.func.attr
            is_casa_call = False
            curr = node.func.value
            if isinstance(curr, ast.Name) and curr.id == "casa":
                is_casa_call = True
            elif isinstance(curr, ast.Attribute) and curr.attr == "casa":
                is_casa_call = True

            if not is_casa_call:
                continue

            method = getattr(Casambi, func_name, None)
            assert method is not None, (
                f"Casambi has no method '{func_name}' ({py_file.name}:{node.lineno})"
            )

            sig = inspect.signature(method)
            # Create dummy values for all passed keyword arguments
            dummy_kwargs = {kw.arg: "dummy" for kw in node.keywords if kw.arg is not None}
            dummy_args = ["dummy"] * len(node.args)

            try:
                sig.bind_partial(*dummy_args, **dummy_kwargs)
            except TypeError as err:
                raise AssertionError(
                    f"Signature mismatch in {py_file.name}:{node.lineno} calling casa.{func_name} "
                    f"with kwargs {list(dummy_kwargs.keys())}: {err}"
                ) from err
            call_count += 1

    assert call_count >= 15, (
        f"Expected at least 15 Casambi API calls in integration, found {call_count}"
    )


def test_no_deprecated_aliases_called_in_integration() -> None:
    """Static AST check verifying no deprecated aliases or private cache files are used in custom_components."""
    deprecated_names = {
        "invalidateCache",
        "networkName",
        "networkId",
        "unregisterDisconnectCallback",
        "unregisterUnitChangedHandler",
        "registerDisconnectCallback",
        "registerUnitChangedHandler",
        "forceOffline",
        "groudId",
        "sceneId",
        "deviceId",
        "unitType",
        "firmwareVersion",
    }

    cc_dir = Path(__file__).resolve().parent.parent / "custom_components" / "casambi_classic_bt"
    for py_file in cc_dir.glob("**/*.py"):
        source = py_file.read_text(encoding="utf-8")
        assert '"networkid"' not in source and "'networkid'" not in source, (
            f"Found hardcoded private cache filename 'networkid' in {py_file.name}"
        )
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in deprecated_names:
                raise AssertionError(
                    f"Found deprecated attribute access '{node.attr}' in {py_file.name}:{node.lineno}"
                )
            if isinstance(node, ast.keyword) and node.arg in deprecated_names:
                raise AssertionError(
                    f"Found deprecated keyword argument '{node.arg}' in {py_file.name}:{node.lineno}"
                )

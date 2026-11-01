"""API contract and deprecation verification tests for casambi-classic-bt-hass."""

import ast
import inspect
from pathlib import Path

import casambi_classic_ble
from casambi_classic_ble import Casambi


def test_casambi_classic_ble_minimum_version() -> None:
    """Verify that installed casambi-classic-ble satisfies declared minimum >=0.6.0."""
    from packaging.version import Version

    version = getattr(casambi_classic_ble, "__version__", None)
    assert version is not None, "casambi_classic_ble must declare __version__"
    assert Version(version) >= Version("0.6.0")


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

    # properties
    assert isinstance(inspect.getattr_static(Casambi, "network_name"), property)
    assert isinstance(inspect.getattr_static(Casambi, "network_id"), property)


def test_no_deprecated_aliases_called_in_integration() -> None:
    """Static AST check verifying no deprecated aliases are invoked anywhere in custom_components."""
    deprecated_names = {
        "invalidateCache",
        "networkName",
        "networkId",
        "unregisterDisconnectCallback",
        "unregisterUnitChangedHandler",
        "registerDisconnectCallback",
        "registerUnitChangedHandler",
        "forceOffline",
    }

    cc_dir = Path(__file__).resolve().parent.parent / "custom_components" / "casambi_classic_bt"
    for py_file in cc_dir.glob("**/*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in deprecated_names:
                raise AssertionError(
                    f"Found deprecated attribute access '{node.attr}' in {py_file.name}:{node.lineno}"
                )
            if isinstance(node, ast.keyword) and node.arg in deprecated_names:
                raise AssertionError(
                    f"Found deprecated keyword argument '{node.arg}' in {py_file.name}:{node.lineno}"
                )

from __future__ import annotations

import importlib.util
import os
import urllib.error
import urllib.request


def optional_package_installed(module_name: str) -> bool:
    """Return whether an optional Python package can be discovered locally."""

    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def aura_sr_installed() -> bool:
    return optional_package_installed("aura_sr")


def local_service_available(base_url: str, timeout_seconds: float = 0.35) -> bool:
    """Check a local optional service without making capability discovery fail."""

    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def optional_service_capabilities() -> dict[str, bool]:
    sam3_url = os.environ.get("ASSET_PIPELINE_SAM3_URL", "http://127.0.0.1:8765")
    rife_url = os.environ.get("ASSET_PIPELINE_INTERPOLATION_URL", "http://127.0.0.1:8775")
    return {
        "sam3": local_service_available(sam3_url),
        "rife": local_service_available(rife_url),
    }

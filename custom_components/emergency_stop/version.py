"""Version helpers for Emergency Stop."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_BUILD_INFO_PATH = Path(__file__).resolve().parent / "build_info.json"


def _load_build_info() -> dict[str, Any]:
    try:
        raw = _BUILD_INFO_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _format_commit(build_info: dict[str, Any]) -> str | None:
    commit_short = build_info.get("commit_short")
    if commit_short:
        return str(commit_short)
    commit = build_info.get("commit")
    if not commit:
        return None
    commit = str(commit)
    return commit[:7] if len(commit) > 7 else commit


async def async_get_version_label(hass: HomeAssistant) -> str:
    """Return a compact version label for UI display."""
    version = "unknown"
    async_get_integration = None
    try:
        from homeassistant.helpers.integration import async_get_integration as _agi

        async_get_integration = _agi
    except ImportError:
        try:
            from homeassistant.loader import async_get_integration as _agi

            async_get_integration = _agi
        except ImportError:
            async_get_integration = None

    if async_get_integration:
        try:
            integration = await async_get_integration(hass, DOMAIN)
            if integration.version:
                version = integration.version
        except Exception:
            pass

    build_info = _load_build_info()
    commit = _format_commit(build_info)
    if commit:
        return f"{version} (commit {commit})"
    return str(version)

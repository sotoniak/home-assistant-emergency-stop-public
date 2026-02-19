import asyncio
import sys
import types
from types import SimpleNamespace

from custom_components.emergency_stop import version as version_module


def test_load_build_info_handles_missing_and_invalid(tmp_path, monkeypatch):
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(version_module, "_BUILD_INFO_PATH", missing_path)
    assert version_module._load_build_info() == {}

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not-json}", encoding="utf-8")
    monkeypatch.setattr(version_module, "_BUILD_INFO_PATH", invalid_path)
    assert version_module._load_build_info() == {}


def test_load_build_info_reads_valid_dict(tmp_path, monkeypatch):
    path = tmp_path / "build_info.json"
    path.write_text('{"commit_short":"abc1234"}', encoding="utf-8")
    monkeypatch.setattr(version_module, "_BUILD_INFO_PATH", path)

    assert version_module._load_build_info() == {"commit_short": "abc1234"}


def test_async_get_version_label_includes_commit(monkeypatch):
    async def fake_get_integration(_hass, _domain):
        return SimpleNamespace(version="2.0.1")

    monkeypatch.setattr(version_module, "_load_build_info", lambda: {"commit_short": "abc1234"})
    fake_module = types.ModuleType("homeassistant.helpers.integration")
    fake_module.async_get_integration = fake_get_integration
    monkeypatch.setitem(
        sys.modules, "homeassistant.helpers.integration", fake_module
    )

    label = asyncio.run(version_module.async_get_version_label(SimpleNamespace()))
    assert label == "2.0.1 (commit abc1234)"


def test_async_get_version_label_fallback_unknown(monkeypatch):
    async def failing_get_integration(_hass, _domain):
        raise RuntimeError("boom")

    monkeypatch.setattr(version_module, "_load_build_info", lambda: {})
    fake_module = types.ModuleType("homeassistant.helpers.integration")
    fake_module.async_get_integration = failing_get_integration
    monkeypatch.setitem(
        sys.modules, "homeassistant.helpers.integration", fake_module
    )

    label = asyncio.run(version_module.async_get_version_label(SimpleNamespace()))
    assert label == "unknown"

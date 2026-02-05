import asyncio

from custom_components.emergency_stop import async_migrate_entry


class FakeConfigEntries:
    def async_update_entry(self, entry, *, data, options, version):
        entry.data = data
        entry.options = options
        entry.version = version


class FakeHass:
    def __init__(self):
        self.config_entries = FakeConfigEntries()


class FakeEntry:
    def __init__(self, data, options=None, version=1):
        self.data = data
        self.options = options or {}
        self.version = version


def test_migration_is_not_supported_for_old_entries():
    entry = FakeEntry({"legacy": True}, version=1)
    hass = FakeHass()

    result = asyncio.run(async_migrate_entry(hass, entry))

    assert result is False
    assert entry.version == 1

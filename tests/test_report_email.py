from pathlib import Path
import asyncio

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator, EmergencyStopState
from custom_components.emergency_stop.const import LEVEL_LIMIT, LEVEL_NOTIFY, LEVEL_SHUTDOWN


def test_async_write_report_sends_email_when_enabled():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        calls: dict[str, object] = {"sent": False}

        async def fake_write_report():
            return {"file_name": "report.json"}, Path("/tmp/report.json")

        async def fake_send_email(report, report_path, provider=None):
            calls["sent"] = True
            calls["report"] = report
            calls["path"] = report_path
            calls["provider"] = provider

        coordinator._async_write_report_file = fake_write_report
        coordinator._send_report_email = fake_send_email

        path = await coordinator.async_write_report(send_email=True)

        assert calls["sent"] is True
        assert calls["report"]["file_name"] == "report.json"
        assert calls["path"] == Path("/tmp/report.json")
        assert path == Path("/tmp/report.json")

    asyncio.run(run())


def test_async_write_report_skips_email_when_disabled():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        calls: dict[str, object] = {"sent": False}

        async def fake_write_report():
            return {"file_name": "report.json"}, Path("/tmp/report.json")

        async def fake_send_email(report, report_path, provider=None):
            calls["sent"] = True

        coordinator._async_write_report_file = fake_write_report
        coordinator._send_report_email = fake_send_email

        path = await coordinator.async_write_report(send_email=False)

        assert calls["sent"] is False
        assert path == Path("/tmp/report.json")

    asyncio.run(run())


def test_send_report_email_uses_brevo():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator._stop_state = EmergencyStopState(level=LEVEL_LIMIT)
        coordinator._brevo_api_key = "token"
        coordinator._brevo_sender = "sender@example.com"
        coordinator._brevo_recipient_default = "recipient@example.com"
        coordinator._brevo_recipients = {
            LEVEL_LIMIT: "recipient@example.com",
            LEVEL_NOTIFY: None,
            LEVEL_SHUTDOWN: None,
        }
        coordinator._email_levels = [LEVEL_LIMIT]
        coordinator._email_levels_set = set(coordinator._email_levels)

        calls = {"brevo": 0}

        async def fake_brevo(message, level):
            calls["brevo"] += 1

        coordinator._send_brevo_email = fake_brevo

        await coordinator._send_report_email(
            {"file_name": "report.json"}, Path("/tmp/report.json")
        )

        assert calls["brevo"] == 1

    asyncio.run(run())

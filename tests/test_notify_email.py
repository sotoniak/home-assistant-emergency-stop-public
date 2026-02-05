from pathlib import Path

from custom_components.emergency_stop.brevo import build_brevo_payload, format_subject
from custom_components.emergency_stop.coordinator import (
    _format_notify_message,
    _should_notify_on_activation,
)
from custom_components.emergency_stop.const import LEVEL_LIMIT, LEVEL_SHUTDOWN


def test_should_notify_on_activation_only_on_off_to_on():
    assert _should_notify_on_activation(False, True) is True
    assert _should_notify_on_activation(False, False) is False
    assert _should_notify_on_activation(True, True) is False
    assert _should_notify_on_activation(True, False) is False


def test_format_notify_message_contains_prompt_and_json():
    report = {
        "generated_at": "2026-01-30T12:00:00+00:00",
        "file_name": "emergency_stop_report_20260130T120000Z.json",
        "outputs": {"level": "notify"},
    }
    message = _format_notify_message(report, "notify", Path("/media/emergency-stop/report.json"))

    assert "Emergency Stop report (JSON)" in message
    assert "Current level: notify" in message
    assert "```json" in message
    assert "\"generated_at\": \"2026-01-30T12:00:00+00:00\"" in message
    assert "/media/emergency-stop/report.json" in message


def test_format_email_subject_with_prefix_and_level():
    assert format_subject("shutdown") == "Emergency Stop [shutdown]"
    assert format_subject(None) == "Emergency Stop [active]"
    assert format_subject("limit") == "Emergency Stop [limit]"


def test_brevo_payload_marks_shutdown_as_urgent():
    payload = build_brevo_payload(
        "message",
        LEVEL_SHUTDOWN,
        "sender@example.com",
        "recipient@example.com",
    )
    assert payload["headers"]["Importance"] == "High"
    assert payload["headers"]["X-Priority"] == "1 (Highest)"
    assert payload["headers"]["X-MSMail-Priority"] == "High"

    payload = build_brevo_payload(
        "message",
        LEVEL_LIMIT,
        "sender@example.com",
        "recipient@example.com",
    )
    assert "headers" not in payload

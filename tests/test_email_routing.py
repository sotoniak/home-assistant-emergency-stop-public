from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator
from custom_components.emergency_stop.const import LEVEL_LIMIT, LEVEL_NOTIFY, LEVEL_SHUTDOWN


def _coordinator_for_email():
    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator._brevo_api_key = "token"
    coordinator._brevo_sender = "sender@example.com"
    coordinator._brevo_recipient_default = "default@example.com"
    coordinator._brevo_recipients = {
        LEVEL_NOTIFY: "notify@example.com",
        LEVEL_LIMIT: None,
        LEVEL_SHUTDOWN: "shutdown@example.com",
    }
    coordinator._email_levels = [LEVEL_LIMIT, LEVEL_SHUTDOWN]
    coordinator._email_levels_set = set(coordinator._email_levels)
    return coordinator


def test_email_level_filter_and_recipient_selection():
    coordinator = _coordinator_for_email()

    assert coordinator._email_should_send(LEVEL_NOTIFY) is False
    assert coordinator._email_should_send(LEVEL_LIMIT) is True
    assert coordinator._recipient_for_level(LEVEL_LIMIT) == "default@example.com"
    assert coordinator._recipient_for_level(LEVEL_SHUTDOWN) == "shutdown@example.com"


def test_email_requires_recipient():
    coordinator = _coordinator_for_email()
    coordinator._brevo_recipient_default = None
    coordinator._brevo_recipients[LEVEL_LIMIT] = None

    assert coordinator._email_should_send(LEVEL_LIMIT) is False

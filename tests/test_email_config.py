from custom_components.emergency_stop.config_flow import _clean_email_config, _normalize_optional_str
from custom_components.emergency_stop.const import (
    CONF_BREVO_API_KEY,
    CONF_BREVO_RECIPIENT_LIMIT,
    CONF_BREVO_RECIPIENT_NOTIFY,
    CONF_BREVO_RECIPIENT_SHUTDOWN,
)


def test_normalize_optional_str():
    assert _normalize_optional_str(None) is None
    assert _normalize_optional_str("") is None
    assert _normalize_optional_str("  ") is None
    assert _normalize_optional_str(" notify.test ") == "notify.test"


def test_clean_email_config_drops_empty_fields():
    data = {
        CONF_BREVO_API_KEY: "",
    }
    cleaned = _clean_email_config(data)
    assert CONF_BREVO_API_KEY not in cleaned


def test_clean_email_config_keeps_brevo_keys():
    data = {
        CONF_BREVO_API_KEY: "token",
    }
    cleaned = _clean_email_config(data)
    assert cleaned[CONF_BREVO_API_KEY] == "token"


def test_clean_email_config_strips_whitespace():
    data = {
        CONF_BREVO_API_KEY: "  token  ",
    }
    cleaned = _clean_email_config(data)
    assert cleaned[CONF_BREVO_API_KEY] == "token"


def test_clean_email_config_strips_per_level_recipients():
    data = {
        CONF_BREVO_RECIPIENT_NOTIFY: " notify@example.com ",
        CONF_BREVO_RECIPIENT_LIMIT: " limit@example.com ",
        CONF_BREVO_RECIPIENT_SHUTDOWN: " shutdown@example.com ",
    }
    cleaned = _clean_email_config(data)
    assert cleaned[CONF_BREVO_RECIPIENT_NOTIFY] == "notify@example.com"
    assert cleaned[CONF_BREVO_RECIPIENT_LIMIT] == "limit@example.com"
    assert cleaned[CONF_BREVO_RECIPIENT_SHUTDOWN] == "shutdown@example.com"


def test_clean_email_config_drops_section_keys():
    data = {
        "section_report": "Report",
        "info_version": "Version",
        CONF_BREVO_RECIPIENT_NOTIFY: "notify@example.com",
    }
    cleaned = _clean_email_config(data)
    assert "section_report" not in cleaned
    assert "info_version" not in cleaned
    assert cleaned[CONF_BREVO_RECIPIENT_NOTIFY] == "notify@example.com"

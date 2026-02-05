"""Brevo email client wrapper."""
from __future__ import annotations

from typing import Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LEVEL_SHUTDOWN


_LOGGER = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def format_subject(level: str | None) -> str:
    tag = level or "active"
    return f"Emergency Stop [{tag}]"


def build_brevo_payload(
    message: str,
    level: str | None,
    sender: str,
    recipient: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sender": {"email": sender},
        "to": [{"email": recipient}],
        "subject": format_subject(level),
        "textContent": message,
    }
    if level == LEVEL_SHUTDOWN:
        payload["headers"] = {
            "Importance": "High",
            "X-Priority": "1 (Highest)",
            "X-MSMail-Priority": "High",
        }
    return payload


async def async_send_brevo_email(
    hass: HomeAssistant,
    api_key: str,
    sender: str,
    recipient: str,
    message: str,
    level: str | None,
) -> None:
    payload = build_brevo_payload(message, level, sender, recipient)
    session = async_get_clientsession(hass)
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    async with session.post(BREVO_API_URL, json=payload, headers=headers) as resp:
        if resp.status not in (200, 201, 202):
            body = await resp.text()
            _LOGGER.warning("Brevo email failed status=%s body=%s", resp.status, body)
            return
    _LOGGER.info("Brevo email sent to %s", recipient)

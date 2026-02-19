import asyncio
import logging
from types import SimpleNamespace

from custom_components.emergency_stop import brevo


class FakeResponse:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, headers: dict):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.response


def test_async_send_brevo_email_success(monkeypatch):
    session = FakeSession(FakeResponse(status=202))
    monkeypatch.setattr(brevo, "async_get_clientsession", lambda _hass: session)

    asyncio.run(
        brevo.async_send_brevo_email(
            hass=SimpleNamespace(),
            api_key="token",
            sender="sender@example.com",
            recipient="recipient@example.com",
            message="hello",
            level="limit",
        )
    )

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == brevo.BREVO_API_URL
    assert call["headers"]["api-key"] == "token"
    assert call["json"]["subject"] == "Emergency Stop [limit]"


def test_async_send_brevo_email_failure_logs_warning(monkeypatch, caplog):
    session = FakeSession(FakeResponse(status=400, body="bad request"))
    monkeypatch.setattr(brevo, "async_get_clientsession", lambda _hass: session)

    with caplog.at_level(logging.WARNING):
        asyncio.run(
            brevo.async_send_brevo_email(
                hass=SimpleNamespace(),
                api_key="token",
                sender="sender@example.com",
                recipient="recipient@example.com",
                message="hello",
                level="notify",
            )
        )

    assert "Brevo email failed status=400 body=bad request" in caplog.text

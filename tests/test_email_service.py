# test_email_service.py
#
# Integration test for the SMTP email path (app/services/email.py) WITHOUT real
# credentials or a network. smtplib.SMTP is fully mocked, so this exercises the
# exact send sequence (connect → starttls → login → send_message) and the
# interview-invite message composition that the live system relies on.

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.services.email import (
    ConsoleEmailSender,
    SmtpEmailSender,
    get_email_sender,
    send_interview_invite,
)


# ── Sender selection ────────────────────────────────────────────────────────────

def test_get_email_sender_falls_back_to_console_without_credentials(monkeypatch):
    monkeypatch.delenv("SMTP_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert isinstance(get_email_sender(), ConsoleEmailSender)


def test_get_email_sender_uses_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("SMTP_EMAIL", "recruiter@acme.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_HOST", "smtp.acme.com")
    monkeypatch.setenv("SMTP_PORT", "2525")

    sender = get_email_sender()
    assert isinstance(sender, SmtpEmailSender)
    assert (sender.host, sender.port, sender.user) == ("smtp.acme.com", 2525, "recruiter@acme.com")


# ── Console fallback never touches the network ──────────────────────────────────

def test_console_sender_does_not_open_a_connection():
    with patch("app.services.email.smtplib.SMTP") as smtp:
        ConsoleEmailSender().send("c@x.com", "Subj", "Body")
    smtp.assert_not_called()


# ── SMTP send sequence (mocked smtplib) ─────────────────────────────────────────

def _mock_smtp():
    """A MagicMock standing in for smtplib.SMTP used as a context manager."""
    server = MagicMock(name="smtp_server")
    smtp_cls = MagicMock(name="SMTP")
    smtp_cls.return_value.__enter__.return_value = server
    return smtp_cls, server


def test_smtp_sender_runs_full_send_sequence():
    smtp_cls, server = _mock_smtp()
    with patch("app.services.email.smtplib.SMTP", smtp_cls):
        SmtpEmailSender("smtp.acme.com", 587, "recruiter@acme.com", "pw").send(
            "cand@example.com", "Hello", "Body text"
        )

    # Connected to the right host/port (with a timeout), then TLS + auth + send.
    smtp_cls.assert_called_once()
    args, kwargs = smtp_cls.call_args
    assert args[0] == "smtp.acme.com" and args[1] == 587
    assert kwargs.get("timeout")  # a timeout is always set so a hung server can't block
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("recruiter@acme.com", "pw")
    server.send_message.assert_called_once()

    # The composed message has the right envelope + body.
    sent = server.send_message.call_args.args[0]
    assert isinstance(sent, EmailMessage)
    assert sent["From"] == "recruiter@acme.com"
    assert sent["To"] == "cand@example.com"
    assert sent["Subject"] == "Hello"
    assert "Body text" in sent.get_content()


def test_smtp_login_failure_propagates():
    smtp_cls, server = _mock_smtp()
    server.login.side_effect = RuntimeError("535 auth failed")
    with patch("app.services.email.smtplib.SMTP", smtp_cls):
        with pytest.raises(RuntimeError, match="auth failed"):
            SmtpEmailSender("h", 587, "u", "p").send("to@x.com", "s", "b")
    server.send_message.assert_not_called()  # never sends if auth fails


# ── Interview-invite composition over the SMTP path ─────────────────────────────

def test_send_interview_invite_composes_link_and_subject(monkeypatch):
    monkeypatch.setenv("SMTP_EMAIL", "recruiter@acme.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    smtp_cls, server = _mock_smtp()

    with patch("app.services.email.smtplib.SMTP", smtp_cls):
        send_interview_invite(
            to="alice@example.com",
            candidate_name="Alice",
            job_title="Backend Engineer",
            link="https://app.example.com/interview/abc123",
        )

    sent = server.send_message.call_args.args[0]
    assert sent["To"] == "alice@example.com"
    assert "Backend Engineer" in sent["Subject"]
    body = sent.get_content()
    assert "Alice" in body
    assert "https://app.example.com/interview/abc123" in body


def test_send_interview_invite_handles_missing_name(monkeypatch):
    monkeypatch.setenv("SMTP_EMAIL", "recruiter@acme.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    smtp_cls, server = _mock_smtp()

    with patch("app.services.email.smtplib.SMTP", smtp_cls):
        send_interview_invite(
            to="nobody@example.com", candidate_name=None,
            job_title="Data Scientist", link="https://x/iv/9",
        )

    body = server.send_message.call_args.args[0].get_content()
    assert "there" in body  # graceful "Hi there," fallback when name is unknown

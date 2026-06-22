"""Provider-agnostic email sending.

Uses SMTP when SMTP_EMAIL/SMTP_PASSWORD are configured, otherwise logs the message
to the console (so the flow is fully testable in dev without real credentials).

All network calls here are blocking; callers in async contexts must offload them
(e.g. ``starlette.concurrency.run_in_threadpool``).
"""

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    """A single message in a batch send."""

    to: str
    subject: str
    body: str


class EmailSender(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None: ...

    def send_batch(self, messages: list[OutgoingEmail]) -> dict[str, str]:
        """Send many messages, returning ``{recipient: error}`` for any that failed.

        The default implementation sends one at a time; subclasses with a connection
        (e.g. SMTP) override this to reuse a single connection for the whole batch.
        """
        errors: dict[str, str] = {}
        for m in messages:
            try:
                self.send(m.to, m.subject, m.body)
            except Exception as e:  # noqa: BLE001 — record per-recipient, keep going
                errors[m.to] = str(e)
        return errors


class ConsoleEmailSender(EmailSender):
    """Dev fallback: log the email (including the interview link) instead of sending."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("[email:console] No SMTP configured — would send:\nTo: %s\nSubject: %s\n%s",
                       to, subject, body)


def _build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


class SmtpEmailSender(EmailSender):
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host, self.port, self.user, self.password = host, port, user, password

    def send(self, to: str, subject: str, body: str) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.send_message(_build_message(self.user, to, subject, body))
        logger.info("[email:smtp] sent to %s (%s)", to, subject)

    def send_batch(self, messages: list[OutgoingEmail]) -> dict[str, str]:
        """Open one SMTP connection (handshake + auth once) and reuse it for the batch."""
        if not messages:
            return {}
        errors: dict[str, str] = {}
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                server.starttls()
                server.login(self.user, self.password)
                for m in messages:
                    try:
                        server.send_message(_build_message(self.user, m.to, m.subject, m.body))
                        logger.info("[email:smtp] sent to %s (%s)", m.to, m.subject)
                    except Exception as e:  # noqa: BLE001 — one bad recipient shouldn't abort the batch
                        errors[m.to] = str(e)
        except Exception as e:  # noqa: BLE001 — connect/TLS/login failed: nothing was delivered
            logger.error("[email:smtp] batch connection failed: %s", e)
            for m in messages:
                errors.setdefault(m.to, f"SMTP connection failed: {e}")
        return errors


def get_email_sender() -> EmailSender:
    user = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    if user and password:
        return SmtpEmailSender(
            os.getenv("SMTP_HOST", "smtp.gmail.com"),
            int(os.getenv("SMTP_PORT", "587")),
            user,
            password,
        )
    return ConsoleEmailSender()


def send_interview_invite(*, to: str, candidate_name: str | None, job_title: str, link: str) -> None:
    subject = f"Your interview for {job_title}"
    body = (
        f"Hi {candidate_name or 'there'},\n\n"
        f"Congratulations — you've been shortlisted for the {job_title} role!\n\n"
        f"Please start your AI interview using the link below. The link is valid for a "
        f"short time, so begin as soon as you're ready:\n\n{link}\n\n"
        f"Find a quiet place with a working microphone before you start.\n\n"
        f"Good luck!\n"
    )
    get_email_sender().send(to, subject, body)


def send_availability_invite(*, to: str, candidate_name: str | None, job_title: str, link: str) -> None:
    subject = f"Schedule Your Interview — {job_title}"
    body = (
        f"Hi {candidate_name or 'there'},\n\n"
        f"Congratulations! Your application for the {job_title} role has cleared our initial "
        f"screening and we'd like to schedule a formal interview with you.\n\n"
        f"Please select your preferred interview time using the link below:\n\n"
        f"{link}\n\n"
        f"The link is valid for 72 hours. You can choose from our available slots or "
        f"specify a custom time that works best for you.\n\n"
        f"Best regards,\nThe Recruitment Team\n"
    )
    get_email_sender().send(to, subject, body)


def send_slot_confirmation(
    *, to: str, candidate_name: str | None, job_title: str, slot: str, room_url: str | None = None
) -> None:
    subject = f"Interview Confirmed — {job_title}"
    room_section = (
        f"\nJoin your interview here:\n{room_url}\n"
        f"\n(The link is valid for 7 days. Please open it a few minutes before your slot.)\n"
        if room_url
        else "\nOur team will send you a meeting link shortly before your interview.\n"
    )
    body = (
        f"Hi {candidate_name or 'there'},\n\n"
        f"Your interview for the {job_title} role has been confirmed for:\n\n"
        f"  {slot}\n"
        f"{room_section}\n"
        f"Before joining, please make sure you're in a quiet space with a working microphone.\n\n"
        f"Best regards,\nThe Recruitment Team\n"
    )
    get_email_sender().send(to, subject, body)

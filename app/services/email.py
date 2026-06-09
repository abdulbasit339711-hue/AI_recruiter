"""Provider-agnostic email sending.

Uses SMTP when SMTP_EMAIL/SMTP_PASSWORD are configured, otherwise logs the message
to the console (so the flow is fully testable in dev without real credentials).
"""

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailSender(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender(EmailSender):
    """Dev fallback: log the email (including the interview link) instead of sending."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("[email:console] No SMTP configured — would send:\nTo: %s\nSubject: %s\n%s",
                       to, subject, body)


class SmtpEmailSender(EmailSender):
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host, self.port, self.user, self.password = host, port, user, password

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.send_message(msg)
        logger.info("[email:smtp] sent to %s (%s)", to, subject)


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

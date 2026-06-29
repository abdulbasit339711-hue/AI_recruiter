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

    def send(self, to: str, subject: str, body: str, html: str | None = None) -> None:
        logger.warning("[email:console] No SMTP configured — would send:\nTo: %s\nSubject: %s\n%s",
                       to, subject, body)


def _build_message(sender: str, to: str, subject: str, body_text: str, body_html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg


def _html_template(
    *,
    org_name: str,
    org_color: str,
    heading: str,
    intro: str,
    paragraphs: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    note: str | None = None,
) -> str:
    initial = (org_name or "R")[0].upper()
    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
      <tr>
        <td align="center" style="background:#ffffff;padding:8px 40px 32px;">
          <a href="{cta_url}" style="display:inline-block;padding:14px 32px;background:{org_color};color:#ffffff;text-decoration:none;border-radius:10px;font-weight:600;font-size:15px;letter-spacing:-0.2px;">{cta_label}</a>
        </td>
      </tr>"""
    note_block = ""
    if note:
        note_block = f"""
      <tr>
        <td style="background:#ffffff;padding:0 40px 32px;">
          <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;border-top:1px solid #f3f4f6;padding-top:16px;">{note}</p>
        </td>
      </tr>"""
    para_html = "".join(
        f'<p style="margin:0 0 14px;color:#374151;font-size:14px;line-height:1.7;">{p}</p>'
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 16px;">
  <tr><td align="center">
    <table width="100%" style="max-width:560px;">
      <tr>
        <td style="background:{org_color};padding:28px 40px;border-radius:12px 12px 0 0;">
          <table cellpadding="0" cellspacing="0"><tr>
            <td style="background:rgba(255,255,255,0.2);border-radius:10px;width:42px;height:42px;text-align:center;vertical-align:middle;font-size:18px;font-weight:700;color:#fff;">{initial}</td>
            <td style="padding-left:12px;color:rgba(255,255,255,0.85);font-size:13px;font-weight:500;">{org_name}</td>
          </tr></table>
          <h1 style="margin:20px 0 0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;line-height:1.3;">{heading}</h1>
        </td>
      </tr>
      <tr>
        <td style="background:#ffffff;padding:28px 40px 8px;">
          <p style="margin:0 0 16px;color:#111827;font-size:15px;font-weight:600;">{intro}</p>
          {para_html}
        </td>
      </tr>
      {cta_block}
      {note_block}
      <tr>
        <td style="background:#f9fafb;border-top:1px solid #e5e7eb;border-radius:0 0 12px 12px;padding:18px 40px;text-align:center;">
          <p style="margin:0;color:#9ca3af;font-size:12px;">{org_name} · Careers &amp; Recruitment</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""


class SmtpEmailSender(EmailSender):
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host, self.port, self.user, self.password = host, port, user, password
        # port 465 = implicit SSL; anything else = STARTTLS
        self._use_ssl = port == 465

    def _connect(self):
        if self._use_ssl:
            return smtplib.SMTP_SSL(self.host, self.port, timeout=20)
        server = smtplib.SMTP(self.host, self.port, timeout=20)
        server.starttls()
        return server

    def send(self, to: str, subject: str, body: str, html: str | None = None) -> None:
        with self._connect() as server:
            server.login(self.user, self.password)
            server.send_message(_build_message(self.user, to, subject, body, html))
        logger.info("[email:smtp] sent to %s (%s)", to, subject)

    def send_batch(self, messages: list[OutgoingEmail]) -> dict[str, str]:
        """Open one SMTP connection (handshake + auth once) and reuse it for the batch."""
        if not messages:
            return {}
        errors: dict[str, str] = {}
        try:
            with self._connect() as server:
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


def send_interview_invite(
    *, to: str, candidate_name: str | None, job_title: str, link: str,
    org_name: str | None = None, org_color: str = "#1C99BF",
) -> None:
    name = candidate_name or "there"
    org  = org_name or "Recruitment Team"
    subject = f"Your AI Interview — {job_title}"
    text = (
        f"Hi {name},\n\n"
        f"Congratulations — you've been shortlisted for the {job_title} role at {org}!\n\n"
        f"Please start your AI-powered interview using the link below. "
        f"The room will only open at your scheduled time, so return then:\n\n{link}\n\n"
        f"Tips before you begin:\n"
        f"  • Find a quiet room with no background noise\n"
        f"  • Make sure your microphone is working\n"
        f"  • Allow microphone access when the browser asks\n\n"
        f"Good luck!\n{org}\n"
    )
    html = _html_template(
        org_name=org,
        org_color=org_color,
        heading=f"Your AI Interview is Ready",
        intro=f"Hi {name}, you're confirmed for the {job_title} role!",
        paragraphs=[
            "You've been shortlisted and your interview room is ready. "
            "The link below will open at your scheduled time — please return then and allow a moment to connect.",
            "Before joining, make sure you're in a quiet room with your microphone enabled.",
        ],
        cta_label="Join Interview Room",
        cta_url=link,
        note="This link is time-gated — it activates 15 minutes before your confirmed slot and expires 90 minutes after.",
    )
    get_email_sender().send(to, subject, text, html)


def send_availability_invite(
    *, to: str, candidate_name: str | None, job_title: str, link: str,
    org_name: str | None = None, org_color: str = "#1C99BF",
) -> None:
    name = candidate_name or "there"
    org  = org_name or "Recruitment Team"
    subject = f"Schedule Your Interview — {job_title}"
    text = (
        f"Hi {name},\n\n"
        f"Congratulations! Your application for the {job_title} role at {org} has cleared "
        f"our initial screening and we'd like to schedule a formal interview with you.\n\n"
        f"Please select your preferred interview date and time using the link below:\n\n{link}\n\n"
        f"The link is valid for 72 hours. Choose any available slot on the calendar.\n\n"
        f"Best regards,\n{org}\n"
    )
    html = _html_template(
        org_name=org,
        org_color=org_color,
        heading="Let's Schedule Your Interview",
        intro=f"Hi {name}, great news!",
        paragraphs=[
            f"Your application for the <strong>{job_title}</strong> role has cleared our initial "
            "screening — congratulations!",
            "Please pick a date and time that works best for you. "
            "You'll see available slots on the calendar — click one and confirm.",
        ],
        cta_label="Choose Your Interview Time",
        cta_url=link,
        note="This scheduling link is valid for 72 hours. After you confirm, you'll receive a separate email with your interview room link.",
    )
    get_email_sender().send(to, subject, text, html)


def send_slot_confirmation(
    *, to: str, candidate_name: str | None, job_title: str, slot: str,
    room_url: str | None = None,
    org_name: str | None = None, org_color: str = "#1C99BF",
) -> None:
    name = candidate_name or "there"
    org  = org_name or "Recruitment Team"
    subject = f"Interview Confirmed — {job_title}"
    room_line = (
        f"Join your interview here:\n{room_url}\n\n"
        f"(The link activates 15 minutes before your slot and works for 90 minutes.)"
        if room_url
        else "Your interview room link will be sent to you shortly before your scheduled time."
    )
    text = (
        f"Hi {name},\n\n"
        f"Your interview for the {job_title} role at {org} has been confirmed for:\n\n"
        f"  {slot}\n\n"
        f"{room_line}\n\n"
        f"Before joining: find a quiet room and make sure your microphone is working.\n\n"
        f"Best of luck!\n{org}\n"
    )
    room_para = (
        f'<strong>Join here:</strong> <a href="{room_url}" style="color:{org_color};">{room_url}</a>'
        if room_url
        else "Your interview room link will arrive in a separate email before your slot."
    )
    html = _html_template(
        org_name=org,
        org_color=org_color,
        heading="Interview Confirmed ✓",
        intro=f"Hi {name}, you're all set!",
        paragraphs=[
            f"Your interview for the <strong>{job_title}</strong> role is confirmed for:",
            f'<span style="display:inline-block;padding:10px 18px;background:#f0fdf4;border-left:3px solid {org_color};border-radius:6px;font-weight:600;color:#111827;font-size:15px;">{slot}</span>',
            room_para,
            "Please be in a quiet space with your microphone ready a few minutes before your slot.",
        ],
        note="The interview room link activates 15 minutes before your scheduled time and remains open for 90 minutes.",
    )
    get_email_sender().send(to, subject, text, html)

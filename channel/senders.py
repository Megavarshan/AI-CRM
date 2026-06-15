"""
Real message senders for the channel gateway.

  send_email   — actual SMTP delivery (HTML + plain-text alternative)
  send_twilio  — actual SMS / WhatsApp via Twilio's REST API (httpx, no SDK dep)

Each returns (ok: bool, reason: str | None). A False result becomes a real
"failed" receipt with the reason — never a fake success.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import httpx

from config import settings

logger = logging.getLogger(__name__)


def send_email(to_addr: str, subject: str, html_body: str, text_body: str | None = None) -> tuple[bool, str | None]:
    """Send a real email over SMTP. Returns (ok, reason)."""
    if not settings.email_configured:
        return False, "email channel not configured (set SMTP_HOST in channel/.env)"
    if not to_addr:
        return False, "no recipient email address"

    from_addr = settings.email_from_addr
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.EMAIL_FROM_NAME, from_addr))
    msg["To"] = to_addr
    msg.attach(MIMEText(text_body or _strip_html(html_body), "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.SMTP_USE_SSL:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx, timeout=30) as s:
                _login(s)
                s.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as s:
                s.ehlo()
                if settings.SMTP_USE_TLS:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                _login(s)
                s.sendmail(from_addr, [to_addr], msg.as_string())
        return True, None
    except Exception as e:  # noqa: BLE001
        logger.warning("SMTP send to %s failed: %s", to_addr, e)
        return False, f"smtp error: {e}"


def _login(s: smtplib.SMTP) -> None:
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)


def send_twilio(channel: str, to_number: str, body: str) -> tuple[bool, str | None]:
    """Send a real SMS or WhatsApp message via Twilio. Returns (ok, reason)."""
    if not settings.twilio_configured:
        return False, "Twilio not configured (set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)"
    if not to_number:
        return False, "no recipient phone number"

    if channel == "whatsapp":
        from_ = settings.TWILIO_WHATSAPP_FROM
        to_ = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
    else:  # sms / rcs -> sms
        from_ = settings.TWILIO_SMS_FROM
        to_ = to_number
    if not from_:
        return False, f"no Twilio sender configured for {channel}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        resp = httpx.post(
            url,
            data={"From": from_, "To": to_, "Body": body},
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True, None
        detail = resp.json().get("message", resp.text) if resp.content else f"HTTP {resp.status_code}"
        return False, f"twilio error: {detail}"
    except Exception as e:  # noqa: BLE001
        logger.warning("Twilio send to %s failed: %s", to_number, e)
        return False, f"twilio error: {e}"


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

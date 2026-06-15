"""
Branded HTML email rendering with real engagement tracking baked in:
  • every CTA link is rewritten through the click-tracking proxy
  • a 1x1 open-tracking pixel is appended
  • a working one-click unsubscribe link is included (compliance)
"""

from __future__ import annotations

from urllib.parse import quote

from config import settings


def _track_click_url(comm_id: str, dest: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}/api/v1/track/click/{comm_id}?u={quote(dest, safe='')}"


def open_pixel_url(comm_id: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}/api/v1/track/open/{comm_id}.gif"


def unsubscribe_url(comm_id: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}/api/v1/track/unsubscribe/{comm_id}"


def render_email(
    *,
    comm_id: str,
    brand_name: str,
    first_name: str,
    body_text: str,
    cta_label: str,
    cta_url: str,
    accent: str = "#7c3aed",
) -> str:
    """Render a clean, mobile-friendly marketing email with tracking."""
    tracked_cta = _track_click_url(comm_id, cta_url)
    pixel = open_pixel_url(comm_id)
    unsub = unsubscribe_url(comm_id)
    safe_body = (body_text or "").replace("\n", "<br>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand_name}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);">
        <tr><td style="background:{accent};padding:20px 28px;">
          <span style="color:#fff;font-size:20px;font-weight:800;letter-spacing:-.3px;">{brand_name}</span>
        </td></tr>
        <tr><td style="padding:32px 28px 8px 28px;">
          <p style="font-size:16px;color:#0f172a;margin:0 0 14px 0;">Hi {first_name or 'there'},</p>
          <p style="font-size:15px;line-height:1.6;color:#334155;margin:0 0 24px 0;">{safe_body}</p>
          <table role="presentation" cellpadding="0" cellspacing="0"><tr><td align="center"
            style="border-radius:10px;background:{accent};">
            <a href="{tracked_cta}" target="_blank"
              style="display:inline-block;padding:13px 30px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;">
              {cta_label}</a>
          </td></tr></table>
        </td></tr>
        <tr><td style="padding:24px 28px 28px 28px;">
          <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 16px 0;">
          <p style="font-size:12px;color:#94a3b8;line-height:1.5;margin:0;">
            You received this because you're a customer of {brand_name}.<br>
            <a href="{unsub}" style="color:#94a3b8;text-decoration:underline;">Unsubscribe</a> ·
            Sent with Orbit
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
  <img src="{pixel}" width="1" height="1" alt="" style="display:block;border:0;width:1px;height:1px;">
</body></html>"""

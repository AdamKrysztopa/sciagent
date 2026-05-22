"""Transactional email sender (Resend / SendGrid compatible)."""

from __future__ import annotations

import structlog

_log = structlog.get_logger()


async def send_email(
    *,
    api_key: str,
    from_address: str,
    to: list[str],
    subject: str,
    text: str,
) -> None:
    """Send a plain-text email via Resend (POST /emails).

    Falls back to a log-only no-op when api_key is empty, so dev/test
    environments never make real network calls.
    """
    if not api_key:
        _log.info("email_send_skipped_no_key", to=to, subject=subject)
        return

    import httpx  # noqa: PLC0415

    payload = {
        "from": from_address,
        "to": to,
        "subject": subject,
        "text": text,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        _log.info("email_sent", to=to, subject=subject, status=response.status_code)

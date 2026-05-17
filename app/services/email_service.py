import structlog
from app.config import settings

logger = structlog.get_logger()


def send_claim_email(email: str, claim_code: str, player_name: str) -> bool:
    """Send a claim code email through Resend HTTP API.

    Returns True on success, False otherwise.
    """
    if not settings.resend_api_key:
        logger.info("email_send_skipped_no_api_key", email=email)
        return False

    try:
        import httpx

        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.from_email,
                "to": [email],
                "subject": "Your JLRS player claim code",
                "text": (
                    f"Your coach has created a JLRS player profile for {player_name}.\n"
                    f"Use this claim code to link the profile to your account: {claim_code}\n\n"
                    f"Visit {settings.frontend_url}/claim?code={claim_code} to claim your player profile.\n\n"
                    "If you did not request this, you can ignore this email."
                ),
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            logger.warning("email_send_failed_httpx", email=email, status_code=resp.status_code, body=body)
            return False
        logger.info("email_sent_httpx", email=email)
        return True
    except Exception as exc:
        logger.warning("email_send_error_httpx", email=email, error=str(exc))
        return False

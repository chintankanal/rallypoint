"""
Webhook delivery: HMAC-SHA256 signed HTTP POST to a configured URL.
Fire-and-forget — never raises on delivery failure.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


def _sign_body(body: str, secret: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def fire(event_type: str, payload: dict) -> None:
    envelope = {
        "event_type": event_type,
        "fired_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    body = json.dumps(envelope, default=str)

    if not settings.webhook_url:
        logger.info("webhook_skipped_no_url", event_type=event_type)
        return

    signature = _sign_body(body, settings.webhook_secret)
    try:
        resp = httpx.post(
            settings.webhook_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-JLRS-Signature": signature,
            },
            timeout=3.0,
        )
        logger.info(
            "webhook_delivered",
            event_type=event_type,
            status_code=resp.status_code,
        )
    except Exception as exc:
        logger.warning("webhook_delivery_failed", event_type=event_type, error=str(exc))

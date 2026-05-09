"""
Unit tests for webhook_service HMAC signing logic.
Tests the _sign_body function directly and verifies fire() doesn't raise on failure.
"""
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.webhook_service import _sign_body


def test_sign_body_produces_sha256_hex():
    sig = _sign_body("hello", "secret")
    # Should be a 64-character hex string
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_sign_body_matches_manual_hmac():
    body = '{"event_type": "test", "payload": {}}'
    secret = "my-test-secret"
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert _sign_body(body, secret) == expected


def test_sign_body_different_secrets_produce_different_sigs():
    body = "same body"
    sig1 = _sign_body(body, "secret-a")
    sig2 = _sign_body(body, "secret-b")
    assert sig1 != sig2


def test_sign_body_different_bodies_produce_different_sigs():
    secret = "same-secret"
    sig1 = _sign_body("body-a", secret)
    sig2 = _sign_body("body-b", secret)
    assert sig1 != sig2


def test_fire_does_not_raise_when_no_webhook_url():
    """fire() should be a no-op (logging only) when webhook_url is empty."""
    from app.services.webhook_service import fire
    with patch("app.services.webhook_service.settings") as mock_settings:
        mock_settings.webhook_url = ""
        mock_settings.webhook_secret = "secret"
        # Must not raise
        fire("test.event", {"key": "value"})


def test_fire_does_not_raise_on_http_failure():
    """fire() must swallow HTTP errors — fire-and-forget."""
    import httpx
    from app.services.webhook_service import fire
    with patch("app.services.webhook_service.settings") as mock_settings:
        mock_settings.webhook_url = "http://localhost:9999/webhook"
        mock_settings.webhook_secret = "secret"
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            fire("test.event", {"key": "value"})  # must not raise


def test_fire_sends_correct_hmac_header():
    """Verify the X-JLRS-Signature header value matches HMAC of the body sent."""
    from app.services.webhook_service import fire

    captured: dict = {}

    def mock_post(url, content, headers, timeout):
        captured["body"] = content
        captured["sig"] = headers.get("X-JLRS-Signature")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    with patch("app.services.webhook_service.settings") as mock_settings:
        mock_settings.webhook_url = "http://example.com/webhook"
        mock_settings.webhook_secret = "test-secret"
        with patch("httpx.post", side_effect=mock_post):
            fire("player.tier_changed", {"player_id": "abc"})

    assert "body" in captured
    expected_sig = _sign_body(captured["body"], "test-secret")
    assert captured["sig"] == expected_sig

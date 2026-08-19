"""Zendesk Webhook Security and Signature Verification.

Implements HMAC-SHA256 signature verification per Zendesk Webhook specification:
https://developer.zendesk.com/documentation/webhooks/verifying/
"""

import base64
import hashlib
import hmac
from typing import Optional, Union
from pydantic import SecretStr


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""
    pass


def compute_zendesk_webhook_signature(
    body: Union[bytes, str],
    timestamp: str,
    secret: Union[str, SecretStr],
) -> str:
    """Compute base64-encoded HMAC-SHA256 signature for Zendesk webhook payload.

    Args:
        body: Raw request body (bytes or str).
        timestamp: Value of 'X-Zendesk-Webhook-Signature-Timestamp' header.
        secret: Zendesk webhook signing secret.

    Returns:
        Base64-encoded SHA256 HMAC signature string.
    """
    secret_str = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)
    secret_bytes = secret_str.encode("utf-8")

    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    payload = timestamp.encode("utf-8") + body_bytes

    computed_digest = hmac.new(secret_bytes, payload, hashlib.sha256).digest()
    return base64.b64encode(computed_digest).decode("utf-8")


def verify_zendesk_webhook_signature(
    body: Union[bytes, str],
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    secret: Union[str, SecretStr],
) -> bool:
    """Verify that an incoming webhook request genuinely originated from Zendesk.

    Args:
        body: Raw request body (bytes or str).
        signature_header: Content of 'X-Zendesk-Webhook-Signature' HTTP header.
        timestamp_header: Content of 'X-Zendesk-Webhook-Signature-Timestamp' HTTP header.
        secret: Zendesk webhook signing secret.

    Returns:
        True if the signature is valid.

    Raises:
        WebhookVerificationError: If required headers are missing or signature does not match.
    """
    if not signature_header:
        raise WebhookVerificationError("Missing 'X-Zendesk-Webhook-Signature' header.")

    if not timestamp_header:
        raise WebhookVerificationError("Missing 'X-Zendesk-Webhook-Signature-Timestamp' header.")

    secret_str = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)
    if not secret_str.strip():
        raise WebhookVerificationError("Zendesk webhook secret is not configured on server.")

    expected_signature = compute_zendesk_webhook_signature(
        body=body,
        timestamp=timestamp_header,
        secret=secret_str,
    )

    # Constant-time comparison to prevent timing side-channel attacks
    if not hmac.compare_digest(expected_signature, signature_header.strip()):
        raise WebhookVerificationError("Invalid webhook signature. HMAC-SHA256 signature mismatch.")

    return True

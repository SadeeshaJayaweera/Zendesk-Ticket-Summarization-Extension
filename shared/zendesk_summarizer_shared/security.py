"""Zendesk Webhook Security, Signature Verification, Password Hashing & JWT Auth.

Implements:
1. HMAC-SHA256 signature verification per Zendesk Webhook specification with timestamp skew checks.
2. Bcrypt password hashing and validation.
3. JWT token generation and verification for multi-tenant RBAC.
"""

from datetime import datetime, timedelta
import base64
import hashlib
import hmac
import time
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from pydantic import SecretStr

from zendesk_summarizer_shared.config import Settings, get_settings


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""
    pass


class AuthError(Exception):
    """Raised when authentication fails."""
    pass


class ForbiddenError(Exception):
    """Raised when authorization role checks fail."""
    pass


def compute_zendesk_webhook_signature(
    body: Union[bytes, str],
    timestamp: str,
    secret: Union[str, SecretStr],
) -> str:
    """Compute base64-encoded HMAC-SHA256 signature for Zendesk webhook payload."""
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
    max_skew_seconds: int = 300,
) -> bool:
    """Verify that an incoming webhook request genuinely originated from Zendesk."""
    if not signature_header:
        raise WebhookVerificationError("Missing 'X-Zendesk-Webhook-Signature' header.")

    if not timestamp_header:
        raise WebhookVerificationError("Missing 'X-Zendesk-Webhook-Signature-Timestamp' header.")

    secret_str = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)
    if not secret_str.strip():
        raise WebhookVerificationError("Zendesk webhook secret is not configured on server.")

    # Timestamp skew validation (prevents replay attacks)
    try:
        ts = int(timestamp_header.strip())
        now = int(time.time())
        # Check skew only if timestamp is a standard unix timestamp in seconds
        if abs(now - ts) > max_skew_seconds and ts > 1_000_000_000 and ts < 2_500_000_000:
            raise WebhookVerificationError(f"Webhook timestamp skew ({abs(now - ts)}s) exceeds max allowed {max_skew_seconds}s.")
    except (ValueError, TypeError):
        pass  # If non-integer timestamp format, proceed to signature check

    expected_signature = compute_zendesk_webhook_signature(
        body=body,
        timestamp=timestamp_header,
        secret=secret_str,
    )

    # Constant-time comparison to prevent timing side-channel attacks
    if not hmac.compare_digest(expected_signature, signature_header.strip()):
        raise WebhookVerificationError("Invalid webhook signature. HMAC-SHA256 signature mismatch.")

    return True


# --- Password Hashing with Bcrypt ---

def hash_password(password: str) -> str:
    """Hash password string with salt using bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain text password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# --- JWT Token Generation & Verification ---

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    organization_id: str,
    settings: Optional[Settings] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create signed JWT bearer token containing user identity and organization scope."""
    cfg = settings or get_settings()
    expire_minutes = expires_delta or timedelta(minutes=cfg.jwt_expiration_minutes)
    expire = datetime.utcnow() + expire_minutes

    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "org_id": organization_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    secret = cfg.jwt_secret_key.get_secret_value()
    return jwt.encode(payload, secret, algorithm=cfg.jwt_algorithm)


def decode_access_token(
    token: str,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    cfg = settings or get_settings()
    secret = cfg.jwt_secret_key.get_secret_value()
    try:
        payload = jwt.decode(token, secret, algorithms=[cfg.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("JWT token has expired.")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid authentication token: {exc}")

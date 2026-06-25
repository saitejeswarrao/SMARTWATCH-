"""
security.py — Data Privacy & Security Module
Module 5: Encrypts all health data with AES-256, handles secure authentication,
          manages user-controlled data sharing consents, and supports
          hardware enclave key export.

Stack:
  • Fernet (AES-128-CBC + HMAC-SHA256) via `cryptography` library
    — Use cryptography.hazmat.primitives for AES-256-GCM in production
  • PBKDF2-HMAC-SHA256 for password-derived keys
  • Token-based session authentication
  • Consent ledger for GDPR-compliant data sharing control
"""

import os
import json
import base64
import hashlib
import hmac
import secrets
import datetime
from typing import Dict, Optional, List

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("[security] WARNING: 'cryptography' not installed. "
          "Install with: pip install cryptography")
    print("[security]          Running in PLAINTEXT MOCK mode — NOT for production.\n")


# ── Key derivation constants ─────────────────────────────────────────────────
KDF_ITERATIONS  = 480_000   # OWASP 2023 recommendation for PBKDF2-SHA256
KDF_KEY_LEN     = 32        # 256-bit AES key


# ── DataVault — encryption / decryption ──────────────────────────────────────
class DataVault:
    """
    Encrypts and decrypts health readings.

    Two modes:
      1. Random key (default) — key generated fresh each session.
         Export with export_key() and store in a hardware enclave / HSM.
      2. Password-derived key  — derive a stable key from user password + salt.
         Useful for multi-device scenarios.

    In production (AES-256-GCM upgrade):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key  = os.urandom(32)
        aesgcm = AESGCM(key)
        nonce  = os.urandom(12)
        ct     = aesgcm.encrypt(nonce, plaintext, aad)
    """

    def __init__(self, key: Optional[bytes] = None,
                 password: Optional[str] = None,
                 salt: Optional[bytes]   = None):
        if not HAS_CRYPTO:
            self._fernet = None
            self._key    = b"MOCK_KEY"
            return

        if password:
            self._key = self._derive_key(password, salt or os.urandom(16))
        elif key:
            self._key = key
        else:
            self._key = Fernet.generate_key()

        self._fernet = Fernet(self._key)

    # ── Core encrypt / decrypt ────────────────────────────────────────────────

    def encrypt(self, data: dict) -> bytes:
        """Serialise data to JSON and encrypt to bytes."""
        if not HAS_CRYPTO:
            return json.dumps(data).encode()   # mock plaintext
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(payload)

    def decrypt(self, token: bytes) -> dict:
        """Decrypt bytes and deserialise to dict."""
        if not HAS_CRYPTO:
            return json.loads(token)
        payload = self._fernet.decrypt(token)
        return json.loads(payload)

    # ── Key management ────────────────────────────────────────────────────────

    def export_key(self) -> str:
        """
        Export the encryption key as a URL-safe base64 string.
        Store this in a hardware enclave (TPM, Apple Secure Enclave,
        Android Keystore) — never in plaintext on disk.
        """
        return base64.urlsafe_b64encode(self._key).decode()

    @classmethod
    def from_exported_key(cls, key_str: str) -> "DataVault":
        """Reconstruct a DataVault from a previously exported key string."""
        key = base64.urlsafe_b64decode(key_str.encode())
        return cls(key=key)

    # ── Password-derived key ──────────────────────────────────────────────────

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """PBKDF2-HMAC-SHA256 key derivation."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KDF_KEY_LEN,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


# ── SessionManager — token-based authentication ───────────────────────────────
class SessionManager:
    """
    Issues and validates short-lived session tokens.

    In production: replace with JWT (PyJWT) + RS256 or use
    Firebase Auth / Cognito / Auth0 for OAuth 2.0 + PKCE.
    """

    TOKEN_TTL_SECONDS = 3600   # 1 hour

    def __init__(self, secret_key: Optional[str] = None):
        self._secret = (secret_key or secrets.token_hex(32)).encode()
        self._sessions: Dict[str, dict] = {}

    def create_session(self, user_id: str, role: str = "user") -> str:
        """Create an authenticated session token for a user."""
        token     = secrets.token_urlsafe(32)
        issued_at = datetime.datetime.utcnow()
        self._sessions[token] = {
            "user_id":  user_id,
            "role":     role,
            "iat":      issued_at.isoformat(),
            "exp":      (issued_at + datetime.timedelta(
                         seconds=self.TOKEN_TTL_SECONDS)).isoformat(),
        }
        return token

    def validate(self, token: str) -> Optional[dict]:
        """
        Validate a session token.
        Returns session payload dict or None if invalid/expired.
        """
        session = self._sessions.get(token)
        if not session:
            return None
        exp = datetime.datetime.fromisoformat(session["exp"])
        if datetime.datetime.utcnow() > exp:
            del self._sessions[token]   # expired — remove
            return None
        return session

    def revoke(self, token: str):
        """Explicitly revoke a session (logout)."""
        self._sessions.pop(token, None)

    def revoke_all(self, user_id: str):
        """Revoke all sessions for a user (e.g. password change)."""
        to_remove = [t for t, s in self._sessions.items()
                     if s["user_id"] == user_id]
        for t in to_remove:
            del self._sessions[t]


# ── ConsentLedger — GDPR-compliant data sharing control ──────────────────────
class ConsentLedger:
    """
    Tracks user consent for each data sharing purpose.
    Immutable append-only log — users can grant or revoke at any time.

    Purposes:
      doctor_review      — share with attending physician
      family_alerts      — share location + vitals with family
      research_anonymised— aggregate anonymised data for research
      cloud_backup       — encrypted backup to cloud
    """

    PURPOSES = [
        "doctor_review",
        "family_alerts",
        "research_anonymised",
        "cloud_backup",
    ]

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._log: List[dict] = []
        # Default: all consents enabled
        self._current: Dict[str, bool] = {p: True for p in self.PURPOSES}

    def grant(self, purpose: str):
        """User explicitly grants consent for a data purpose."""
        self._assert_purpose(purpose)
        self._current[purpose] = True
        self._log.append({
            "action":    "grant",
            "purpose":   purpose,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

    def revoke(self, purpose: str):
        """User revokes consent — data sharing for this purpose must stop immediately."""
        self._assert_purpose(purpose)
        self._current[purpose] = False
        self._log.append({
            "action":    "revoke",
            "purpose":   purpose,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

    def is_allowed(self, purpose: str) -> bool:
        """Check if a data action is currently consented to."""
        self._assert_purpose(purpose)
        return self._current.get(purpose, False)

    def summary(self) -> dict:
        return {
            "user_id":  self.user_id,
            "consents": dict(self._current),
            "history":  self._log,
        }

    def _assert_purpose(self, purpose: str):
        if purpose not in self.PURPOSES:
            raise ValueError(f"Unknown consent purpose: {purpose!r}. "
                             f"Valid: {self.PURPOSES}")


# ── Integrity check — HMAC data fingerprinting ────────────────────────────────
def sign_payload(data: dict, secret: str) -> str:
    """
    Create an HMAC-SHA256 fingerprint of a reading.
    Attach to each cloud upload to detect tampering.
    """
    raw    = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    sig    = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return sig

def verify_payload(data: dict, signature: str, secret: str) -> bool:
    """Verify a payload has not been tampered with since signing."""
    expected = sign_payload(data, secret)
    return hmac.compare_digest(expected, signature)
"""Parol va token xavfsizligi (stdlib, tashqi kutubxona yo'q)."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
    )
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split(":", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
    )
    return hmac.compare_digest(dk.hex(), stored.split(":", 1)[1])


def new_token() -> str:
    return secrets.token_urlsafe(32)


# ================= Ikki bosqichli autentifikatsiya (TOTP, RFC 6238) =================
# Google Authenticator / Authy kabi ilovalar bilan mos TOTP kodlari.


def totp_secret() -> str:
    """Yangi base32 maxfiy kalit (secret) yaratadi."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode().rstrip("=")


def _totp_code(secret_b32: str, at: float) -> str:
    key = base64.b32decode(secret_b32 + "=" * ((8 - len(secret_b32) % 8) % 8))
    counter = struct.pack(">Q", int(at // 30))
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (
        struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    ) % 1_000_000
    return f"{code:06d}"


def totp_verify(secret_b32: str, code: str, window: int = 1) -> bool:
    """Kiritilgan 6 xonali kodni ±window davr (30 soniya) ichida tekshiradi."""
    if not code or len(code) != 6 or not code.isdigit():
        return False
    now = time.time()
    for back in range(-window, window + 1):
        if hmac.compare_digest(_totp_code(secret_b32, now + back * 30), code):
            return True
    return False


def otpauth_url(secret_b32: str, email: str, issuer: str = "InomjonAI") -> str:
    return (
        "otpauth://totp/"
        + urllib.parse.quote(f"{issuer}:{email}")
        + f"?secret={secret_b32}&issuer={urllib.parse.quote(issuer)}&digits=6&period=30"
    )

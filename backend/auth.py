"""Parol va token xavfsizligi (stdlib, tashqi kutubxona yo'q)."""

import hashlib
import hmac
import secrets

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

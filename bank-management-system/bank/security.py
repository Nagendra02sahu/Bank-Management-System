"""PIN / password hashing using PBKDF2 (standard library only)."""
import hashlib
import hmac
import os

_ITERATIONS = 100_000


def hash_secret(secret: str) -> str:
    """Return 'salt$hash' (both hex) for the given secret."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    """Check a secret against a stored 'salt$hash' value."""
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)

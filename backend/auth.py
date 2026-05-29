import hashlib
import hmac
import secrets
import json
import base64
import time

# Generate a random secret at startup (changes on restart, invalidates all tokens)
TOKEN_SECRET = secrets.token_bytes(32)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, stored = hashed.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(dk.hex(), stored)
    except (ValueError, AttributeError):
        return False


def create_token(user_id: int) -> str:
    payload = {"uid": user_id, "iat": int(time.time()), "exp": int(time.time()) + 86400 * 7}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(TOKEN_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> int | None:
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(TOKEN_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return None
        # Pad for base64 decode
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += "=" * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload["exp"] < time.time():
            return None
        return payload["uid"]
    except Exception:
        return None


def get_token_secret_for_cookie() -> bytes:
    return TOKEN_SECRET

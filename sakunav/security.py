"""安全工具：密码哈希与 CSRF 令牌。

- 密码使用 PBKDF2-HMAC-SHA256（标准库实现，无额外依赖），盐随机生成；
- CSRF 令牌与会话绑定，全程签名 Cookie 防篡改。
"""

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """返回格式：pbkdf2_sha256$iterations$salt_hex$digest_hex"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, TypeError):
        return False


def csrf_token(session: dict) -> str:
    """取回或生成会话绑定的 CSRF 令牌（同一会话内保持稳定）。"""
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf"] = token
    return token


def verify_csrf(session: dict, token: str) -> bool:
    return bool(token) and hmac.compare_digest(session.get("csrf", ""), token)

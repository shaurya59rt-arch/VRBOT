import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl


def is_admin(user_id: int, admin_ids: set[int]) -> bool:
    return user_id in admin_ids


def display_name(user) -> str:
    return user.full_name or user.first_name


def make_referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def random_bonus(max_amount: float) -> float:
    minimum = max(1, int(max_amount * 0.5))
    return float(random.randint(minimum, max(int(max_amount), minimum)))


def format_money(value: float) -> str:
    return f"{value:.2f}"


def parse_float(text: str) -> float:
    return round(float(text.strip()), 2)


def telegram_webapp_validate(init_data: str, bot_token: str) -> dict | None:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    auth_date = int(pairs.get("auth_date", "0"))
    if not auth_date or abs(time.time() - auth_date) > 86400:
        return None

    user_payload = pairs.get("user")
    if not user_payload:
        return None
    return json.loads(user_payload)


def fingerprint_from_request(ip: str | None, user_agent: str | None) -> str:
    payload = f"{ip or ''}|{user_agent or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()


def human_datetime(dt) -> str:
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    webapp_base_url: str
    host: str
    port: int
    db_path: str


def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            result.add(int(part))
    return result


def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    db_path = os.getenv("DB_PATH", str(root / "data" / "bot.db"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    token = os.getenv("BOT_TOKEN", "8417164599:AAFgQtmpdzlZHSAz1qVCJb2Ol22rJ7cxNEM").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required.")

    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "7117775366")),
        webapp_base_url=os.getenv("WEBAPP_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        db_path=db_path,
    )


settings = load_settings()

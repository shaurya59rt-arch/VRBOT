from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()

    async def fetchone(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def init(self) -> None:
        assert self.conn is not None
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                balance REAL NOT NULL DEFAULT 0,
                wallet TEXT,
                referred_by INTEGER,
                referrals_count INTEGER NOT NULL DEFAULT 0,
                is_verified INTEGER NOT NULL DEFAULT 0,
                is_banned INTEGER NOT NULL DEFAULT 0,
                is_suspicious INTEGER NOT NULL DEFAULT 0,
                referral_rewarded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_bonus_at TEXT,
                verify_ip TEXT,
                verify_ua TEXT,
                verify_fingerprint TEXT,
                last_action_at TEXT
            );

            CREATE TABLE IF NOT EXISTS required_channels (
                chat_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                invite_link TEXT NOT NULL,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                tax_amount REAL NOT NULL,
                net_amount REAL NOT NULL,
                wallet TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                max_uses INTEGER NOT NULL,
                uses_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gift_redemptions (
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                redeemed_at TEXT NOT NULL,
                PRIMARY KEY (code, user_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        await self.conn.commit()
        await self._seed_defaults()

    async def _seed_defaults(self) -> None:
        defaults = {
            "referral_reward": "5",
            "bonus_amount": "10",
            "withdraw_enabled": "1",
            "withdraw_tax_percent": "5",
            "payout_channel": "",
        }
        for key, value in defaults.items():
            await self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self.conn.commit()

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetchone(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        )
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await self.conn.commit()

    async def register_user(
        self,
        user_id: int,
        username: str | None,
        full_name: str,
        referred_by: int | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_user(user_id)
        if existing:
            await self.conn.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id),
            )
            await self.conn.commit()
            return await self.get_user(user_id)

        safe_referred_by = referred_by if referred_by and referred_by != user_id else None
        await self.conn.execute(
            """
            INSERT INTO users (
                user_id, username, full_name, referred_by, created_at, last_action_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, safe_referred_by, utcnow(), utcnow()),
        )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        row = await self.fetchone(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    async def set_wallet(self, user_id: int, wallet: str) -> None:
        await self.conn.execute(
            "UPDATE users SET wallet = ? WHERE user_id = ?",
            (wallet, user_id),
        )
        await self.conn.commit()

    async def adjust_balance(self, user_id: int, amount: float) -> None:
        await self.conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.conn.commit()

    async def set_balance(self, user_id: int, amount: float) -> None:
        await self.conn.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.conn.commit()

    async def can_claim_bonus(self, user_id: int) -> tuple[bool, datetime | None]:
        user = await self.get_user(user_id)
        if not user or not user["last_bonus_at"]:
            return True, None
        last_bonus = datetime.fromisoformat(user["last_bonus_at"])
        next_time = last_bonus + timedelta(hours=24)
        return datetime.now(timezone.utc) >= next_time, next_time

    async def claim_bonus(self, user_id: int, amount: float) -> None:
        await self.conn.execute(
            "UPDATE users SET balance = balance + ?, last_bonus_at = ? WHERE user_id = ?",
            (amount, utcnow(), user_id),
        )
        await self.conn.commit()

    async def add_channel(self, chat_id: int, title: str, invite_link: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO required_channels (chat_id, title, invite_link, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                invite_link = excluded.invite_link
            """,
            (chat_id, title, invite_link, utcnow()),
        )
        await self.conn.commit()

    async def remove_channel(self, chat_id: int) -> None:
        await self.conn.execute("DELETE FROM required_channels WHERE chat_id = ?", (chat_id,))
        await self.conn.commit()

    async def get_channels(self) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT * FROM required_channels ORDER BY added_at DESC"
        )
        return [dict(row) for row in rows]

    async def create_withdrawal(
        self,
        user_id: int,
        amount: float,
        tax_amount: float,
        net_amount: float,
        wallet: str,
    ) -> int:
        await self.conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id),
        )
        cursor = await self.conn.execute(
            """
            INSERT INTO withdrawals (user_id, amount, tax_amount, net_amount, wallet, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, amount, tax_amount, net_amount, wallet, utcnow()),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def list_withdrawals(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT * FROM withdrawals ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    async def create_gift_code(
        self,
        code: str,
        amount: float,
        max_uses: int,
        created_by: int,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO gift_codes (code, amount, max_uses, created_at, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code.upper(), amount, max_uses, utcnow(), created_by),
        )
        await self.conn.commit()

    async def list_gift_codes(self) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT * FROM gift_codes ORDER BY created_at DESC"
        )
        return [dict(row) for row in rows]

    async def redeem_gift_code(self, user_id: int, code: str) -> tuple[bool, str, float]:
        code = code.upper()
        gift = await self.fetchone(
            "SELECT * FROM gift_codes WHERE code = ?",
            (code,),
        )
        if not gift:
            return False, "This gift code does not exist.", 0
        if not gift["is_active"]:
            return False, "This gift code is inactive.", 0
        if gift["uses_count"] >= gift["max_uses"]:
            return False, "This gift code has reached its usage limit.", 0

        already = await self.fetchone(
            "SELECT 1 FROM gift_redemptions WHERE code = ? AND user_id = ?",
            (code, user_id),
        )
        if already:
            return False, "You have already redeemed this gift code.", 0

        await self.conn.execute(
            "INSERT INTO gift_redemptions (code, user_id, redeemed_at) VALUES (?, ?, ?)",
            (code, user_id, utcnow()),
        )
        await self.conn.execute(
            "UPDATE gift_codes SET uses_count = uses_count + 1 WHERE code = ?",
            (code,),
        )
        await self.conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (gift["amount"], user_id),
        )
        await self.conn.commit()
        return True, "Gift code redeemed successfully.", float(gift["amount"])

    async def set_ban_status(self, user_id: int, is_banned: bool) -> None:
        await self.conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if is_banned else 0, user_id),
        )
        await self.conn.commit()

    async def mark_user_verified(
        self,
        user_id: int,
        ip: str | None,
        user_agent: str | None,
        fingerprint: str,
    ) -> tuple[bool, float]:
        user = await self.get_user(user_id)
        if not user:
            return False, 0

        suspicious = False
        if ip:
            count_row = await self.fetchone(
                """
                SELECT COUNT(*) AS total
                FROM users
                WHERE verify_ip = ?
                  AND created_at >= ?
                """,
                (ip, (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()),
            )
            suspicious = count_row["total"] >= 3

        await self.conn.execute(
            """
            UPDATE users
            SET is_verified = 1,
                is_suspicious = ?,
                verify_ip = ?,
                verify_ua = ?,
                verify_fingerprint = ?
            WHERE user_id = ?
            """,
            (1 if suspicious else 0, ip, user_agent, fingerprint, user_id),
        )

        reward_amount = 0.0
        refreshed = await self.get_user(user_id)
        referral_reward = float(await self.get_setting("referral_reward", "0"))
        if (
            refreshed
            and refreshed["referred_by"]
            and not refreshed["referral_rewarded"]
            and not refreshed["is_suspicious"]
            and refreshed["referred_by"] != user_id
        ):
            reward_amount = referral_reward
            await self.conn.execute(
                """
                UPDATE users
                SET balance = balance + ?,
                    referrals_count = referrals_count + 1
                WHERE user_id = ?
                """,
                (reward_amount, refreshed["referred_by"]),
            )
            await self.conn.execute(
                "UPDATE users SET referral_rewarded = 1 WHERE user_id = ?",
                (user_id,),
            )

        await self.conn.commit()
        return True, reward_amount

    async def stats(self) -> dict[str, Any]:
        users_row = await self.fetchone("SELECT COUNT(*) AS total FROM users")
        verified_row = await self.fetchone(
            "SELECT COUNT(*) AS total FROM users WHERE is_verified = 1"
        )
        withdrawals_row = await self.fetchone(
            "SELECT COUNT(*) AS total FROM withdrawals"
        )
        return {
            "users": users_row["total"],
            "verified": verified_row["total"],
            "withdrawals": withdrawals_row["total"],
        }

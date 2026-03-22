from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import Database
from app.utils import fingerprint_from_request, telegram_webapp_validate


def create_app(bot, db: Database, settings) -> FastAPI:
    app = FastAPI(title="Telegram Earning Bot WebApp")
    static_dir = Path(__file__).resolve().parent / "web_static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/verify")
    async def verify_page():
        return FileResponse(static_dir / "verify.html")

    @app.post("/api/verify")
    async def verify_api(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"ok": False, "message": "Invalid request payload."},
                status_code=400,
            )
        init_data = body.get("init_data", "")
        payload = telegram_webapp_validate(init_data, settings.bot_token)
        if not payload:
            return JSONResponse(
                {"ok": False, "message": "Invalid verification session."},
                status_code=400,
            )

        user_id = int(payload["id"])
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        fingerprint = fingerprint_from_request(ip, user_agent)
        verified, reward = await db.mark_user_verified(user_id, ip, user_agent, fingerprint)
        if not verified:
            return JSONResponse(
                {"ok": False, "message": "User is not registered in the bot yet."},
                status_code=404,
            )

        try:
            if reward > 0:
                user = await db.get_user(user_id)
                if user and user["referred_by"]:
                    await bot.send_message(
                        user["referred_by"],
                        f"🎉 Referral reward credited: <b>{reward:.2f}</b>",
                    )
            await bot.send_message(
                user_id,
                "✅ Verification completed successfully. Return to the bot to continue.",
            )
        except Exception:
            pass

        return {"ok": True, "message": "Verification completed.", "reward": reward}

    return app

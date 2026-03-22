# Telegram Earning Bot

Single-repository Telegram earning bot built with `aiogram v3` and `FastAPI`.

## Features

- User registration, balances, wallet storage, referrals
- Required channel join enforcement with invite link generation
- Telegram Mini App verification flow
- Daily bonus with cooldown
- Withdraw requests with tax support
- Gift code creation and redemption
- Admin panel with channel, balance, bonus, referral, payout, ban, and user messaging controls
- Auto-approval of join requests for configured channels
- Basic anti-spam and multi-account abuse protection

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your values.
4. Start the bot:

```bash
python main.py
```

## Important Note About Mini App URL

Telegram Web Apps must use a reachable URL in real usage. This project hosts the backend inside the same repository and process, but `WEBAPP_BASE_URL` still needs to point to that running server with a Telegram-compatible URL.

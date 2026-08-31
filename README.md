# trade-bot

Auto-trading bot for XM (MetaTrader 5) with pluggable strategies and Telegram
notifications, formatted like:

```
📡 btc_scalp เข้าไม้จริง
SELL BTCUSD.s 0.02 @ 62479.84 🔴
SL 61932.68
เงื่อนไข: -
🧩 #60201154
```

```
🐝 btc_scalp ปิดไม้ BTCUSD
💰 +0.10$ ✅ · trail/SL (virtual +27.16)
balance 987.45 · equity 997.94
```

## How it works

- `src/strategies/` — one class per strategy (`btc_scalp`, `btc_m15`,
  `ai_trader`). Each only decides BUY/SELL/None from OHLC candles; the
  ships-with logic is a simple EMA/RSI example meant to be tuned or replaced,
  not a proven-profitable system.
- `src/trade_manager.py` — polls each strategy, opens trades, tracks an
  internal ("virtual") trailing stop per position, and closes trades either
  on a hard SL breach or once price gives back `trail_distance_pips` from its
  best point.
- `src/mt5_client.py` — `MT5Client` wraps the real `MetaTrader5` package;
  `MockMT5Client` simulates prices/account/positions so you can run and watch
  the bot without a live connection.
- `src/telegram_notifier.py` — formats and sends the entry/close messages
  shown above.

## Important: MT5 is Windows-only

The `MetaTrader5` Python package talks to a locally running MT5 terminal via
IPC and **only works on Windows** (or a Windows VPS). For live trading with
XM you need:

1. MT5 terminal installed and logged into your XM account (demo or live).
2. This bot running on that same Windows machine, with `DRY_RUN=false`.

On Linux/Mac (including this dev container) run with `DRY_RUN=true` — the
bot uses `MockMT5Client` to simulate everything, so you can verify strategy
logic and the exact Telegram message format before deploying to Windows.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
cp config/config.example.yaml config/config.yaml
```

Edit `.env`:
- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather) (`/newbot`).
- `TELEGRAM_CHAT_ID` — the chat/group/channel id to post into (add the bot to
  the group, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`
  after sending a message, or use a helper bot like @userinfobot / @RawDataBot).
- `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` — from your XM MT5 account
  (server name looks like `XMGlobal-MT5` or `XMGlobal-MT5 3`, exact string is
  shown in the MT5 terminal's login window).
- `DRY_RUN` — `true` to test safely, `false` for real orders.

Edit `config/config.yaml` to enable/disable strategies, symbols, lot size,
SL distance, and trailing behavior.

## Run

```bash
python main.py
```

Ctrl+C to stop (shuts down the MT5 connection cleanly).

## Notes / next steps

- `ai_trader` ships disabled with a placeholder heuristic (EMA slope vs ATR)
  — `src/strategies/ai_trader.py` has a `TODO` marking where to load a real
  trained model.
- SL is set on the broker at order time; the trailing stop is managed by the
  bot itself (a "virtual" trail, matching `trail/SL (virtual +X)` in the
  close message) rather than modifying the broker-side SL on every tick.
- Trading involves real financial risk. Test thoroughly on a demo XM account
  with `DRY_RUN=false` before ever pointing this at a live account, and treat
  the bundled strategies as starting points, not trading advice.

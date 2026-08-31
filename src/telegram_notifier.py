"""Sends trade notifications to Telegram in the house message format:

    entry:
        📡 btc_scalp เข้าไม้จริง
        SELL BTCUSD.s 0.02 @ 62479.84 🔴
        SL 61932.68
        เงื่อนไข: -
        🧩 #60201154

    close:
        🐝 btc_scalp ปิดไม้ BTCUSD
        💰 +0.10$ ✅ · trail/SL (virtual +27.16)
        balance 987.45 · equity 997.94
"""
from __future__ import annotations

import logging

import requests

from .risk import pip_size

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _strip_broker_suffix(symbol: str) -> str:
    """BTCUSD.s -> BTCUSD (close messages show the plain symbol)."""
    return symbol[:-2] if symbol.endswith(".s") else symbol


def _decimals_for(symbol: str) -> int:
    size = pip_size(symbol)
    if size == 1.0:  # BTC/ETH-style
        return 2
    if size == 0.01:  # JPY pairs
        return 3
    if size == 0.1:  # XAU
        return 2
    return 5  # standard 4/5-digit FX


def _format_price(value: float, symbol: str) -> str:
    return f"{value:.{_decimals_for(symbol)}f}"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, dry_run: bool = False):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.dry_run = dry_run

    def _send(self, text: str) -> None:
        if self.dry_run or not self.bot_token:
            logger.info("[telegram:dry_run]\n%s", text)
            return
        try:
            resp = requests.post(
                TELEGRAM_API_URL.format(token=self.bot_token),
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to send Telegram message")

    def send_entry(
        self,
        strategy_name: str,
        symbol: str,
        direction: str,  # "BUY" | "SELL"
        volume: float,
        price: float,
        sl: float,
        ticket: int,
        condition: str = "-",
    ) -> None:
        dir_emoji = "🟢" if direction == "BUY" else "🔴"
        text = (
            f"📡 {strategy_name} เข้าไม้จริง\n"
            f"{direction} {symbol} {volume} @ {_format_price(price, symbol)} {dir_emoji}\n"
            f"SL {_format_price(sl, symbol)}\n"
            f"เงื่อนไข: {condition}\n"
            f"🧩 #{ticket}"
        )
        self._send(text)

    def send_close(
        self,
        strategy_name: str,
        symbol: str,
        pnl: float,
        balance: float,
        equity: float,
        reason: str,
        virtual_value: float | None = None,
    ) -> None:
        result_emoji = "✅" if pnl >= 0 else "❌"
        sign = "+" if pnl >= 0 else ""
        reason_text = reason
        if virtual_value is not None:
            v_sign = "+" if virtual_value >= 0 else ""
            reason_text = f"{reason} (virtual {v_sign}{_format_price(virtual_value, symbol)})"

        text = (
            f"🐝 {strategy_name} ปิดไม้ {_strip_broker_suffix(symbol)}\n"
            f"💰 {sign}{pnl:.2f}$ {result_emoji} · {reason_text}\n"
            f"balance {balance:.2f} · equity {equity:.2f}"
        )
        self._send(text)

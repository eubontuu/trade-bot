"""Entry point.

Usage:
    cp .env.example .env               # fill in Telegram + MT5 credentials
    cp config/config.example.yaml config/config.yaml   # tune strategies
    pip install -r requirements.txt
    python main.py
"""
from __future__ import annotations

import logging
import signal
import sys
import time

from src.config import load_config
from src.mt5_client import MockMT5Client, MT5Client
from src.telegram_notifier import TelegramNotifier
from src.trade_manager import TradeManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("trade_bot")

_running = True


def _handle_stop(signum, frame):
    global _running
    logger.info("Received signal %s, shutting down...", signum)
    _running = False


def main() -> int:
    config = load_config()

    if not config.telegram.bot_token or not config.telegram.chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set -- messages will only be logged.")

    notifier = TelegramNotifier(
        bot_token=config.telegram.bot_token,
        chat_id=config.telegram.chat_id,
        dry_run=config.dry_run,
    )

    if config.dry_run:
        logger.info("DRY_RUN=true -- using simulated MT5 client, no real orders will be placed.")
        client = MockMT5Client(starting_balance=1000.0)
    else:
        client = MT5Client(
            login=config.mt5.login,
            password=config.mt5.password,
            server=config.mt5.server,
            terminal_path=config.mt5.terminal_path,
        )

    manager = TradeManager(config, client, notifier)
    if not manager.strategies:
        logger.warning("No enabled strategies found in config -- nothing to do.")

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    logger.info("Starting main loop (poll every %ss)...", config.poll_interval_seconds)
    while _running:
        manager.run_once()
        time.sleep(config.poll_interval_seconds)

    if isinstance(client, MT5Client):
        client.shutdown()
    logger.info("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

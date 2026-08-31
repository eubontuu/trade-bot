"""Loads settings from .env and config/config.yaml into plain dataclasses."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass
class MT5Config:
    login: int
    password: str
    server: str
    terminal_path: str


@dataclass
class StrategyConfig:
    name: str
    enabled: bool
    symbol: str
    timeframe: str
    magic: int
    lot: float
    sl_pips: float
    trail_start_pips: float
    trail_distance_pips: float
    params: dict = field(default_factory=dict)


@dataclass
class AppConfig:
    dry_run: bool
    poll_interval_seconds: int
    telegram: TelegramConfig
    mt5: MT5Config
    strategies: list[StrategyConfig]


def load_config(config_path: str | None = None) -> AppConfig:
    path = Path(config_path or os.getenv("CONFIG_PATH", "config/config.yaml"))
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found at {path}. "
            "Copy config/config.example.yaml to config/config.yaml and edit it."
        )

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    strategies = [
        StrategyConfig(
            name=s["name"],
            enabled=bool(s.get("enabled", True)),
            symbol=s["symbol"],
            timeframe=s["timeframe"],
            magic=int(s["magic"]),
            lot=float(s["lot"]),
            sl_pips=float(s["sl_pips"]),
            trail_start_pips=float(s["trail_start_pips"]),
            trail_distance_pips=float(s["trail_distance_pips"]),
            params=s.get("params", {}) or {},
        )
        for s in raw.get("strategies", [])
    ]

    return AppConfig(
        dry_run=_env_bool("DRY_RUN", True),
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 5)),
        telegram=TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        ),
        mt5=MT5Config(
            login=int(os.getenv("MT5_LOGIN", "0") or 0),
            password=os.getenv("MT5_PASSWORD", ""),
            server=os.getenv("MT5_SERVER", ""),
            terminal_path=os.getenv("MT5_TERMINAL_PATH", ""),
        ),
        strategies=strategies,
    )

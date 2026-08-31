"""MT5 connection layer.

Two implementations share the same interface so TradeManager never has to
know which one it's talking to:

- MT5Client:  wraps the real `MetaTrader5` package. Only importable/usable on
  Windows with an MT5 terminal installed and logged into an XM account.
- MockMT5Client: simulates prices/account/positions in-memory. Used when
  DRY_RUN=true so the bot (and this message format) can be exercised
  anywhere, including this Linux dev environment.
"""
from __future__ import annotations

import itertools
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TIMEFRAME_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


@dataclass
class AccountInfo:
    balance: float
    equity: float


@dataclass
class Position:
    ticket: int
    symbol: str
    magic: int
    direction: str  # "BUY" | "SELL"
    volume: float
    price_open: float
    sl: float
    price_current: float
    profit: float


@dataclass
class ClosedDeal:
    ticket: int
    symbol: str
    magic: int
    profit: float
    reason: str  # "sl" | "tp" | "manual"


class MT5Client:
    """Thin wrapper around the real MetaTrader5 package. Windows-only."""

    def __init__(self, login: int, password: str, server: str, terminal_path: str = ""):
        try:
            import MetaTrader5 as mt5  # noqa: N814
        except ImportError as exc:  # pragma: no cover - Windows-only dependency
            raise RuntimeError(
                "MetaTrader5 package is not available on this platform. "
                "Run the bot with DRY_RUN=true here, and deploy on a Windows "
                "machine with the MT5 terminal + XM login for live trading."
            ) from exc

        self._mt5 = mt5
        if not mt5.initialize(path=terminal_path or None, login=login, password=password, server=server):
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")
        logger.info("Connected to MT5 as %s on %s", login, server)

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def get_account_info(self) -> AccountInfo:
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info() failed: {self._mt5.last_error()}")
        return AccountInfo(balance=info.balance, equity=info.equity)

    def get_rates(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        tf_const = getattr(self._mt5, f"TIMEFRAME_{timeframe}")
        rates = self._mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
        if rates is None:
            raise RuntimeError(f"copy_rates_from_pos({symbol}) failed: {self._mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def get_price(self, symbol: str, direction: str) -> float:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick({symbol}) failed: {self._mt5.last_error()}")
        return tick.ask if direction == "BUY" else tick.bid

    def get_positions(self, magic: int | None = None) -> list[Position]:
        raw = self._mt5.positions_get(magic=magic) if magic is not None else self._mt5.positions_get()
        if raw is None:
            return []
        out = []
        for p in raw:
            direction = "BUY" if p.type == self._mt5.ORDER_TYPE_BUY else "SELL"
            out.append(
                Position(
                    ticket=p.ticket,
                    symbol=p.symbol,
                    magic=p.magic,
                    direction=direction,
                    volume=p.volume,
                    price_open=p.price_open,
                    sl=p.sl,
                    price_current=p.price_current,
                    profit=p.profit,
                )
            )
        return out

    def open_order(
        self, symbol: str, direction: str, volume: float, sl: float, magic: int, comment: str = ""
    ) -> Position:
        mt5 = self._mt5
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if direction == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"order_send failed: retcode={result.retcode} comment={result.comment}")

        return Position(
            ticket=result.order,
            symbol=symbol,
            magic=magic,
            direction=direction,
            volume=volume,
            price_open=result.price,
            sl=sl,
            price_current=result.price,
            profit=0.0,
        )

    def close_position(self, position: Position) -> float:
        mt5 = self._mt5
        tick = mt5.symbol_info_tick(position.symbol)
        close_type = mt5.ORDER_TYPE_SELL if position.direction == "BUY" else mt5.ORDER_TYPE_BUY
        price = tick.bid if position.direction == "BUY" else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": price,
            "magic": position.magic,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"close order_send failed: retcode={result.retcode} comment={result.comment}")
        return position.profit


class MockMT5Client:
    """Simulated broker for DRY_RUN=true. Deterministic-ish random walk prices."""

    def __init__(self, starting_balance: float = 1000.0, seed: int | None = None):
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)
        self._balance = starting_balance
        self._equity = starting_balance
        self._positions: dict[int, Position] = {}
        self._ticket_seq = itertools.count(60_200_000)
        self._price_state: dict[str, float] = {}

    def _base_price(self, symbol: str) -> float:
        if symbol not in self._price_state:
            self._price_state[symbol] = 60_000.0 if "BTC" in symbol else 2400.0
        return self._price_state[symbol]

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(balance=self._balance, equity=self._equity)

    def get_price(self, symbol: str, direction: str) -> float:
        return self._base_price(symbol)

    def get_rates(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        minutes = TIMEFRAME_MINUTES.get(timeframe, 1)
        base = self._base_price(symbol)
        vol = base * 0.0015
        steps = self._np_rng.normal(loc=0.0, scale=vol, size=count).cumsum()
        closes = base + steps
        now = datetime.utcnow()
        times = [now - timedelta(minutes=minutes * (count - i)) for i in range(count)]

        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        highs = np.maximum(opens, closes) + np.abs(self._np_rng.normal(0, vol * 0.3, count))
        lows = np.minimum(opens, closes) - np.abs(self._np_rng.normal(0, vol * 0.3, count))

        self._price_state[symbol] = float(closes[-1])

        return pd.DataFrame(
            {
                "time": times,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "tick_volume": self._np_rng.integers(10, 500, count),
            }
        )

    def get_positions(self, magic: int | None = None) -> list[Position]:
        positions = list(self._positions.values())
        if magic is not None:
            positions = [p for p in positions if p.magic == magic]
        return [self._mark_to_market(p) for p in positions]

    def _mark_to_market(self, position: Position) -> Position:
        price = self._base_price(position.symbol)
        direction_sign = 1 if position.direction == "BUY" else -1
        price_diff = (price - position.price_open) * direction_sign
        position.price_current = price
        position.profit = price_diff * position.volume
        return position

    def open_order(
        self, symbol: str, direction: str, volume: float, sl: float, magic: int, comment: str = ""
    ) -> Position:
        price = self._base_price(symbol)
        ticket = next(self._ticket_seq)
        position = Position(
            ticket=ticket,
            symbol=symbol,
            magic=magic,
            direction=direction,
            volume=volume,
            price_open=price,
            sl=sl,
            price_current=price,
            profit=0.0,
        )
        self._positions[ticket] = position
        logger.info("[mock] opened %s %s %s @ %.2f ticket=%s", direction, volume, symbol, price, ticket)
        return position

    def close_position(self, position: Position) -> float:
        live = self._positions.pop(position.ticket, position)
        live = self._mark_to_market(live)
        self._balance += live.profit
        self._equity = self._balance
        logger.info("[mock] closed ticket=%s pnl=%.2f", live.ticket, live.profit)
        return live.profit

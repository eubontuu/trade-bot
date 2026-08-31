"""Ties strategies + MT5 client + Telegram notifier together.

Each poll cycle, per enabled strategy:
  - no open position for its magic number -> ask the strategy for a signal;
    if BUY/SELL, place the order and send the "เข้าไม้จริง" message.
  - open position exists -> update the internal virtual trailing stop; if
    price has given back `trail_distance_pips` from its best point (once it
    reached `trail_start_pips`), close the trade and send the "ปิดไม้"
    message with realized pnl + balance/equity. A hard stop-loss breach is
    reported the same way with reason "SL" instead of "trail/SL".
"""
from __future__ import annotations

import logging

from .config import AppConfig, StrategyConfig
from .mt5_client import MT5Client, MockMT5Client, Position
from .risk import compute_sl, favorable_excursion, pip_size
from .strategies import STRATEGY_REGISTRY
from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

MT5ClientType = MT5Client | MockMT5Client


class TradeManager:
    def __init__(self, config: AppConfig, client: MT5ClientType, notifier: TelegramNotifier):
        self.config = config
        self.client = client
        self.notifier = notifier

        self.strategies = []
        for sc in config.strategies:
            if not sc.enabled:
                continue
            strategy_cls = STRATEGY_REGISTRY.get(sc.name)
            if strategy_cls is None:
                logger.warning("Unknown strategy %r in config, skipping", sc.name)
                continue
            strategy = strategy_cls(sc.name, sc.symbol, sc.timeframe, sc.magic, sc.params)
            self.strategies.append((sc, strategy))

        # ticket -> best favorable excursion seen so far (price units)
        self._peak_favorable: dict[int, float] = {}

    def run_once(self) -> None:
        for sc, strategy in self.strategies:
            try:
                self._process_strategy(sc, strategy)
            except Exception:
                logger.exception("Error processing strategy %s", sc.name)

    def _process_strategy(self, sc: StrategyConfig, strategy) -> None:
        positions = self.client.get_positions(magic=sc.magic)

        if positions:
            for position in positions:
                self._manage_open_position(sc, position)
            return

        bars_needed = max(200, getattr(strategy, "min_bars", 50) + 20)
        rates = self.client.get_rates(sc.symbol, sc.timeframe, count=bars_needed)
        signal = strategy.generate_signal(rates)
        if signal:
            self._open_trade(sc, signal)

    def _open_trade(self, sc: StrategyConfig, direction: str) -> None:
        try:
            estimated_price = self.client.get_price(sc.symbol, direction)
            sl = compute_sl(estimated_price, direction, sc.sl_pips, sc.symbol)
            position = self.client.open_order(
                symbol=sc.symbol,
                direction=direction,
                volume=sc.lot,
                sl=sl,
                magic=sc.magic,
                comment=sc.name,
            )
        except Exception:
            logger.exception("Failed to open %s %s for %s", direction, sc.symbol, sc.name)
            return

        logger.info(
            "%s: %s %s %s @ %s ticket=%s", sc.name, direction, sc.symbol, sc.lot, position.price_open, position.ticket
        )
        self.notifier.send_entry(
            strategy_name=sc.name,
            symbol=sc.symbol,
            direction=direction,
            volume=sc.lot,
            price=position.price_open,
            sl=position.sl,
            ticket=position.ticket,
        )

    def _manage_open_position(self, sc: StrategyConfig, position: Position) -> None:
        pip = pip_size(sc.symbol)
        fav = favorable_excursion(position.direction, position.price_open, position.price_current)

        peak = max(self._peak_favorable.get(position.ticket, 0.0), fav)
        self._peak_favorable[position.ticket] = peak

        hard_sl_hit = (
            (position.direction == "BUY" and position.price_current <= position.sl)
            or (position.direction == "SELL" and position.price_current >= position.sl)
        )
        trailing_armed = peak >= sc.trail_start_pips * pip
        trailing_hit = trailing_armed and fav <= peak - sc.trail_distance_pips * pip

        if hard_sl_hit:
            self._close_trade(sc, position, reason="SL")
        elif trailing_hit:
            self._close_trade(sc, position, reason="trail/SL", virtual_value=peak)

    def _close_trade(
        self, sc: StrategyConfig, position: Position, reason: str, virtual_value: float | None = None
    ) -> None:
        try:
            pnl = self.client.close_position(position)
        except Exception:
            logger.exception("Failed to close ticket=%s for %s", position.ticket, sc.name)
            return

        self._peak_favorable.pop(position.ticket, None)
        account = self.client.get_account_info()

        logger.info("%s: closed ticket=%s pnl=%.2f reason=%s", sc.name, position.ticket, pnl, reason)
        self.notifier.send_close(
            strategy_name=sc.name,
            symbol=sc.symbol,
            pnl=pnl,
            balance=account.balance,
            equity=account.equity,
            reason=reason,
            virtual_value=virtual_value,
        )

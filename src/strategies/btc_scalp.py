"""Example fast scalping strategy: EMA(fast) / EMA(slow) crossover on low timeframe.

This is a simple, transparent starting point -- tune fast_ema/slow_ema in
config/config.yaml, or replace generate_signal entirely with your own logic.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema
from .base import Signal, Strategy


class BtcScalpStrategy(Strategy):
    min_bars = 60

    def generate_signal(self, rates: pd.DataFrame) -> Signal:
        if len(rates) < self.min_bars:
            return None

        fast_period = int(self.params.get("fast_ema", 5))
        slow_period = int(self.params.get("slow_ema", 13))

        fast = ema(rates["close"], fast_period)
        slow = ema(rates["close"], slow_period)

        prev_fast, prev_slow = fast.iloc[-2], slow.iloc[-2]
        last_fast, last_slow = fast.iloc[-1], slow.iloc[-1]

        crossed_up = prev_fast <= prev_slow and last_fast > last_slow
        crossed_down = prev_fast >= prev_slow and last_fast < last_slow

        if crossed_up:
            return "BUY"
        if crossed_down:
            return "SELL"
        return None

"""Example M15 swing strategy: EMA(fast)/EMA(slow) trend filter + RSI confirmation.

Trades in the direction of the EMA trend only when RSI confirms momentum,
which filters out more noise than a plain crossover -- suited to a slower
timeframe than btc_scalp. Tune via config/config.yaml `params`.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi
from .base import Signal, Strategy


class BtcM15Strategy(Strategy):
    min_bars = 80

    def generate_signal(self, rates: pd.DataFrame) -> Signal:
        if len(rates) < self.min_bars:
            return None

        fast_period = int(self.params.get("fast_ema", 20))
        slow_period = int(self.params.get("slow_ema", 50))
        rsi_period = int(self.params.get("rsi_period", 14))

        fast = ema(rates["close"], fast_period)
        slow = ema(rates["close"], slow_period)
        rsi_val = rsi(rates["close"], rsi_period)

        prev_fast, prev_slow = fast.iloc[-2], slow.iloc[-2]
        last_fast, last_slow = fast.iloc[-1], slow.iloc[-1]
        last_rsi = rsi_val.iloc[-1]

        crossed_up = prev_fast <= prev_slow and last_fast > last_slow
        crossed_down = prev_fast >= prev_slow and last_fast < last_slow

        if crossed_up and last_rsi > 50:
            return "BUY"
        if crossed_down and last_rsi < 50:
            return "SELL"
        return None

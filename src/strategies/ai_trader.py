"""Placeholder for an ML/AI-driven strategy.

This ships with a simple trend + volatility heuristic (EMA slope filtered by
ATR) purely so the strategy runs end-to-end out of the box. It is NOT a real
model. To use an actual trained model, replace `_predict` with a call to
your classifier/regressor (load it once in __init__ and run inference here).
Disabled by default in config/config.example.yaml until you wire in real logic.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr, ema
from .base import Signal, Strategy


class AiTraderStrategy(Strategy):
    min_bars = 80

    def __init__(self, name: str, symbol: str, timeframe: str, magic: int, params: dict):
        super().__init__(name, symbol, timeframe, magic, params)
        # TODO: load your trained model here, e.g.:
        # self.model = joblib.load(params["model_path"])

    def _predict(self, rates: pd.DataFrame) -> Signal:
        trend = ema(rates["close"], 20)
        volatility = atr(rates, 14)

        slope = trend.iloc[-1] - trend.iloc[-5]
        avg_vol = volatility.iloc[-20:].mean()

        if avg_vol == 0 or pd.isna(avg_vol):
            return None

        # Only trade when the move is meaningfully larger than average noise.
        if slope > avg_vol * 0.5:
            return "BUY"
        if slope < -avg_vol * 0.5:
            return "SELL"
        return None

    def generate_signal(self, rates: pd.DataFrame) -> Signal:
        if len(rates) < self.min_bars:
            return None
        return self._predict(rates)

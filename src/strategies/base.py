"""Base class every strategy plugs into.

A strategy only decides WHEN to enter (BUY/SELL/None) from OHLC data.
Position sizing, SL price, trailing, and order placement all live in
TradeManager / risk.py so every strategy behaves consistently.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional

import pandas as pd

Signal = Optional[Literal["BUY", "SELL"]]


class Strategy(ABC):
    #: minimum number of closed candles needed before generate_signal can decide anything
    min_bars: int = 50

    def __init__(self, name: str, symbol: str, timeframe: str, magic: int, params: dict):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic = magic
        self.params = params

    @abstractmethod
    def generate_signal(self, rates: pd.DataFrame) -> Signal:
        """rates has columns: time, open, high, low, close, tick_volume (oldest first).

        Return "BUY", "SELL", or None (no trade).
        """
        raise NotImplementedError

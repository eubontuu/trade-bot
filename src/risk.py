"""Price-unit helpers shared by every strategy's SL/trailing calculations.

`sl_pips` / `trail_*_pips` in config/config.yaml are expressed in "price
units" (a whole dollar for BTCUSD, 0.1 for XAUUSD, 0.0001 for a 4-digit FX
pair) rather than broker fractional pips -- simpler to reason about across
very different instruments.
"""
from __future__ import annotations


def pip_size(symbol: str) -> float:
    upper = symbol.upper()
    if upper.startswith("XAU"):
        return 0.1
    if "JPY" in upper:
        return 0.01
    if upper.startswith("BTC") or upper.startswith("ETH"):
        return 1.0
    return 0.0001


def compute_sl(entry_price: float, direction: str, sl_pips: float, symbol: str) -> float:
    offset = sl_pips * pip_size(symbol)
    return entry_price - offset if direction == "BUY" else entry_price + offset


def favorable_excursion(direction: str, entry_price: float, current_price: float) -> float:
    """How far price has moved in the trade's favor, in price units (can be negative)."""
    return (current_price - entry_price) if direction == "BUY" else (entry_price - current_price)

from .base import Strategy
from .btc_scalp import BtcScalpStrategy
from .btc_m15 import BtcM15Strategy
from .ai_trader import AiTraderStrategy

STRATEGY_REGISTRY = {
    "btc_scalp": BtcScalpStrategy,
    "btc_m15": BtcM15Strategy,
    "ai_trader": AiTraderStrategy,
}

__all__ = [
    "Strategy",
    "BtcScalpStrategy",
    "BtcM15Strategy",
    "AiTraderStrategy",
    "STRATEGY_REGISTRY",
]

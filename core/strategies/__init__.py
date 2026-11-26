"""
Advanced Strategy Framework
Plugin-based architecture for composable trading strategies
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"


@dataclass
class Signal:
    """Trading signal with full metadata"""
    symbol: str
    signal_type: SignalType
    price: float
    timestamp: datetime
    confidence: float
    strength: float  # 0-1, position sizing hint
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    strategy_name: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    regime: str = ""
    confidence_interval: Tuple[float, float] = (0.0, 1.0)


@dataclass
class StrategyConfig:
    """Configuration for a strategy"""
    name: str
    enabled: bool = True
    weight: float = 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    symbols: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=lambda: ["1h"])
    risk_params: Dict[str, float] = field(default_factory=dict)


class StrategyBase(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self.weight = config.weight
        self.parameters = config.parameters
        self.logger = logging.getLogger(f"strategy.{config.name}")
        self._initialized = False
    
    @abstractmethod
    def analyze(self, data: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Signal]:
        """Analyze market data and generate signal"""
        pass
    
    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """Return list of required indicator names"""
        pass
    
    def initialize(self, data: pd.DataFrame) -> bool:
        """Initialize strategy with historical data"""
        try:
            self._initialize(data)
            self._initialized = True
            return True
        except Exception as e:
            logging.error(f"Strategy {self.name} initialization failed: {e}")
            return False
    
    def _initialize(self, data: pd.DataFrame):
        """Override in subclass for custom initialization"""
        pass
    
    def validate_signal(self, signal: Signal) -> bool:
        """Validate signal before returning"""
        if signal.confidence < 0 or signal.confidence > 1:
            return False
        if signal.strength < 0 or signal.strength > 1:
            return False
        if signal.stop_loss and signal.take_profit:
            if signal.signal_type == "BUY":
                return signal.stop_loss < signal.price < signal.take_profit
            else:
                return signal.take_profit < signal.price < signal.stop_loss
        return True
    
    def get_required_data(self) -> Dict[str, Any]:
        """Return data requirements for this strategy"""
        return {
            "indicators": self.get_required_indicators(),
            "lookback": self.parameters.get("lookback", 200),
            "timeframes": self.config.timeframes,
        }


class EnsembleStrategy:
    """Ensemble strategy combining multiple sub-strategies"""
    
    def __init__(self, strategies: List[StrategyBase], voting_method: str = "weighted"):
        self.strategies = strategies
        self.voting_method = voting_method
        self.logger = logging.getLogger("ensemble")
    
    def analyze(self, data: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Signal]:
        """Aggregate signals from all sub-strategies"""
        signals = []
        weights = []
        
        for strategy in self.strategies:
            if not strategy.enabled:
                continue
            
            signal = strategy.analyze(data, symbol, timeframe)
            if signal and strategy.validate_signal(signal):
                signals.append(signal)
                weights.append(strategy.weight)
        
        if not signals:
            return None
        
        return self._aggregate_signals(signals, weights)
    
    def _aggregate_signals(self, signals: List[Signal], weights: List[float]) -> Signal:
        """Aggregate multiple signals into one"""
        if not signals:
            return None
        
        if self.voting_method == "weighted":
            return self._weighted_vote(signals, weights)
        elif self.voting_method == "majority":
            return self._majority_vote(signals)
        elif self.voting_method == "consensus":
            return self._consensus_vote(signals)
        else:
            return self._weighted_vote(signals, weights)
    
    def _weighted_vote(self, signals: List[Signal], weights: List[float]) -> Signal:
        """Weighted voting based on strategy weights and confidence"""
        total_weight = sum(weights)
        if total_weight == 0:
            return signals[0]
        
        # Weight by strategy weight * confidence * strength
        weighted_confidence = sum(s.confidence * s.strength * w for s, w in zip(signals, weights)) / sum(weights)
        weighted_strength = sum(s.strength * w for s, w in zip(signals, weights)) / sum(weights)
        
        # Determine signal type by weighted vote
        buy_weight = sum(w for s, w in zip(signals, weights) if s.signal_type == "BUY")
        sell_weight = sum(w for s, w in zip(signals, weights) if s.signal_type == "SELL")
        
        signal_type = "BUY" if buy_weight >= sell_weight else "SELL"
        
        # Use first signal as template
        base = signals[0]
        return Signal(
            symbol=base.symbol,
            signal_type=signal_type,
            price=base.price,
            timestamp=base.timestamp,
            confidence=weighted_confidence,
            strength=weighted_strength,
            stop_loss=base.stop_loss,
            take_profit=base.take_profit,
            trailing_stop=base.trailing_stop,
            strategy_name=f"Ensemble({len(signals)})",
            reason=f"Ensemble of {len(signals)} strategies",
            metadata={"sub_signals": [s.__dict__ for s in signals]},
            regime=base.regime,
        )
    
    def _majority_vote(self, signals: List[Signal]) -> Signal:
        """Simple majority vote"""
        buy_count = sum(1 for s in signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in signals if s.signal_type == "SELL")
        signal_type = "BUY" if buy_count >= sell_count else "SELL"
        base = signals[0]
        return Signal(
            symbol=base.symbol,
            signal_type=signal_type,
            price=base.price,
            timestamp=base.timestamp,
            confidence=sum(s.confidence for s in signals) / len(signals),
            strength=sum(s.strength for s in signals) / len(signals),
            strategy_name="Ensemble(Majority)",
        )
    
    def _consensus_vote(self, signals: List[Signal]) -> Optional[Signal]:
        """Require consensus (all agree)"""
        signal_types = set(s.signal_type for s in signals)
        if len(signal_types) == 1:
            return self._weighted_vote(signals, [1.0] * len(signals))
        return None


class StrategyRegistry:
    """Registry for managing and discovering strategies"""
    
    def __init__(self):
        self._strategies: Dict[str, type] = {}
        self._instances: Dict[str, StrategyBase] = {}
    
    def register(self, name: str, strategy_class: type):
        """Register a strategy class"""
        if not issubclass(name, StrategyBase):
            raise ValueError("Strategy must inherit from StrategyBase")
        self._strategies[name] = strategy_class
        logging.info(f"Registered strategy: {name}")
    
    def create(self, name: str, config: StrategyConfig) -> Optional[StrategyBase]:
        """Create strategy instance"""
        if name not in self._strategies:
            logging.error(f"Strategy not found: {name}")
            return None
        return self._strategies[name](config)
    
    def get_available(self) -> List[str]:
        return list(self._strategies.keys())
    
    def get_instance(self, name: str) -> Optional[object]:
        return self._instances.get(name)


# Global registry
strategy_registry = StrategyRegistry()


def register_strategy(name: str):
    """Decorator for registering strategies"""
    def decorator(cls):
        strategy_registry.register(name, cls)
        return cls
    return decorator

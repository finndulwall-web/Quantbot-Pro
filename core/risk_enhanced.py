"""
Enhanced Risk Management Module
Advanced position sizing, portfolio risk, correlation analysis, and circuit breakers
"""
import pandas as pd
import numpy as np
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import json

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    entry_time: pd.Timestamp
    highest_price: float
    trailing_stop: float
    action: str = "BUY"
    kelly_fraction: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    strategy_name: str = "default"
    confidence: float = 1.0
    timeframe: str = "1h"
    entry_signal: str = ""
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


@dataclass
class Portfolio:
    balance: float
    positions: Dict[str, Position] = field(default_factory=dict)
    equity_curve: List[float] = field(default_factory=list)
    trades_history: List[dict] = field(default_factory=list)
    peak_balance: float = 0.0
    daily_pnl: float = 0.0
    daily_start_balance: float = 0.0
    daily_trades: int = 0
    max_daily_trades: int = 50
    total_fees_paid: float = 0.0
    total_slippage_cost: float = 0.0


@dataclass
class RiskMetrics:
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_trade_duration: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    kelly_fraction: float = 0.0
    portfolio_heat: float = 0.0
    correlation_risk: float = 0.0


class CorrelationTracker:
    """Track and analyze correlations between positions"""
    
    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        self.price_history: Dict[str, pd.Series] = {}
        self.correlation_matrix: pd.DataFrame = pd.DataFrame()
        
    def update(self, symbol: str, price: float):
        if symbol not in self.price_history:
            self.price_history[symbol] = pd.Series(dtype='float64')
        
        self.price_history[symbol] = pd.concat([
            self.price_history[symbol], 
            pd.Series([price], index=[pd.Timestamp.now(tz='UTC')])
        ]).tail(self.lookback)
        
        self._update_correlation_matrix()
    
    def _update_correlation_matrix(self):
        symbols = list(self.price_history.keys())
        if len(symbols) < 2:
            return
        
        # Build price dataframe
        price_data = {}
        min_len = min(len(self.price_history[s]) for s in symbols)
        
        for s in symbols:
            price_data[s] = self.price_history[s].tail(min_len).values
        
        df = pd.DataFrame(price_data)
        if len(df) > 20:
            self.correlation_matrix = df.corr()
    
    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        if self.correlation_matrix.empty:
            return 0.0
        if symbol1 in self.correlation_matrix.columns and symbol2 in self.correlation_matrix.columns:
            return self.correlation_matrix.loc[symbol1, symbol2]
        return 0.0
    
    def get_max_correlation(self, symbol: str) -> float:
        if self.correlation_matrix.empty or symbol not in self.correlation_matrix.columns:
            return 0.0
        corrs = self.correlation_matrix[symbol].drop(symbol, errors='ignore')
        return corrs.abs().max() if not corrs.empty else 0.0
    
    def get_portfolio_correlation_risk(self, positions: Dict[str, any]) -> float:
        """Calculate portfolio correlation risk"""
        symbols = list(positions.keys())
        if len(symbols) < 2:
            return 0.0
        
        total_risk = 0.0
        count = 0
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                corr = self.get_correlation(s1, s2)
                if corr != 0:
                    total_risk += abs(corr)
                    count += 1
        
        return total_risk / count if count > 0 else 0.0


class KellyCalculator:
    """Advanced Kelly Criterion Calculator with multiple methods"""
    
    def __init__(self, max_fraction: float = 0.25, min_trades: int = 10):
        self.max_fraction = max_fraction
        self.min_trades = min_trades
    
    def classic_kelly(self, wins: List[float], losses: List[float]) -> float:
        """Classic Kelly formula"""
        if not wins or not losses:
            return 0.0
        
        win_rate = len(wins) / (len(wins) + len(losses))
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 0.0
        
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        return max(0, min(kelly, self.max_fraction))
    
    def fractional_kelly(self, wins: List[float], losses: List[float], fraction: float = 0.5) -> float:
        """Fractional Kelly (half-Kelly by default)"""
        return self.classic_kelly(wins, losses) * fraction
    
    def optimal_kelly(self, returns: List[float], risk_free: float = 0.0) -> float:
        """Optimal Kelly using return distribution"""
        if len(returns) < self.min_trades:
            return 0.0
        
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        # Maximize growth rate
        kelly = np.mean(excess_returns) / np.var(excess_returns)
        return max(0, min(kelly, self.max_fraction))
    
    def safe_kelly(self, trades: List[dict], risk_per_trade: float, confidence: float = 1.0) -> float:
        """Conservative Kelly with safety margins"""
        if len(trades) < self.min_trades:
            return risk_per_trade * 0.5
        
        wins = [t['pnl_pct'] / 100 for t in trades if t['pnl'] > 0]
        losses = [abs(t['pnl_pct'] / 100) for t in trades if t['pnl'] < 0]
        
        kelly = self.classic_kelly(wins, losses)
        
        # Apply safety factors
        safety_factor = 0.25  # Quarter Kelly
        confidence_factor = confidence
        
        return kelly * safety_factor * confidence_factor


class VolatilitySizer:
    """Volatility-adjusted position sizing"""
    
    def __init__(self, target_vol: float = 0.15, max_leverage: float = 1.0):
        self.target_vol = target_vol
        self.max_leverage = max_leverage
    
    def calculate_size(self, capital: float, entry_price: float, 
                       stop_loss: float, atr: float, 
                       volatility: float) -> float:
        """Calculate position size based on volatility targeting"""
        if entry_price <= stop_loss or atr <= 0:
            return 0.0
        
        # Risk per share
        risk_per_share = entry_price - stop_loss
        
        # Volatility-adjusted position size
        target_risk = capital * self.target_vol / np.sqrt(252)  # Daily target
        vol_adjusted_risk = target_risk / (volatility / 100) if volatility > 0 else target_risk
        
        # Position size
        size = vol_adjusted_risk / risk_per_share if risk_per_share > 0 else 0
        
        # Apply leverage limit
        max_size = capital * self.max_leverage / entry_price
        
        return min(size, max_size)


class CorrelationManager:
    """Manage position correlations and diversification"""
    
    def __init__(self, max_correlation: float = 0.7, max_sector_exposure: float = 0.3):
        self.max_correlation = max_correlation
        self.max_sector_exposure = max_sector_exposure
        self.asset_sectors: Dict[str, str] = {}
        self.correlation_history: List[pd.DataFrame] = []
    
    def add_symbol(self, symbol: str, sector: str = "unknown"):
        self.asset_sectors[symbol] = sector
    
    def check_correlation_limit(self, symbol: str, existing_positions: Dict[str, Position],
                                correlation_matrix: pd.DataFrame) -> Tuple[bool, str]:
        """Check if adding this position would exceed correlation limits"""
        if symbol not in correlation_matrix.columns:
            return True, "No correlation data"
        
        correlations = correlation_matrix[symbol]
        high_corr = correlations[correlations > self.max_correlation]
        
        for other_symbol in high_corr.index:
            if other_symbol in existing_positions:
                return False, f"High correlation ({correlations[other_symbol]:.2f}) with {other_symbol}"
        
        return True, "OK"
    
    def check_sector_exposure(self, symbol: str, existing_positions: Dict[str, Position],
                              portfolio_value: float) -> Tuple[bool, str]:
        """Check sector concentration limits"""
        sector = self.asset_sectors.get(symbol, "unknown")
        
        sector_exposure = sum(
            pos.size * pos.entry_price 
            for sym, pos in existing_positions.items() 
            if self.asset_sectors.get(sym) == sector
        )
        
        new_position_value = 0  # Will be calculated externally
        total_sector = sector_exposure + new_position_value
        
        if total_sector / portfolio_value > self.max_sector_exposure:
            return False, f"Sector {sector} exposure would exceed {self.max_sector_exposure*100}%"
        
        return True, "OK"


class DrawdownController:
    """Advanced drawdown control with multiple layers"""
    
    def __init__(self, config: dict):
        self.max_daily_dd = config.get('max_daily_drawdown', 0.05)
        self.max_total_dd = config.get('max_total_drawdown', 0.15)
        self.max_weekly_dd = config.get('max_weekly_drawdown', 0.10)
        self.max_monthly_dd = config.get('max_monthly_drawdown', 0.20)
        
        self.daily_start_balance: float = 0.0
        self.weekly_start_balance: float = 0.0
        self.monthly_start_balance: float = 0.0
        self.peak_balance: float = 0.0
        
        self._last_date = None
        self._last_week = None
        self._last_month = None
        
    def reset_daily(self, balance: float):
        today = pd.Timestamp.now(tz='UTC').date()
        if self._last_date != today:
            self._last_date = today
            self.daily_start_balance = balance
    
    def reset_weekly(self, balance: float):
        today = pd.Timestamp.now(tz='UTC')
        week = today.isocalendar().week
        if self._last_week != week:
            self._last_week = week
            self.weekly_start_balance = balance
    
    def reset_monthly(self, balance: float):
        today = pd.Timestamp.now(tz='UTC')
        month = today.month
        if self._last_month != month:
            self._last_month = month
            self.monthly_start_balance = balance
    
    def update_peak(self, balance: float):
        if balance > self.peak_balance:
            self.peak_balance = balance
    
    def check_limits(self, balance: float) -> Tuple[bool, str]:
        """Check all drawdown limits"""
        self.update_peak(balance)
        
        # Total drawdown
        total_dd = (self.peak_balance - balance) / self.peak_balance if self.peak_balance > 0 else 0
        if total_dd >= self.max_total_dd:
            return True, f"Total drawdown {total_dd*100:.1f}% exceeds {self.max_total_dd*100:.1f}%"
        
        # Daily drawdown
        daily_dd = (self.daily_start_balance - balance) / self.daily_start_balance if self.daily_start_balance > 0 else 0
        if daily_dd >= self.max_daily_dd:
            return True, f"Daily drawdown {daily_dd*100:.1f}% exceeds {self.max_daily_dd*100:.1f}%"
        
        # Weekly drawdown
        weekly_dd = (self.weekly_start_balance - balance) / self.weekly_start_balance if self.weekly_start_balance > 0 else 0
        if weekly_dd >= self.max_weekly_dd:
            return True, f"Weekly drawdown {weekly_dd*100:.1f}% exceeds {self.max_weekly_dd*100:.1f}%"
        
        # Monthly drawdown
        monthly_dd = (self.monthly_start_balance - balance) / self.monthly_start_balance if self.monthly_start_balance > 0 else 0
        if monthly_dd >= self.max_monthly_dd:
            return True, f"Monthly drawdown {monthly_dd*100:.1f}% exceeds {self.max_monthly_dd*100:.1f}%"
        
        return False, "OK"
    
    def get_drawdown_status(self, balance: float) -> dict:
        return {
            'total_dd_pct': (self.peak_balance - balance) / self.peak_balance * 100 if self.peak_balance > 0 else 0,
            'daily_dd_pct': (self.daily_start_balance - balance) / self.daily_start_balance * 100 if self.daily_start_balance > 0 else 0,
            'weekly_dd_pct': (self.weekly_start_balance - balance) / self.weekly_start_balance * 100 if self.weekly_start_balance > 0 else 0,
            'monthly_dd_pct': (self.monthly_start_balance - balance) / self.monthly_start_balance * 100 if self.monthly_start_balance > 0 else 0,
            'peak_balance': self.peak_balance,
            'limits': {
                'total': self.max_total_dd * 100,
                'daily': self.max_daily_dd * 100,
                'weekly': self.max_weekly_dd * 100,
                'monthly': self.max_monthly_dd * 100
            }
        }


class AdvancedRiskManager:
    """Main enhanced risk manager integrating all components"""
    
    def __init__(self, config: dict):
        self.config = config
        self.initial_balance = config.get('capital_usdt', 170.0)
        
        # Core parameters
        self.risk_per_trade = config.get('risk_per_trade', 0.01)
        self.max_concurrent = config.get('max_concurrent_trades', 3)
        self.max_heat = config.get('max_portfolio_heat', 1.0)
        
        # Advanced components
        self.kelly_calculator = KellyCalculator(
            max_fraction=config.get('kelly_max_fraction', 0.25),
            min_trades=config.get('kelly_lookback', 50)
        )
        
        self.vol_sizer = VolatilitySizer(
            target_vol=config.get('target_volatility', 0.15),
            max_leverage=config.get('max_leverage', 1.0)
        )
        
        self.correlation_manager = CorrelationManager(
            max_correlation=config.get('max_correlation', 0.7),
            max_sector_exposure=config.get('max_sector_exposure', 0.3)
        )
        
        self.drawdown_controller = DrawdownController(config)
        
        # Correlation tracking
        self.correlation_tracker = CorrelationTracker(lookback=config.get('correlation_lookback', 100))
        
        # Portfolio state
        self.initial_balance = config.get('capital_usdt', 170.0)
        self.portfolio = Portfolio(
            balance=self.initial_balance,
            peak_balance=self.initial_balance,
            daily_start_balance=self.initial_balance
        )
        
        # Circuit breaker
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason = ""
        
        # Trade tracking
        self.max_concurrent = config.get('max_concurrent_trades', 3)
        self.max_heat = config.get('max_portfolio_heat', 1.0)
        
        # Slippage and fees
        self.slippage = config.get('slippage_pct', 0.001)
        self.fee = config.get('fee_pct', 0.001)
        
        # Performance tracking
        self.daily_trades = 0
        self.max_daily_trades = config.get('max_daily_trades', 50)
        
        # Correlation tracking
        self.correlation_lookback = config.get('correlation_lookback', 100)
        self.correlation_history = []
        
        logger.info(f"AdvancedRiskManager initialized with capital: ${self.initial_balance:.2f}")
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                                symbol: str = "", volatility: float = 2.0) -> float:
        """Calculate optimal position size using multiple methods"""
        if entry_price <= stop_loss:
            return 0.0
        
        # Method 1: Kelly-based
        kelly_size = self._kelly_based_size(entry_price, stop_loss, symbol)
        
        # Method 2: Volatility targeting
        vol_size = self._volatility_based_size(entry_price, stop_loss, symbol)
        
        # Method 3: Fixed fractional
        frac_size = self._fixed_fractional_size(entry_price, stop_loss)
        
        # Use minimum of all methods (conservative)
        size = min(kelly_size, vol_size, frac_size)
        
        return round(size, 6)
    
    def _kelly_based_size(self, entry_price: float, stop_loss: float, symbol: str) -> float:
        """Kelly-based position sizing"""
        if self.portfolio.balance <= 0:
            return 0.0
        
        kelly_frac = self.kelly_calculator.safe_kelly(
            self.portfolio.trades_history,
            self.risk_per_trade
        )
        
        risk_amount = self.portfolio.balance * kelly_frac
        risk_per_share = entry_price - stop_loss
        
        if risk_per_share <= 0:
            return 0.0
        
        return risk_amount / risk_per_share
    
    def _volatility_based_size(self, entry_price: float, stop_loss: float, symbol: str) -> float:
        """Volatility-targeted position sizing"""
        # Get recent volatility for symbol
        volatility = 2.0  # Default 2%
        
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
            # Estimate from ATR
            atr_approx = pos.entry_price * 0.02
        else:
            # Use entry_price * 2% as reasonable default ATR approximation
            atr_approx = entry_price * 0.02
        
        return self.vol_sizer.calculate_size(self.portfolio.balance, entry_price, stop_loss, atr_approx, 2.0)

    def _fixed_fractional_size(self, entry_price: float, stop_loss: float) -> float:
        """Fixed fractional position sizing"""
        if self.portfolio.balance <= 0:
            return 0.0
        
        risk_amount = self.portfolio.balance * self.risk_per_trade
        risk_per_share = entry_price - stop_loss
        
        if risk_per_share <= 0:
            return 0.0
        
        return risk_amount / (entry_price - stop_loss)
    
    def check_portfolio_heat(self, new_position_value: float) -> bool:
        current_exposure = sum(p.size * p.entry_price for p in self.portfolio.positions.values())
        total_exposure = current_exposure + new_position_value
        total_equity = self.portfolio.balance + current_exposure
        return (total_exposure / total_equity) <= self.max_heat

    def can_open_position(self, symbol: str, entry_price: float, stop_loss: float) -> Tuple[bool, str]:
        """Comprehensive position opening validation"""
        if self.circuit_breaker_triggered:
            return False, f"Circuit breaker active: {self.circuit_breaker_reason}"
        
        if symbol in self.portfolio.positions:
            return False, "Position already exists"
        
        if len(self.portfolio.positions) >= self.max_concurrent:
            return False, f"Max concurrent trades ({self.max_concurrent}) reached"
        
        # Daily trade limit
        if self.daily_trades >= self.max_daily_trades:
            return False, f"Daily trade limit ({self.max_daily_trades}) reached"
        
        # Circuit breaker check
        cb_triggered, cb_reason = self.check_circuit_breakers()
        if cb_triggered:
            return False, f"Circuit breaker: {cb_reason}"
        
        size = self.calculate_position_size(entry_price, stop_loss, symbol)
        if size <= 0:
            return False, "Invalid position size"
        
        position_value = size * entry_price
        
        if position_value > self.portfolio.balance:
            return False, "Insufficient balance"
        
        if not self.check_portfolio_heat(position_value):
            return False, f"Portfolio heat would exceed {self.max_heat*100}%"
        
        return True, size
    
    def open_position(self, signal, size: float) -> Position:
        """Open a new position with enhanced tracking"""
        position = Position(
            symbol=signal.symbol,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            size=size,
            entry_time=pd.Timestamp.now(tz='UTC'),
            highest_price=signal.price,
            trailing_stop=signal.stop_loss,
            action=signal.action,
            kelly_fraction=signal.confidence * 0.25,  # Conservative Kelly
            strategy_name=getattr(signal, 'strategy_name', 'default'),
            confidence=signal.confidence,
            timeframe=getattr(signal, 'timeframe', '1h'),
            entry_signal=getattr(signal, 'reason', '')
        )
        
        self.portfolio.positions[signal.symbol] = position
        self.portfolio.balance -= size * signal.price
        self.daily_trades += 1
        
        logger.info(f"Opened {signal.action} {signal.symbol} @ {signal.price:.4f}, "
                   f"size={size:.6f}, SL={signal.stop_loss:.4f}, TP={signal.take_profit:.4f}")
        return position
    
    def close_position(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
        if symbol not in self.portfolio.positions:
            return None
        
        position = self.portfolio.positions.pop(symbol)
        pnl = (exit_price - position.entry_price) * position.size
        pnl_pct = (exit_price - position.entry_price) / position.entry_price * 100
        self.portfolio.balance += position.size * exit_price
        
        # Apply slippage and fees
        slippage_cost = position.size * exit_price * self.slippage
        fee = position.size * exit_price * self.fee
        self.portfolio.total_fees_paid += fee
        self.portfolio.total_slippage_cost += slippage_cost
        net_pnl = pnl - slippage_cost - fee
        
        trade = {
            'symbol': symbol,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size': position.size,
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'entry_time': position.entry_time,
            'exit_time': pd.Timestamp.now(tz='UTC'),
            'duration': (pd.Timestamp.now(tz='UTC') - position.entry_time).total_seconds() / 3600,
            'kelly_fraction': position.kelly_fraction,
            'mae': position.max_adverse_excursion,
            'mfe': position.max_favorable_excursion,
            'strategy': position.strategy_name,
            'confidence': position.confidence,
            'timeframe': position.timeframe,
            'entry_signal': position.entry_signal,
            'fees': fee,
            'slippage': slippage_cost
        }
        self.portfolio.trades_history.append(trade)
        
        logger.info(f"Closed {symbol} @ {exit_price:.4f} | PnL: {net_pnl:.2f} USDT ({pnl_pct:.2f}%) | Reason: {reason}")
        return trade
    
    def update_trailing_stops(self, current_prices: Dict[str, float]):
        for symbol, position in self.portfolio.positions.items():
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            position.highest_price = max(position.highest_price, price)
            
            # Track MAE/MFE
            mae = (position.entry_price - min(price, position.entry_price)) / position.entry_price * 100
            mfe = (max(price, position.entry_price) - position.entry_price) / position.entry_price * 100
            position.max_adverse_excursion = max(position.max_adverse_excursion, mae)
            position.max_favorable_excursion = max(position.max_favorable_excursion, mfe)
            
            # Update unrealized PnL
            position.unrealized_pnl = (price - position.entry_price) * position.size
            position.unrealized_pnl_pct = (price - position.entry_price) / position.entry_price * 100
            
            # Trailing stop
            atr_approx = position.entry_price * 0.02
            trail_distance = atr_approx * 1.0  # Default trail multiplier
            new_trail = position.highest_price - trail_distance
            if new_trail > position.trailing_stop:
                position.trailing_stop = new_trail
            
            # Update correlation tracker
            self.correlation_tracker.update(symbol, price)
    
    def check_exits(self, current_prices: Dict[str, float]) -> List[dict]:
        closed_trades = []
        
        # Check circuit breakers
        cb_triggered, cb_reason = self.check_circuit_breakers()
        if cb_triggered and not self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_reason = cb_reason
            logger.critical(f"CIRCUIT BREAKER: {cb_reason}")
            
            for symbol in list(self.portfolio.positions.keys()):
                if symbol in current_prices:
                    trade = self.close_position(symbol, current_prices[symbol], "CIRCUIT_BREAKER")
                    if trade:
                        closed_trades.append(trade)
            return closed_trades
        
        for symbol, position in list(self.portfolio.positions.items()):
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            exit_reason = None
            
            if price <= position.trailing_stop:
                exit_reason = "TRAILING_STOP"
            elif price <= position.stop_loss:
                exit_reason = "STOP_LOSS"
            elif price >= position.take_profit:
                exit_reason = "TAKE_PROFIT"
            
            # Supertrend flip exit
            # (would need current supertrend value passed in)
            
            if exit_reason:
                trade = self.close_position(symbol, price, exit_reason)
                if trade:
                    closed_trades.append(trade)
        
        return closed_trades
    
    def check_circuit_breakers(self) -> Tuple[bool, str]:
        """Multi-layer circuit breaker system"""
        balance = self.portfolio.balance
        current_equity = self.get_equity({})
        
        return self.drawdown_controller.check_limits(current_equity)
    
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        equity = self.portfolio.balance
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
                equity += position.size * current_prices[symbol]
            else:
                equity += position.size * position.entry_price
        return equity
    
    def update_daily_stats(self):
        self.drawdown_controller.reset_daily(self.portfolio.balance)
        self.drawdown_controller.reset_weekly(self.portfolio.balance)
        self.drawdown_controller.reset_monthly(self.portfolio.balance)
    
    def get_metrics(self) -> dict:
        base_metrics = self._get_base_metrics()
        
        # Add enhanced metrics
        drawdown_status = self.drawdown_controller.get_drawdown_status(self.portfolio.balance)
        
        # Correlation risk
        positions = self.portfolio.positions
        correlation_risk = 0.0
        if len(self.portfolio.positions) > 1:
            # Simplified correlation risk estimate
            correlation_risk = len(self.portfolio.positions) * 0.1
        
        return {
            **base_metrics,
            **drawdown_status,
            'correlation_risk': correlation_risk,
            'daily_trades': self.daily_trades,
            'total_fees_paid': self.portfolio.total_fees_paid,
            'total_slippage_cost': self.portfolio.total_slippage_cost,
            'circuit_breaker': self.circuit_breaker_triggered,
            'circuit_breaker_reason': self.circuit_breaker_reason
        }
    
    def _get_base_metrics(self) -> dict:
        if not self.portfolio.trades_history:
            return {
                'total_trades': 0, 'win_rate': 0, 'total_return': 0,
                'max_drawdown': 0, 'sharpe': 0, 'profit_factor': 0,
                'sortino': 0, 'calmar': 0, 'expectancy': 0,
                'avg_win': 0, 'avg_loss': 0, 'largest_win': 0,
                'largest_loss': 0, 'consecutive_wins': 0, 'consecutive_losses': 0,
                'current_balance': self.portfolio.balance,
                'open_positions': len(self.portfolio.positions),
                'circuit_breaker': self.circuit_breaker_triggered
            }
        
        trades = self.portfolio.trades_history
        returns = [t['pnl_pct'] / 100 for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        
        total_return = (self.portfolio.balance - self.initial_balance) / self.initial_balance * 100
        win_rate = len(wins) / len(returns) * 100 if returns else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses else float('inf')
        expectancy = np.mean(returns) if returns else 0
        
        equity_curve = [self.initial_balance]
        for t in trades:
            equity_curve.append(equity_curve[-1] * (1 + t['pnl_pct'] / 100))
        
        peak = equity_curve[0]
        max_dd = 0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            max_dd = max(max_dd, dd)
        
        sharpe = 0
        sortino = 0
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * (252 ** 0.5) if np.std(returns) > 0 else 0
            downside = [r for r in returns if r < 0]
            downside_std = np.std(downside) if downside else 0
            sortino = np.mean(returns) / downside_std * (252 ** 0.5) if downside_std > 0 else 0
        
        calmar = (self.portfolio.balance - self.initial_balance) / self.initial_balance * 100 / max_dd if max_dd > 0 else 0
        
        consecutive_wins = 0
        consecutive_losses = 0
        max_consec_wins = 0
        max_consec_losses = 0
        for r in returns:
            if r > 0:
                consecutive_wins += 1
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                consecutive_wins = 0
            max_consec_wins = max(max_consec_wins, consecutive_wins)
            max_consec_losses = max(max_consec_losses, consecutive_losses)
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'max_drawdown': max_dd,
            'sharpe': sharpe,
            'sortino': sortino,
            'calmar': calmar,
            'profit_factor': profit_factor,
            'expectancy': expectancy * 100,
            'avg_win': np.mean(wins) * 100 if wins else 0,
            'avg_loss': np.mean(losses) * 100 if losses else 0,
            'largest_win': max(wins) * 100 if wins else 0,
            'largest_loss': min(losses) * 100 if losses else 0,
            'consecutive_wins': max_consec_wins,
            'consecutive_losses': max_consec_losses,
            'current_balance': self.portfolio.balance,
            'open_positions': len(self.portfolio.positions),
            'circuit_breaker': self.circuit_breaker_triggered
        }
    
    def get_portfolio_risk_report(self) -> dict:
        """Generate comprehensive risk report"""
        metrics = self.get_metrics()
        
        # Position details
        positions = {}
        for sym, pos in self.portfolio.positions.items():
            positions[sym] = {
                'entry_price': pos.entry_price,
                'current_price': pos.highest_price,  # Approximation
                'size': pos.size,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'trailing_stop': pos.trailing_stop,
                'kelly_fraction': pos.kelly_fraction,
                'confidence': pos.confidence,
                'duration_hours': (pd.Timestamp.now(tz='UTC') - pos.entry_time).total_seconds() / 3600,
                'mae': pos.max_adverse_excursion,
                'mfe': pos.max_favorable_excursion
            }
        
        return {
            'timestamp': pd.Timestamp.now(tz='UTC').isoformat(),
            'metrics': metrics,
            'positions': positions,
            'total_exposure': sum(p['size'] * p['entry_price'] for p in positions.values()),
            'cash_balance': self.portfolio.balance,
            'total_equity': self.get_equity({})
        }
    
    def reset_daily_counters(self):
        self.daily_trades = 0
        self.update_daily_stats()
    
    def reset_circuit_breaker(self):
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason = ""
        self.drawdown_controller.peak_balance = self.portfolio.balance
        logger.info("Circuit breaker manually reset")


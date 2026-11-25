from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import logging
import math

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

@dataclass
class Portfolio:
    balance: float
    positions: Dict[str, Position] = field(default_factory=dict)
    equity_curve: List[float] = field(default_factory=list)
    trades_history: List[dict] = field(default_factory=list)
    peak_balance: float = 0.0
    daily_pnl: float = 0.0
    daily_start_balance: float = 0.0

class RiskManager:
    def __init__(self, config: dict):
        self.config = config
        self.initial_balance = config.get('capital_usdt', 170.0)
        self.risk_per_trade = config.get('risk_per_trade', 0.01)
        self.max_concurrent = config.get('max_concurrent_trades', 3)
        self.max_heat = config.get('max_portfolio_heat', 1.0)
        self.max_daily_dd = config.get('max_daily_drawdown', 0.05)
        self.max_total_dd = config.get('max_total_drawdown', 0.15)
        self.kelly_lookback = config.get('kelly_lookback', 50)
        self.kelly_max_fraction = config.get('kelly_max_fraction', 0.25)
        self.circuit_breaker_triggered = False
        
        self.portfolio = Portfolio(
            balance=self.initial_balance, 
            peak_balance=self.initial_balance,
            daily_start_balance=self.initial_balance
        )
    
    def calculate_kelly_fraction(self, symbol: str) -> float:
        trades = [t for t in self.portfolio.trades_history if t['symbol'] == symbol]
        if len(trades) < 10:
            return self.risk_per_trade
        
        recent = trades[-self.kelly_lookback:]
        wins = [t['pnl_pct'] / 100 for t in recent if t['pnl'] > 0]
        losses = [abs(t['pnl_pct'] / 100) for t in recent if t['pnl'] < 0]
        
        if not wins or not losses:
            return self.risk_per_trade
        
        win_rate = len(wins) / len(recent)
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return self.risk_per_trade
        
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly = max(0, min(kelly, self.kelly_max_fraction))
        
        return kelly * 0.5
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, symbol: str = "") -> float:
        if entry_price <= stop_loss:
            return 0.0
        
        kelly_frac = self.calculate_kelly_fraction(symbol) if symbol else self.risk_per_trade
        risk_amount = self.portfolio.balance * kelly_frac
        size = risk_amount / (entry_price - stop_loss)
        return round(size, 6)
    
    def check_circuit_breakers(self) -> Tuple[bool, str]:
        current_equity = self.portfolio.balance
        for symbol, pos in self.portfolio.positions.items():
            current_equity += pos.size * pos.entry_price
        
        total_dd = (self.portfolio.peak_balance - current_equity) / self.portfolio.peak_balance
        if total_dd >= self.max_total_dd:
            return True, f"Total drawdown {total_dd*100:.1f}% exceeds limit {self.max_total_dd*100:.1f}%"
        
        daily_dd = (self.portfolio.daily_start_balance - self.portfolio.balance) / self.portfolio.daily_start_balance
        if daily_dd >= self.max_daily_dd:
            return True, f"Daily drawdown {daily_dd*100:.1f}% exceeds limit {self.max_daily_dd*100:.1f}%"
        
        return False, ""
    
    def check_portfolio_heat(self, new_position_value: float) -> bool:
        current_exposure = sum(p.size * p.entry_price for p in self.portfolio.positions.values())
        total_exposure = current_exposure + new_position_value
        total_equity = self.portfolio.balance + current_exposure
        return (total_exposure / total_equity) <= self.max_heat
    
    def can_open_position(self, symbol: str, entry_price: float, stop_loss: float) -> tuple:
        if self.circuit_breaker_triggered:
            return False, "Circuit breaker active - max drawdown exceeded"
        
        if symbol in self.portfolio.positions:
            return False, "Position already exists"
        
        if len(self.portfolio.positions) >= self.max_concurrent:
            return False, f"Max concurrent trades ({self.max_concurrent}) reached"
        
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
        kelly_frac = self.calculate_kelly_fraction(signal.symbol)
        position = Position(
            symbol=signal.symbol,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            size=size,
            entry_time=pd.Timestamp.now(tz='UTC'),
            highest_price=signal.price,
            trailing_stop=signal.stop_loss,
            kelly_fraction=kelly_frac
        )
        self.portfolio.positions[signal.symbol] = position
        self.portfolio.balance -= size * signal.price
        logger.info(f"Opened {signal.action} {signal.symbol} @ {signal.price:.4f}, size={size:.6f}, kelly={kelly_frac:.4f}")
        return position
    
    def close_position(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
        if symbol not in self.portfolio.positions:
            return None
        
        position = self.portfolio.positions.pop(symbol)
        pnl = (exit_price - position.entry_price) * position.size
        pnl_pct = (exit_price - position.entry_price) / position.entry_price * 100
        self.portfolio.balance += position.size * exit_price
        
        trade = {
            'symbol': symbol,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size': position.size,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'entry_time': position.entry_time,
            'exit_time': pd.Timestamp.now(tz='UTC'),
            'duration': (pd.Timestamp.now(tz='UTC') - position.entry_time).total_seconds() / 3600,
            'kelly_fraction': position.kelly_fraction,
            'mae': position.max_adverse_excursion,
            'mfe': position.max_favorable_excursion
        }
        self.portfolio.trades_history.append(trade)
        
        logger.info(f"Closed {symbol} @ {exit_price:.4f} | PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%) | Reason: {reason}")
        return trade
    
    def update_trailing_stops(self, current_prices: Dict[str, float]):
        for symbol, position in self.portfolio.positions.items():
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            position.highest_price = max(position.highest_price, price)
            
            mae = (position.entry_price - min(price, position.entry_price)) / position.entry_price * 100
            mfe = (max(price, position.entry_price) - position.entry_price) / position.entry_price * 100
            position.max_adverse_excursion = max(position.max_adverse_excursion, mae)
            position.max_favorable_excursion = max(position.max_favorable_excursion, mfe)
            
            atr_approx = position.entry_price * 0.02
            trail_distance = atr_approx * self.config.get('trail_atr_mult', 1.0)
            new_trail = position.highest_price - trail_distance
            if new_trail > position.trailing_stop:
                position.trailing_stop = new_trail
    
    def check_exits(self, current_prices: Dict[str, float]) -> List[dict]:
        closed_trades = []
        
        cb_triggered, cb_reason = self.check_circuit_breakers()
        if cb_triggered and not self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = True
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
            
            if exit_reason:
                trade = self.close_position(symbol, price, exit_reason)
                if trade:
                    closed_trades.append(trade)
        
        return closed_trades
    
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        equity = self.portfolio.balance
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
                equity += position.size * current_prices[symbol]
            else:
                equity += position.size * position.entry_price
        return equity
    
    def update_daily_stats(self):
        today = pd.Timestamp.now(tz='UTC').date()
        if not hasattr(self, '_last_date') or self._last_date != today:
            self._last_date = today
            self.portfolio.daily_start_balance = self.portfolio.balance
            self.portfolio.daily_pnl = 0.0
    
    def get_metrics(self) -> dict:
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
        
        calmar = total_return / max_dd if max_dd > 0 else 0
        
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
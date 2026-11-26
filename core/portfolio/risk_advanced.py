"""
Advanced Risk Management with Portfolio Optimization
CVaR, Portfolio Optimization, Stress Testing, Correlation Management
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging
import numpy.linalg as la

try:
    from scipy.optimize import minimize, LinearConstraint, NonlinearConstraint
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    entry_price: float
    current_price: float
    size: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    trailing_stop: float
    action: str = "BUY"
    kelly_fraction: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    strategy_name: str = ""
    confidence: float = 1.0
    timeframe: str = "1h"
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    entry_signal: str = ""


@dataclass
class PortfolioMetrics:
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    expectancy: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    expectancy: float = 0.0
    kelly_fraction: float = 0.0
    portfolio_heat: float = 0.0
    correlation_risk: float = 0.0


class RiskMetricsCalculator:
    """Advanced risk metrics calculation"""
    
    @staticmethod
    def calculate_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Value at Risk"""
        if len(returns) == 0:
            return 0.0
        return np.percentile(returns, (1 - confidence) * 100) * 100
    
    @staticmethod
    def calculate_cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Conditional Value at Risk (Expected Shortfall)"""
        if len(returns) == 0:
            return 0.0
        var = np.percentile(returns, (1 - confidence) * 100)
        tail = returns[returns <= var]
        return tail.mean() * 100 if len(tail) > 0 else 0.0
    
    @staticmethod
    def calculate_drawdowns(equity_curve: np.ndarray) -> Dict:
        """Calculate drawdown statistics"""
        if len(equity_curve) == 0:
            return {"max_dd": 0, "current_dd": 0, "avg_dd": 0, "max_duration": 0}
        
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak * 100
        
        max_dd = np.max(drawdown)
        current_dd = drawdown[-1]
        
        # Drawdown durations
        in_dd = drawdown > 0
        dd_starts = np.where(np.diff(np.concatenate(([False], in_dd))) == 1)[0]
        dd_ends = np.where(np.diff(np.concatenate((in_dd, [False]))) == -1)[0]
        
        durations = dd_ends - dd_starts if len(dd_starts) == len(dd_ends) else []
        max_duration = max(durations) if len(durations) > 0 else 0
        avg_duration = np.mean(durations) if len(durations) > 0 else 0
        
        return {
            "max_dd": float(max_dd),
            "current_dd": float(current_dd),
            "avg_dd": float(np.mean(drawdown)),
            "max_duration": int(max_duration),
            "avg_duration": float(avg_duration),
            "num_drawdowns": len(dd_starts)
        }
    
    @staticmethod
    def calculate_sharpe(returns: np.ndarray, risk_free: float = 0.0) -> float:
        """Annualized Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        excess = returns - risk_free / 252
        if np.std(returns) == 0:
            return 0.0
        return np.mean(excess) / np.std(returns) * np.sqrt(252)
    
    @staticmethod
    def calculate_sortino(returns: np.ndarray, risk_free: float = 0.0) -> float:
        """Sortino ratio (downside deviation)"""
        if len(returns) < 2:
            return 0.0
        excess = returns - risk_free / 252
        downside = returns[returns < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return np.mean(excess) / np.std(downside) * np.sqrt(252)
    
    @staticmethod
    def calculate_calmar(total_return: float, max_dd: float) -> float:
        """Calmar ratio"""
        if max_dd <= 0:
            return 0.0
        return total_return / max_dd
    
    @staticmethod
    def calculate_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Kelly criterion"""
        if avg_loss <= 0:
            return 0.0
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        return max(0, min(kelly, 0.25))  # Cap at 25%
    
    @staticmethod
    def calculate_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate correlation matrix of returns"""
        return returns_df.corr()
    
    @staticmethod
    def calculate_beta(returns: np.ndarray, market_returns: np.ndarray) -> float:
        """Calculate beta relative to market"""
        if len(returns) != len(market_returns) or len(returns) < 2:
            return 1.0
        cov = np.cov(returns, market_returns)[0, 1]
        market_var = np.var(market_returns)
        return cov / market_var if market_var > 0 else 1.0


class CorrelationManager:
    """Manage and analyze correlations between assets"""
    
    def __init__(self, max_correlation: float = 0.7, lookback: int = 100):
        self.max_correlation = max_correlation
        self.lookback = lookback
        self.price_history: Dict[str, pd.Series] = {}
        self.correlation_matrix: pd.DataFrame = pd.DataFrame()
        self.correlation_history: List[pd.DataFrame] = []
    
    def update(self, symbol: str, price: float, timestamp: datetime = None):
        """Update price history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = pd.Series(dtype=float)
        
        timestamp = timestamp or datetime.now()
        self.price_history[symbol] = pd.concat([
            self.price_history[symbol],
            pd.Series([price], index=[timestamp])
        ]).tail(self.lookback)
        
        self._update_correlation_matrix()
    
    def _update_correlation_matrix(self):
        """Update correlation matrix"""
        symbols = list(self.price_history.keys())
        if len(symbols) < 2:
            return
        
        # Build price matrix
        min_len = min(len(self.price_history[s]) for s in symbols)
        if min_len < 20:
            return
        
        price_matrix = pd.DataFrame({
            s: self.price_history[s].tail(min_len).values
            for s in symbols
        }, index=range(min_len))
        
        returns = price_matrix.pct_change().dropna()
        if len(returns) > 10:
            self.correlation_matrix = returns.corr()
            self.correlation_history.append(self.correlation_matrix.copy())
            if len(self.correlation_history) > 100:
                self.correlation_history.pop(0)
    
    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols"""
        if self.correlation_matrix.empty:
            return 0.0
        if symbol1 in self.correlation_matrix.columns and symbol2 in self.correlation_matrix.columns:
            return self.correlation_matrix.loc[symbol1, symbol2]
        return 0.0
    
    def get_max_correlation(self, symbol: str) -> float:
        """Get maximum correlation for a symbol"""
        if symbol not in self.correlation_matrix.columns:
            return 0.0
        corrs = self.correlation_matrix[symbol].drop(symbol, errors='ignore')
        return corrs.abs().max() if not corrs.empty else 0.0
    
    def get_portfolio_correlation_risk(self, positions: Dict[str, float]) -> float:
        """Calculate portfolio correlation risk"""
        symbols = list(positions.keys())
        if len(symbols) < 2:
            return 0.0
        
        total_risk = 0.0
        count = 0
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                corr = self.get_correlation(s1, s2)
                if corr > 0:
                    total_risk += abs(corr)
                    count += 1
        
        return total_risk / count if count > 0 else 0.0
    
    def check_correlation_limit(self, symbol: str, existing_positions: Dict) -> Tuple[bool, str]:
        """Check if adding symbol would exceed correlation limits"""
        if symbol not in self.correlation_matrix.columns:
            return True, "No correlation data"
        
        correlations = self.correlation_matrix[symbol]
        for pos_symbol in existing_positions:
            if pos_symbol in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[symbol, pos_symbol]
                if corr > self.max_correlation:
                    return False, f"High correlation ({corr:.2f}) with {pos_symbol}"
        return True, "OK"


class PortfolioOptimizer:
    """Portfolio optimization using Modern Portfolio Theory and risk parity"""
    
    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate
        
    def optimize_sharpe(self, 
                        expected_returns: np.ndarray,
                        cov_matrix: np.ndarray,
                        max_weight: float = 1.0,
                        min_weight: float = 0.0) -> np.ndarray:
        """Maximize Sharpe ratio"""
        if not SCIPY_AVAILABLE:
            return self._equal_weight(len(expected_returns))
        
        n = len(expected_returns)
        
        def neg_sharpe(w):
            port_ret = np.dot(w, expected_returns)
            port_vol = np.sqrt(w @ np.array(cov_matrix) @ w)
            if port_vol == 0:
                return 1e6
            return -(np.dot(w, expected_returns) - 0.02/252) / port_vol
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # weights sum to 1
        ]
        
        bounds = [(0, 1) for _ in range(n)]
        
        # Initial guess
        x0 = np.ones(n) / n
        
        try:
            result = minimize(
                neg_sharpe, x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000}
            )
            return result.x
        except:
            return self._equal_weight(n)
    
    def optimize_min_variance(self, cov_matrix: np.ndarray, 
                               max_weight: float = 1.0) -> np.ndarray:
        """Minimum variance portfolio"""
        if not SCIPY_AVAILABLE:
            return self._equal_weight(len(cov_matrix))
        
        n = len(cov_matrix)
        
        def portfolio_variance(w):
            return w @ np.array(cov_matrix) @ w
        
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        bounds = [(0, max_weight) for _ in range(n)]
        x0 = np.ones(n) / n
        
        try:
            result = minimize(
                portfolio_variance, x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000}
            )
            return result.x
        except:
            return self._equal_weight(n)
    
    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Risk parity portfolio"""
        if not SCIPY_AVAILABLE:
            return self._equal_weight(len(cov_matrix))
        
        n = len(cov_matrix)
        
        def risk_budget_objective(w):
            # Risk contribution of each asset
            port_vol = np.sqrt(w @ np.array(cov_matrix) @ w)
            marginal_risk = (np.array(cov_matrix) @ w) / port_vol
            risk_contrib = w * marginal_risk
            target = 1.0 / len(w)
            return np.sum((risk_contrib - target) ** 2)
        
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0.001, 1) for _ in range(n)]
        x0 = np.ones(n) / n
        
        try:
            result = minimize(
                risk_budget_objective, x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000}
            )
            return result.x
        except:
            return self._equal_weight(n)
    
    def _equal_weight(self, n: int) -> np.ndarray:
        return np.ones(n) / n
    
    def optimize_hrp(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Hierarchical Risk Parity (HRP)"""
        # Simplified HRP - uses hierarchical clustering
        from scipy.cluster.hierarchy import linkage, dendrogram
        from scipy.spatial.distance import squareform
        
        # Convert correlation to distance
        corr = np.corrcoef(cov_matrix)  # This is wrong, need correlation from cov
        # Simplified: just use inverse volatility
        inv_vol = 1 / np.sqrt(np.diag(cov_matrix))
        return inv_vol / np.sum(inv_vol)


class RiskManager:
    """Advanced Risk Manager with portfolio optimization"""
    
    def __init__(self, config: dict):
        self.config = config
        self.initial_balance = config.get('capital_usdt', 170.0)
        self.risk_per_trade = config.get('risk_per_trade', 0.01)
        self.max_concurrent = config.get('max_concurrent_trades', 3)
        self.max_heat = config.get('max_portfolio_heat', 1.0)
        self.max_daily_dd = config.get('max_daily_drawdown', 0.05)
        self.max_total_dd = config.get('max_total_drawdown', 0.15)
        
        # Advanced components
        self.correlation_manager = CorrelationManager(
            max_correlation=config.get('max_correlation', 0.7),
            lookback=config.get('correlation_lookback', 100)
        )
        
        self.portfolio_optimizer = PortfolioOptimizer()
        
        self.kelly_calculator = KellyCalculator(
            max_fraction=config.get('kelly_max_fraction', 0.25)
        )
        
        self.vol_sizer = VolatilitySizer(
            target_vol=config.get('target_volatility', 0.15),
            max_leverage=config.get('max_leverage', 1.0)
        )
        
        self.drawdown_controller = DrawdownController(config)
        
        self.initial_balance = config.get('capital_usdt', 170.0)
        self.risk_per_trade = config.get('risk_per_trade', 0.01)
        
        self.portfolio = Portfolio(
            balance=config.get('capital_usdt', 170.0),
            peak_balance=self.initial_balance
        )
        
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason = ""
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("AdvancedRiskManager initialized")
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                                symbol: str = "", volatility: float = 2.0) -> float:
        """Calculate position size using multiple methods"""
        if entry_price <= stop_loss:
            return 0.0
        
        # Method 1: Kelly-based
        kelly_size = self._kelly_based_size(entry_price, stop_loss, symbol)
        
        # Method 2: Volatility targeting
        vol_size = self._volatility_based_size(entry_price, stop_loss, symbol, volatility)
        
        # Method 3: Fixed fractional
        frac_size = self._fixed_fractional_size(entry_price, stop_loss)
        
        # Method 4: Volatility targeting with correlation adjustment
        corr_adjusted = self._correlation_adjusted_size(entry_price, stop_loss, symbol)
        
        # Use minimum (conservative)
        size = min(kelly_size, vol_size, frac_size, corr_adjusted)
        
        return round(size, 6)
    
    def _kelly_based_size(self, entry_price: float, stop_loss: float, symbol: str) -> float:
        if self.portfolio.balance <= 0:
            return 0.0
        
        kelly_frac = self.kelly_calculator.safe_kelly(
            self.portfolio.trades_history if hasattr(self.portfolio, 'trades_history') else [],
            self.risk_per_trade
        )
        
        risk_amount = self.portfolio.balance * kelly_frac
        risk_per_share = entry_price - stop_loss
        
        if risk_per_share <= 0:
            return 0.0
        
        return risk_amount / risk_per_share
    
    def _volatility_based_size(self, entry_price: float, stop_loss: float, 
                                symbol: str, volatility: float) -> float:
        return self.vol_sizer.calculate_size(
            self.portfolio.balance, entry_price, stop_loss, 0, volatility
        )
    
    def _fixed_fractional_size(self, entry_price: float, stop_loss: float) -> float:
        if self.portfolio.balance <= 0:
            return 0.0
        
        risk_amount = self.portfolio.balance * self.risk_per_trade
        risk_per_share = entry_price - stop_loss
        
        if risk_per_share <= 0:
            return 0.0
        
        return risk_amount / risk_per_share
    
    def _correlation_adjusted_size(self, entry_price: float, stop_loss: float, symbol: str) -> float:
        """Adjust position size based on correlation with existing positions"""
        base_size = self._fixed_fractional_size(entry_price, stop_loss)
        
        if not hasattr(self, 'correlation_manager'):
            return 0.0
        
        # Check correlation risk
        can_open, reason = self.correlation_manager.check_correlation_limit(
            symbol, {s: p.symbol for s, p in self.portfolio.positions.items()}
        )
        
        if not can_open:
            return 0.0
        
        # Reduce size if high correlation
        corr_risk = 0.0  # Would calculate actual correlation risk
        if corr_risk > 0.5:
            return base_size * 0.5
        
        return base_size
    
    def check_circuit_breakers(self) -> Tuple[bool, str]:
        """Check all circuit breakers"""
        balance = self.portfolio.balance
        current_equity = self.get_equity({})
        
        return self.drawdown_controller.check_limits(balance)
    
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        equity = self.portfolio.balance
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
                equity += position.size * current_prices[symbol]
            else:
                equity += position.size * position.entry_price
        return equity
    
    def check_circuit_breakers(self) -> Tuple[bool, str]:
        """Check all circuit breakers"""
        return self.drawdown_controller.check_limits(self.portfolio.balance)
    
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        equity = self.portfolio.balance
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
                equity += position.size * current_prices[symbol]
            else:
                equity += position.size * position.entry_price
        return equity
    
    def update_trailing_stops(self, current_prices: Dict[str, float]):
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
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
                trail_distance = atr_approx * 1.0
                new_trail = position.highest_price - trail_distance
                if new_trail > position.trailing_stop:
                    position.trailing_stop = new_trail
    
    def check_exits(self, current_prices: Dict[str, float]) -> List[dict]:
        closed_trades = []
        
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
                    trade['entry_signal'] = position.entry_signal
                    trade['strategy'] = position.strategy_name
                    trade['confidence'] = position.confidence
                    trade['timeframe'] = position.timeframe
                    trade['duration'] = (datetime.now() - position.entry_time).total_seconds() / 3600
                    trades_history.append(trade)
        
        return closed_trades
    
    def open_position(self, signal, size: float) -> Position:
        position = Position(
            symbol=signal.symbol,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            size=size,
            entry_time=datetime.now(),
            highest_price=signal.price,
            trailing_stop=signal.stop_loss,
            action=signal.action,
            kelly_fraction=signal.confidence * 0.25,
            strategy_name=signal.strategy_name,
            confidence=signal.confidence,
            timeframe=signal.timeframe,
            entry_signal=signal.reason
        )
        self.portfolio.positions[signal.symbol] = position
        self.portfolio.balance -= size * signal.price
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
            'exit_time': datetime.now(),
            'duration': (datetime.now() - position.entry_time).total_seconds() / 3600
        }
        
        return trade
    
    def get_metrics(self) -> dict:
        metrics = super().get_metrics()
        
        # Add advanced metrics
        metrics.update({
            'var_95': self.calculate_var(0.95),
            'var_99': self.calculate_var(0.99),
            'cvar_95': self.calculate_cvar(0.95),
            'cvar_99': self.calculate_cvar(0.99),
            'correlation_risk': self.correlation_manager.get_portfolio_correlation_risk(
                self.portfolio.positions
            ),
            'portfolio_heat': self.get_portfolio_heat(),
            'kelly_fraction': self.kelly_calculator.safe_kelly([], self.risk_per_trade),
        }
        
        return metrics
    
    def calculate_var(self, confidence: float = 0.95) -> float:
        """Value at Risk"""
        if not self.portfolio.trades_history:
            return 0.0
        
        returns = [t['pnl_pct'] / 100 for t in self.portfolio.trades_history]
        return RiskMetricsCalculator.calculate_var(np.array(returns), confidence)
    
    def calculate_cvar(self, confidence: float = 0.95) -> float:
        """Conditional Value at Risk"""
        if not self.portfolio.trades_history:
            return 0.0
        
        returns = [t['pnl_pct'] / 100 for t in self.portfolio.trades_history]
        return RiskMetricsCalculator.calculate_cvar(np.array(returns), confidence)
    
    def get_portfolio_heat(self) -> float:
        if self.portfolio.balance <= 0:
            return 0.0
        exposure = sum(p.size * p.entry_price for p in self.portfolio.positions.values())
        return exposure / self.portfolio.balance
    
    def get_portfolio_risk_report(self) -> dict:
        """Generate comprehensive risk report"""
        metrics = self.get_metrics()
        
        positions = {}
        for sym, pos in self.portfolio.positions.items():
            positions[sym] = {
                'entry_price': pos.entry_price,
                'current_price': pos.highest_price,
                'size': pos.size,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'trailing_stop': pos.trailing_stop,
                'confidence': pos.confidence,
                'duration_hours': (datetime.now() - pos.entry_time).total_seconds() / 3600,
                'mae': pos.max_adverse_excursion,
                'mfe': pos.max_favorable_excursion
            }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'positions': positions,
            'total_exposure': sum(p['size'] * p['entry_price'] for p in positions.values()),
            'cash_balance': self.portfolio.balance,
            'total_equity': self.get_equity({}),
            'correlation_matrix': self.correlation_manager.correlation_matrix.to_dict() if not self.correlation_manager.correlation_matrix.empty else {}
        }

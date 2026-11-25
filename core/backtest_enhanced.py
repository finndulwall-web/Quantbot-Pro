"""
Enhanced Backtesting Module
Monte Carlo simulation, sensitivity analysis, regime-aware testing, and advanced visualization
"""
import pandas as pd
import numpy as np
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import json
from collections import defaultdict
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total_return: float
    win_rate: float
    max_drawdown: float
    sharpe: float
    total_trades: int
    profit_factor: float
    equity_curve: List[float]
    buy_hold_curve: List[float]
    timestamps: List[pd.Timestamp]
    trades: List[dict]
    params: dict
    # Enhanced metrics
    sortino: float = 0.0
    calmar: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    avg_trade_duration: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    equity_curve_daily: List[float] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    drawdown_periods: List[dict] = field(default_factory=list)
    regime_performance: Dict[str, dict] = field(default_factory=dict)


@dataclass
class MonteCarloResult:
    n_simulations: int
    median_return: float
    mean_return: float
    std_return: float
    percentile_5: float
    percentile_95: float
    prob_profit: float
    percentile_5_dd: float
    percentile_95_dd: float
    ruin_probability: float
    equity_curves: List[List[float]]


@dataclass
class SensitivityResult:
    param_name: str
    param_values: List[float]
    returns: List[float]
    sharpes: List[float]
    drawdowns: List[float]
    win_rates: List[float]
    optimal_value: float
    sensitivity_score: float


class MonteCarloSimulator:
    """Monte Carlo simulation for strategy validation"""
    
    def __init__(self, config: dict):
        self.config = config
        self.n_simulations = config.get('mc_simulations', 200)
        self.bootstrap_method = config.get('mc_method', 'bootstrap')  # 'bootstrap', 'parametric', 'block'
        self.block_size = config.get('mc_block_size', 20)
        
    def run(self, trades: List[dict], equity_curve: List[float], 
            initial_balance: float) -> MonteCarloResult:
        """Run Monte Carlo simulation on trade results"""
        if len(trades) < 10:
            logger.warning("Insufficient trades for Monte Carlo simulation")
            return self._empty_result()
        
        returns = [t['pnl_pct'] / 100 for t in trades]
        
        equity_curves = []
        final_returns = []
        max_drawdowns = []
        
        for sim in range(self.n_simulations):
            if self.bootstrap_method == 'bootstrap':
                sim_returns = np.random.choice(returns, size=len(returns), replace=True)
            elif self.bootstrap_method == 'block':
                sim_returns = self._block_bootstrap(returns)
            elif self.bootstrap_method == 'parametric':
                sim_returns = self._parametric_bootstrap(returns)
            else:
                sim_returns = np.random.choice(returns, size=len(returns), replace=True)
            
            # Build equity curve
            equity = [initial_balance]
            for r in sim_returns:
                equity.append(equity[-1] * (1 + r))
            
            equity_curves.append(equity)
            final_returns.append((equity[-1] - initial_balance) / initial_balance * 100)
            
            # Calculate drawdown
            peak = equity[0]
            max_dd = 0
            for val in equity:
                peak = max(peak, val)
                dd = (peak - val) / peak * 100
                max_dd = max(max_dd, dd)
            max_drawdowns.append(max_dd)
        
        final_returns = np.array(final_returns)
        max_drawdowns = np.array(max_drawdowns)
        
        # Probability of profit
        prob_profit = np.mean(final_returns > 0) * 100
        
        # Ruin probability (drawdown > 50%)
        ruin_prob = np.mean(np.array(max_drawdowns) > 50) * 100
        
        return MonteCarloResult(
            n_simulations=self.n_simulations,
            median_return=np.median(final_returns),
            mean_return=np.mean(final_returns),
            std_return=np.std(final_returns),
            percentile_5=np.percentile(final_returns, 5),
            percentile_95=np.percentile(final_returns, 95),
            prob_profit=prob_profit,
            percentile_5_dd=np.percentile(max_drawdowns, 5),
            percentile_95_dd=np.percentile(max_drawdowns, 95),
            ruin_probability=ruin_prob,
            equity_curves=equity_curves[:10]  # Store first 10 for plotting
        )
    
    def _block_bootstrap(self, returns: List[float]) -> np.ndarray:
        """Block bootstrap for time series dependence"""
        n = len(returns)
        block_size = self.block_size
        n_blocks = int(np.ceil(n / block_size))
        
        result = []
        for _ in range(n_blocks):
            start = np.random.randint(0, len(returns) - block_size + 1)
            block = returns[start:start + block_size]
            result.extend(block)
        
        return np.array(result[:n])
    
    def _parametric_bootstrap(self, returns: List[float]) -> np.ndarray:
        """Parametric bootstrap assuming normal distribution"""
        mean = np.mean(returns)
        std = np.std(returns)
        return np.random.normal(mean, std, len(returns))
    
    def _empty_result(self) -> MonteCarloResult:
        return MonteCarloResult(
            n_simulations=0, median_return=0, mean_return=0, std_return=0,
            percentile_5=0, percentile_95=0, prob_profit=0,
            percentile_5_dd=0, percentile_95_dd=0, ruin_probability=0,
            equity_curves=[]
        )


class SensitivityAnalyzer:
    """Parameter sensitivity analysis"""
    
    def __init__(self, config: dict):
        self.config = config
        self.n_points = config.get('sensitivity_points', 10)
        
    def analyze(self, engine, symbol: str, timeframe: str, start: str, end: str,
                param_ranges: Dict[str, Tuple[float, float]]) -> Dict[str, SensitivityResult]:
        """Analyze sensitivity of each parameter"""
        results = {}
        
        for param_name, (min_val, max_val) in param_ranges.items():
            logger.info(f"Analyzing sensitivity for {param_name}")
            result = self._analyze_param(engine, symbol, timeframe, start, end,
                                         param_name, min_val, max_val)
            results[param_name] = result
        
        return results
    
    def _analyze_param(self, engine, symbol: str, timeframe: str, start: str, end: str,
                       param_name: str, min_val: float, max_val: float) -> SensitivityResult:
        """Analyze single parameter sensitivity"""
        n_points = self.n_points
        param_values = np.linspace(min_val, max_val, n_points)
        
        returns = []
        sharpes = []
        drawdowns = []
        win_rates = []
        
        for val in param_values:
            params = {param_name: val}
            result = engine.run(symbol, timeframe, start, end, params)
            
            returns.append(result.total_return)
            sharpes.append(result.sharpe)
            drawdowns.append(result.max_drawdown)
            win_rates.append(result.win_rate)
        
        # Find optimal value (max Sharpe)
        if sharpes:
            optimal_idx = np.argmax(sharpes)
            optimal_value = param_values[optimal_idx]
        else:
            optimal_value = param_values[len(param_values)//2]
        
        # Sensitivity score: how much output changes relative to input change
        if len(returns) > 1:
            return_range = max(returns) - min(returns)
            param_range = max(param_values) - min(param_values)
            sensitivity = return_range / param_range if param_range > 0 else 0
        else:
            sensitivity = 0
        
        return SensitivityResult(
            param_name=param_name,
            param_values=param_values.tolist(),
            returns=returns,
            sharpes=sharpes,
            drawdowns=drawdowns,
            win_rates=win_rates,
            optimal_value=optimal_value,
            sensitivity_score=sensitivity
        )


class RegimeDetector:
    """Market regime detection for strategy adaptation"""
    
    def __init__(self, config: dict):
        self.config = config
        self.lookback = config.get('regime_lookback', 200)
        self.regimes = ['bull', 'bear', 'sideways', 'volatile', 'calm']
        self.current_regime = 'unknown'
        self.regime_history = []
        
    def detect(self, df: pd.DataFrame) -> str:
        """Detect current market regime"""
        if len(df) < self.lookback:
            return 'unknown'
        
        recent = df.tail(self.lookback)
        close = recent['close']
        
        # Trend strength
        ema_50 = close.ewm(span=50).mean().iloc[-1]
        ema_200 = close.ewm(span=200).mean().iloc[-1]
        trend = 'bull' if ema_50 > ema_200 else 'bear'
        
        # Volatility regime
        returns = close.pct_change().dropna()
        vol = returns.rolling(20).std().iloc[-1]
        vol_median = returns.rolling(100).std().median()
        
        if vol > vol_median * 1.5:
            vol_regime = 'volatile'
        elif vol < vol_median * 0.5:
            vol_regime = 'calm'
        else:
            vol_regime = 'normal'
        
        # Momentum
        mom_20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) > 20 else 0
        mom_60 = (close.iloc[-1] / close.iloc[-60] - 1) if len(close) > 60 else 0
        
        # Determine regime
        if trend == 'bull' and vol_regime == 'calm':
            regime = 'bull_trending'
        elif trend == 'bull' and vol_regime == 'volatile':
            regime = 'bull_volatile'
        elif trend == 'bear' and vol_regime == 'calm':
            regime = 'bear_trending'
        elif trend == 'bear' and vol_regime == 'volatile':
            regime = 'bear_volatile'
        else:
            regime = 'sideways'
        
        self.current_regime = regime
        self.regime_history.append({
            'timestamp': pd.Timestamp.now(),
            'regime': regime,
            'trend': trend,
            'vol_regime': vol_regime,
            'momentum_20': mom_20,
            'momentum_60': mom_60
        })
        
        return regime
    
    def get_regime_stats(self, trades: List[dict]) -> Dict[str, dict]:
        """Analyze performance by regime"""
        if not hasattr(self, 'regime_history') or not self.regime_history:
            return {}
        
        # This would need trade timestamps to match with regimes
        # Simplified for now
        return {}


class EnhancedBacktestEngine:
    """Enhanced backtesting engine with Monte Carlo, sensitivity, and regime analysis"""
    
    def __init__(self, config: dict):
        self.config = config
        self.slippage = config.get('slippage_pct', 0.001)
        self.fee = config.get('fee_pct', 0.001)
        
        # Enhanced components
        self.mc_simulator = MonteCarloSimulator(config)
        self.sensitivity_analyzer = SensitivityAnalyzer(config)
        self.regime_detector = RegimeDetector(config)
        
        # Slippage models
        self.slippage_model = config.get('slippage_model', 'fixed')  # 'fixed', 'sqrt', 'linear', 'adaptive'
        self.slippage_base = config.get('slippage_pct', 0.001)
        self.fee = config.get('fee_pct', 0.001)
        
    def run(self, symbol: str, timeframe: str, start: str, end: str, 
            params: Optional[dict] = None) -> 'BacktestResult':
        """Enhanced backtest with regime detection and detailed metrics"""
        from core.data import fetch_backtest_data
        from core.strategy import Strategy, Signal
        from core.risk_enhanced import AdvancedRiskManager, Portfolio
        from core.indicators_enhanced import add_all_enhanced_indicators
        
        test_config = self.config.copy()
        if params:
            test_config.update(params)
        
        # Fetch data
        df = fetch_backtest_data(symbol, timeframe, start, end)
        if df.empty:
            logger.error(f"No data for {symbol} backtest")
            return self._empty_result()
        
        # Add enhanced indicators
        df = add_all_enhanced_indicators(df, test_config)
        df = df.dropna()
        
        if len(df) < 200:
            logger.error(f"Insufficient data after indicators: {len(df)} candles")
            return self._empty_result()
        
        # Detect regimes
        regime = self.regime_detector.detect(df)
        logger.info(f"Detected market regime: {regime}")
        
        # Initialize
        strategy = Strategy(test_config)
        risk = AdvancedRiskManager(test_config)
        risk.portfolio = Portfolio(balance=test_config.get('capital_usdt', 170.0))
        
        equity_curve = [risk.portfolio.balance]
        buy_hold_curve = [risk.portfolio.balance]
        timestamps = [df.index[0]]
        daily_equity = {}
        daily_returns = []
        initial_price = df['close'].iloc[0]
        
        # Track regime performance
        regime_trades = defaultdict(list)
        
        for i in range(200, len(df)):
            current_df = df.iloc[:i+1]
            current_price = current_df['close'].iloc[-1]
            current_time = current_df.index[-1]
            
            # Buy & hold
            buy_hold_value = risk.portfolio.balance * (current_price / initial_price)
            
            # Detect regime for this period
            regime = self.regime_detector.detect(current_df)
            
            # Generate signal
            signal = strategy.generate_signal(current_df, symbol)
            
            if signal and len(risk.portfolio.positions) < test_config.get('max_concurrent_trades', 3):
                can_open, size = risk.can_open_position(symbol, signal.price, signal.stop_loss)
                if can_open:
                    signal.strategy_name = f"regime_{self.regime_detector.current_regime}"
                    risk.open_position(signal, size)
                # Update positions
            current_prices = {symbol: current_price}
            risk.update_trailing_stops(current_prices)
            closed = risk.check_exits(current_prices)
            
            # Track regime performance
            for trade in closed:
                regime_trades[self.regime_detector.current_regime].append(trade)
            
            equity = risk.get_equity(current_prices)
            
            # Daily tracking
            date_key = current_time.date()
            if date_key not in daily_equity:
                daily_equity[date_key] = equity
            else:
                daily_equity[date_key] = equity
            
            equity_curve.append(equity)
            buy_hold_curve.append(buy_hold_value)
            timestamps.append(current_time)
        
        # Calculate enhanced metrics
        metrics = risk.get_metrics()
        
        # Daily returns
        daily_eq = pd.Series(daily_equity)
        daily_eq.index = pd.to_datetime(daily_eq.index)
        daily_rets = daily_eq.pct_change().dropna()
        
        # Monthly returns
        monthly_rets = daily_eq.resample('ME').last().pct_change().dropna() * 100
        
        # Drawdown periods
        drawdown_periods = self._calculate_drawdown_periods(equity_curve, timestamps)
        
        # Regime performance
        regime_performance = {}
        for regime_name, trades in regime_trades.items():
            if trades:
                returns = [t['pnl_pct'] / 100 for t in trades]
                regime_performance[regime_name] = {
                    'trades': len(trades),
                    'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100,
                    'avg_return': np.mean(returns) * 100,
                    'total_return': sum(returns) * 100,
                    'sharpe': np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
                }
        
        # Monte Carlo simulation
        mc_result = None
        if len(trades) >= 10:
            mc = MonteCarloSimulator(self.config)
            mc_result = mc.run(risk.portfolio.trades_history, equity_curve, risk.initial_balance)
        
        # Calculate enhanced metrics
        returns = [t['pnl_pct'] / 100 for t in trades]
        daily_returns = daily_rets.tolist()
        
        return BacktestResult(
            total_return=metrics['total_return'],
            win_rate=metrics['win_rate'],
            max_drawdown=metrics['max_drawdown'],
            sharpe=metrics['sharpe'],
            total_trades=metrics['total_trades'],
            profit_factor=metrics['profit_factor'],
            equity_curve=equity_curve,
            buy_hold_curve=buy_hold_curve,
            timestamps=timestamps,
            trades=risk.portfolio.trades_history,
            params=test_config,
            # Enhanced
            sortino=metrics.get('sortino', 0),
            calmar=metrics.get('calmar', 0),
            expectancy=metrics.get('expectancy', 0),
            avg_win=metrics.get('avg_win', 0),
            avg_loss=metrics.get('avg_loss', 0),
            largest_win=metrics.get('largest_win', 0),
            largest_loss=metrics.get('largest_loss', 0),
            consecutive_wins=metrics.get('consecutive_wins', 0),
            consecutive_losses=metrics.get('consecutive_losses', 0),
            avg_trade_duration=0,
            max_consecutive_wins=metrics.get('consecutive_wins', 0),
            max_consecutive_losses=metrics.get('consecutive_losses', 0),
            var_95=np.percentile(daily_returns, 5) * 100 if len(daily_returns) > 0 else 0,
            var_99=np.percentile(daily_returns, 1) * 100 if len(daily_returns) > 0 else 0,
            expected_shortfall=np.mean([r for r in daily_returns if r < np.percentile(daily_returns, 5)]) * 100 if len(daily_returns) > 0 else 0,
            equity_curve_daily=list(daily_equity.values()),
            daily_returns=daily_returns,
            monthly_returns=monthly_rets.to_dict() if len(monthly_rets) > 0 else {},
            drawdown_periods=self._calculate_drawdown_periods(equity_curve, timestamps),
            regime_performance=regime_performance
        )
    
    def _calculate_drawdown_periods(self, equity_curve: List[float], timestamps: List[pd.Timestamp]) -> List[dict]:
        """Calculate drawdown periods"""
        periods = []
        peak = equity_curve[0]
        in_drawdown = False
        dd_start = None
        peak_idx = 0
        
        for i, (val, ts) in enumerate(zip(equity_curve, timestamps)):
            if val < peak:
                if not in_drawdown:
                    in_drawdown = True
                    dd_start = timestamps[peak_idx]
            if val > peak:
                if in_drawdown:
                    in_drawdown = False
                    if dd_start is not None:
                        # peak_idx is the index of the peak before the drawdown started
                        trough_idx = peak_idx + equity_curve[peak_idx:i].index(min(equity_curve[peak_idx:i]))
                        periods.append({
                            'start': dd_start.isoformat(),
                            'end': timestamps[i-1].isoformat(),
                            'peak': peak,
                            'trough': equity_curve[trough_idx],
                            'max_dd_pct': (peak - equity_curve[trough_idx]) / peak * 100,
                            'duration_days': (ts - dd_start).days
                        })
                    dd_start = None
                peak = val
                peak_idx = i
        
        return [p for p in periods if p['max_dd_pct'] > 1.0]  # Only significant drawdowns
    
    def _empty_result(self):
        return BacktestResult(0, 0, 0, 0, 0, 0, [], [], [], [], {})
    
    def grid_search(self, symbol: str, timeframe: str, start: str, end: str) -> Tuple[dict, 'BacktestResult']:
        """Enhanced grid search with more parameters"""
        param_grid = {
            'rsi_oversold': [20, 25, 30, 35],
            'ema_short': [10, 20, 30],
            'ema_medium': [30, 50, 80],
            'ema_long': [100, 150, 200],
            'macd_fast': [8, 12, 16],
            'macd_slow': [21, 26, 34],
            'macd_signal': [7, 9, 12],
            'atr_period': [10, 14, 20],
            'st_period': [7, 10, 14],
            'st_mult': [2.0, 3.0, 4.0],
            'tp_atr_mult': [1.5, 2.0, 2.5, 3.0],
            'sl_atr_mult': [0.8, 1.0, 1.2, 1.5],
            'trail_atr_mult': [0.5, 1.0, 1.5],
            'volume_mult': [1.2, 1.5, 2.0],
            'min_confidence': [0.5, 0.6, 0.7],
        }
        
        # Use random search for efficiency (random subset of combinations)
        n_iterations = self.config.get('grid_search_iterations', 50)
        
        best_result = None
        best_params = None
        best_score = -float('inf')
        
        import random
        keys = list(param_grid.keys())
        
        for i in range(n_iterations):
            params = {k: random.choice(v) for k, v in param_grid.items()}
            
            # Ensure EMA ordering
            if not (params['ema_short'] < params['ema_medium'] < params['ema_long']):
                continue
            
            logger.info(f"Random search {i+1}/{n_iterations}: {params}")
            result = self.run(symbol, timeframe, start, end, params)
            
            if result.total_trades < 10:
                continue
            
            # Multi-objective score
            score = (result.win_rate * 0.3 + 
                     (100 - result.max_drawdown) * 0.25 + 
                     result.sharpe * 10 * 0.25 +
                     result.total_return * 0.2)
            
            if score > best_score:
                best_score = score
                best_params = params
                best_result = result
        
        if best_params:
            logger.info(f"Best params: {best_params} | Score: {best_score:.2f}")
            logger.info(f"  Return: {best_result.total_return:.2f}% | WR: {best_result.win_rate:.1f}% | DD: {best_result.max_drawdown:.2f}% | Sharpe: {best_result.sharpe:.2f}")
        
        return best_params, best_result
    
    def sensitivity_analysis(self, engine, symbol: str, timeframe: str, start: str, end: str,
                            param_ranges: Dict[str, Tuple[float, float]]) -> Dict[str, SensitivityResult]:
        """Run sensitivity analysis on key parameters"""
        return self.sensitivity_analyzer.analyze(engine, symbol, timeframe, start, end, param_ranges)
    
    def walk_forward_optimize(self, symbol: str, timeframe: str, start: str, end: str,
                              train_window: int = 90, test_window: int = 30, 
                              step: int = 30) -> WalkForwardResult:
        """Enhanced walk-forward with regime-aware validation"""
        from datetime import datetime, timedelta
        
        start_dt = pd.Timestamp(start)
        end_dt = pd.Timestamp(end)
        total_days = (end_dt - start_dt).days
        
        windows = []
        all_params = []
        
        current_start = start_dt
        window_num = 0
        
        while current_start + timedelta(days=train_window + test_window) <= end_dt:
            window_num += 1
            train_start = current_start
            train_end = current_start + timedelta(days=train_window)
            test_start = train_end
            test_end = min(test_start + timedelta(days=test_window), end_dt)
            
            logger.info(f"Walk-forward window {window_num}: Train {train_start.date()} to {train_end.date()}, Test {test_start.date()} to {test_end.date()}")
            
            best_params, best_result = self.grid_search(
                symbol, timeframe, 
                train_start.strftime('%Y-%m-%d'), 
                train_end.strftime('%Y-%m-%d')
            )
            
            if best_params:
                test_result = self.run(
                    symbol, timeframe,
                    test_start.strftime('%Y-%m-%d'),
                    test_end.strftime('%Y-%m-%d'),
                    best_params
                )
                
                windows.append({
                    'window': window_num,
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'params': best_params,
                    'train_result': best_result,
                    'test_result': test_result
                })
                all_params.append(best_params)
            
            current_start += timedelta(days=step)
        
        if not windows:
            return WalkForwardResult([], 0, 0, 0, 0, {})
        
        test_returns = [w['test_result'].total_return for w in windows]
        test_sharpes = [w['test_result'].sharpe for w in windows]
        test_dds = [w['test_result'].max_drawdown for w in windows]
        
        positive_windows = sum(1 for r in test_returns if r > 0)
        consistency = positive_windows / len(windows) * 100
        
        param_keys = windows[0]['params'].keys()
        avg_params = {}
        for k in param_keys:
            values = [w['params'][k] for w in windows]
            avg_params[k] = max(set(values), key=values.count)
        
        logger.info(f"Walk-forward complete: {len(windows)} windows, consistency={consistency:.1f}%")
        logger.info(f"Avg test return: {np.mean(test_returns):.2f}%, Avg Sharpe: {np.mean(test_sharpes):.2f}")
        
        return WalkForwardResult(
            windows=windows,
            avg_return=np.mean(test_returns),
            avg_sharpe=np.mean(test_sharpes),
            avg_dd=np.mean(test_dds),
            consistency=consistency,
            params=avg_params
        )
    
    def run_monte_carlo(self, result: 'BacktestResult', n_simulations: int = 500) -> MonteCarloResult:
        """Run Monte Carlo simulation on backtest results"""
        mc = MonteCarloSimulator(self.config)
        mc.n_simulations = n_simulations
        return mc.run(result.trades, result.equity_curve, self.config.get('capital_usdt', 170.0))
    
    def plot_enhanced_results(self, result: 'BacktestResult', symbol: str, 
                              mc_result: Optional[MonteCarloResult] = None,
                              save_path: str = "backtest_enhanced.png"):
        """Create comprehensive backtest visualization"""
        fig = plt.figure(figsize=(16, 14))
        gs = GridSpec(5, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # 1. Equity Curve with MC envelopes
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(result.timestamps, result.equity_curve, label='Strategy', color='#00ff88', linewidth=1.5)
        ax1.plot(result.timestamps, result.buy_hold_curve, label='Buy & Hold', color='#ffaa00', linewidth=1, alpha=0.7)
        
        if mc_result and mc_result.equity_curves:
            for i, eq_curve in enumerate(mc_result.equity_curves[:20]):
                alpha = 0.05 if i > 0 else 0.15
                ax1.plot(result.timestamps[:len(eq_curve)], eq_curve, color='#00ff88', alpha=alpha, linewidth=0.5)
        
        ax1.set_title(f'{symbol} Backtest Equity Curve', color='white', fontsize=14)
        ax1.set_ylabel('Equity (USDT)', color='white')
        ax1.legend(facecolor='#1a1a2e', edgecolor='#00ff88', labelcolor='white')
        ax1.grid(True, alpha=0.3)
        ax1.set_facecolor('#0d0d1a')
        ax1.tick_params(colors='white')
        
        # 2. Drawdown
        ax2 = fig.add_subplot(gs[1, 0])
        dd_curve = []
        peak = result.equity_curve[0]
        for val in result.equity_curve:
            peak = max(peak, val)
            dd_curve.append((peak - val) / peak * 100)
        
        ax2.fill_between(result.timestamps, dd_curve, 0, color='#ff3366', alpha=0.3)
        ax2.plot(result.timestamps, dd_curve, color='#ff3366', linewidth=1)
        ax2.set_title('Drawdown %', color='white')
        ax2.set_ylabel('Drawdown %', color='white')
        ax2.grid(True, alpha=0.3)
        ax2.set_facecolor('#0d0d1a')
        ax2.tick_params(colors='white')
        
        # 3. Monthly Returns Heatmap
        ax3 = fig.add_subplot(gs[1, 1])
        if result.monthly_returns:
            months = list(result.monthly_returns.keys())
            returns = list(result.monthly_returns.values())
            colors = ['#00ff88' if r > 0 else '#ff3366' for r in returns]
            ax3.bar(range(len(months)), returns, color=colors, alpha=0.8)
            ax3.set_xticks(range(len(months)))
            ax3.set_xticklabels([m[:3] for m in months], rotation=45)
            ax3.set_title('Monthly Returns %', color='white')
            ax3.set_ylabel('Return %', color='white')
            ax3.grid(True, alpha=0.3)
            ax3.set_facecolor('#0d0d1a')
            ax3.tick_params(colors='white')
        
        # 4. Trade Distribution
        ax4 = fig.add_subplot(gs[2, 0])
        if result.trades:
            returns_pct = [t['pnl_pct'] for t in result.trades]
            ax4.hist(returns_pct, bins=30, color='#00ff88', alpha=0.7, edgecolor='#0d0d1a')
            ax3.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            ax4.set_title('Trade Return Distribution', color='white')
            ax4.set_xlabel('Return %', color='white')
            ax4.set_ylabel('Frequency', color='white')
            ax4.set_facecolor('#0d0d1a')
            ax4.tick_params(colors='white')
        
        # 5. Monthly Returns
        ax5 = fig.add_subplot(gs[2, 1])
        if result.monthly_returns:
            months = list(result.monthly_returns.keys())
            returns = list(result.monthly_returns.values())
            colors = ['#00ff88' if r > 0 else '#ff3366' for r in returns]
            ax5.bar(range(len(months)), returns, color=colors, alpha=0.8)
            ax5.set_xticks(range(len(months)))
            ax5.set_xticklabels([m[:3] for m in months], rotation=45)
            ax5.set_title('Monthly Returns %', color='white')
            ax5.set_facecolor('#0d0d1a')
            ax5.tick_params(colors='white')
        
        # 5. Drawdown Periods
        ax6 = fig.add_subplot(gs[3, 0])
        if result.drawdown_periods:
            dd_starts = [pd.Timestamp(p['start']) for p in result.drawdown_periods]
            dd_magnitudes = [p['max_dd_pct'] for p in result.drawdown_periods]
            durations = [p['duration_days'] for p in result.drawdown_periods]
            scatter = ax6.scatter(dd_starts, dd_magnitudes, s=[d*10 for d in durations], 
                                 c=durations, cmap='Reds', alpha=0.7, edgecolors='white')
            ax6.set_title('Drawdown Periods', color='white')
            ax6.set_ylabel('Max DD %', color='white')
            ax6.set_facecolor('#0d0d1a')
            ax6.tick_params(colors='white')
            plt.colorbar(scatter, ax=ax6, label='Duration (days)')
        
        # 6. Regime Performance
        ax7 = fig.add_subplot(gs[3, 1])
        if result.regime_performance:
            regimes = list(result.regime_performance.keys())
            returns = [result.regime_performance[r]['total_return'] for r in regimes]
            trades = [result.regime_performance[r]['trades'] for r in regimes]
            colors = ['#00ff88' if r > 0 else '#ff3366' for r in returns]
            ax7.bar(regimes, returns, color=colors, alpha=0.8)
            ax7.set_title('Performance by Regime', color='white')
            ax7.set_ylabel('Return %', color='white')
            ax7.set_facecolor('#0d0d1a')
            ax7.tick_params(colors='white')
            for i, (r, t) in enumerate(zip(regimes, trades)):
                ax7.text(i, returns[i] + (2 if returns[i] > 0 else -5), f'{t} trades', 
                        ha='center', color='white', fontsize=8)
        
        # 7. Monte Carlo Distribution
        ax8 = fig.add_subplot(gs[4, :])
        # (Monte Carlo equity curves would be plotted here if mc_result provided)
        ax8.text(0.5, 0.5, 'Monte Carlo Distribution\n(Run mc_simulation to populate)', 
                ha='center', va='center', color='white', fontsize=12)
        ax8.set_facecolor('#0d0d1a')
        
        fig.patch.set_facecolor('#0d0d1a')
        plt.suptitle(f'{symbol} Enhanced Backtest Results', color='white', fontsize=16)
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, facecolor='#0d0d1a', edgecolor='none', bbox_inches='tight')
        plt.close()
        
        logger.info(f"Enhanced backtest chart saved to {save_path}")
    
    def _empty_result(self):
        return BacktestResult(0, 0, 0, 0, 0, 0, [], [], [], [], {})


def print_backtest_summary(result: BacktestResult):
    print("\n" + "="*70)
    print(f"ENHANCED BACKTEST RESULTS")
    print("="*70)
    print(f"Total Return:       {result.total_return:>10.2f}%")
    print(f"Win Rate:           {result.win_rate:>10.2f}%")
    print(f"Max Drawdown:       {result.max_drawdown:>10.2f}%")
    print(f"Sharpe Ratio:       {result.sharpe:>10.2f}")
    print(f"Sortino Ratio:      {result.sortino:>10.2f}")
    print(f"Calmar Ratio:       {result.calmar:>10.2f}")
    print(f"Profit Factor:      {result.profit_factor:>10.2f}")
    print(f"Expectancy:         {result.expectancy:>10.2f}%")
    print(f"Avg Win:            {result.avg_win:>10.2f}%")
    print(f"Avg Loss:           {result.avg_loss:>10.2f}%")
    print(f"Largest Win:        {result.largest_win:>10.2f}%")
    print(f"Largest Loss:       {result.largest_loss:>10.2f}%")
    print(f"Consecutive Wins:   {result.consecutive_wins:>10d}")
    print(f"Consecutive Losses: {result.consecutive_losses:>10d}")
    print(f"Total Trades:       {result.total_trades:>10d}")
    print(f"VaR 95%:            {result.var_95:>10.2f}%")
    print(f"VaR 99%:            {result.var_99:>10.2f}%")
    print(f"Expected Shortfall: {result.expected_shortfall:>10.2f}%")
    print("="*70 + "\n")


def print_monte_carlo_summary(result: MonteCarloResult):
    print("\n" + "="*60)
    print(f"MONTE CARLO SIMULATION ({result.n_simulations} runs)")
    print("="*60)
    print(f"Mean Return:        {result.mean_return:>10.2f}%")
    print(f"Median Return:      {result.median_return:>10.2f}%")
    print(f"Std Return:         {result.std_return:>10.2f}%")
    print(f"5th Percentile:     {result.percentile_5:>10.2f}%")
    print(f"95th Percentile:    {result.percentile_95:>10.2f}%")
    print(f"Probability Profit: {result.prob_profit:>10.1f}%")
    print(f"5th Pctile DD:      {result.percentile_5_dd:>10.2f}%")
    print(f"95th Pctile DD:     {result.percentile_95_dd:>10.2f}%")
    print(f"Ruin Probability:   {result.ruin_probability:>10.2f}%")
    print("="*60 + "\n")


def print_sensitivity_summary(results: Dict[str, SensitivityResult]):
    print("\n" + "="*70)
    print("PARAMETER SENSITIVITY ANALYSIS")
    print("="*70)
    for param, result in results.items():
        print(f"\n{param}:")
        print(f"  Optimal Value:    {result.optimal_value:.4f}")
        print(f"  Sensitivity:      {result.sensitivity_score:.4f}")
        print(f"  Return Range:     {min(result.returns):.2f}% to {max(result.returns):.2f}%")
        print(f"  Sharpe Range:     {min(result.sharpes):.2f} to {max(result.sharpes):.2f}")
        print(f"  DD Range:         {min(result.drawdowns):.2f}% to {max(result.drawdowns):.2f}%")
    print("="*70 + "\n")


def print_walkforward_summary(result: WalkForwardResult):
    print("\n" + "="*60)
    print("WALK-FORWARD OPTIMIZATION RESULTS")
    print("="*60)
    print(f"Windows Tested:     {len(result.windows)}")
    print(f"Avg Test Return:    {result.avg_return:.2f}%")
    print(f"Avg Test Sharpe:    {result.avg_sharpe:.2f}")
    print(f"Avg Test DD:        {result.avg_dd:.2f}%")
    print(f"Consistency:        {result.consistency:.1f}%")
    print(f"Optimized Params:   {result.params}")
    print("\nPer-Window Results:")
    for w in result.windows:
        tr = w['test_result']
        print(f"  W{w['window']}: Return={tr.total_return:.2f}% WR={tr.win_rate:.1f}% DD={tr.max_drawdown:.2f}% Sharpe={tr.sharpe:.2f}")
    print("="*60 + "\n")

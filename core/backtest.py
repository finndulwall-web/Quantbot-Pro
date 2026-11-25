import pandas as pd
import numpy as np
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from core.data import fetch_backtest_data
from core.strategy import Strategy, Signal
from core.risk import RiskManager, Portfolio
from core.indicators import add_all_indicators

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

@dataclass
class WalkForwardResult:
    windows: List[dict]
    avg_return: float
    avg_sharpe: float
    avg_dd: float
    consistency: float
    params: dict

class BacktestEngine:
    def __init__(self, config: dict):
        self.config = config
        self.slippage = config.get('slippage_pct', 0.001)
        self.fee = config.get('fee_pct', 0.001)
    
    def run(self, symbol: str, timeframe: str, start: str, end: str, 
            params: Optional[dict] = None) -> BacktestResult:
        
        test_config = self.config.copy()
        if params:
            test_config.update(params)
        
        df = fetch_backtest_data(symbol, timeframe, start, end)
        if df.empty:
            logger.error(f"No data for {symbol} backtest")
            return self._empty_result()
        
        df = add_all_indicators(df, test_config)
        df = df.dropna()
        
        if len(df) < 200:
            logger.error(f"Insufficient data after indicators: {len(df)} candles")
            return self._empty_result()
        
        strategy = Strategy(test_config)
        risk = RiskManager(test_config)
        risk.portfolio = Portfolio(balance=test_config.get('capital_usdt', 170.0))
        
        equity_curve = [risk.portfolio.balance]
        buy_hold_curve = [risk.portfolio.balance]
        timestamps = [df.index[0]]
        initial_price = df['close'].iloc[0]
        
        for i in range(200, len(df)):
            current_df = df.iloc[:i+1]
            current_price = current_df['close'].iloc[-1]
            current_time = current_df.index[-1]
            
            buy_hold_value = risk.portfolio.balance * (current_price / initial_price)
            buy_hold_curve.append(buy_hold_value)
            
            signal = strategy.generate_signal(current_df, symbol)
            
            if signal and len(risk.portfolio.positions) < test_config.get('max_concurrent_trades', 3):
                can_open, size_or_reason = risk.can_open_position(symbol, signal.price, signal.stop_loss)
                if can_open:
                    risk.open_position(signal, size_or_reason)
            
            current_prices = {symbol: current_price}
            risk.update_trailing_stops(current_prices)
            closed = risk.check_exits(current_prices)
            
            equity = risk.get_equity(current_prices)
            equity_curve.append(equity)
            timestamps.append(current_time)
        
        metrics = risk.get_metrics()
        
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
            params=test_config
        )
    
    def _empty_result(self) -> BacktestResult:
        return BacktestResult(0, 0, 0, 0, 0, 0, [], [], [], [], {})
    
    def grid_search(self, symbol: str, timeframe: str, start: str, end: str) -> Tuple[dict, BacktestResult]:
        rsi_values = [20, 25, 30, 35]
        ema_short_values = [20, 50]
        ema_medium_values = [50, 100]
        ema_long_values = [100, 200]
        
        best_result = None
        best_params = None
        best_score = -float('inf')
        
        total_combos = len(rsi_values) * len(ema_short_values) * len(ema_medium_values) * len(ema_long_values)
        logger.info(f"Starting grid search: {total_combos} combinations")
        
        combo = 0
        for rsi in rsi_values:
            for es in ema_short_values:
                for em in ema_medium_values:
                    for el in ema_long_values:
                        if not (es < em < el):
                            continue
                        
                        combo += 1
                        params = {
                            'rsi_oversold': rsi,
                            'ema_short': es,
                            'ema_medium': em,
                            'ema_long': el
                        }
                        
                        logger.info(f"Grid search {combo}/{total_combos}: {params}")
                        result = self.run(symbol, timeframe, start, end, params)
                        
                        if result.total_trades < 10:
                            continue
                        
                        score = result.win_rate * 0.4 + (100 - result.max_drawdown) * 0.3 + result.sharpe * 10 * 0.3
                        
                        if score > best_score:
                            best_score = score
                            best_params = params
                            best_result = result
        
        if best_params:
            logger.info(f"Best params: {best_params} | Score: {best_score:.2f}")
            logger.info(f"  Return: {best_result.total_return:.2f}% | WR: {best_result.win_rate:.1f}% | DD: {best_result.max_drawdown:.2f}% | Sharpe: {best_result.sharpe:.2f}")
        
        return best_params, best_result
    
    def optimize_loop(self, symbol: str, timeframe: str, start: str, end: str) -> dict:
        current_config = self.config.copy()
        max_iterations = self.config.get('max_opt_iterations', 5)
        
        for iteration in range(max_iterations):
            logger.info(f"=== Optimization Iteration {iteration + 1}/{max_iterations} ===")
            
            result = self.run(symbol, timeframe, start, end, current_config)
            
            logger.info(f"Current: WR={result.win_rate:.1f}% DD={result.max_drawdown:.2f}% Trades={result.total_trades}")
            
            if result.win_rate >= self.config.get('min_win_rate', 55) * 100 and \
               result.max_drawdown <= self.config.get('max_drawdown', 10) and \
               result.total_trades >= 10:
                logger.info("Strategy meets criteria. Stopping optimization.")
                break
            
            if iteration < max_iterations - 1:
                logger.info("Running grid search for better parameters...")
                best_params, best_result = self.grid_search(symbol, timeframe, start, end)
                
                if best_params and best_result.total_trades >= 10:
                    current_config.update(best_params)
                    logger.info(f"Updated config with: {best_params}")
                else:
                    logger.info("No better parameters found. Stopping.")
                    break
        
        return current_config
    
    def walk_forward_optimize(self, symbol: str, timeframe: str, start: str, end: str,
                              train_window: int = 90, test_window: int = 30, 
                              step: int = 30) -> WalkForwardResult:
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
    
    def plot_results(self, result: BacktestResult, symbol: str, save_path: str = "backtest_result.png"):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        ax1.plot(result.timestamps, result.equity_curve, label='Strategy', color='#00ff88', linewidth=1.5)
        ax1.plot(result.timestamps, result.buy_hold_curve, label='Buy & Hold', color='#ffaa00', linewidth=1, alpha=0.7)
        ax1.set_title(f'{symbol} Backtest Equity Curve', color='white', fontsize=14)
        ax1.set_ylabel('Equity (USDT)', color='white')
        ax1.legend(facecolor='#1a1a2e', edgecolor='#00ff88', labelcolor='white')
        ax1.grid(True, alpha=0.3)
        ax1.set_facecolor('#0d0d1a')
        ax1.tick_params(colors='white')
        
        for trade in result.trades:
            color = '#00ff88' if trade['pnl'] > 0 else '#ff3366'
            ax1.scatter(trade['exit_time'], trade['entry_price'] * (1 + trade['pnl_pct']/100), 
                       color=color, s=30, alpha=0.7, zorder=5)
        
        dd_curve = []
        peak = result.equity_curve[0]
        for val in result.equity_curve:
            peak = max(peak, val)
            dd_curve.append((peak - val) / peak * 100)
        
        ax2.fill_between(result.timestamps, dd_curve, 0, color='#ff3366', alpha=0.3)
        ax2.plot(result.timestamps, dd_curve, color='#ff3366', linewidth=1)
        ax2.set_title('Drawdown %', color='white')
        ax2.set_ylabel('Drawdown %', color='white')
        ax2.set_xlabel('Time', color='white')
        ax2.grid(True, alpha=0.3)
        ax2.set_facecolor('#0d0d1a')
        ax2.tick_params(colors='white')
        
        fig.patch.set_facecolor('#0d0d1a')
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, facecolor='#0d0d1a', edgecolor='none')
        plt.close()
        
        logger.info(f"Backtest chart saved to {save_path}")

def print_backtest_summary(result: BacktestResult):
    print("\n" + "="*60)
    print(f"BACKTEST RESULTS: {result.params.get('default_symbol', 'SYMBOL')}")
    print("="*60)
    print(f"Total Return:     {result.total_return:>10.2f}%")
    print(f"Win Rate:         {result.win_rate:>10.2f}%")
    print(f"Max Drawdown:     {result.max_drawdown:>10.2f}%")
    print(f"Sharpe Ratio:     {result.sharpe:>10.2f}")
    print(f"Profit Factor:    {result.profit_factor:>10.2f}")
    print(f"Total Trades:     {result.total_trades:>10d}")
    print("="*60 + "\n")
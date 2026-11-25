"""
QuantBot Pro - Professional Autonomous Trading Bot
Supports local, Render.com, and Docker deployments
"""
import json
import logging
import signal
import sys
import time
import threading
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

from utils.logger import setup_logger
from core.data import fetch_ohlcv
from core.strategy import Strategy
from core.risk_enhanced import AdvancedRiskManager
from core.llm_brain import LLMBrain
from core.backtest_enhanced import BacktestEngine, print_backtest_summary
from utils.notifier import DiscordNotifier

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class QuantBot:
    def __init__(self, config_path: str = "config.json"):
        # Load config from file and environment
        with open(config_path) as f:
            self.config = json.load(f)
        
        # Override with environment variables (for Render deployment)
        self.config.update({
            'mode': os.getenv('MODE', self.config.get('mode', 'paper')),
            'default_symbol': os.getenv('SYMBOL', self.config.get('default_symbol', 'BTC/USDT')),
            'capital_usdt': float(os.getenv('CAPITAL_USDT', self.config.get('capital_usdt', 170.0))),
            'risk_per_trade': float(os.getenv('RISK_PER_TRADE', self.config.get('risk_per_trade', 0.01))),
            'max_concurrent_trades': int(os.getenv('MAX_CONCURRENT_TRADES', self.config.get('max_concurrent_trades', 3))),
            'max_portfolio_heat': float(os.getenv('MAX_PORTFOLIO_HEAT', self.config.get('max_portfolio_heat', 1.0))),
            'max_daily_drawdown': float(os.getenv('MAX_DAILY_DRAWDOWN', self.config.get('max_daily_drawdown', 0.05))),
            'max_total_drawdown': float(os.getenv('MAX_TOTAL_DRAWDOWN', self.config.get('max_total_drawdown', 0.15))),
            'nvidia_api_key': os.getenv('NVIDIA_API_KEY', self.config.get('nvidia_api_key', '')),
            'webhook_url': os.getenv('WEBHOOK_URL', self.config.get('webhook_url', '')),
        })
        
        self.logger = setup_logger("QuantBot", self.config)
        self.logger.info("="*50)
        self.logger.info("QuantBot Pro initializing...")
        self.logger.info(f"Mode: {self.config.get('mode', 'paper')}")
        self.logger.info(f"Capital: ${self.config.get('capital_usdt', 170):.2f} USDT")
        self.logger.info(f"Environment: {'Render' if os.getenv('RENDER') else 'Local'}")
        
        self.strategy = Strategy(self.config)
        self.risk_manager = AdvancedRiskManager(self.config)
        self.llm_brain = LLMBrain(self.config)
        self.notifier = DiscordNotifier(self.config)
        self.backtest_engine = BacktestEngine(self.config)
        
        self.ui = None
        
        self.running = False
        self.mode = self.config.get('mode', 'paper')
        self.update_interval = self.config.get('update_interval_sec', 900)
        self.current_symbol = self.config.get('default_symbol', 'BTC/USDT')
        self.current_timeframe = self.config.get('timeframe', '1h')
        
        self._shutdown = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown = True
        self.running = False
    
    def set_ui(self, ui):
        self.ui = ui
    
    def configure(self, params: dict):
        if 'symbol' in params:
            self.current_symbol = params['symbol']
            self.logger.info(f"Symbol changed to {self.current_symbol}")
        if 'risk_per_trade' in params:
            self.config['risk_per_trade'] = params['risk_per_trade']
            self.risk_manager.risk_per_trade = params['risk_per_trade']
            self.logger.info(f"Risk per trade updated to {params['risk_per_trade']*100:.2f}%")
        if 'timeframe' in params:
            self.current_timeframe = params['timeframe']
            self.logger.info(f"Timeframe changed to {self.current_timeframe}")
    
    def get_current_prices(self) -> Dict[str, float]:
        prices = {}
        for sym in self.config.get('symbols', ['BTC/USDT']):
            try:
                df = fetch_ohlcv(sym, self.current_timeframe, limit=2, use_cache=False)
                if not df.empty:
                    prices[sym] = df['close'].iloc[-1]
            except Exception as e:
                self.logger.error(f"Price fetch failed for {sym}: {e}")
        return prices
    
    def run_backtest(self):
        self.logger.info(f"Starting backtest for {self.current_symbol}...")
        result = self.backtest_engine.run(
            self.current_symbol,
            self.current_timeframe,
            self.config['backtest_start'],
            self.config['backtest_end']
        )
        print_backtest_summary(result)
        self.backtest_engine.plot_results(result, self.current_symbol)
        
        if self.config.get('optimization_enabled', True):
            if result.win_rate < self.config.get('min_win_rate', 55) or \
               result.max_drawdown > self.config.get('max_drawdown', 10):
                self.logger.info("Strategy below thresholds. Running optimization...")
                optimized = self.backtest_engine.optimize_loop(
                    self.current_symbol, self.current_timeframe,
                    self.config['backtest_start'], self.config['backtest_end']
                )
                self.config.update(optimized)
                with open("config.json", "w") as f:
                    json.dump(self.config, f, indent=2)
                self.logger.info("Config updated with optimized parameters")
        
        return result
    
    def run_walkforward(self):
        self.logger.info(f"Starting walk-forward optimization for {self.current_symbol}...")
        result = self.backtest_engine.walk_forward_optimize(
            self.current_symbol,
            self.current_timeframe,
            self.config['backtest_start'],
            self.config['backtest_end'],
            self.config.get('wf_train_days', 90),
            self.config.get('wf_test_days', 30),
            self.config.get('wf_step_days', 30)
        )
        self.logger.info(f"Walk-forward complete: {len(result.windows)} windows, consistency={result.consistency:.1f}%")
        return result
    
    def run_cycle(self):
        try:
            self.logger.debug(f"Running cycle for {self.current_symbol}")
            
            df = fetch_ohlcv(self.current_symbol, self.current_timeframe, 
                           self.config.get('lookback_candles', 200))
            if df.empty or len(df) < 50:
                self.logger.warning("Insufficient data, skipping cycle")
                return
            
            current_prices = self.get_current_prices()
            self.risk_manager.update_trailing_stops(current_prices)
            closed = self.risk_manager.check_exits(current_prices)
            
            for trade in closed:
                self.notifier.send_status(
                    f"Closed {trade['symbol']} @ {trade['exit_price']:.4f} | "
                    f"PnL: {trade['pnl']:+.2f} USDT ({trade['pnl_pct']:+.2f}%) | {trade['reason']}",
                    "success" if trade['pnl'] > 0 else "warning"
                )
                
                if self.ui:
                    self.ui.broadcast_trade({
                        'type': 'close',
                        'symbol': trade['symbol'],
                        'price': trade['exit_price'],
                        'pnl': trade['pnl'],
                        'pnl_pct': trade['pnl_pct'],
                        'reason': trade['reason']
                    })
            
            signal = self.strategy.generate_signal(df, self.current_symbol)
            
            if signal:
                can_open, size_or_reason = self.risk_manager.can_open_position(
                    signal.symbol, signal.price, signal.stop_loss
                )
                
                if can_open:
                    signal.position_size = size_or_reason
                    self.logger.info(f"Signal generated: {signal.reason}")
                    
                    signal.llm_analysis = self.llm_brain.analyze_signal(signal, df)
                    
                    self.risk_manager.open_position(signal, size_or_reason)
                    
                    self.notifier.send_signal(signal, df)
                    
                    if self.ui:
                        self.ui.broadcast_trade({
                            'type': 'open',
                            'symbol': signal.symbol,
                            'price': signal.price,
                            'stop_loss': signal.stop_loss,
                            'take_profit': signal.take_profit,
                            'confidence': signal.confidence
                        })
                else:
                    self.logger.info(f"Signal rejected: {size_or_reason}")
            
            # Broadcast status updates
            if self.ui:
                current_prices = self.get_current_prices()
                equity = self.risk_manager.get_equity(current_prices)
                initial_price = df['close'].iloc[0] if len(df) > 0 else 1
                buyhold = self.risk_manager.initial_balance * (df['close'].iloc[-1] / initial_price) if initial_price > 0 else self.risk_manager.initial_balance
                self.ui.broadcast_equity({
                    'timestamp': datetime.now().isoformat(),
                    'equity': equity,
                    'buyhold': buyhold
                })
                
                risk = self.risk_manager
                metrics = risk.get_metrics()
                self.ui.broadcast_status({
                    'running': self.running,
                    'balance': risk.portfolio.balance,
                    'daily_pnl': risk.portfolio.balance - risk.initial_balance,
                    'daily_pnl_pct': (risk.portfolio.balance - risk.initial_balance) / risk.initial_balance * 100,
                    'active_trades': len(risk.portfolio.positions),
                    'win_rate': metrics['win_rate'],
                    'sharpe': metrics.get('sharpe', 0),
                    'max_drawdown': metrics.get('max_drawdown', 0),
                    'positions': [],
                    'recent_trades': risk.portfolio.trades_history[-20:],
                    'metrics': metrics
                })
            
            gc.collect()
            
        except Exception as e:
            self.logger.error(f"Cycle error: {e}", exc_info=True)
    
    def run_paper(self):
        self.logger.info("Starting paper trading loop...")
        self.running = True
        
        while self.running and not self._shutdown:
            cycle_start = time.time()
            self.run_cycle()
            
            elapsed = time.time() - cycle_start
            sleep_time = max(0, self.update_interval - elapsed)
            
            if sleep_time > 0:
                for _ in range(int(sleep_time)):
                    if not self.running or self._shutdown:
                        break
                    time.sleep(1)
        
        self.logger.info("Paper trading loop stopped")
    
    def start(self):
        if self.mode == 'backtest':
            self.run_backtest()
        elif self.mode == 'walkforward':
            self.run_walkforward()
        elif self.mode in ('paper', 'live'):
            self.run_paper()
        else:
            self.logger.error(f"Unknown mode: {self.mode}")
    
    def stop(self):
        self.logger.info("Stopping bot...")
        self.running = False


def create_app(config: dict, bot_instance=None):
    """Create Flask app for web UI"""
    from ui.app_enhanced import create_app as create_enhanced_app
    return create_enhanced_app(config, bot_instance)


def run_ui(config: dict, bot_instance=None, host: str = '0.0.0.0', port: int = 8080):
    """Run the web UI server"""
    app, socketio, ui = create_app(config, bot_instance)
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='QuantBot Pro - Autonomous Trading Bot')
    parser.add_argument('--mode', choices=['paper', 'backtest', 'walkforward', 'live'], default='paper',
                       help='Trading mode')
    parser.add_argument('--symbol', default='BTC/USDT', help='Trading symbol')
    parser.add_argument('--config', default='config.json', help='Config file path')
    parser.add_argument('--port', type=int, default=8080, help='Web UI port')
    parser.add_argument('--host', default='0.0.0.0', help='Web UI host')
    args = parser.parse_args()
    
    with open(args.config) as f:
        config = json.load(f)
    
    config['mode'] = args.mode
    config['default_symbol'] = args.symbol
    
    with open(args.config, 'w') as f:
        json.dump(config, f, indent=2)
    
    bot = QuantBot(args.config)
    
    if args.mode == 'backtest':
        bot.run_backtest()
    elif args.mode == 'walkforward':
        bot.run_walkforward()
    else:
        from ui.app_enhanced import create_app
        app, socketio, ui = create_app(config, bot)
        bot.set_ui(ui)
        
        # Run bot in a separate thread (non-daemon so it stays alive)
        bot_thread = threading.Thread(target=bot.start, daemon=False)
        bot_thread.start()
        
        # Handle shutdown gracefully
        import signal
        def signal_handler(signum, frame):
            bot.logger.info(f"Received signal {signum}, shutting down...")
            bot.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Run the UI in the main thread (blocking)
            from ui.app_enhanced import socketio as sio
            from ui.app_enhanced import create_app as create_app_func
            app, socketio, _ = create_app(config, bot)
            socketio.run(app, host=args.host, port=args.port, debug=False, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            pass
        finally:
            bot.stop()
            bot_thread.join(timeout=10)


if __name__ == '__main__':
    main()

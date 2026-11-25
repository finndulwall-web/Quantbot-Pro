#!/usr/bin/env python3
"""
Render.com Startup Script for QuantBot Pro
Handles health checks, graceful startup, and graceful shutdown
"""
import os
import sys
import signal
import threading
import time
import json
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("QuantBot-Render")

# Global shutdown flag
_shutdown = False

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    globals()['_shutdown'] = True

def main():
    global _shutdown
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load config
    config_path = os.getenv('CONFIG_PATH', 'config.json')
    with open(config_path) as f:
        config = json.load(f)
    
    # Override with environment variables
    config.update({
        'mode': os.getenv('MODE', config.get('mode', 'paper')),
        'default_symbol': os.getenv('SYMBOL', config.get('default_symbol', 'BTC/USDT')),
        'capital_usdt': float(os.getenv('CAPITAL_USDT', config.get('capital_usdt', 170.0))),
        'risk_per_trade': float(os.getenv('RISK_PER_TRADE', config.get('risk_per_trade', 0.01))),
        'max_concurrent_trades': int(os.getenv('MAX_CONCURRENT_TRADES', config.get('max_concurrent_trades', 3))),
        'max_portfolio_heat': float(os.getenv('MAX_PORTFOLIO_HEAT', config.get('max_portfolio_heat', 1.0))),
        'max_daily_drawdown': float(os.getenv('MAX_DAILY_DRAWDOWN', config.get('max_daily_drawdown', 0.05))),
        'max_total_drawdown': float(os.getenv('MAX_TOTAL_DRAWDOWN', config.get('max_total_drawdown', 0.15))),
        'nvidia_api_key': os.getenv('NVIDIA_API_KEY', ''),
        'webhook_url': os.getenv('WEBHOOK_URL', ''),
    }
    
    # Import after config is set
    from utils.logger import setup_logger
    from core.data import fetch_ohlcv
    from core.strategy import Strategy
    from core.risk_enhanced import AdvancedRiskManager
    from core.llm_brain import LLMBrain
    from core.backtest_enhanced import BacktestEngine
    from utils.notifier import DiscordNotifier
    
    logger = setup_logger("QuantBot", {
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_file': 'bot.log',
        'log_max_mb': 10,
        'log_backup_count': 3
    })
    
    logger.info("="*50)
    logger.info("QuantBot Pro initializing on Render...")
    logger.info(f"Mode: {os.getenv('MODE', 'paper')}")
    logger.info(f"Capital: ${os.getenv('CAPITAL_USDT', '170.0')} USDT")
    logger.info(f"Symbol: {os.getenv('SYMBOL', 'BTC/USDT')}")
    
    # Initialize components
    config = {
        'capital_usdt': float(os.getenv('CAPITAL_USDT', '170.0')),
        'risk_per_trade': float(os.getenv('RISK_PER_TRADE', '0.01')),
        'max_concurrent_trades': int(os.getenv('MAX_CONCURRENT_TRADES', '3')),
        'max_portfolio_heat': float(os.getenv('MAX_PORTFOLIO_HEAT', '1.0')),
        'max_daily_drawdown': float(os.getenv('MAX_DAILY_DRAWDOWN', '0.05')),
        'max_total_drawdown': float(os.getenv('MAX_TOTAL_DRAWDOWN', '0.15')),
        'slippage_pct': 0.001,
        'fee_pct': 0.001,
        'rsi_oversold': 30,
        'ema_short': 20,
        'ema_medium': 50,
        'ema_long': 200,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'atr_period': 14,
        'volume_mult': 1.5,
        'tp_atr_mult': 2.0,
        'sl_atr_mult': 1.0,
        'trail_atr_mult': 1.0,
        'optimization_enabled': True,
        'min_win_rate': 55,
        'max_drawdown': 10,
        'max_opt_iterations': 5,
        'default_symbol': os.getenv('SYMBOL', 'BTC/USDT'),
        'timeframe': os.getenv('TIMEFRAME', '1h'),
        'lookback_candles': 200,
        'backtest_start': '2023-01-01',
        'backtest_end': '2024-01-01',
        'symbols': ['BTC/USDT', 'ETH/USDT', 'AAPL', 'TSLA'],
        'timeframe': '1h',
        'lookback_candles': 200,
        'backtest_start': '2023-01-01',
        'backtest_end': '2024-01-01',
        'mode': os.getenv('MODE', 'paper'),
        'rsi_period': 14,
        'rsi_oversold': 30,
        'ema_short': 20,
        'ema_medium': 50,
        'ema_long': 200,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'atr_period': 14,
        'bb_period': 20,
        'bb_std': 2,
        'vwap_period': 20,
        'vwap_std': 2.0,
        'st_period': 10,
        'st_mult': 3.0,
        'ichi_tenkan': 9,
        'ichi_kijun': 26,
        'ichi_senkou_b': 52,
        'ichi_disp': 26,
        'adx_period': 14,
        'volume_mult': 1.5,
        'tp_atr_mult': 2.0,
        'sl_atr_mult': 1.0,
        'trail_atr_mult': 1.0,
        'use_mtf_confirmation': True,
        'min_confidence': 0.6,
        'optimization_enabled': True,
        'walkforward_enabled': True,
        'wf_train_days': 90,
        'wf_test_days': 30,
        'wf_step_days': 30,
        'min_win_rate': 55,
        'max_drawdown': 10,
        'max_opt_iterations': 5,
        'log_level': 'INFO',
        'log_file': 'bot.log',
        'log_max_mb': 10,
        'log_backup_count': 3,
        'ui_port': int(os.getenv('PORT', '10000')),
        'ui_host': '0.0.0.0',
        'update_interval_sec': 900
    }
    
    # Initialize components
    from core.strategy import Strategy
    from core.risk_enhanced import AdvancedRiskManager
    from core.llm_brain import LLMBrain
    from core.backtest_enhanced import BacktestEngine
    from utils.notifier import DiscordNotifier
    
    logger.info("Initializing components...")
    strategy = Strategy(config)
    risk_manager = AdvancedRiskManager(config)
    llm_brain = LLMBrain(config)
    notifier = DiscordNotifier(config)
    backtest_engine = BacktestEngine(config)
    
    # Import UI
    from ui.app_enhanced import create_app
    app, socketio, ui = create_app({
        **config,
        'webhook_url': os.getenv('WEBHOOK_URL', ''),
        'nvidia_api_key': os.getenv('NVIDIA_API_KEY', '')
    }, None)
    
    # Health check endpoint
    from flask import jsonify
    from flask import Flask
    
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'quantbot-pro',
            'version': '1.0.0'
        })
    
    logger.info("Starting QuantBot Pro on Render...")
    
    # Start trading in background thread
    from core.risk_enhanced import AdvancedRiskManager
    from core.strategy import Strategy
    from core.llm_brain import LLMBrain
    from core.backtest_enhanced import BacktestEngine
    from utils.notifier import DiscordNotifier
    
    class QuantBotRunner:
        def __init__(self, config):
            self.config = config
            self.logger = setup_logger("QuantBot", config)
            self.strategy = Strategy(config)
            self.risk_manager = AdvancedRiskManager(config)
            self.llm_brain = LLMBrain(config)
            self.notifier = DiscordNotifier(config)
            self.backtest_engine = BacktestEngine(config)
            self.running = False
            self.mode = config.get('mode', 'paper')
            self.update_interval = config.get('update_interval_sec', 900)
            self.current_symbol = config.get('default_symbol', 'BTC/USDT')
            self.current_timeframe = config.get('timeframe', '1h')
            self._shutdown = False
        
        def run_paper(self):
            self.logger.info("Starting paper trading loop...")
            self.running = True
            
            while self.running:
                try:
                    from core.data import fetch_ohlcv
                    from core.indicators_enhanced import add_all_enhanced_indicators
                    from core.risk_enhanced import AdvancedRiskManager
                    from core.strategy import Strategy, Signal
                    from core.llm_brain import LLMBrain
                    from core.backtest_enhanced import BacktestEngine
                    from utils.notifier import DiscordNotifier
                    
                    df = self.fetch_ohlcv(self.current_symbol, self.current_timeframe, 
                                        self.config.get('lookback_candles', 200))
                    if df.empty or len(df) < 50:
                        self.logger.warning("Insufficient data, skipping cycle")
                        time.sleep(60)
                        continue
                    
                    current_prices = self.get_current_prices()
                    self.risk_manager.update_trailing_stops(current_prices)
                    closed = self.risk_manager.check_exits(current_prices)
                    
                    for trade in closed:
                        print(f"Closed {trade['symbol']} @ {trade['exit_price']:.4f} | "
                              f"PnL: {trade['pnl']:+.2f} USDT ({trade['pnl_pct']:+.2f}%) | {trade['reason']}")
                    
                    signal = self.strategy.generate_signal(df, self.current_symbol)
                    
                    if signal:
                        can_open, size = self.risk_manager.can_open_position(
                            signal.symbol, signal.price, signal.stop_loss
                        )
                        
                        if can_open:
                            signal.position_size = size
                            self.logger.info(f"Signal generated: {signal.reason}")
                            signal.llm_analysis = self.llm_brain.analyze_signal(signal, df)
                            self.risk_manager.open_position(signal, size)
                            print(f"Opened {signal.symbol} @ {signal.price:.4f}")
                    
                    gc.collect()
                    
                except Exception as e:
                    logger.error(f"Cycle error: {e}", exc_info=True)
                
                time.sleep(60)
        
        def get_current_prices(self):
            from core.data import fetch_ohlcv
            prices = {}
            for sym in self.config.get('symbols', ['BTC/USDT']):
                try:
                    df = fetch_ohlcv(sym, self.current_timeframe, limit=2, use_cache=False)
                    if not df.empty:
                        prices[sym] = df['close'].iloc[-1]
                except Exception as e:
                    self.logger.error(f"Price fetch failed for {sym}: {e}")
            return prices
        
        def get_current_prices(self):
            from core.data import fetch_ohlcv
            prices = {}
            for sym in self.config.get('symbols', ['BTC/USDT']):
                try:
                    df = fetch_ohlcv(sym, self.current_timeframe, limit=2, use_cache=False)
                    if not df.empty:
                        prices[sym] = df['close'].iloc[-1]
                except Exception as e:
                    self.logger.error(f"Price fetch failed for {sym}: {e}")
            return prices
    
    bot = QuantBotRunner(config)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        bot._shutdown = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=bot.run_paper, daemon=True)
    bot_thread.start()
    
    logger.info("QuantBot Pro started successfully on Render!")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down...")
        bot._shutdown = True

if __name__ == '__main__':
    main()

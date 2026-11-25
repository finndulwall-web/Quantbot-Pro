# QuantBot Pro - Professional Autonomous Trading Bot

A production-ready, institutional-grade autonomous trading bot with advanced features for cryptocurrency and stock trading.

## 🚀 Features

### Core Trading Engine
- **Multi-Strategy Engine**: 3 built-in strategies (Safe/Steady/Bold) with dynamic switching
- **Advanced Technical Analysis**: 50+ indicators (Supertrend, Ichimoku, VWAP, MACD variants, etc.)
- **Multi-Timeframe Analysis**: Automatic confirmation across timeframes
- **Market Regime Detection**: Automatic bull/bear/sideways/volatile/calm detection
- **Confidence Scoring**: ML-inspired signal confidence with adaptive thresholds

### Risk Management (Institutional Grade)
- **Kelly Criterion Position Sizing**: Dynamic sizing based on historical win/loss rates
- **Volatility Targeting**: Position sizes adapt to market volatility
- **Circuit Breakers**: Multi-layer (daily/weekly/monthly/total drawdown limits)
- **Correlation Management**: Prevents over-concentration in correlated assets
- **Trailing Stops**: ATR-based trailing with Supertrend flip detection
- **Kelly Fraction Sizing**: Conservative quarter-Kelly with confidence scaling

### Advanced Backtesting
- **Walk-Forward Optimization**: Rolling train/test windows with consistency metrics
- **Monte Carlo Simulation**: 200+ simulations for strategy validation
- **Parameter Sensitivity Analysis**: Identify robust vs fragile parameters
- **Regime-Aware Testing**: Performance breakdown by market regime
- **Realistic Costs**: Slippage models, fees, slippage, spread simulation
- **Monte Carlo Validation**: 200+ simulations with confidence intervals

### Professional Web Dashboard
- **Real-time WebSocket Updates**: Live equity curve, positions, trades
- **Cyberpunk Dark Theme**: Professional trading terminal aesthetic
- **Interactive Charts**: Plotly.js with real-time equity, drawdowns, distributions
- **Strategy Builder**: Visual strategy configuration with presets
- **Walk-Forward Dashboard**: Visual walk-forward results with consistency metrics
- **Glossary**: 20+ trading terms explained in plain English
- **Setup Wizard**: Guided first-time configuration
- **Dark/Light Theme**: Automatic detection with manual toggle

### Deployment Ready
- **Systemd Services**: Auto-restart, resource limits, security hardening
- **Memory Watchdog**: Automatic restart on memory limits (4GB RAM optimized)
- **Log Rotation**: Automatic log rotation with compression
- **Tailscale Integration**: Secure remote access from anywhere
- **Docker Support**: Containerized deployment option

## 📋 Requirements

### Minimum Hardware
- **RAM**: 2GB (4GB recommended for full features)
- **Storage**: 2GB free space
- **CPU**: 2 cores (4+ recommended)
- **OS**: Linux (Ubuntu 20.04+, Debian 11+, Termux on Android)

### Software Dependencies
- Python 3.10+
- pip, venv
- Git
- Systemd (for daemon mode)

### API Keys (Optional)
- **Discord Webhook**: Trade notifications
- **NVIDIA API Key**: LLM trade analysis (Nemotron-3-Ultra)

## 🚀 Quick Start

### Option 1: Termux on Android (S25 Ultra)
```bash
# 1. Install Termux from F-Droid
# 2. Run setup
pkg update && pkg upgrade -y
pkg install -y python python-pip git clang make cmake libjpeg-turbo libpng freetype openblas

# Clone and setup
git clone <your-repo> autopilot
cd autopilot
chmod +x setup.sh
./setup.sh

# Run
python main.py --mode paper --symbol BTC/USDT
```

### Option 2: Ubuntu Server (4GB RAM)
```bash
# 1. Install dependencies
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git curl

# 2. Install Tailscale (for remote access)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 3. Deploy
git clone <your-repo> autopilot
cd autopilot
sudo ./setup_daemon.sh
sudo systemctl start quantbot quantbot-ui quantbot-watchdog

# Access at http://<tailscale-ip>:8080
```

### Option 3: Docker (Any Platform)
```bash
docker build -t quantbot .
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/data:/opt/quantbot/data \
  -v $(pwd)/config.json:/opt/quantbot/config.json \
  --name quantbot \
  quantbot
```

## 📁 Project Structure

```
autopilot/
├── main.py                    # Entry point
├── config.json                # Configuration
├── requirements.txt           # Python dependencies
├── setup.sh                   # Termux setup
├── setup_daemon.sh            # Ubuntu daemon setup
├── watchdog.py                # Memory watchdog
├── quantbot*.service          # Systemd services
├── core/
│   ├── data.py               # Data ingestion (CCXT, yfinance, caching)
│   ├── indicators.py         # Core indicators (50+)
│   ├── indicators_enhanced.py # Advanced indicators (50+)
│   ├── strategy.py           # Core strategy logic
│   ├── risk.py               # Basic risk management
│   ├── risk_enhanced.py      # Advanced risk management
│   ├── strategy_enhanced.py  # Advanced strategies
│   ├── backtest.py           # Basic backtesting
│   ├── backtest_enhanced.py  # Advanced backtesting (MC, WF, sensitivity)
│   ├── llm_brain.py          # LLM analysis (NVIDIA Nemotron)
│   └── risk_enhanced.py      # Advanced risk management
├── ui/
│   ├── app.py                # Basic Flask UI
│   └── app_enhanced.py       # Enhanced SocketIO dashboard
├── utils/
│   ├── logger.py             # Colored logging with buffers
│   └── notifier.py           # Discord notifications
├── quantbot.service          # Systemd trading engine
├── quantbot-ui.service       # Systemd web UI
├── quantbot-watchdog.service # Memory watchdog
├── setup.sh                  # Termux setup script
├── setup_daemon.sh           # Ubuntu daemon setup
└── config.json               # Configuration file
```

## ⚙️ Configuration

Key settings in `config.json`:

```json
{
  "capital_usdt": 170.0,
  "risk_per_trade": 0.01,
  "max_concurrent_trades": 3,
  "max_portfolio_heat": 1.0,
  "max_daily_drawdown": 0.05,
  "max_total_drawdown": 0.15,
  "strategy_preset": "steady",
  "symbols": ["BTC/USDT", "ETH/USDT", "AAPL", "TSLA"],
  "timeframe": "1h",
  "optimization_enabled": true,
  "walkforward_enabled": true,
  "mc_simulations": 200,
  "slippage_model": "adaptive",
  "slippage_pct": 0.001,
  "fee_pct": 0.001
}
```

### Strategy Presets
| Preset | Risk/Trade | Max Trades | Max Heat | Daily DD | Best For |
|--------|------------|------------|----------|----------|----------|
| Safe   | 0.5%       | 2          | 50%      | 3%       | Beginners |
| Steady | 1%         | 3          | 100%     | 5%       | Most users |
| Bold   | 2%         | 5          | 200%     | 10%      | Experienced |

## 📊 Backtesting

```bash
# Quick backtest
python main.py --mode backtest --symbol BTC/USDT

# Walk-forward optimization
python main.py --mode walkforward --symbol BTC/USDT

# Custom date range
python main.py --mode backtest --symbol ETH/USDT --start 2023-01-01 --end 2024-01-01
```

## 🌐 Web Dashboard

Access at `http://localhost:8080` (or your Tailscale IP:8080)

### Dashboard Tabs
1. **Dashboard** - Live equity, positions, trades, logs
2. **Positions** - Detailed position view with MAE/MFE
3. **Analytics** - Monthly returns, drawdowns, distributions, rolling metrics
4. **Backtest** - Strategy testing with walk-forward
5. **Settings** - Risk params, API keys, display options

### Key Features
- **Real-time WebSocket**: Live updates without refresh
- **Interactive Charts**: Plotly.js with zoom/pan/hover
- **Strategy Builder**: Visual preset selection with risk warnings
- **Glossary**: 20+ terms explained in plain English
- **Setup Wizard**: Guided first-time configuration
- **Dark/Light Theme**: Persisted preference

## 🔔 Notifications

### Discord Setup
1. Create webhook: Server Settings → Integrations → Webhooks
2. Copy webhook URL to `config.json` → `webhook_url`
3. Get notifications for: trade entry/exit, circuit breakers, daily summary

### NVIDIA LLM Analysis
1. Get API key from NVIDIA NGC
2. Add to `config.json` → `nvidia_api_key`
3. Each trade signal gets AI analysis

## 🛡️ Safety Features

### Circuit Breakers
- **Daily Loss Limit**: Stops trading if daily loss exceeds threshold
- **Total Drawdown**: Emergency stop at max total drawdown
- **Weekly/Monthly Limits**: Additional protection layers
- **Auto-Reset**: Resets at midnight/week/month boundaries

### Position Safety
- **Max Concurrent**: Hard limit on simultaneous positions
- **Portfolio Heat**: Max total exposure as % of equity
- **Correlation Limits**: Prevents correlated position clustering
- **Sector Limits**: Max exposure per asset class

### Data Integrity
- **SQLite Caching**: Persistent OHLCV cache with deduplication
- **Graceful Degradation**: Falls back to cached data on API failure
- **Atomic Writes**: Config changes are atomic

## 📈 Performance Monitoring

### Key Metrics Tracked
- **Sharpe/Sortino/Calmar**: Risk-adjusted returns
- **Win Rate / Profit Factor**: Trade quality metrics
- **Expectancy**: Expected value per trade
- **Max Drawdown**: Peak-to-trough decline
- **VaR/ES**: Value at Risk / Expected Shortfall
- **Regime Performance**: Per-regime win rates

### Daily Summary (Discord)
- Net P&L and percentage
- Trade count and win rate
- Open positions summary
- Risk metrics snapshot

## 🔧 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ip command not found` | `pkg install net-tools` (Termux) or `apt install net-tools` (Ubuntu) |
| `dhclient not found` | `apt install isc-dhcp-client` |
| `nmcli not found` | `apt install network-manager` |
| USB tether not working | Toggle USB tethering OFF/ON on phone |
| Port 8080 in use | `sudo lsof -i :8080` then kill process |
| Module not found | `pip install -r requirements.txt` |

### Logs
```bash
# View logs
tail -f /opt/quantbot/logs/bot.log

# Systemd logs
journalctl -u quantbot -f
journalctl -u quantbot-ui -f
```

## 📚 Advanced Usage

### Custom Strategies
Extend `core/strategy.py`:
```python
class MyStrategy(Strategy):
    def check_trigger_custom(self, df):
        # Your logic here
        return condition
```

### Custom Indicators
Add to `core/indicators_enhanced.py`:
```python
def my_indicator(series, period=14):
    # Your calculation
    return result
```

### Backtest Custom Parameters
```python
engine = BacktestEngine(config)
result = engine.run('BTC/USDT', '1h', '2023-01-01', '2024-01-01', {
    'rsi_oversold': 25,
    'ema_short': 10,
    'st_mult': 2.5
})
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see LICENSE file for details

## ⚠️ Disclaimer

**This software is for educational and research purposes only.**

- Past performance does not guarantee future results
- Trading involves substantial risk of loss
- Never trade with money you cannot afford to lose
- Always test thoroughly in paper mode before live trading
- The authors are not responsible for any financial losses

## 🙏 Acknowledgments

- CCXT for exchange connectivity
- yfinance for stock data
- NVIDIA Nemotron for LLM analysis
- Plotly.js for beautiful charts
- Flask/SocketIO for real-time UI
- CCXT, pandas, numpy, scikit-learn communities

---

**Built with ❤️ for the algorithmic trading community**

*QuantBot Pro - Trade smarter, not harder*

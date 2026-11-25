import requests
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import base64
from typing import Optional, Dict, Any
from core.strategy import Signal

logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, config: dict):
        self.webhook_url = config.get('webhook_url')
        self.enabled = bool(self.webhook_url and self.webhook_url != 'https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE')
        
        if not self.enabled:
            logger.warning("Discord webhook not configured. Notifications disabled.")
    
    def create_chart_image(self, df: pd.DataFrame, signal: Signal) -> Optional[str]:
        try:
            last_50 = df.tail(50).copy()
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), 
                                            gridspec_kw={'height_ratios': [3, 1]},
                                            facecolor='#1a1a2e')
            
            ax1.set_facecolor('#0d0d1a')
            ax2.set_facecolor('#0d0d1a')
            
            colors = ['#00ff88' if c >= o else '#ff3366' for c, o in zip(last_50['close'], last_50['open'])]
            
            for i, (idx, row) in enumerate(last_50.iterrows()):
                ax1.plot([i, i], [row['low'], row['high']], color=colors[i], linewidth=1)
                ax1.plot([i, i], [row['open'], row['close']], color=colors[i], linewidth=3)
            
            if 'ema_20' in last_50.columns:
                ax1.plot(range(len(last_50)), last_50['ema_20'], color='#00aaff', linewidth=1, label='EMA20', alpha=0.8)
            if 'ema_50' in last_50.columns:
                ax1.plot(range(len(last_50)), last_50['ema_50'], color='#ffaa00', linewidth=1, label='EMA50', alpha=0.8)
            if 'ema_200' in last_50.columns:
                ax1.plot(range(len(last_50)), last_50['ema_200'], color='#ff3366', linewidth=1, label='EMA200', alpha=0.8)
            
            ax1.axhline(y=signal.price, color='#00ff88', linestyle='--', linewidth=2, label=f'Entry: {signal.price:.4f}')
            ax1.axhline(y=signal.stop_loss, color='#ff3366', linestyle='--', linewidth=1.5, label=f'SL: {signal.stop_loss:.4f}')
            ax1.axhline(y=signal.take_profit, color='#00ff88', linestyle='--', linewidth=1.5, label=f'TP: {signal.take_profit:.4f}')
            
            ax1.set_title(f'{signal.symbol} - {signal.action} Signal', color='white', fontsize=12)
            ax1.set_ylabel('Price', color='white')
            ax1.legend(facecolor='#1a1a2e', edgecolor='#00ff88', labelcolor='white', fontsize=8)
            ax1.grid(True, alpha=0.2)
            ax1.tick_params(colors='white')
            
            if 'volume' in last_50.columns:
                vol_colors = ['#00ff88' if c >= o else '#ff3366' for c, o in zip(last_50['close'], last_50['open'])]
                ax2.bar(range(len(last_50)), last_50['volume'], color=vol_colors, alpha=0.6, width=0.6)
                ax2.set_ylabel('Volume', color='white')
                ax2.grid(True, alpha=0.2)
                ax2.tick_params(colors='white')
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, facecolor='#1a1a2e', edgecolor='none', bbox_inches='tight')
            plt.close()
            buf.seek(0)
            
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            return img_base64
            
        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            return None
    
    def send_signal(self, signal: Signal, df: pd.DataFrame) -> bool:
        if not self.enabled:
            return False
        
        color = 0x00ff88 if signal.action == 'BUY' else 0xff3366
        emoji = "🟢" if signal.action == 'BUY' else "🔴"
        
        fields = [
            {"name": "💰 Entry Price", "value": f"{signal.price:.4f}", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"{signal.stop_loss:.4f}", "inline": True},
            {"name": "🎯 Take Profit", "value": f"{signal.take_profit:.4f}", "inline": True},
            {"name": "📊 Position Size", "value": f"{signal.position_size:.6f}" if signal.position_size else "N/A", "inline": True},
            {"name": "📈 RSI", "value": f"{signal.rsi:.1f}" if signal.rsi else "N/A", "inline": True},
            {"name": "📉 MACD", "value": f"{signal.macd:.4f}" if signal.macd else "N/A", "inline": True},
        ]
        
        embed = {
            "title": f"{emoji} [{signal.action}] {signal.symbol} @ {signal.price:.4f}",
            "description": signal.llm_analysis or signal.reason,
            "color": color,
            "fields": fields,
            "footer": {"text": f"QuantBot | {signal.reason}"},
            "timestamp": pd.Timestamp.now(tz='UTC').isoformat()
        }
        
        payload = {
            "embeds": [embed]
        }
        
        img_base64 = self.create_chart_image(df, signal)
        if img_base64:
            payload["embeds"][0]["image"] = {"url": f"attachment://chart.png"}
            files = {"file": ("chart.png", io.BytesIO(base64.b64decode(img_base64)), "image/png")}
            try:
                response = requests.post(self.webhook_url, json=payload, files=files, timeout=10)
                response.raise_for_status()
                logger.info(f"Discord notification sent for {signal.symbol}")
                return True
            except Exception as e:
                logger.error(f"Discord send failed: {e}")
                return False
        else:
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                logger.info(f"Discord notification sent for {signal.symbol} (no chart)")
                return True
            except Exception as e:
                logger.error(f"Discord send failed: {e}")
                return False
    
    def send_status(self, message: str, level: str = "info") -> bool:
        if not self.enabled:
            return False
        
        colors = {"info": 0x00aaff, "warning": 0xffaa00, "error": 0xff3366, "success": 0x00ff88}
        emojis = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}
        
        embed = {
            "title": f"{emojis.get(level, 'ℹ️')} QuantBot Status",
            "description": message,
            "color": colors.get(level, 0x00aaff)
        }
        
        try:
            response = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Discord status send failed: {e}")
            return False
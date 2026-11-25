import os
import logging
import requests
import json
from typing import Optional

logger = logging.getLogger(__name__)

class LLMBrain:
    def __init__(self, config: dict):
        self.config = config
        self.api_key = config.get('nvidia_api_key') or os.getenv('NVIDIA_API_KEY')
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.model = "nvidia/nemotron-3-ultra-550b-a55b"
        
        if not self.api_key or self.api_key == 'YOUR_NVIDIA_API_KEY_HERE':
            logger.warning("NVIDIA API key not configured. LLM analysis will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
    
    def analyze_signal(self, signal, df) -> Optional[str]:
        if not self.enabled:
            return "LLM analysis unavailable (no API key configured)"
        
        try:
            last_candles = df.tail(5)[['open', 'high', 'low', 'close', 'volume']].to_dict('records')
            
            data = {
                'symbol': signal.symbol,
                'entry_price': signal.price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'rsi': signal.rsi,
                'macd': signal.macd,
                'atr': signal.atr,
                'recent_candles': last_candles
            }
            
            prompt = f"""You are a quant analyst. Here is the trade signal data:
{data}

Write a 3-sentence thesis on why this is a good entry, and what the biggest risk is. Be concise and professional."""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional quantitative analyst. Provide concise, professional trade analysis."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 300,
                "temperature": 0.3
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"NVIDIA API error: {response.status_code} - {response.text}")
                return f"LLM analysis failed: HTTP {response.status_code}"
            
            result = response.json()
            message = result['choices'][0]['message']
            content = message.get('content') or message.get('reasoning_content')
            if not content:
                logger.warning(f"NVIDIA API returned empty content: {result}")
                return "LLM analysis unavailable (empty response)"
            analysis = content.strip()
            logger.info(f"LLM analysis for {signal.symbol}: {analysis[:100]}...")
            return analysis
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return f"LLM analysis failed: {str(e)[:100]}"
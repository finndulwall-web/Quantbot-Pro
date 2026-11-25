from dataclasses import dataclass
from typing import Optional, List, Dict
import pandas as pd
import numpy as np
from core.indicators import add_all_indicators, ema, rsi, macd, atr, supertrend, ichimoku, adx

@dataclass
class Signal:
    action: str
    symbol: str
    price: float
    stop_loss: float
    take_profit: float
    reason: str
    llm_analysis: Optional[str] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    atr: Optional[float] = None
    position_size: Optional[float] = None
    confidence: float = 1.0
    timeframe: str = "1h"

class Strategy:
    def __init__(self, config: dict):
        self.config = config
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.volume_mult = config.get('volume_mult', 1.5)
        self.tp_atr_mult = config.get('tp_atr_mult', 2.0)
        self.sl_atr_mult = config.get('sl_atr_mult', 1.0)
        self.trail_atr_mult = config.get('trail_atr_mult', 1.0)
        self.use_mtf = config.get('use_mtf_confirmation', True)
        self.min_confidence = config.get('min_confidence', 0.6)
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return add_all_indicators(df, self.config)
    
    def check_regime(self, df: pd.DataFrame) -> bool:
        if len(df) < 200:
            return False
        return df['ema_50'].iloc[-1] > df['ema_200'].iloc[-1]
    
    def check_supertrend(self, df: pd.DataFrame) -> int:
        if 'supertrend_dir' not in df.columns:
            return 0
        return int(df['supertrend_dir'].iloc[-1])
    
    def check_ichimoku(self, df: pd.DataFrame) -> int:
        if 'ichi_tenkan' not in df.columns:
            return 0
        last = df.iloc[-1]
        if pd.isna(last['ichi_tenkan']) or pd.isna(last['ichi_kijun']):
            return 0
        if last['close'] > last['ichi_senkou_a'] and last['close'] > last['ichi_senkou_b']:
            if last['ichi_tenkan'] > last['ichi_kijun']:
                return 1
        elif last['close'] < last['ichi_senkou_a'] and last['close'] < last['ichi_senkou_b']:
            if last['ichi_tenkan'] < last['ichi_kijun']:
                return -1
        return 0
    
    def check_adx(self, df: pd.DataFrame) -> bool:
        if 'adx' not in df.columns:
            return True
        return df['adx'].iloc[-1] > 20
    
    def check_trigger_a(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        cond1 = last['rsi'] < self.rsi_oversold
        cond2 = last['close'] > last['ema_200']
        cond3 = prev['rsi'] >= self.rsi_oversold
        cond4 = last['close'] > last['vwap'] if 'vwap' in df.columns else True
        cond5 = self.check_supertrend(df) == 1
        cond6 = self.check_ichimoku(df) >= 0
        
        return cond1 and cond2 and cond3 and cond4 and cond5 and cond6
    
    def check_trigger_b(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        cond1 = prev['macd'] <= prev['macd_signal'] and last['macd'] > last['macd_signal']
        cond2 = last['close'] > last['ema_50']
        cond3 = last['volume_ratio'] >= self.volume_mult
        cond4 = last['close'] > last['vwap'] if 'vwap' in df.columns else True
        cond5 = self.check_supertrend(df) == 1
        cond6 = self.check_adx(df)
        
        return cond1 and cond2 and cond3 and cond4 and cond5 and cond6
    
    def check_trigger_c(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        cond1 = last['close'] < last['bb_lower'] if 'bb_lower' in df.columns else False
        cond2 = last['rsi'] < 35
        cond3 = last['volume_ratio'] >= 1.2
        cond4 = prev['macd_hist'] < 0 and last['macd_hist'] > prev['macd_hist']
        cond5 = self.check_supertrend(df) == 1
        
        return cond1 and cond2 and cond3 and cond4 and cond5
    
    def calculate_confidence(self, df: pd.DataFrame, trigger: str) -> float:
        conf = 0.5
        last = df.iloc[-1]
        
        if trigger == 'A':
            if last['rsi'] < 25: conf += 0.15
            elif last['rsi'] < 30: conf += 0.1
            if last['close'] > last['ema_50']: conf += 0.1
            if last['volume_ratio'] > 2.0: conf += 0.15
        elif trigger == 'B':
            if last['macd_hist'] > 0: conf += 0.15
            if last['close'] > last['ema_20']: conf += 0.1
            if last['volume_ratio'] > 2.5: conf += 0.15
        elif trigger == 'C':
            if last['rsi'] < 30: conf += 0.15
            if last['volume_ratio'] > 2.0: conf += 0.1
        
        if 'supertrend_dir' in df.columns and df['supertrend_dir'].iloc[-1] == 1:
            conf += 0.1
        if 'adx' in df.columns and last['adx'] > 25:
            conf += 0.1
        
        return min(conf, 1.0)
    
    def calculate_levels(self, df: pd.DataFrame, entry_price: float) -> tuple:
        atr = df['atr'].iloc[-1]
        if pd.isna(atr) or atr <= 0:
            atr = entry_price * 0.02
        
        stop_loss = entry_price - (atr * self.sl_atr_mult)
        take_profit = entry_price + (atr * self.tp_atr_mult)
        
        if 'supertrend' in df.columns and not pd.isna(df['supertrend'].iloc[-1]):
            st = df['supertrend'].iloc[-1]
            if st < entry_price and st > stop_loss:
                stop_loss = st
        
        return stop_loss, take_profit, atr
    
    def generate_signal(self, df: pd.DataFrame, symbol: str, timeframe: str = "1h") -> Optional[Signal]:
        df = self.prepare_data(df)
        
        if not self.check_regime(df):
            return None
        
        entry_price = df['close'].iloc[-1]
        action = "BUY"
        trigger = None
        
        if self.check_trigger_a(df):
            trigger = 'A'
            reason = f"Trigger A: RSI oversold ({df['rsi'].iloc[-1]:.1f}) in uptrend, ST bullish, Ichimoku bullish"
        elif self.check_trigger_b(df):
            trigger = 'B'
            reason = f"Trigger B: MACD bullish cross, price > EMA50, volume {df['volume_ratio'].iloc[-1]:.1f}x, ST bullish"
        elif self.check_trigger_c(df):
            trigger = 'C'
            reason = f"Trigger C: BB lower band touch, RSI {df['rsi'].iloc[-1]:.1f}, volume spike, ST bullish"
        else:
            return None
        
        confidence = self.calculate_confidence(df, trigger)
        if confidence < self.min_confidence:
            return None
        
        stop_loss, take_profit, atr_val = self.calculate_levels(df, entry_price)
        
        return Signal(
            action=action,
            symbol=symbol,
            price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            rsi=df['rsi'].iloc[-1],
            macd=df['macd'].iloc[-1],
            atr=atr_val,
            confidence=confidence,
            timeframe=timeframe
        )
    
    def check_exit(self, df: pd.DataFrame, entry_price: float, stop_loss: float, 
                   take_profit: float, highest_price: float) -> tuple:
        current_price = df['close'].iloc[-1]
        atr = df['atr'].iloc[-1]
        
        new_stop = stop_loss
        exit_reason = None
        
        if current_price <= stop_loss:
            exit_reason = "STOP_LOSS"
        elif current_price >= take_profit:
            exit_reason = "TAKE_PROFIT"
        elif current_price > entry_price + (atr * self.trail_atr_mult):
            new_stop = max(stop_loss, entry_price)
            if current_price <= new_stop:
                exit_reason = "TRAILING_STOP"
        
        if 'supertrend' in df.columns and not pd.isna(df['supertrend'].iloc[-1]):
            if current_price < df['supertrend'].iloc[-1]:
                exit_reason = "SUPER_TREND_FLIP"
        
        return exit_reason, new_stop
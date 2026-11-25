import pandas as pd
import numpy as np
from typing import Tuple, Optional

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1/period, adjust=False).mean()

def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    
    vwap_vals = pd.Series(index=typical_price.index, dtype='float32')
    
    for date, group in typical_price.groupby(typical_price.index.date):
        mask = typical_price.index.date == date
        grp_vol = volume[mask].cumsum()
        grp_pv = (typical_price[mask] * volume[mask]).cumsum()
        vwap_vals.loc[mask] = (grp_pv / grp_vol.replace(0, np.nan)).astype('float32').values
    
    return vwap_vals.ffill()

def vwap_bands(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, 
               period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    typical_price = (high + low + close) / 3
    vwap_vals = vwap(high, low, close, volume)
    
    rolling_std = typical_price.rolling(period).std()
    upper = vwap_vals + (rolling_std * std_dev)
    lower = vwap_vals - (rolling_std * std_dev)
    return upper, vwap_vals, lower

def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, 
               period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    atr_vals = atr(high, low, close, period)
    hl2 = (high + low) / 2
    
    upper_band = hl2 + (multiplier * atr_vals)
    lower_band = hl2 - (multiplier * atr_vals)
    
    supertrend = pd.Series(index=close.index, dtype='float64')
    direction = pd.Series(index=close.index, dtype='int8')
    
    supertrend.iloc[0] = float(lower_band.iloc[0])
    direction.iloc[0] = 1
    
    for i in range(1, len(close)):
        if close.iloc[i] > supertrend.iloc[i-1]:
            supertrend.iloc[i] = float(max(lower_band.iloc[i], supertrend.iloc[i-1]))
            direction.iloc[i] = 1
        else:
            supertrend.iloc[i] = float(min(upper_band.iloc[i], supertrend.iloc[i-1]))
            direction.iloc[i] = -1
    
    return supertrend.astype('float32'), direction

def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52, displacement: int = 26) -> dict:
    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    
    senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)
    senkou_b = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(displacement)
    
    chikou = close.shift(-displacement)
    
    return {
        'tenkan': tenkan_sen,
        'kijun': kijun_sen,
        'senkou_a': senkou_a,
        'senkou_b': senkou_b,
        'chikou': chikou
    }

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    tr = atr(high, low, close, 1) * period
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1/period).mean() / tr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1/period).mean() / tr
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1/period).mean()
    
    return adx_val.fillna(0), plus_di.fillna(0), minus_di.fillna(0)

def add_all_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()
    
    df['ema_20'] = ema(df['close'], config.get('ema_short', 20))
    df['ema_50'] = ema(df['close'], config.get('ema_medium', 50))
    df['ema_200'] = ema(df['close'], config.get('ema_long', 200))
    
    df['rsi'] = rsi(df['close'], config.get('rsi_period', 14))
    
    macd_line, signal_line, histogram = macd(
        df['close'],
        config.get('macd_fast', 12),
        config.get('macd_slow', 26),
        config.get('macd_signal', 9)
    )
    df['macd'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_hist'] = histogram
    
    df['atr'] = atr(df['high'], df['low'], df['close'], config.get('atr_period', 14))
    
    bb_upper, bb_middle, bb_lower = bollinger_bands(
        df['close'],
        config.get('bb_period', 20),
        config.get('bb_std', 2.0)
    )
    df['bb_upper'] = bb_upper
    df['bb_middle'] = bb_middle
    df['bb_lower'] = bb_lower
    
    df['vwap'] = vwap(df['high'], df['low'], df['close'], df['volume'])
    
    vwap_u, vwap_m, vwap_l = vwap_bands(
        df['high'], df['low'], df['close'], df['volume'],
        config.get('vwap_period', 20), config.get('vwap_std', 2.0)
    )
    df['vwap_upper'] = vwap_u
    df['vwap_lower'] = vwap_l
    
    st, st_dir = supertrend(
        df['high'], df['low'], df['close'],
        config.get('st_period', 10), config.get('st_mult', 3.0)
    )
    df['supertrend'] = st
    df['supertrend_dir'] = st_dir
    
    ich = ichimoku(
        df['high'], df['low'], df['close'],
        config.get('ichi_tenkan', 9), config.get('ichi_kijun', 26),
        config.get('ichi_senkou_b', 52), config.get('ichi_disp', 26)
    )
    df['ichi_tenkan'] = ich['tenkan']
    df['ichi_kijun'] = ich['kijun']
    df['ichi_senkou_a'] = ich['senkou_a']
    df['ichi_senkou_b'] = ich['senkou_b']
    df['ichi_chikou'] = ich['chikou']
    
    adx_val, plus_di, minus_di = adx(df['high'], df['low'], df['close'], config.get('adx_period', 14))
    df['adx'] = adx_val
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    
    df['volume_avg_20'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_avg_20'].replace(0, np.nan)
    
    return df
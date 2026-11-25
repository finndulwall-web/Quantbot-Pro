"""
Enhanced Technical Indicators Module
Advanced indicators for professional trading strategies
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, List
# from numba import jit (not available on this platform)
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# Core Moving Averages
# ============================================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return series.rolling(period).mean()

def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def dema(series: pd.Series, period: int) -> pd.Series:
    """Double Exponential Moving Average"""
    ema1 = ema(series, period)
    ema2 = ema(ema1, period)
    return 2 * ema1 - ema2

def tema(series: pd.Series, period: int) -> pd.Series:
    """Triple Exponential Moving Average"""
    ema1 = ema(series, period)
    ema2 = ema(ema1, period)
    ema3 = ema(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3

def hma(series: pd.Series, period: int) -> pd.Series:
    """Hull Moving Average"""
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    wma_half = wma(series, half_period)
    wma_full = wma(series, period)
    return wma(2 * wma_half - wma_full, sqrt_period)

# @jit(nopython=True)  # numba not available
def _wma_numba(values, weights):
    result = np.empty_like(values)
    result[:] = np.nan
    for i in range(len(values)):
        if i >= len(weights) - 1:
            result[i] = np.dot(values[i-len(weights)+1:i+1], weights)
    return result

def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1, dtype=np.float64)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum() if not np.any(np.isnan(x)) else np.nan,
        raw=True
    )

def zlema(series: pd.Series, period: int) -> pd.Series:
    """Zero Lag Exponential Moving Average"""
    lag = (period - 1) // 2
    data = series + (series - series.shift(lag))
    return ema(data, period)


# ============================================================================
# Momentum Oscillators
# ============================================================================

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's)"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)

def rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI using Wilder's smoothing (1/period)"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)

def stoch_rsi(series: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series]:
    """Stochastic RSI"""
    rsi_vals = rsi(series, period)
    min_rsi = rsi_vals.rolling(period).min()
    max_rsi = rsi_vals.rolling(period).max()
    stoch = (rsi_vals - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan)
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k.fillna(50), d.fillna(50)

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD with signal line and histogram"""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def macd_zl(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Zero-Lag MACD"""
    fast_ema = zlema(series, fast)
    slow_ema = zlema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = zlema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def true_strength_index(series: pd.Series, long: int = 25, short: int = 13) -> pd.Series:
    """True Strength Index (TSI)"""
    momentum = series.diff()
    abs_momentum = momentum.abs()
    
    ema_long_m = momentum.ewm(span=long, adjust=False).mean()
    ema_long_abs = abs_momentum.ewm(span=long, adjust=False).mean()
    
    ema_short_m = ema_long_m.ewm(span=short, adjust=False).mean()
    ema_short_abs = ema_long_abs.ewm(span=short, adjust=False).mean()
    
    tsi = 100 * (ema_short_m / ema_short_abs.replace(0, np.nan))
    return tsi.fillna(0)

def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R"""
    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    wr = -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan)
    return wr.fillna(-50)

def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index"""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci_val = (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))
    return cci_val.fillna(0)

def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index"""
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
    
    pos_mf = positive_flow.rolling(period).sum()
    neg_mf = negative_flow.rolling(period).sum()
    
    mfi = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.nan)))
    return mfi.fillna(50)


# ============================================================================
# Volatility Indicators
# ============================================================================

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder's)"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1/period, adjust=False).mean()

def atr_pct(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ATR as percentage of price"""
    atr_val = atr(high, low, close, period)
    return (atr_val / close * 100).fillna(0)

def natr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Normalized ATR"""
    atr_val = atr(high, low, close, period)
    return (atr_val / close * 100).fillna(0)

def kc(high: pd.Series, low: pd.Series, close: pd.Series, 
       period: int = 20, mult: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Keltner Channels"""
    ema_val = ema(close, period)
    atr_val = atr(high, low, close, period)
    upper = ema_val + mult * atr_val
    lower = ema_val - mult * atr_val
    return upper, ema_val, lower

def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Donchian Channels"""
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    middle = (upper + lower) / 2
    return upper, middle, lower

def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands"""
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def bb_width(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Bollinger Band Width"""
    upper, middle, lower = bollinger_bands(series, period, std_dev)
    return (upper - lower) / middle.replace(0, np.nan) * 100

def bb_percent_b(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Bollinger %B"""
    upper, middle, lower = bollinger_bands(series, period, std_dev)
    return (series - lower) / (upper - lower).replace(0, np.nan) * 100

def std_dev(series: pd.Series, period: int = 20) -> pd.Series:
    """Rolling Standard Deviation"""
    return series.rolling(period).std()

def variance(series: pd.Series, period: int = 20) -> pd.Series:
    """Rolling Variance"""
    return series.rolling(period).var()

def historical_volatility(close: pd.Series, period: int = 20, trading_days: int = 252) -> pd.Series:
    """Annualized Historical Volatility"""
    log_returns = np.log(close / close.shift(1))
    return log_returns.rolling(period).std() * np.sqrt(trading_days) * 100

def parkinson_volatility(high: pd.Series, low: pd.Series, period: int = 20, trading_days: int = 252) -> pd.Series:
    """Parkinson Volatility (uses high/low)"""
    hl_ratio = np.log(high / low)
    park_var = (1 / (4 * np.log(2))) * hl_ratio.rolling(period).var()
    return np.sqrt(park_var * trading_days) * 100

def garman_klass_volatility(high: pd.Series, low: pd.Series, close: pd.Series, open_: pd.Series, 
                             period: int = 20, trading_days: int = 252) -> pd.Series:
    """Garman-Klass Volatility"""
    log_hl = np.log(high / low)
    log_co = np.log(close / open_)
    var = 0.5 * log_hl**2 - (2*np.log(2) - 1) * log_co**2
    gk_var = var.rolling(period).mean()
    return np.sqrt(gk_var * trading_days) * 100


# ============================================================================
# Volume Indicators
# ============================================================================

def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price (session-based reset)"""
    typical_price = (high + low + close) / 3
    
    vwap_vals = pd.Series(index=typical_price.index, dtype='float32')
    
    for date, group in typical_price.groupby(typical_price.index.date):
        mask = typical_price.index.date == date
        grp_vol = volume[mask].cumsum()
        grp_pv = (typical_price[mask] * volume[mask]).cumsum()
        vwap_vals.loc[mask] = (grp_pv / grp_vol.replace(0, np.nan)).astype('float32').values
    
    return vwap_vals.ffill()

def anchored_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, 
                  anchor_date: pd.Timestamp) -> pd.Series:
    """Anchored VWAP from a specific date"""
    typical_price = (high + low + close) / 3
    mask = typical_price.index >= anchor_date
    tp = typical_price[mask]
    vol = volume[mask]
    cum_vol = vol.cumsum()
    cum_pv = (tp * vol).cumsum()
    vwap = (cum_pv / cum_vol.replace(0, np.nan)).ffill()
    return vwap.reindex(volume.index).ffill()

def vwap_bands(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, 
               period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """VWAP with Standard Deviation Bands"""
    typical_price = (high + low + close) / 3
    vwap_vals = vwap(high, low, close, volume)
    
    rolling_std = typical_price.rolling(period).std()
    upper = vwap_vals + (rolling_std * std_dev)
    lower = vwap_vals - (rolling_std * std_dev)
    return upper, vwap_vals, lower

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume"""
    direction = np.sign(close.diff()).fillna(0)
    return (volume * direction).cumsum()

def ad_line(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Accumulation/Distribution Line"""
    clv = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    clv = clv.fillna(0)
    ad = (clv * volume).cumsum()
    return ad

def ad_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, 
                   fast: int = 3, slow: int = 10) -> pd.Series:
    """Chaikin A/D Oscillator"""
    ad = ad_line(high, low, close, volume)
    return ema(ad, fast) - ema(ad, slow)

def cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    """Chaikin Money Flow"""
    mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mfm = mfm.fillna(0)
    mfv = mfm * volume
    cmf_val = mfv.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)
    return cmf_val.fillna(0)

def vwap_distance(close: pd.Series, vwap_val: pd.Series) -> pd.Series:
    """Distance from VWAP as percentage"""
    return (close - vwap_val) / vwap_val.replace(0, np.nan) * 100


# ============================================================================
# Trend Indicators
# ============================================================================

def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, 
               period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """Supertrend Indicator"""
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
    """Ichimoku Kinko Hyo"""
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

def parabolic_sar(high: pd.Series, low: pd.Series, close: pd.Series, 
                   af: float = 0.02, max_af: float = 0.2) -> pd.Series:
    """Parabolic SAR"""
    psar = pd.Series(index=close.index, dtype='float64')
    af = af
    ep = high.iloc[0]
    trend = 1  # 1 = up, -1 = down
    psar.iloc[0] = low.iloc[0]
    
    for i in range(1, len(close)):
        if trend == 1:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            if high.iloc[i] > ep:
                ep = high.iloc[i]
                af = min(af + 0.02, max_af)
            if low.iloc[i] <= psar.iloc[i]:
                trend = -1
                psar.iloc[i] = ep
                ep = low.iloc[i]
                af = 0.02
        else:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            if low.iloc[i] < ep:
                ep = low.iloc[i]
                af = min(af + 0.02, max_af)
            if high.iloc[i] >= psar.iloc[i]:
                trend = 1
                psar.iloc[i] = ep
                ep = high.iloc[i]
                af = 0.02
    
    return psar

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index"""
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

def aroon(high: pd.Series, low: pd.Series, period: int = 25) -> Tuple[pd.Series, pd.Series]:
    """Aroon Indicator"""
    aroon_up = 100 * (period - high.rolling(period).apply(lambda x: np.argmax(x[::-1]), raw=True)) / period
    aroon_down = 100 * (period - low.rolling(period).apply(lambda x: np.argmax(x[::-1]), raw=True)) / period
    return aroon_up, aroon_down

def tsi(close: pd.Series, long: int = 25, short: int = 13) -> pd.Series:
    """True Strength Index"""
    momentum = close.diff()
    abs_momentum = momentum.abs()
    
    ema_long_m = momentum.ewm(span=long, adjust=False).mean()
    ema_long_abs = abs_momentum.ewm(span=long, adjust=False).mean()
    
    ema_short_m = ema_long_m.ewm(span=short, adjust=False).mean()
    ema_short_abs = ema_long_abs.ewm(span=short, adjust=False).mean()
    
    tsi = 100 * (ema_short_m / ema_short_abs.replace(0, np.nan))
    return tsi.fillna(0)


# ============================================================================
# Pattern Recognition
# ============================================================================

def detect_doji(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, 
                threshold: float = 0.1) -> pd.Series:
    """Detect Doji candles"""
    body = abs(close - open_)
    range_ = high - low
    return (body / range_.replace(0, np.nan) < threshold).fillna(False)

def detect_hammer(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Detect Hammer/Inverted Hammer"""
    body = abs(close - open_)
    lower_shadow = np.minimum(open_, close) - low
    upper_shadow = high - np.maximum(open_, close)
    body_size = abs(close - open_)
    range_ = high - low
    
    hammer = (lower_shadow > 2 * body_size) & (upper_shadow < 0.1 * range_) & (close > open_)
    inverted = (upper_shadow > 2 * body_size) & (lower_shadow < 0.1 * range_) & (close < open_)
    return hammer | inverted

def detect_engulfing(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Detect Bullish/Bearish Engulfing"""
    prev_open = open_.shift(1)
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    
    bullish = (close > open_) & (prev_close < prev_open) & \
              (close > prev_open) & (open_ < prev_close) & \
              (close - open_ > prev_open - prev_close)
    
    bearish = (close < open_) & (prev_close > prev_open) & \
              (close < prev_open) & (open_ > prev_close) & \
              (open_ - close > prev_close - prev_open)
    
    return bullish | bearish

def detect_morning_evening_star(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Detect Morning Star / Evening Star"""
    # Simplified 3-candle pattern detection
    c1 = close.shift(2)
    c2 = close.shift(1)
    c3 = close
    o1 = open_.shift(2)
    o2 = open_.shift(1)
    o3 = open_
    
    # Morning Star: large bearish, small body, large bullish
    ms = (c1 < o1) & (abs(c2 - o2) < 0.3 * abs(c2 - o2).abs()) & (c3 > o3) & (c3 > c1)
    # Evening Star: large bullish, small body, large bearish
    es = (c1 > o1) & (abs(c2 - o2) < 0.3 * abs(c2 - o2).abs()) & (c3 < o3) & (c3 < c1)
    
    return ms | es


# ============================================================================
# Advanced Composite Indicators
# ============================================================================

def squeeze_momentum(high: pd.Series, low: pd.Series, close: pd.Series, 
                      bb_period: int = 20, bb_std: float = 2.0,
                      kc_period: int = 20, kc_mult: float = 1.5) -> pd.Series:
    """TTM Squeeze Momentum"""
    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = bollinger_bands(close, bb_period, bb_std)
    # Keltner Channels
    kc_upper, kc_middle, kc_lower = kc(high, low, close, kc_period, 1.5)
    
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    
    # Momentum
    highest_high = high.rolling(20).max()
    lowest_low = low.rolling(20).min()
    mid = (highest_high + lowest_low) / 2
    momentum = close - (mid + close.rolling(20).mean()) / 2
    
    return momentum, squeeze_on

def vix_fix(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 22) -> pd.Series:
    """VIX Fix (Synthetic VIX)"""
    highest_high = high.rolling(period).max()
    vix = (highest_high - close) / highest_high * 100
    return vix

def fisher_transform(series: pd.Series, period: int = 10) -> pd.Series:
    """Fisher Transform"""
    # Normalize to -1, 1
    min_val = series.rolling(period).min()
    max_val = series.rolling(period).max()
    normalized = 2 * (series - min_val) / (max_val - min_val).replace(0, np.nan) - 1
    normalized = np.clip(normalized, -0.999, 0.999)
    fisher = 0.5 * np.log((1 + normalized) / (1 - normalized))
    return fisher

def ewma_cross(series: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
    """EMA Cross Signal"""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    cross = np.where(fast_ema > slow_ema, 1, -1)
    return pd.Series(cross, index=series.index)


# ============================================================================
# Utility Functions
# ============================================================================

def normalize_series(series: pd.Series, period: int = 100) -> pd.Series:
    """Normalize series to 0-1 range"""
    min_val = series.rolling(period).min()
    max_val = series.rolling(period).max()
    return (series - min_val) / (max_val - min_val).replace(0, np.nan)

def standardize_series(series: pd.Series, period: int = 20) -> pd.Series:
    """Standardize series (z-score)"""
    mean = series.rolling(period).mean()
    std = series.rolling(period).std().replace(0, np.nan)
    return (series - mean) / std

def rank_series(series: pd.Series, period: int = 20) -> pd.Series:
    """Percentile rank"""
    return series.rolling(period).rank(pct=True)

def hurst_exponent(series: pd.Series, period: int = 100) -> pd.Series:
    """Hurst Exponent (simplified)"""
    def hurst(ts):
        lags = range(2, min(20, len(ts)))
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    return series.rolling(100).apply(hurst, raw=True)

def fractional_diff(series: pd.Series, d: float = 0.5, window: int = 100) -> pd.Series:
    """Fractional Differentiation (stationarity preserving)"""
    weights = [1.0]
    for k in range(1, window):
        weights.append(-weights[-1] * (d - k + 1) / k)
    weights = np.array(weights[::-1])
    
    result = pd.Series(index=series.index, dtype='float64')
    for i in range(len(series)):
        if i >= window:
            result.iloc[i] = np.dot(weights, series.iloc[i-window:i+1].values)
    return result


# ============================================================================
# Main Function to Add All Enhanced Indicators
# ============================================================================

def add_all_enhanced_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Add all enhanced indicators to dataframe"""
    df = df.copy()
    
    # Core EMAs
    df['ema_20'] = ema(df['close'], config.get('ema_short', 20))
    df['ema_50'] = ema(df['close'], config.get('ema_medium', 50))
    df['ema_200'] = ema(df['close'], config.get('ema_long', 200))
    
    # Advanced MAs
    df['dema_20'] = dema(df['close'], config.get('ema_short', 20))
    df['tema_20'] = tema(df['close'], config.get('ema_short', 20))
    df['hma_20'] = hma(df['close'], config.get('ema_short', 20))
    df['zlema_20'] = zlema(df['close'], config.get('ema_short', 20))
    
    # RSI variants
    df['rsi'] = rsi(df['close'], config.get('rsi_period', 14))
    df['rsi_wilder'] = rsi_wilder(df['close'], config.get('rsi_period', 14))
    df['stoch_rsi_k'], df['stoch_rsi_d'] = stoch_rsi(df['close'])
    df['tsi'] = tsi(df['close'])
    df['williams_r'] = williams_r(df['high'], df['low'], df['close'])
    df['cci'] = cci(df['high'], df['low'], df['close'])
    df['mfi'] = mfi(df['high'], df['low'], df['close'], df['volume'])
    
    # MACD variants
    macd_line, signal_line, histogram = macd(
        df['close'],
        config.get('macd_fast', 12),
        config.get('macd_slow', 26),
        config.get('macd_signal', 9)
    )
    df['macd'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_hist'] = histogram
    
    macd_zl_line, macd_zl_signal, macd_zl_hist = macd_zl(df['close'])
    df['macd_zl'] = macd_zl_line
    df['macd_zl_signal'] = macd_zl_signal
    df['macd_zl_hist'] = macd_zl_hist
    
    # TSI
    df['tsi'] = tsi(df['close'])
    df['williams_r'] = williams_r(df['high'], df['low'], df['close'])
    df['cci'] = cci(df['high'], df['low'], df['close'])
    df['mfi'] = mfi(df['high'], df['low'], df['close'], df['volume'])
    
    # ATR variants
    df['atr'] = atr(df['high'], df['low'], df['close'], config.get('atr_period', 14))
    df['atr_pct'] = atr_pct(df['high'], df['low'], df['close'])
    df['natr'] = natr(df['high'], df['low'], df['close'])
    
    # Volatility
    bb_upper, bb_middle, bb_lower = bollinger_bands(
        df['close'],
        config.get('bb_period', 20),
        config.get('bb_std', 2.0)
    )
    df['bb_upper'] = bb_upper
    df['bb_middle'] = bb_middle
    df['bb_lower'] = bb_lower
    df['bb_width'] = bb_width(df['close'])
    df['bb_pct_b'] = bb_percent_b(df['close'])
    
    kc_u, kc_m, kc_l = kc(df['high'], df['low'], df['close'])
    df['kc_upper'] = kc_u
    df['kc_middle'] = kc_m
    df['kc_lower'] = kc_l
    
    donch_u, donch_m, donch_l = donchian(df['high'], df['low'])
    df['donch_upper'] = donch_u
    df['donch_middle'] = donch_m
    df['donch_lower'] = donch_l
    
    df['atr'] = atr(df['high'], df['low'], df['close'], config.get('atr_period', 14))
    df['atr_pct'] = atr_pct(df['high'], df['low'], df['close'])
    df['natr'] = natr(df['high'], df['low'], df['close'])
    
    df['historical_vol'] = historical_volatility(df['close'])
    df['parkinson_vol'] = parkinson_volatility(df['high'], df['low'])
    df['gk_vol'] = garman_klass_volatility(df['high'], df['low'], df['close'], df['open'])
    
    # VWAP
    df['vwap'] = vwap(df['high'], df['low'], df['close'], df['volume'])
    vwap_u, vwap_m, vwap_l = vwap_bands(
        df['high'], df['low'], df['close'], df['volume'],
        config.get('vwap_period', 20), config.get('vwap_std', 2.0)
    )
    df['vwap_upper'] = vwap_u
    df['vwap_lower'] = vwap_l
    df['vwap_dist'] = vwap_distance(df['close'], df['vwap'])
    
    # Anchored VWAP (from start of data)
    anchor = df.index[0] + pd.Timedelta(days=1)
    df['anchored_vwap'] = anchored_vwap(df['high'], df['low'], df['close'], df['volume'], df.index[0])
    
    # OBV and Volume
    df['obv'] = obv(df['close'], df['volume'])
    df['ad_line'] = ad_line(df['high'], df['low'], df['close'], df['volume'])
    df['ad_osc'] = ad_oscillator(df['high'], df['low'], df['close'], df['volume'])
    df['cmf'] = cmf(df['high'], df['low'], df['close'], df['volume'])
    
    # Supertrend
    st, st_dir = supertrend(
        df['high'], df['low'], df['close'],
        config.get('st_period', 10), config.get('st_mult', 3.0)
    )
    df['supertrend'] = st
    df['supertrend_dir'] = st_dir
    
    # Ichimoku
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
    
    # ADX
    adx_val, plus_di, minus_di = adx(df['high'], df['low'], df['close'], config.get('adx_period', 14))
    df['adx'] = adx_val
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    
    # Aroon
    aroon_up, aroon_down = aroon(df['high'], df['low'])
    df['aroon_up'] = aroon_up
    df['aroon_down'] = aroon_down
    
    # Parabolic SAR
    df['psar'] = parabolic_sar(df['high'], df['low'], df['close'])
    
    # Volume indicators
    df['obv'] = obv(df['close'], df['volume'])
    df['ad_line'] = ad_line(df['high'], df['low'], df['close'], df['volume'])
    df['ad_osc'] = ad_oscillator(df['high'], df['low'], df['close'], df['volume'])
    df['cmf'] = cmf(df['high'], df['low'], df['close'], df['volume'])
    df['obv_ema'] = ema(df['obv'], 20)
    
    # Volume profile
    df['volume_avg_20'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_avg_20'].replace(0, np.nan)
    df['volume_zscore'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std().replace(0, np.nan)
    
    # Pattern recognition
    df['doji'] = detect_doji(df['open'], df['high'], df['low'], df['close'])
    df['hammer'] = detect_hammer(df['open'], df['high'], df['low'], df['close'])
    df['engulfing'] = detect_engulfing(df['open'], df['high'], df['low'], df['close'])
    df['morning_evening_star'] = detect_morning_evening_star(df['open'], df['high'], df['low'], df['close'])
    
    # Squeeze
    momentum, squeeze_on = squeeze_momentum(df['high'], df['low'], df['close'])
    df['squeeze_momentum'] = momentum
    df['squeeze_on'] = squeeze_on
    
    # VIX Fix
    df['vix_fix'] = vix_fix(df['high'], df['low'], df['close'])
    
    # Fisher Transform
    df['fisher'] = fisher_transform(df['close'])
    
    # VIX Fix
    df['vix_fix'] = vix_fix(df['high'], df['low'], df['close'])
    
    # EMA Cross
    df['ema_cross'] = ewma_cross(df['close'])
    
    # Z-score normalization
    df['close_zscore'] = standardize_series(df['close'])
    df['volume_zscore'] = standardize_series(df['volume'])
    df['rsi_zscore'] = standardize_series(df['rsi'])
    
    # Rank and percentile
    df['close_rank'] = rank_series(df['close'])
    df['volume_rank'] = rank_series(df['volume'])
    
    return df

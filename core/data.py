import ccxt
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
import time
import logging
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_DB = Path("data_cache.db")
CACHE_DB.parent.mkdir(exist_ok=True)

def init_cache_db():
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                symbol TEXT,
                timeframe TEXT,
                timestamp INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                source TEXT,
                PRIMARY KEY (symbol, timeframe, timestamp)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_tf ON ohlcv(symbol, timeframe)")

init_cache_db()

def _symbol_key(symbol: str) -> str:
    return symbol.replace('/', '_').replace(':', '_')

def _cache_key(symbol: str, timeframe: str, start: int, end: int) -> str:
    return hashlib.md5(f"{symbol}_{timeframe}_{start}_{end}".encode()).hexdigest()

def fetch_ccxt_ohlcv(symbol: str, timeframe: str = '1h', limit: int = 100, 
                     since: Optional[int] = None, retries: int = 3) -> pd.DataFrame:
    exchange = ccxt.binance({'enableRateLimit': True, 'timeout': 30000})
    
    for attempt in range(retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not ohlcv:
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            df = df.astype({'open': 'float32', 'high': 'float32', 'low': 'float32', 
                           'close': 'float32', 'volume': 'float32'})
            return df
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"CCXT fetch failed (attempt {attempt+1}/{retries}): {e}. Retrying in {wait}s")
            time.sleep(wait)
    
    logger.error(f"CCXT fetch failed after {retries} attempts for {symbol}")
    return pd.DataFrame()

def fetch_yfinance_ohlcv(symbol: str, timeframe: str = '1h', period: str = '730d',
                         retries: int = 3) -> pd.DataFrame:
    interval_map = {'1h': '1h', '1d': '1d', '4h': '4h'}
    interval = interval_map.get(timeframe, '1h')
    
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if df.empty:
                return pd.DataFrame()
            
            df.index = pd.to_datetime(df.index, utc=True)
            df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low',
                                   'Close': 'close', 'Volume': 'volume'})
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df = df.astype({'open': 'float32', 'high': 'float32', 'low': 'float32',
                           'close': 'float32', 'volume': 'float32'})
            return df
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"YFinance fetch failed (attempt {attempt+1}/{retries}): {e}. Retrying in {wait}s")
            time.sleep(wait)
    
    logger.error(f"YFinance fetch failed after {retries} attempts for {symbol}")
    return pd.DataFrame()

def cache_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, source: str):
    if df.empty:
        return
    
    records = []
    for ts, row in df.iterrows():
        records.append((
            symbol, timeframe, int(ts.timestamp() * 1000),
            float(row['open']), float(row['high']), float(row['low']),
            float(row['close']), float(row['volume']), source
        ))
    
    with sqlite3.connect(CACHE_DB) as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO ohlcv 
            (symbol, timeframe, timestamp, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

def load_cached_ohlcv(symbol: str, timeframe: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    with sqlite3.connect(CACHE_DB) as conn:
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, start_ms, end_ms))
    
    if df.empty:
        return pd.DataFrame()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    df = df.astype({'open': 'float32', 'high': 'float32', 'low': 'float32',
                   'close': 'float32', 'volume': 'float32'})
    return df

def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    df = df[~df.index.duplicated(keep='last')]
    df = df.sort_index()
    
    df = df.replace([np.inf, -np.inf], np.nan)
    df['volume'] = df['volume'].ffill()
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    
    return df

def fetch_ohlcv(symbol: str, timeframe: str = '1h', limit: int = 100,
                use_cache: bool = True) -> pd.DataFrame:
    is_crypto = '/' in symbol or ':' in symbol
    now_ms = int(time.time() * 1000)
    
    if is_crypto:
        since = now_ms - (limit * 3600 * 1000)
        
        if use_cache:
            cached = load_cached_ohlcv(symbol, timeframe, since, now_ms)
            if len(cached) >= limit * 0.8:
                logger.debug(f"Cache hit for {symbol} ({len(cached)} candles)")
                return cached.tail(limit)
        
        df = fetch_ccxt_ohlcv(symbol, timeframe, limit, since)
        source = 'binance'
    else:
        period = '730d' if limit > 500 else '60d'
        
        if use_cache:
            since = now_ms - (limit * 3600 * 1000)
            cached = load_cached_ohlcv(symbol, timeframe, since, now_ms)
            if len(cached) >= limit * 0.8:
                logger.debug(f"Cache hit for {symbol} ({len(cached)} candles)")
                return cached.tail(limit)
        
        df = fetch_yfinance_ohlcv(symbol, timeframe, period)
        source = 'yfinance'
    
    df = clean_ohlcv(df)
    
    if use_cache and not df.empty:
        cache_ohlcv(df, symbol, timeframe, source)
    
    return df.tail(limit) if len(df) > limit else df

def fetch_backtest_data(symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    start_dt = pd.Timestamp(start, tz='UTC')
    end_dt = pd.Timestamp(end, tz='UTC')
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    cached = load_cached_ohlcv(symbol, timeframe, start_ms, end_ms)
    expected_candles = int((end_dt - start_dt).total_seconds() / 3600)
    
    if len(cached) >= expected_candles * 0.9:
        logger.info(f"Full cache hit for backtest {symbol}: {len(cached)} candles")
        return cached
    
    logger.info(f"Fetching backtest data for {symbol} from {start} to {end}")
    
    is_crypto = '/' in symbol or ':' in symbol
    all_dfs = []
    chunk_days = 30 if is_crypto else 60
    current = start_dt
    
    while current < end_dt:
        chunk_end = min(current + timedelta(days=chunk_days), end_dt)
        
        if is_crypto:
            since = int(current.timestamp() * 1000)
            df = fetch_ccxt_ohlcv(symbol, timeframe, limit=1000, since=since)
        else:
            period = f"{(chunk_end - current).days}d"
            df = fetch_yfinance_ohlcv(symbol, timeframe, period=period)
        
        if not df.empty:
            all_dfs.append(df)
        
        current = chunk_end
        time.sleep(0.5)
    
    if not all_dfs:
        return pd.DataFrame()
    
    full_df = pd.concat(all_dfs)
    full_df = clean_ohlcv(full_df)
    full_df = full_df[(full_df.index >= start_dt) & (full_df.index <= end_dt)]
    
    if use_cache := True:
        cache_ohlcv(full_df, symbol, timeframe, 'binance' if is_crypto else 'yfinance')
    
    return full_df
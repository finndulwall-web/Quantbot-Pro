"""
Async Data Pipeline with Caching, Validation, and Quality Checks
"""
import asyncio
import asyncio
import aiohttp
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from collections import defaultdict
import asyncio
import hashlib
import json
import pickle
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    """Data quality report"""
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    total_candles: int
    missing_candles: int
    duplicate_candles: int
    zero_volume_candles: int
    anomalous_candles: int
    gaps: List[Dict]
    quality_score: float  # 0-1


class DataValidator:
    """Validate OHLCV data quality"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.max_gap_minutes = config.get('max_gap_minutes', 60)
        self.max_price_change_pct = config.get('max_price_change_pct', 0.5)
        self.min_volume = config.get('min_volume', 0)
    
    def validate(self, df: pd.DataFrame, symbol: str, timeframe: str) -> DataQualityReport:
        """Validate OHLCV data quality"""
        if df.empty:
            return DataQualityReport(
                symbol="", timeframe="", start_time=datetime.now(), end_time=datetime.now(),
                total_candles=0, missing_candles=0, duplicate_candles=0,
                zero_volume_candles=0, anomalous_candles=0, gaps=[], quality_score=0.0
            )
        
        start_time = df.index[0]
        end_time = df.index[-1]
        total_candles = len(df)
        
        # Check for duplicates
        duplicate_candles = df.index.duplicated().sum()
        
        # Check for missing candles (gaps)
        expected_freq = self._infer_frequency(df.index)
        expected_index = pd.date_range(start=df.index[0], end=df.index[-1], freq=expected_freq)
        missing_index = expected_index.difference(df.index)
        missing_candles = len(missing_index)
        
        gaps = []
        if len(missing_index) > 0:
            # Group consecutive missing timestamps
            gap_groups = []
            for ts in missing_index:
                if not gap_groups or (ts - gap_groups[-1][-1]) > pd.Timedelta(minutes=1):
                    gap_groups.append([ts])
                else:
                    gap_groups[-1].append(ts)
            
            for group in gap_groups:
                gaps.append({
                    'start': group[0].isoformat(),
                    'end': group[-1].isoformat(),
                    'count': len(group)
                })
        
        # Check for zero volume candles
        zero_volume = (df['volume'] == 0).sum() if 'volume' in df.columns else 0
        
        # Check for anomalous price movements
        anomalous = 0
        if 'close' in df.columns:
            returns = df['close'].pct_change().abs()
            anomalous = (returns > self.max_price_change_pct).sum()
        
        # Calculate quality score
        total_issues = duplicate_candles + missing_candles + zero_volume + anomalous
        max_possible = len(df) * 4
        quality_score = max(0, 1 - (total_issues / max(1, max_possible)))
        
        return DataQualityReport(
            symbol="",
            timeframe="",
            start_time=start_time,
            end_time=end_time,
            total_candles=total_candles,
            missing_candles=missing_candles,
            duplicate_candles=duplicate_candles,
            zero_volume_candles=zero_volume,
            anomalous_candles=anomalous,
            gaps=gaps,
            quality_score=quality_score
        )
    
    def _infer_frequency(self, index: pd.DatetimeIndex) -> str:
        """Infer frequency from datetime index"""
        if len(index) < 2:
            return '1H'
        delta = index[1] - index[0]
        seconds = delta.total_seconds()
        if seconds <= 60:
            return '1T'
        elif seconds <= 300:
            return '5T'
        elif seconds <= 900:
            return '15T'
        elif seconds <= 1800:
            return '30T'
        elif seconds <= 3600:
            return '1H'
        elif seconds <= 7200:
            return '2H'
        elif seconds <= 14400:
            return '4H'
        else:
            return '1D'


class CacheManager:
    """Multi-level cache with TTL and size limits"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600, 
                 persist_path: str = "cache"):
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}
        self.access_times: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._load_persisted()
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments"""
        key_data = json.dumps([args, kwargs], sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            return None
        
        # Check TTL
        if time.time() - self.timestamps.get(key, 0) > self.ttl:
            self.delete(key)
            return None
        
        # Update access time
        self.access_times[key] = time.time()
        return self.cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
        self.access_times[key] = time.time()
        
        # Persist to disk
        self._persist(key, value)
    
    def delete(self, key: str):
        """Delete key from cache"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)
        self.access_times.pop(key, None)
        # Remove from disk
        try:
            (self.persist_path / f"{key}.pkl").unlink(missing_ok=True)
        except:
            pass
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if not self.access_times:
            return
        lru_key = min(self.access_times, key=self.access_times.get)
        self.delete(lru_key)
    
    def _persist(self, key: str, value: Any):
        """Persist cache entry to disk"""
        try:
            with open(self.persist_path / f"{key}.pkl", 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            logger.warning(f"Failed to persist cache: {e}")
    
    def _load_persisted(self):
        """Load persisted cache entries"""
        for pkl_file in self.persist_path.glob("*.pkl"):
            try:
                key = pkl_file.stem
                with open(pkl_file, 'rb') as f:
                    value = pickle.load(f)
                self.cache[key] = value
                self.timestamps[key] = time.time()  # Approximate
                self.access_times[key] = time.time()
            except Exception as e:
                logger.warning(f"Failed to load cache {pkl_file}: {e}")
    
    def clear_expired(self):
        """Remove expired entries"""
        now = time.time()
        expired = [
            k for k, ts in self.timestamps.items()
            if now - ts > self.ttl
        ]
        for key in expired:
            self.delete(key)
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.timestamps.clear()
        self.access_times.clear()
        for f in self.persist_path.glob("*.pkl"):
            f.unlink(missing_ok=True)


class DataPipeline:
    """Async data pipeline with validation, caching, and multiple sources"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.cache = CacheManager(
            max_size=config.get('cache_size', 1000),
            ttl_seconds=config.get('cache_ttl', 3600),
            persist_path=config.get('cache_path', 'cache')
        )
        self.validator = DataValidator(config.get('validation', {}))
        self.sources: Dict[str, Any] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, 
                          limit: int = 100, since: Optional[datetime] = None) -> pd.DataFrame:
        """Fetch OHLCV data with caching and validation"""
        cache_key = self.cache._make_key('ohlcv', symbol, timeframe, limit, since)
        
        # Try cache first
        cached = self.cache.get(f"ohlcv:{cache_key}")
        if cached is not None:
            logger.debug(f"Cache hit for {symbol} {timeframe}")
            return cached
        
        # Fetch from source
        df = await self._fetch_from_source(symbol, timeframe, limit, since)
        
        if df is not None and not df.empty:
            # Validate
            report = self.validator.validate(df, symbol, timeframe)
            if report.quality_score < 0.5:
                logger.warning(f"Low quality data for {symbol}: {report.quality_score:.2f}")
            
            # Cache result
            self.cache.set(f"ohlcv:{cache_key}", df)
            
            return df
        
        return pd.DataFrame()
    
    async def _fetch_from_source(self, symbol: str, timeframe: str, 
                                  limit: int, since: Optional[datetime]) -> pd.DataFrame:
        """Fetch from data source (to be implemented by subclass)"""
        raise NotImplementedError
    
    async def fetch_multiple(self, symbols: List[str], timeframe: str, 
                             limit: int = 100) -> Dict[str, pd.DataFrame]:
        """Fetch multiple symbols concurrently"""
        tasks = [self.fetch_ohlcv(sym, timeframe, limit) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        results_dict = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {sym}: {result}")
                results_dict[sym] = pd.DataFrame()
            else:
                results_dict[sym] = result
        
        return results_dict
    
    async def stream_ohlcv(self, symbol: str, timeframe: str, 
                           callback: Callable[[pd.DataFrame], None],
                           interval: int = 60):
        """Stream real-time OHLCV data"""
        self._running = True
        while True:
            try:
                df = await self.fetch_ohlcv(symbol, timeframe, limit=2)
                if not df.empty:
                    await callback(df.iloc[-1:])
            except Exception as e:
                logger.error(f"Stream error: {e}")
            
            await asyncio.sleep(interval)


class BinanceDataSource:
    """Binance data source with async support"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.base_url = "https://api.binance.com/api/v3"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                          limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV from Binance"""
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        interval = interval_map.get(timeframe, '1h')
        
        params = {
            'symbol': symbol.replace('/', ''),
            'interval': interval,
            'limit': min(limit, 1000)
        }
        
        async with self.session.get(f"{self.base_url}/klines", params=params) as resp:
            if resp.status != 200:
                raise Exception(f"Binance API error: {resp.status}")
            
            data = await resp.json()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']].astype('float32')
            df = df.sort_index()
            
            return df


class YFinanceDataSource:
    """Yahoo Finance data source"""
    
    def __init__(self):
        pass
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                    period: str = '60d') -> pd.DataFrame:
        import yfinance as yf
        
        interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                       '1h': '1h', '4h': '4h', '1d': '1d'}
        interval = interval_map.get(timeframe, '1h')
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        
        if df.empty:
            return pd.DataFrame()
        
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume'
        })
        df = df[['open', 'high', 'low', 'close', 'volume']].astype('float32')
        return df


class DataPipeline:
    """High-level data pipeline orchestrator"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.sources = {
            'binance': BinanceDataSource(config),
            'yfinance': YFinanceDataSource(),
        }
        self.cache = CacheManager(
            max_size=config.get('cache_size', 1000),
            ttl_seconds=config.get('cache_ttl', 3600)
        )
        self.validator = DataValidator(config.get('validation', {}))
    
    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', 
                        limit: int = 100, source: str = 'binance') -> pd.DataFrame:
        """Get OHLCV data with caching and validation"""
        cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}"
        
        # Try cache
        cached = self.cache.get(f"ohlcv:{cache_key}")
        if cached is not None:
            return cached
        
        # Fetch from source
        source_obj = self.sources.get(source)
        if not source_obj:
            raise ValueError(f"Unknown source: {source}")
        
        if hasattr(source_obj, '__aenter__'):
            async with source_obj as src:
                df = await source_obj.fetch_ohlcv(symbol, timeframe, limit)
        else:
            df = source_obj.fetch_ohlcv(symbol, timeframe)
        
        # Validate
        if not df.empty:
            report = self.validator.validate(df, symbol, timeframe)
            if config.get('validation', {}).get('strict', False):
                if report.quality_score < 0.7:
                    logger.warning(f"Low quality data for {symbol}: {report.quality_score:.2f}")
        
        # Cache
        self.cache.set(f"ohlcv:{cache_key}", df)
        return df
    
    async def fetch_multi(self, symbols: List[str], timeframe: str = '1h', 
                          limit: int = 100) -> Dict[str, pd.DataFrame]:
        """Fetch multiple symbols concurrently"""
        tasks = [self.get_ohlcv(sym, timeframe, limit) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        results_dict = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {sym}: {result}")
                results_dict[sym] = pd.DataFrame()
            else:
                results_dict[sym] = result
        
        return results_dict
    
    async def stream(self, symbol: str, timeframe: str, 
                     callback: Callable, interval: int = 60):
        """Stream real-time data"""
        while True:
            try:
                df = await self.get_ohlcv(symbol, timeframe, limit=2)
                if not df.empty:
                    await callback(df.iloc[-1:])
            except Exception as e:
                logger.error(f"Stream error: {e}")
            await asyncio.sleep(interval)


# Singleton instance
_pipeline_instance: Optional[DataPipeline] = None


def get_pipeline(config: Dict = None) -> DataPipeline:
    """Get global pipeline instance"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = DataPipeline(config)
    return _pipeline_instance


async def shutdown_pipeline():
    """Shutdown global pipeline"""
    global _pipeline_instance
    if _pipeline_instance:
        for src in _pipeline_instance.sources.values():
            if hasattr(src, '__aexit__'):
                await src.__aexit__(None, None, None)
        _pipeline_instance = None

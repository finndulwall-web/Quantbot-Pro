"""
ML-based Signal Enhancement
Lightweight ML models for signal filtering and enhancement
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import json
import pickle
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MLSignalFeatures:
    """Features for ML model"""
    # Technical indicators
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_upper: float
    bb_lower: float
    bb_middle: float
    bb_width: float
    bb_pct_b: float
    atr: float
    atr_pct: float
    ema_20: float
    ema_50: float
    ema_200: float
    vwap: float
    vwap_dist: float
    volume_ratio: float
    obv: float
    cmf: float
    adx: float
    plus_di: float
    minus_di: float
    supertrend: float
    supertrend_dir: int
    ichi_tenkan: float
    ichi_kijun: float
    ichi_senkou_a: float
    ichi_senkou_b: float
    
    # Price action
    returns_1: float
    returns_5: float
    returns_20: float
    volatility: float
    
    # Regime
    regime: str
    trend_strength: float
    
    # Target (for training)
    target: Optional[int] = None  # 1 = profitable, 0 = not profitable
    
    def to_array(self) -> np.ndarray:
        """Convert to feature array"""
        features = [
            self.rsi, self.macd, self.macd_signal, self.macd_hist,
            self.bb_upper, self.bb_lower, self.bb_middle, self.bb_width, self.bb_pct_b,
            self.atr, self.atr_pct,
            self.ema_20, self.ema_50, self.ema_200,
            self.vwap, self.vwap_dist,
            self.volume_ratio, self.obv, self.cmf,
            self.adx, self.plus_di, self.minus_di,
            self.supertrend, self.supertrend_dir,
            self.ichi_tenkan, self.ichi_kijun, self.ichi_senkou_a, self.ichi_senkou_b,
            self.returns_1, self.returns_5, self.returns_20, self.volatility,
            self.trend_strength
        ]
        return np.array([f if not np.isnan(f) else 0.0 for f in features])


class MLSignalEnhancer:
    """ML-based signal enhancer for filtering and confidence scoring"""
    
    def __init__(self, model_dir: str = "models", model_type: str = "rf"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.feature_names = []
        self.is_trained = False
        self.feature_importance = {}
        
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, ML features disabled")
    
    def extract_features(self, df: pd.DataFrame, idx: int) -> Optional[np.ndarray]:
        """Extract features for a specific row"""
        if idx < 50:  # Need enough history
            return None
        
        row = df.iloc[idx]
        
        try:
            features = MLSignalFeatures(
                rsi=row.get('rsi', 50),
                macd=row.get('macd', 0),
                macd_signal=row.get('macd_signal', 0),
                macd_hist=row.get('macd_hist', 0),
                bb_upper=row.get('bb_upper', 0),
                bb_lower=row.get('bb_lower', 0),
                bb_middle=row.get('bb_middle', 0),
                bb_width=row.get('bb_width', 0),
                bb_pct_b=row.get('bb_pct_b', 0.5),
                atr=row.get('atr', 0),
                atr_pct=row.get('atr_pct', 0),
                ema_20=row.get('ema_20', 0),
                ema_50=row.get('ema_50', 0),
                ema_200=row.get('ema_200', 0),
                vwap=row.get('vwap', 0),
                vwap_dist=row.get('vwap_dist', 0),
                volume_ratio=row.get('volume_ratio', 1),
                obv=row.get('obv', 0),
                cmf=row.get('cmf', 0),
                adx=row.get('adx', 0),
                plus_di=row.get('plus_di', 0),
                minus_di=row.get('minus_di', 0),
                supertrend=row.get('supertrend', 0),
                supertrend_dir=row.get('supertrend_dir', 0),
                ichi_tenkan=row.get('ichi_tenkan', 0),
                ichi_kijun=row.get('ichi_kijun', 0),
                ichi_senkou_a=row.get('ichi_senkou_a', 0),
                ichi_senkou_b=row.get('ichi_senkou_b', 0),
                returns_1=0,  # Will compute below
                returns_5=0,
                returns_20=0,
                volatility=0,
                regime='unknown',
                trend_strength=0.5
            )
            
            # Compute returns
            close_prices = df['close'].values
            if len(close_prices) > idx:
                features.returns_1 = (close_prices[idx] - close_prices[idx-1]) / close_prices[idx-1] if idx > 0 else 0
                features.returns_5 = (close_prices[idx] - close_prices[idx-5]) / close_prices[idx-5] if idx >= 5 else 0
                features.returns_20 = (close_prices[idx] - close_prices[idx-20]) / close_prices[idx-20] if idx >= 20 else 0
                features.volatility = np.std(np.diff(np.log(close_prices[max(0,idx-20):idx+1]))) if idx >= 20 else 0
                
                # Regime
                if 'ema_50' in df.columns and 'ema_200' in df.columns:
                    features.regime = 'bull' if df['ema_50'].iloc[idx] > df['ema_200'].iloc[idx] else 'bear'
                
                # Trend strength
                if 'adx' in df.columns:
                    features.trend_strength = min(row.get('adx', 0) / 50, 1.0)
            
            return features.to_array()
            
        except Exception as e:
            logger.warning(f"Feature extraction failed: {e}")
            return None
    
    def prepare_training_data(self, df: pd.DataFrame, lookforward: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data with labels"""
        if not SKLEARN_AVAILABLE:
            return np.array([]), np.array([])
        
        # Add indicators
        from core.indicators_enhanced import add_all_enhanced_indicators
        df_ind = add_all_enhanced_indicators(df.copy(), {})
        
        features_list = []
        labels = []
        
        for i in range(50, len(df) - lookforward):
            features = self.extract_features(df, i)
            if features is None:
                continue
            
            # Label: 1 if price goes up in next N periods, 0 otherwise
            future_return = (df['close'].iloc[i + lookforward] - df['close'].iloc[i]) / df['close'].iloc[i]
            label = 1 if future_return > 0.01 else 0  # 1% threshold
            
            features_list.append(features)
            labels.append(label)
        
        if not features_list:
            return np.array([]), np.array([])
        
        X = np.array(features_list)
        y = np.array(labels)
        
        self.feature_names = [f"f_{i}" for i in range(X.shape[1])]
        return X, y
    
    def train(self, df: pd.DataFrame, lookforward: int = 5) -> Dict[str, float]:
        """Train the ML model"""
        if not SKLEARN_AVAILABLE:
            logger.warning("sklearn not available, skipping training")
            return {"error": "sklearn not available"}
        
        logger.info("Preparing training data...")
        X, y = self.prepare_training_data(df)
        
        if len(X) == 0:
            return {"error": "Insufficient training data"}
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        if self.model_type == "rf":
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == "gb":
            self.model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                random_state=42
            )
        
        logger.info(f"Training {self.model_type} model on {len(X_train)} samples...")
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_pred = self.model.predict(X_train_scaled)
        test_pred = self.model.predict(X_test_scaled)
        
        train_acc = accuracy_score(y_train, train_pred)
        test_acc = accuracy_score(y_test, test_pred)
        train_prec = precision_score(y_train, train_pred, zero_division=0)
        test_prec = precision_score(y_test, test_pred, zero_division=0)
        train_rec = recall_score(y_train, train_pred, zero_division=0)
        test_rec = recall_score(y_test, test_pred, zero_division=0)
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            self.feature_importance = dict(zip(
                [f"f_{i}" for i in range(len(self.model.feature_importances_))],
                self.model.feature_importances_
            ))
        
        self.is_trained = True
        
        metrics = {
            "train_accuracy": train_acc,
            "test_accuracy": test_acc,
            "train_precision": train_prec,
            "test_precision": test_prec,
            "train_recall": train_rec,
            "test_recall": test_rec,
            "train_samples": len(y_train),
            "test_samples": len(y_test),
        }
        
        logger.info(f"Training complete: Train Acc={train_acc:.3f}, Test Acc={test_acc:.3f}, "
                   f"Prec={test_prec:.3f}, Rec={test_rec:.3f}")
        
        self.save_model()
        return metrics
    
    def predict(self, df: pd.DataFrame, idx: int = -1) -> Tuple[float, float]:
        """Predict probability of profitable trade"""
        if not self.is_trained or self.model is None:
            return 0.5, 0.5  # Neutral
        
        features = self.extract_features(df, idx if idx >= 0 else len(df) + idx)
        if features is None:
            return 0.5, 0.5
        
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        proba = self.model.predict_proba(features_scaled)[0]
        
        # Return probability of class 1 (profitable) and confidence
        prob_profitable = proba[1] if len(proba) > 1 else 0.5
        confidence = max(proba)  # Max probability as confidence
        
        return float(prob_profitable), float(confidence)
    
    def predict_batch(self, df: pd.DataFrame) -> np.ndarray:
        """Predict for entire dataframe"""
        if not self.is_trained or self.model is None:
            return np.full(len(df), 0.5)
        
        probs = []
        for i in range(len(df)):
            prob, _ = self.predict(df, i)
            probs.append(prob)
        return np.array(probs)
    
    def save_model(self):
        """Save model to disk"""
        if not self.is_trained:
            return
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'feature_importance': self.feature_importance,
            'timestamp': datetime.now().isoformat()
        }
        
        model_path = self.model_dir / f"signal_enhancer_{self.model_type}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        logger.info(f"Model saved to {model_path}")
    
    def load_model(self) -> bool:
        """Load model from disk"""
        model_path = self.model_dir / f"signal_enhancer_{self.model_type}.pkl"
        if not model_path.exists():
            return False
        
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.model_type = model_data.get('model_type', 'rf')
            self.feature_importance = model_data.get('feature_importance', {})
            self.is_trained = True
            logger.info(f"Model loaded from {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def get_feature_importance(self, top_n: int = 20) -> Dict[str, float]:
        """Get top N feature importances"""
        if not self.feature_importance:
            return {}
        sorted_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_features[:top_n])


class SignalFilter:
    """Post-processing filter for ML-enhanced signals"""
    
    def __init__(self, ml_enhancer: MLSignalEnhancer, threshold: float = 0.6):
        self.ml_enhancer = ml_enhancer
        self.threshold = threshold
    
    def filter_signal(self, signal, df: pd.DataFrame, idx: int = -1) -> Tuple[bool, float, str]:
        """
        Filter signal through ML model
        Returns: (should_trade, confidence, reason)
        """
        if not self.ml_enhancer.is_trained:
            return True, 0.5, "ML model not trained"
        
        prob, confidence = self.ml_enhancer.predict(df)
        
        if prob < self.threshold:
            return False, confidence, f"ML probability {prob:.2f} below threshold {self.threshold}"
        
        # Additional checks
        if hasattr(signal, 'confidence'):
            # Combine strategy confidence with ML probability
            combined_conf = (signal.confidence + prob) / 2
            if combined_conf < self.threshold * 0.8:
                return False, combined_conf, f"Combined confidence {combined_conf:.2f} below threshold"
        
        return True, prob, f"ML approved: prob={prob:.2f}, conf={confidence:.2f}"
    
    def filter_signals(self, signals: List, df: pd.DataFrame) -> List:
        """Filter multiple signals"""
        filtered = []
        for i, signal in enumerate(signals):
            should_trade, conf, reason = self.filter_signal(signal, df, i)
            if should_trade:
                signal.metadata['ml_probability'] = signal.metadata.get('ml_probability', 0)
                signal.metadata['ml_confidence'] = conf
                signal.metadata['ml_reason'] = reason
                filtered.append(signal)
            else:
                logger.info(f"Signal filtered: {reason}")
        return filtered


class OnlineLearner:
    """Online learning for continuous model updates"""
    
    def __init__(self, ml_enhancer: MLSignalEnhancer, update_frequency: int = 100):
        self.ml_enhancer = ml_enhancer
        self.update_frequency = update_frequency
        self.trade_buffer = []
        self.update_counter = 0
        self.min_buffer = 50
    
    def record_trade(self, signal, df: pd.DataFrame, outcome: dict):
        """Record trade outcome for learning"""
        # Extract features at signal time
        features = self.ml_enhancer.extract_features(df)
        if features is None:
            return
        
        # Determine outcome
        pnl_pct = outcome.get('pnl_pct', 0)
        label = 1 if pnl_pct > 0 else 0
        
        self.trade_buffer.append({
            'features': features,
            'label': label,
            'timestamp': datetime.now(),
            'symbol': signal.symbol,
            'pnl_pct': pnl_pct
        })
        
        self.update_counter += 1
        
        if self.update_counter >= self.update_frequency and len(self.trade_buffer) >= self.min_buffer:
            self._update_model()
    
    def _update_model(self):
        """Incremental model update"""
        if not self.ml_enhancer.is_trained or len(self.trade_buffer) < self.min_buffer:
            return
        
        # Prepare new training data
        X_new = np.array([t['features'] for t in self.trade_buffer])
        y_new = np.array([t['label'] for t in self.trade_buffer])
        
        # Scale
        X_scaled = self.ml_enhancer.scaler.transform(X_new)
        
        # Partial fit if supported
        if hasattr(self.ml_enhancer.model, 'partial_fit'):
            self.ml_enhancer.model.partial_fit(X_scaled, self.ml_enhancer.scaler.transform(X_new))
            logger.info(f"Model updated with {len(self.trade_buffer)} new samples")
            self.trade_buffer.clear()
            self.update_counter = 0
        else:
            # Full retrain periodically
            if len(self.trade_buffer) > self.min_buffer * 5:
                self._full_retrain()
    
    def _full_retrain(self):
        """Full retrain with accumulated data"""
        # This would combine old and new data
        pass

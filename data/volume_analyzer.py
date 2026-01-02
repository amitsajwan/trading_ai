"""Volume analysis utilities for market data."""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VolumeAnalyzer:
    """Analyze volume patterns and signals."""
    
    @staticmethod
    def calculate_volume_profile(ohlc_data: List[Dict[str, Any]], bins: int = 20) -> Dict[str, Any]:
        """
        Calculate volume profile (volume at different price levels).
        
        Args:
            ohlc_data: List of OHLC candles
            bins: Number of price bins
        
        Returns:
            Volume profile with price levels and volumes
        """
        if not ohlc_data:
            return {}
        
        try:
            df = pd.DataFrame(ohlc_data)
            
            # Get price range
            min_price = df["low"].min()
            max_price = df["high"].max()
            price_range = max_price - min_price
            
            if price_range == 0:
                return {}
            
            # Create price bins
            bin_size = price_range / bins
            price_bins = [min_price + i * bin_size for i in range(bins + 1)]
            
            # Calculate volume in each bin
            volume_profile = {}
            for i in range(bins):
                bin_low = price_bins[i]
                bin_high = price_bins[i + 1]
                bin_center = (bin_low + bin_high) / 2
                
                # Find candles that overlap with this bin
                overlapping = df[
                    ((df["low"] <= bin_high) & (df["high"] >= bin_low))
                ]
                
                # Calculate volume in this bin (proportional to overlap)
                bin_volume = 0
                for _, candle in overlapping.iterrows():
                    overlap_low = max(candle["low"], bin_low)
                    overlap_high = min(candle["high"], bin_high)
                    overlap_pct = (overlap_high - overlap_low) / (candle["high"] - candle["low"]) if (candle["high"] - candle["low"]) > 0 else 0
                    bin_volume += candle["volume"] * overlap_pct
                
                volume_profile[bin_center] = bin_volume
            
            # Find point of control (POC) - price level with highest volume
            poc_price = max(volume_profile.items(), key=lambda x: x[1])[0] if volume_profile else None
            
            return {
                "volume_profile": volume_profile,
                "poc_price": poc_price,
                "value_area_high": max(volume_profile.keys()) if volume_profile else None,
                "value_area_low": min(volume_profile.keys()) if volume_profile else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return {}
    
    @staticmethod
    def calculate_volume_trends(ohlc_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate volume trends and momentum.
        
        Args:
            ohlc_data: List of OHLC candles
        
        Returns:
            Volume trend indicators
        """
        if not ohlc_data or len(ohlc_data) < 20:
            return {}
        
        try:
            df = pd.DataFrame(ohlc_data)
            df = df.sort_values("timestamp") if "timestamp" in df.columns else df
            
            # Volume moving averages
            volume_ma_5 = df["volume"].tail(5).mean()
            volume_ma_20 = df["volume"].tail(20).mean()
            
            # Current volume vs average
            current_volume = df["volume"].iloc[-1]
            volume_ratio = current_volume / volume_ma_20 if volume_ma_20 > 0 else 1.0
            
            # Volume trend direction
            recent_volumes = df["volume"].tail(5)
            volume_trend = "INCREASING" if recent_volumes.iloc[-1] > recent_volumes.iloc[0] else "DECREASING"
            
            # Volume momentum (rate of change)
            volume_roc = ((current_volume - df["volume"].iloc[-5]) / df["volume"].iloc[-5] * 100) if len(df) >= 5 else 0
            
            return {
                "current_volume": float(current_volume),
                "volume_ma_5": float(volume_ma_5),
                "volume_ma_20": float(volume_ma_20),
                "volume_ratio": float(volume_ratio),
                "volume_trend": volume_trend,
                "volume_momentum": float(volume_roc),
                "volume_status": (
                    "HIGH" if volume_ratio > 1.5 else
                    "LOW" if volume_ratio < 0.5 else
                    "NORMAL"
                )
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume trends: {e}")
            return {}
    
    @staticmethod
    def calculate_vwap(ohlc_data: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate Volume-Weighted Average Price (VWAP).
        
        Args:
            ohlc_data: List of OHLC candles
        
        Returns:
            VWAP value
        """
        if not ohlc_data:
            return None
        
        try:
            df = pd.DataFrame(ohlc_data)
            
            # Typical price (high + low + close) / 3
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
            
            # VWAP = sum(typical_price * volume) / sum(volume)
            vwap = (df["typical_price"] * df["volume"]).sum() / df["volume"].sum()
            
            return float(vwap)
            
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return None
    
    @staticmethod
    def calculate_obv(ohlc_data: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate On-Balance Volume (OBV).
        
        Args:
            ohlc_data: List of OHLC candles
        
        Returns:
            OBV value
        """
        if not ohlc_data or len(ohlc_data) < 2:
            return None
        
        try:
            df = pd.DataFrame(ohlc_data)
            df = df.sort_values("timestamp") if "timestamp" in df.columns else df
            
            obv = 0
            for i in range(1, len(df)):
                if df["close"].iloc[i] > df["close"].iloc[i-1]:
                    obv += df["volume"].iloc[i]
                elif df["close"].iloc[i] < df["close"].iloc[i-1]:
                    obv -= df["volume"].iloc[i]
                # If close unchanged, OBV unchanged
            
            return float(obv)
            
        except Exception as e:
            logger.error(f"Error calculating OBV: {e}")
            return None
    
    @staticmethod
    def volume_confirmation(price_change: float, volume_change: float) -> str:
        """
        Check if volume confirms price move.
        
        Args:
            price_change: Price change percentage
            volume_change: Volume change percentage
        
        Returns:
            Confirmation status
        """
        if abs(price_change) < 0.1:  # Less than 0.1% change
            return "NEUTRAL"
        
        # Volume should increase with significant price moves
        if price_change > 0 and volume_change > 0:
            return "CONFIRMED"  # Price up, volume up
        elif price_change < 0 and volume_change > 0:
            return "CONFIRMED"  # Price down, volume up
        elif price_change > 0 and volume_change < -0.2:
            return "DIVERGENCE"  # Price up, volume down (weak move)
        elif price_change < 0 and volume_change < -0.2:
            return "DIVERGENCE"  # Price down, volume down (weak move)
        else:
            return "NEUTRAL"


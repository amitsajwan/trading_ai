"""Standardized Technical Indicators Constants

This module defines the canonical names for all technical indicators used across the system.
All processes (agents, APIs, services) must use these constants to ensure consistency.

Usage:
    from market_data.technical_indicators_constants import RSI_14, MACD_VALUE
    rsi_value = technical_data.get(RSI_14)
"""

# === TREND INDICATORS ===
SMA_10 = "sma_10"
SMA_20 = "sma_20"
SMA_50 = "sma_50"
EMA_10 = "ema_10"
EMA_20 = "ema_20"
EMA_50 = "ema_50"
WMA_20 = "wma_20"

# === MOMENTUM INDICATORS ===
RSI_9 = "rsi_9"
RSI_14 = "rsi_14"
RSI_STATUS = "rsi_status"  # OVERSOLD, OVERBOUGHT, NEUTRAL
STOCH_K = "stoch_k"
STOCH_D = "stoch_d"
WILLIAMS_R = "williams_r"

# === MACD INDICATORS ===
MACD_VALUE = "macd_value"
MACD_SIGNAL = "macd_signal"
MACD_HISTOGRAM = "macd_histogram"

# === VOLATILITY INDICATORS ===
BOLlinger_UPPER = "bollinger_upper"
BOLlinger_MIDDLE = "bollinger_middle"
BOLlinger_LOWER = "bollinger_lower"
BOLlinger_WIDTH = "bollinger_width"
BOLlinger_PERCENT_B = "bollinger_percent_b"
ATR_14 = "atr_14"
ATR_20 = "atr_20"

# === TREND STRENGTH ===
ADX_14 = "adx_14"
DI_PLUS = "di_plus"
DI_MINUS = "di_minus"

# === VOLUME INDICATORS ===
OBV = "obv"
VOLUME_SMA_20 = "volume_sma_20"
VOLUME_RSI_14 = "volume_rsi_14"
CMF_20 = "cmf_20"  # Chaikin Money Flow

# === OPEN INTEREST INDICATORS ===
OI = "oi"
OI_CHANGE = "oi_change"
OI_PCT_CHANGE = "oi_pct_change"
OI_SMA_5 = "oi_sma_5"
OI_EMA_10 = "oi_ema_10"
OI_MOMENTUM_5 = "oi_momentum_5"

# === OSCILLATORS ===
CCI_20 = "cci_20"
MFI_14 = "mfi_14"
ROC_12 = "roc_12"
MOMENTUM_10 = "momentum_10"

# === SUPPORT/RESISTANCE ===
PIVOT_POINT = "pivot_point"
PIVOT_R1 = "pivot_r1"
PIVOT_R2 = "pivot_r2"
PIVOT_S1 = "pivot_s1"
PIVOT_S2 = "pivot_s2"

# === PRICE ACTION ===
HIGH_20 = "high_20"
LOW_20 = "low_20"
RANGE_20 = "range_20"

# === DERIVED SIGNALS ===
TREND_DIRECTION = "trend_direction"  # UP, DOWN, SIDEWAYS
TREND_STRENGTH = "trend_strength"    # 0-100 scale
SIGNAL_STRENGTH = "signal_strength"  # 0-100 composite signal
VOLATILITY_LEVEL = "volatility_level"  # LOW, MEDIUM, HIGH

# === CURRENT PRICE ===
CURRENT_PRICE = "current_price"

# === METADATA ===
TIMESTAMP = "timestamp"
INSTRUMENT = "instrument"
TIMEFRAME = "timeframe"

# === CORE INDICATORS LIST (for validation) ===
CORE_INDICATORS = [
    RSI_14, MACD_VALUE, BOLlinger_UPPER, ADX_14,
    TREND_DIRECTION, SIGNAL_STRENGTH, CURRENT_PRICE
]

# === ALL INDICATORS LIST ===
ALL_INDICATORS = [
    # Trend
    SMA_10, SMA_20, SMA_50, EMA_10, EMA_20, EMA_50, WMA_20,
    # Momentum
    RSI_9, RSI_14, RSI_STATUS, STOCH_K, STOCH_D, WILLIAMS_R,
    # MACD
    MACD_VALUE, MACD_SIGNAL, MACD_HISTOGRAM,
    # Volatility
    BOLlinger_UPPER, BOLlinger_MIDDLE, BOLlinger_LOWER, BOLlinger_WIDTH, BOLlinger_PERCENT_B,
    ATR_14, ATR_20,
    # Trend Strength
    ADX_14, DI_PLUS, DI_MINUS,
    # Volume
    OBV, VOLUME_SMA_20, VOLUME_RSI_14, CMF_20,
    # Open Interest
    OI, OI_CHANGE, OI_PCT_CHANGE, OI_SMA_5, OI_EMA_10, OI_MOMENTUM_5,
    # Oscillators
    CCI_20, MFI_14, ROC_12, MOMENTUM_10,
    # Support/Resistance
    PIVOT_POINT, PIVOT_R1, PIVOT_R2, PIVOT_S1, PIVOT_S2,
    # Price Action
    HIGH_20, LOW_20, RANGE_20,
    # Derived
    TREND_DIRECTION, TREND_STRENGTH, SIGNAL_STRENGTH, VOLATILITY_LEVEL,
    # Current
    CURRENT_PRICE,
    # Metadata
    TIMESTAMP, INSTRUMENT, TIMEFRAME
]

# === REDIS KEY PATTERNS ===
def get_indicator_redis_key(instrument: str, indicator: str, timeframe: str = "1min") -> str:
    """Get Redis key for a specific indicator."""
    return f"indicators:{instrument.upper()}:{timeframe}:{indicator}"

def get_all_indicators_redis_pattern(instrument: str, timeframe: str = "1min") -> str:
    """Get Redis key pattern for all indicators of an instrument."""
    return f"indicators:{instrument.upper()}:{timeframe}:*"
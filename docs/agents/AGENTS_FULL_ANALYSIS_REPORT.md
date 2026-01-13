# 🔬 COMPREHENSIVE AGENTS ANALYSIS REPORT

**Generated:** 2026-01-12 17:07:56
**Total Agents Tested:** 19
**Successful:** 19
**Failed:** 0

## 📊 TEST DATA OVERVIEW

- **Symbol:** BANKNIFTY26JANFUT
- **Current Price:** ₹5,264,795.48
- **OHLC Periods:** 100 (15-min candles)
- **Technical Indicators:** RSI 43.25, SMA20 ₹5,339,528.22
- **Positions:** 1 active (Long)
- **Options:** 3 calls, 3 puts, PCR 0.85
- **Fundamental:** Earnings surprise 15.0%, Revenue growth 12.0%

## 🎯 TECHNICAL AGENTS

### TECHNICAL

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "current_price": 5264795.48,
  "symbol": "BANKNIFTY26JANFUT"
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "rsi": 100.0,
    "rsi_status": "OVERBOUGHT",
    "atr": 215118.8636461673,
    "support_level": 1042456.95,
    "resistance_level": 5276018.52,
    "trend_direction": "UP",
    "trend_strength": 100,
    "decision_basis": "trend=UP, rsi_status=OVERBOUGHT"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.012s execution time

## 🎯 STRATEGY AGENTS

### MOMENTUM

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "agent": "MomentumAgent",
    "strategy": "momentum",
    "indicators": {
      "rsi": 43.25,
      "rsi_period": 14,
      "sma_20": 5339528.22,
      "volume_spike": false,
      "volume_ratio": 1.38,
      "price_change_pct": -0.0179
    },
    "reasoning": [],
    "entry_price": 5264795.48,
    "stop_loss": 5317443.434800001,
    "take_profit": 5185823.547800001,
    "risk_reward_ratio": 1.5
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### ENHANCED_MOMENTUM

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.3333333333333333,
  "details": {
    "agent": "EnhancedMomentumAgent",
    "strategy": "momentum",
    "reasoning": "Insufficient momentum signals. Waiting for clearer setup.",
    "conditions_met": [],
    "conditions_failed": [],
    "technical_data": {
      "rsi_15m": 43.25,
      "rsi_1h": 43.25,
      "rsi_daily": 43.25,
      "macd": -26323.98,
      "volume_ratio": 1.38,
      "adx": 34.84
    },
    "risk_assessment": {
      "risk_score": 0,
      "risk_level": "LOW",
      "volatility_regime": "normal",
      "portfolio_exposure": 0,
      "recommendation": "OK"
    },
    "regime": null,
    "target": "BANKNIFTY",
    "entry_price": 5264795.48,
    "structured_report": {
      "agent_name": "EnhancedMomentumAgent",
      "report_type": "analysis",
      "priority": "medium",
      "title": "EnhancedMomentumAgent Analysis: HOLD",
      "summary": "Decision: HOLD. Confidence: 33.3% (weak). Current Positions: 1. Reasoning: Insufficient momentum signals. Waiting for clearer setup.",
      "sections": [
        {
          "title": "Analysis",
          "content": "Insufficient momentum signals. Waiting for clearer setup.",
          "evidence": [],
          "subsections": [],
          "confidence": 0.3333333333333333
        }
      ],
      "actions": [],
      "confidence": 0.3333333333333333,
      "timestamp": "2026-01-12T17:07:49.453779",
      "metadata": {}
    },
    "signal_strength": "weak"
  },
  "agent": "EnhancedMomentumAgent",
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### TREND

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "current_price": 5264795.48,
  "symbol": "BANKNIFTY26JANFUT"
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "BUY",
  "confidence": 0.65,
  "details": {
    "agent": "TrendAgent",
    "strategy": "trend_following",
    "indicators": {
      "ma_fast": 2577182.863,
      "ma_fast_period": 20,
      "ma_slow": 1285835.7131999996,
      "ma_slow_period": 50,
      "adx": 25.0,
      "adx_period": 14,
      "adx_threshold": 25,
      "trend_strength_pct": 104.28490176562224
    },
    "reasoning": [
      "Moderate uptrend signal"
    ],
    "entry_price": 5264795.48,
    "stop_loss": 1279406.5346339997,
    "take_profit": 13235573.370732002,
    "risk_reward_ratio": 2.0
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.418s execution time

### MEAN_REVERSION

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "SELL",
  "confidence": 0.65,
  "details": {
    "agent": "MeanReversionAgent",
    "strategy": "mean_reversion",
    "indicators": {
      "rsi": 100.0,
      "rsi_period": 14,
      "rsi_oversold": 30,
      "rsi_overbought": 70,
      "bb_upper": -11515.148092948366,
      "bb_middle": 2577182.863,
      "bb_lower": 5165880.874092948,
      "bb_period": 20,
      "bb_std": 2.0,
      "band_position": -0.019105087863317636
    },
    "reasoning": [
      "RSI 100.0 > 70 (overbought)",
      "Price 5264795.48 > BB upper -11515.15",
      "Expected mean reversion pullback toward middle BB 2577182.86"
    ],
    "entry_price": 5264795.48,
    "stop_loss": -1305864.1536394225,
    "take_profit": 2577182.863,
    "risk_reward_ratio": 0.4090323904833522
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.010s execution time

### VOLUME

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "current_price": 5264795.48,
  "symbol": "BANKNIFTY26JANFUT"
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.0,
  "details": {
    "reason": "NO_VOLUME_SPIKE",
    "agent": "VolumeAgent",
    "current_volume": "13799",
    "avg_volume": 32336.65
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.001s execution time

## 🎯 FUNDAMENTAL AGENTS

### FUNDAMENTAL

**INPUT CONTEXT:**
```json
{
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "BUY",
  "confidence": 0.6,
  "details": {
    "earnings_surprise": 0.15,
    "revenue_growth": 0.12
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### SENTIMENT

**INPUT CONTEXT:**
```json
{
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "retail_sentiment": 0.0,
    "institutional_sentiment": 0.0,
    "sentiment_divergence": "NONE",
    "options_flow_signal": "NEUTRAL",
    "fear_greed_index": 50.0,
    "confidence_score": 0.5,
    "status": "ACTIVE",
    "sentiment_bias": "NEUTRAL",
    "note": "Analyzed via LLM"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### MACRO

**INPUT CONTEXT:**
```json
{
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "instrument_name": "BANKNIFTY26JANFUT"
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "macro_regime": "MIXED",
    "sector_headwind_score": 0.0,
    "macro_bias": "NEUTRAL",
    "confidence_score": 0.5
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

## 🎯 RESEARCH AGENTS

### BULL_RESEARCHER

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.3,
  "details": {
    "thesis": "No strong bullish signals detected",
    "signals": [],
    "past_experiences_considered": 2,
    "confidence_boost": 0.0,
    "report_type": "bullish_research"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 1.933s execution time

### BEAR_RESEARCHER

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.3,
  "details": {
    "thesis": "No strong bearish signals detected",
    "signals": [],
    "past_experiences_considered": 2,
    "confidence_boost": 0.0,
    "report_type": "bearish_research"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 1.623s execution time

### RESEARCH_MANAGER

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "IRON_CONDOR",
  "confidence": 0.6,
  "details": {
    "bull_thesis": {
      "thesis": "No strong bullish signals detected",
      "signals": [],
      "past_experiences_considered": 2,
      "confidence_boost": 0.0,
      "report_type": "bullish_research"
    },
    "bear_thesis": {
      "thesis": "No strong bearish signals detected",
      "signals": [],
      "past_experiences_considered": 2,
      "confidence_boost": 0.0,
      "report_type": "bearish_research"
    },
    "debate_summary": {
      "debate_points": [],
      "winner": "neutral",
      "summary": "Balanced debate - no clear winner",
      "bull_confidence": 0.3,
      "bear_confidence": 0.3
    },
    "research_plan": "Market range-bound - implement iron condor for premium collection"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 3.491s execution time

## 🎯 OPTIONS AGENTS

### OPTIONS_ANALYSIS

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.3,
  "details": {
    "atm_strike": 46000,
    "call_oi_total": 3300,
    "put_oi_total": 3100,
    "pcr": 0.85,
    "max_call_oi_strike": 45000,
    "max_put_oi_strike": 44000,
    "pcr_signal": "NEUTRAL",
    "max_pain": 45000,
    "max_pain_distance_pct": 99.14526594298019,
    "max_pain_signal": "ABOVE_MAX_PAIN_BULLISH",
    "avg_call_iv": 0.22333333333333336,
    "avg_put_iv": 0.22666666666666666,
    "iv_skew": 0.0033333333333332993,
    "iv_skew_signal": "BALANCED",
    "strategy": null,
    "note": "NO_SUITABLE_STRATEGY"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.001s execution time

### OPTIONS_STRATEGY

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "iron_condor",
  "confidence": 0.8,
  "details": {
    "strategy": "iron_condor",
    "underlying": "BANKNIFTY26JANFUT",
    "expiry": "2026-01-30",
    "max_profit": 55260.0,
    "max_loss": 184200,
    "margin_required": 18420000,
    "legs_count": 4
  },
  "agent": null,
  "options_strategy": "OptionsStrategyDetails(strategy_type=<OptionsStrategy.IRON_CONDOR: 'iron_condor'>, underlying='BANKNIFTY26JANFUT', expiry='2026-01-30', legs=[OptionsLeg(strike_price=5001600, option_type='PE', position='SELL', quantity=1, premium=0.0), OptionsLeg(strike_price=5185800, option_type='PE', position='BUY', quantity=1, premium=0.0), OptionsLeg(strike_price=5343800, option_type='CE', position='SELL', quantity=1, premium=0.0), OptionsLeg(strike_price=5528000, option_type='CE', position='BUY', quantity=1, premium=0.0)], max_profit=55260.0, max_loss=184200, breakeven_points=[4946340.0, 5583260.0], risk_reward_ratio=0.3, margin_required=18420000)"
}
```
**Performance:** 0.000s execution time

## 🎯 RISK & PORTFOLIO AGENTS

### PORTFOLIO_MANAGER

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.9,
  "details": {
    "votes": {
      "BUY": 0,
      "SELL": 0,
      "HOLD": 3
    }
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### ENHANCED_RISK

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "agent": "EnhancedRiskAgent",
    "risk_level": "LOW",
    "deliberation_result": {
      "winner": null,
      "winner_confidence": 0.5,
      "summary": "Debate concluded. ConservativeRiskPerspective (conservative): 1 arguments, avg confidence 60.00% | ModerateRiskPerspective (moderate): 1 arguments, avg confidence 70.00%",
      "key_points": [
        "ConservativeRiskPerspective: RISK MODERATE",
        "ModerateRiskPerspective: RISK ACCEPTABLE"
      ],
      "consensus": null,
      "recommended_action": null,
      "participants": [
        {
          "name": "ConservativeRiskPerspective",
          "position": "conservative",
          "argument_count": 1,
          "average_confidence": 0.6,
          "arguments": [
            {
              "participant_name": "ConservativeRiskPerspective",
              "argument_type": "initial",
              "claim": "RISK MODERATE",
              "reasoning": "IV percentile 50%, portfolio risk 0.00%",
              "evidence": [
                {
                  "type": "market_data",
                  "description": "IV percentile: 50%",
                  "value": 50,
                  "source": "IV_Percentile",
                  "confidence": 0.8,
                  "timestamp": "2026-01-12T17:07:56.932778"
                }
              ],
              "confidence": 0.6,
              "counter_argument_to": null,
              "timestamp": "2026-01-12T17:07:56.933033",
              "strength": "strong"
            }
          ]
        },
        {
          "name": "ModerateRiskPerspective",
          "position": "moderate",
          "argument_count": 1,
          "average_confidence": 0.7,
          "arguments": [
            {
              "participant_name": "ModerateRiskPerspective",
              "argument_type": "initial",
              "claim": "RISK ACCEPTABLE",
              "reasoning": "Balanced risk assessment: portfolio risk 0.00%",
              "evidence": [
                {
                  "type": "market_data",
                  "description": "Volatility: 1.30%",
                  "value": 0.013,
                  "source": "Volatility",
                  "confidence": 0.7,
                  "timestamp": "2026-01-12T17:07:56.932811"
                }
              ],
              "confidence": 0.7,
              "counter_argument_to": null,
              "timestamp": "2026-01-12T17:07:56.933082",
              "strength": "strong"
            }
          ]
        }
      ],
      "rounds": [
        {
          "round_number": 1,
          "arguments": [
            {
              "participant_name": "ConservativeRiskPerspective",
              "argument_type": "initial",
              "claim": "RISK MODERATE",
              "reasoning": "IV percentile 50%, portfolio risk 0.00%",
              "evidence": [
                {
                  "type": "market_data",
                  "description": "IV percentile: 50%",
                  "value": 50,
                  "source": "IV_Percentile",
                  "confidence": 0.8,
                  "timestamp": "2026-01-12T17:07:56.932778"
                }
              ],
              "confidence": 0.6,
              "counter_argument_to": null,
              "timestamp": "2026-01-12T17:07:56.933033",
              "strength": "strong"
            },
            {
              "participant_name": "ModerateRiskPerspective",
              "argument_type": "initial",
              "claim": "RISK ACCEPTABLE",
              "reasoning": "Balanced risk assessment: portfolio risk 0.00%",
              "evidence": [
                {
                  "type": "market_data",
                  "description": "Volatility: 1.30%",
                  "value": 0.013,
                  "source": "Volatility",
                  "confidence": 0.7,
                  "timestamp": "2026-01-12T17:07:56.932811"
                }
              ],
              "confidence": 0.7,
              "counter_argument_to": null,
              "timestamp": "2026-01-12T17:07:56.933082",
              "strength": "strong"
            }
          ],
          "timestamp": "2026-01-12T17:07:56.932845"
        },
        {
          "round_number": 2,
          "arguments": [],
          "timestamp": "2026-01-12T17:07:56.933134"
        }
      ],
      "timestamp": "2026-01-12T17:07:56.933395"
    },
    "portfolio_risk": 0.0,
    "recommendation": "HOLD",
    "risk_assessment": {
      "risk_score": 0,
      "risk_level": "LOW",
      "volatility_regime": "normal",
      "portfolio_exposure": 0,
      "recommendation": "OK"
    },
    "structured_report": {
      "agent_name": "EnhancedRiskAgent",
      "report_type": "analysis",
      "priority": "medium",
      "title": "EnhancedRiskAgent Analysis: HOLD",
      "summary": "Decision: HOLD. Confidence: 50.0% (moderate). Current Positions: 1",
      "sections": [
        {
          "title": "Analysis",
          "content": "Analysis completed",
          "evidence": [],
          "subsections": [],
          "confidence": 0.5
        },
        {
          "title": "Risk Deliberation",
          "content": "Risk deliberation concluded: Debate concluded. ConservativeRiskPerspective (conservative): 1 arguments, avg confidence 60.00% | ModerateRiskPerspective (moderate): 1 arguments, avg confidence 70.00%",
          "evidence": [],
          "subsections": [],
          "confidence": 0.5
        },
        {
          "title": "Portfolio Risk Assessment",
          "content": "Current portfolio risk: 0.00% (Limit: 2.00%)",
          "evidence": [],
          "subsections": [],
          "confidence": 0.9
        }
      ],
      "actions": [],
      "confidence": 0.5666666666666667,
      "timestamp": "2026-01-12T17:07:56.933712",
      "metadata": {}
    },
    "signal_strength": "moderate"
  },
  "agent": "EnhancedRiskAgent",
  "options_strategy": null
}
```
**Performance:** 0.002s execution time

## 🎯 EXECUTION & LEARNING AGENTS

### EXECUTION

**INPUT CONTEXT:**
```json
{
  "final_signal": {
    "action": "BUY",
    "confidence": 0.75,
    "entry_price": 5264795.48
  },
  "position_size": 10,
  "entry_price": 5264795.48,
  "stop_loss": 5159499.570400001,
  "take_profit": 5475387.2992,
  "current_price": 5264795.48
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.0,
  "details": {
    "note": "NO_EXECUTION"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### LEARNING

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "note": "learning agent stub"
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

### REVIEW

**INPUT CONTEXT:**
```json
{
  "ohlc": "[100 OHLC periods]",
  "symbol": "BANKNIFTY26JANFUT",
  "current_price": 5264795.48,
  "technical_indicators": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  },
  "calls": [
    {
      "strike": 44000,
      "oi": 1000,
      "volume": 500,
      "bid": 1200,
      "ask": 1250,
      "iv": 0.25
    },
    {
      "strike": 45000,
      "oi": 1500,
      "volume": 800,
      "bid": 800,
      "ask": 850,
      "iv": 0.22
    },
    {
      "strike": 46000,
      "oi": 800,
      "volume": 300,
      "bid": 450,
      "ask": 480,
      "iv": 0.2
    }
  ],
  "puts": [
    {
      "strike": 44000,
      "oi": 1200,
      "volume": 600,
      "bid": 350,
      "ask": 380,
      "iv": 0.23
    },
    {
      "strike": 45000,
      "oi": 1000,
      "volume": 400,
      "bid": 680,
      "ask": 710,
      "iv": 0.21
    },
    {
      "strike": 46000,
      "oi": 900,
      "volume": 350,
      "bid": 1100,
      "ask": 1130,
      "iv": 0.24
    }
  ],
  "underlying_price": 5264795.48,
  "pcr": 0.85,
  "max_pain": 45000,
  "consensus_direction": "BULLISH",
  "earnings_surprise": 0.15,
  "revenue_growth": 0.12,
  "rbi_rate": 0.065,
  "inflation_rate": 0.045,
  "latest_news": [
    {
      "title": "BANKNIFTY shows strong momentum",
      "sentiment": 0.8
    },
    {
      "title": "Market volatility expected to rise",
      "sentiment": -0.3
    }
  ],
  "sentiment_score": 0.65,
  "current_positions": [
    {
      "position_id": "pos_1",
      "symbol": "BANKNIFTY26JANFUT",
      "action": "BUY",
      "quantity": 10,
      "entry_price": 44800,
      "current_price": 44950,
      "stop_loss": 44400,
      "take_profit": 45200,
      "status": "active"
    }
  ],
  "has_long_position": true,
  "has_short_position": false,
  "position_count": 1,
  "account_size": 100000,
  "timestamp": "datetime",
  "market_hours": true,
  "technical": {
    "rsi": 43.25,
    "sma_20": 5339528.22,
    "sma_50": 5153787.95,
    "ema_12": 5211150.87,
    "ema_26": 5179162.08,
    "macd": -26323.98,
    "macd_signal": -21059.18,
    "adx": 34.84,
    "bb_upper": 5370091.38,
    "bb_middle": 5264795.48,
    "bb_lower": 5159499.57,
    "volume_sma": 50000,
    "volume_ratio": 1.38,
    "price_change_pct": -0.0179,
    "volatility": 0.013,
    "timestamp": "2026-01-12T17:07:48.901055"
  }
}
```
**OUTPUT RESULT:**
```json
{
  "decision": "HOLD",
  "confidence": 0.5,
  "details": {
    "summary": {
      "technical": true
    }
  },
  "agent": null,
  "options_strategy": null
}
```
**Performance:** 0.000s execution time

## 🎲 ORCHESTRATOR AGGREGATION ANALYSIS

**Agent Decisions Summary:**
- **technical:** HOLD (0.50)
- **momentum:** HOLD (0.50)
- **enhanced_momentum:** HOLD (0.33)
- **trend:** BUY (0.65)
- **mean_reversion:** SELL (0.65)
- **volume:** HOLD (0.00)
- **fundamental:** BUY (0.60)
- **sentiment:** HOLD (0.50)
- **macro:** HOLD (0.50)
- **bull_researcher:** HOLD (0.30)
- **bear_researcher:** HOLD (0.30)
- **research_manager:** IRON_CONDOR (0.60)
- **options_analysis:** HOLD (0.30)
- **options_strategy:** iron_condor (0.80)
- **portfolio_manager:** HOLD (0.90)
- **enhanced_risk:** HOLD (0.50)
- **execution:** HOLD (0.00)
- **learning:** HOLD (0.50)
- **review:** HOLD (0.50)

**Signal Counts:** 2 BUY, 1 SELL, 14 HOLD

**Orchestrator Final Decision:** HOLD (no clear consensus: 2 BUY vs 1 SELL)

---
*This report shows the complete analysis flow for all available agents with their inputs, outputs, and performance metrics.*
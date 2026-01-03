"""LLM-based strategy planner that generates trading rules."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import redis.asyncio as redis
from kiteconnect import KiteConnect
from agents.base_agent import BaseAgent
from data.market_memory import MarketMemory
from engines.instrument_detector import InstrumentDetector
from data.data_source_factory import DataSourceFactory
from data.derivatives_fetcher import DerivativesFetcher
from config.settings import settings

logger = logging.getLogger(__name__)


class StrategyPlanner(BaseAgent):
    """Generic LLM-based strategy planner - works for any instrument, region, currency."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, market_memory: Optional[MarketMemory] = None):
        """Initialize strategy planner."""
        system_prompt = self._get_default_prompt()
        super().__init__("strategy_planner", system_prompt)
        self.kite = kite
        self.market_memory = market_memory or MarketMemory()
        self.redis_client: Optional[redis.Redis] = None  # type: ignore
        
        # Generic components - no hardcoding
        self.instrument_detector = InstrumentDetector()
        self.data_source_factory = DataSourceFactory(kite=kite)
        self.derivatives_fetcher: Optional[DerivativesFetcher] = None
        self.instrument_profile = None
        
    def _get_default_prompt(self) -> str:
        """Get default system prompt - generic for any instrument with PREDICTIVE capabilities."""
        return """You are a Strategy Planner for trading any instrument (options, futures, spot).
Your role: Analyze current market conditions AND predict future scenarios to generate high-probability trading rules as JSON.

IMPORTANT: Generate TWO types of rules:
1. CURRENT rules - for immediate trading opportunities based on current conditions
2. FUTURE/PREPARATORY rules - for potential scenarios that might happen (predictive strategies)

Generate rules based on available data:
- Options chain data (OI, premiums, strikes) - if available
- Futures data (price, funding rate, open interest) - if available
- Recent price action (OHLC)
- Technical indicators (RSI, support/resistance)
- Market momentum
- FUTURE SCENARIOS (what-if analysis)

Return ONLY valid JSON matching this schema:
{
  "strategy_id": "unique-strategy-id",
  "valid_until": "ISO timestamp",
  "rules": [
    {
      "rule_id": "unique-rule-id",
      "name": "Rule name",
      "scenario_type": "CURRENT" or "FUTURE",  # NEW: Distinguish current vs predictive rules
      "direction": "BUY" or "SELL",
      "instrument": "Instrument symbol (e.g., BTCUSDT, BANKNIFTY 27JAN26 60200 CE)",
      "conditions": [
        {"type": "price_above", "value": 90200},
        {"type": "oi_spike", "min_pct": 15, "window_min": 2},  # For options
        {"type": "funding_rate_below", "value": -0.01},  # For crypto futures
        {"type": "funding_rate_above", "value": 0.02},  # For crypto futures (future scenario)
        {"type": "price_breaks_resistance", "value": 91000},  # Future scenario
        {"type": "price_breaks_support", "value": 89000},  # Future scenario
        {"type": "premium_acceleration", "min_pct": 5, "window_min": 1},  # For options
        {"type": "rsi_5_above", "value": 55},
        {"type": "volume_spike", "min_pct": 20, "window_min": 5}
      ],
      "position_size": {"risk_pct": 0.5},
      "stop_loss": {"price_pct": -2.0},  # For futures/spot
      "target": {"price_pct": 5.0},  # For futures/spot
      "max_trades": 2,
      "scenario_description": "What future scenario this rule prepares for"  # NEW: Explain the scenario
    }
  ]
}

Condition types (use appropriate ones based on instrument):
- price_above/below: Price comparison
- fut_ltp_above/below: Futures LTP comparison (for options)
- oi_spike: OI spike detection (for options)
- premium_acceleration: Premium momentum (for options)
- funding_rate_below/above: Funding rate comparison (for crypto futures)
- open_interest_change: OI change (for futures)
- open_interest_spike: OI spike (for futures - future scenario)
- rsi_5_above/below: RSI(5) comparison
- volume_spike: Volume spike detection
- support_resistance_break: Support/resistance break
- price_breaks_resistance: Price breaks above resistance (future scenario)
- price_breaks_support: Price breaks below support (future scenario)

FUTURE SCENARIOS to consider:
- IF funding rate becomes extremely negative (< -0.02%) → prepare LONG
- IF funding rate spikes positive (> 0.02%) → prepare SHORT
- IF price breaks resistance → prepare momentum LONG
- IF price breaks support → prepare momentum SHORT
- IF OI spikes significantly → prepare breakout trade
- IF volume suddenly increases → prepare directional trade

Focus on high-probability setups with clear entry/exit conditions.
Adapt conditions based on instrument type (options vs futures vs spot).
Generate BOTH current and future/preparatory rules."""
    
    async def initialize(self):
        """Initialize Redis connection and instrument-specific components."""
        # Initialize Redis
        try:
            self.redis_client = redis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Strategy planner Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
        
        # Detect instrument and create appropriate fetcher (generic)
        try:
            self.instrument_profile = self.instrument_detector.detect(
                symbol=settings.instrument_symbol,
                exchange=settings.instrument_exchange,
                data_source=settings.data_source
            )
            
            logger.info(
                f"Detected instrument: {self.instrument_profile.instrument_type} "
                f"({self.instrument_profile.currency}, {self.instrument_profile.region})"
            )
            
            # Create appropriate fetcher
            self.derivatives_fetcher = self.data_source_factory.create_derivatives_fetcher(
                self.instrument_profile
            )
            
            # Initialize fetcher
            await self.derivatives_fetcher.initialize()
            
            logger.info(
                f"Initialized {self.instrument_profile.data_source} fetcher: "
                f"options={self.derivatives_fetcher.supports_options()}, "
                f"futures={self.derivatives_fetcher.supports_futures()}"
            )
            
        except Exception as e:
            logger.error(f"Error initializing instrument-specific components: {e}", exc_info=True)
            self.derivatives_fetcher = None
    
    def process(self, state):
        """
        Process method required by BaseAgent.
        StrategyPlanner doesn't use AgentState, so this is a no-op.
        Use generate_rules() instead.
        """
        return state
    
    async def generate_rules(self) -> Optional[Dict[str, Any]]:
        """
        Generate trading rules using LLM - PREDICTIVE MODE.
        Analyzes current conditions AND potential future scenarios to prepare strategies.
        """
        try:
            # Get market context
            context = await self._get_market_context()
            
            # Build predictive prompt (analyzes future scenarios)
            prompt = self._build_predictive_prompt(context)
            
            # Call LLM
            response_format = {
                "strategy_id": "string",
                "valid_until": "ISO timestamp string",
                "rules": [
                    {
                        "rule_id": "string",
                        "name": "string",
                        "direction": "BUY or SELL",
                        "instrument": "string (options symbol)",
                        "conditions": "array of condition objects",
                        "position_size": {"risk_pct": "float"},
                        "stop_loss": {"premium_pct": "float"},
                        "target": {"premium_pct": "float"},
                        "max_trades": "integer"
                    }
                ]
            }
            
            analysis = await asyncio.to_thread(
                self._call_llm_structured,
                prompt,
                response_format
            )
            
            if not analysis:
                logger.error("LLM returned empty analysis")
                return None
            
            # Validate and format rules
            rules = self._validate_rules(analysis)
            
            if not rules:
                logger.warning("No valid rules generated")
                return None
            
            # Store rules in Redis with TTL
            await self._store_rules(rules)
            
            logger.info(f"Generated {len(rules.get('rules', []))} trading rules")
            return rules
            
        except Exception as e:
            logger.error(f"Error generating rules: {e}", exc_info=True)
            return None
    
    async def _get_market_context(self) -> Dict[str, Any]:
        """Get current market context for rule generation - completely generic."""
        context = {
            "instrument": settings.instrument_symbol,
            "instrument_type": self.instrument_profile.instrument_type if self.instrument_profile else "UNKNOWN",
            "currency": self.instrument_profile.currency if self.instrument_profile else "USD",
            "region": self.instrument_profile.region if self.instrument_profile else "GLOBAL",
            "current_price": None,
            "ohlc_data": [],
            "indicators": {}
        }
        
        try:
            # Get current price (generic)
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            context["current_price"] = self.market_memory.get_current_price(instrument_key)
            
            # Get recent OHLC (generic)
            ohlc_5min = self.market_memory.get_recent_ohlc(instrument_key, "5min", 20)
            context["ohlc_data"] = ohlc_5min[-10:] if ohlc_5min else []  # Last 10 candles
            
            # Get derivatives data based on what's available (generic)
            if self.derivatives_fetcher:
                if self.derivatives_fetcher.supports_options():
                    try:
                        context["options_chain"] = await self.derivatives_fetcher.fetch_options_chain()
                    except Exception as e:
                        logger.warning(f"Options chain fetch failed: {e}")
                        context["options_chain"] = {}
                
                if self.derivatives_fetcher.supports_futures():
                    try:
                        futures_data = await self.derivatives_fetcher.fetch_futures()
                        context["futures"] = futures_data
                        
                        # Use futures price if available
                        if futures_data.get("futures_price"):
                            context["current_price"] = futures_data["futures_price"]
                        
                        # Store futures data in Redis for dashboard to read
                        if futures_data and (
                            futures_data.get("futures_price", 0) > 0 or
                            futures_data.get("funding_rate") is not None or
                            futures_data.get("open_interest", 0) > 0
                        ):
                            self.market_memory.store_futures_data(instrument_key, futures_data)
                            logger.debug(f"Stored futures data in Redis: price={futures_data.get('futures_price')}, funding={futures_data.get('funding_rate')}")
                    except Exception as e:
                        logger.warning(f"Futures fetch failed: {e}")
                        context["futures"] = {}
            
            # Get technical indicators (generic)
            if ohlc_5min and len(ohlc_5min) >= 5:
                context["indicators"] = self._calculate_indicators(ohlc_5min)
            
        except Exception as e:
            logger.error(f"Error getting market context: {e}", exc_info=True)
        
        return context
    
    # Removed _fetch_options_chain - now handled by derivatives_fetcher
    
    def _calculate_indicators(self, ohlc_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate technical indicators from OHLC data."""
        try:
            import pandas as pd
            import pandas_ta as ta
            
            df = pd.DataFrame(ohlc_data)
            if df.empty or len(df) < 5:
                return {}
            
            # Ensure numeric columns
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=["close"])
            
            if len(df) < 5:
                return {}
            
            indicators = {}
            
            # RSI(5)
            rsi = ta.rsi(df["close"], length=5)
            if not rsi.empty and pd.notna(rsi.iloc[-1]):
                indicators["rsi5"] = float(rsi.iloc[-1])
            
            # Support/Resistance
            indicators["support"] = float(df["low"].tail(10).min())
            indicators["resistance"] = float(df["high"].tail(10).max())
            
            # Current price
            indicators["current_price"] = float(df["close"].iloc[-1])
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for LLM - generic for any instrument type."""
        instrument_type = context.get('instrument_type', 'UNKNOWN')
        currency = context.get('currency', 'USD')
        
        prompt = f"""Current Market Context:

Instrument: {context.get('instrument', 'N/A')}
Type: {instrument_type}
Currency: {currency}
Region: {context.get('region', 'N/A')}
Current Price: {context.get('current_price', 'N/A')} {currency}

Recent OHLC Data (5-min candles): {len(context.get('ohlc_data', []))} candles
"""
        
        # Add technical indicators
        if context.get("indicators"):
            indicators = context["indicators"]
            prompt += f"""
Technical Indicators:
- RSI(5): {indicators.get('rsi5', 'N/A')}
- Support: {indicators.get('support', 'N/A')} {currency}
- Resistance: {indicators.get('resistance', 'N/A')} {currency}
"""
        
        # Add options chain data (if available)
        if context.get("options_chain") and context["options_chain"].get("strikes"):
            options_chain = context["options_chain"]
            prompt += f"""
Options Chain:
- Underlying Price: {options_chain.get('underlying_price', options_chain.get('futures_price', 'N/A'))} {currency}
- Strikes Available: {len(options_chain.get('strikes', {}))}
- Expiry: {options_chain.get('expiry', 'N/A')}
"""
        
        # Add futures data (if available - for crypto)
        if context.get("futures"):
            futures = context["futures"]
            prompt += f"""
Futures Data:
- Futures Price: {futures.get('futures_price', 'N/A')} {currency}
- Volume (24h): {futures.get('volume', 'N/A')}
"""
            
            if futures.get('funding_rate') is not None:
                funding_rate = futures['funding_rate']
                prompt += f"- Funding Rate: {funding_rate * 100:.4f}%\n"
            
            if futures.get('open_interest'):
                prompt += f"- Open Interest: {futures.get('open_interest', 'N/A')}\n"
        
        # Generate rules based on instrument type
        if instrument_type in ["OPTIONS", "INDEX"]:
            prompt += """
Generate 2-3 high-probability options trading rules based on this data.
Focus on:
1. OI spikes indicating strong directional moves
2. Premium momentum (acceleration)
3. Support/resistance breaks
4. RSI momentum signals
"""
        elif instrument_type.startswith("CRYPTO"):
            prompt += """
Generate 2-3 high-probability futures trading rules based on this data.
Focus on:
1. Funding rate reversals (negative funding = bullish signal)
2. Futures basis (premium/discount to spot)
3. Open interest changes
4. Price momentum and volume
5. Support/resistance breaks
"""
        else:
            prompt += """
Generate 2-3 high-probability trading rules based on this data.
Focus on:
1. Price momentum
2. Volume analysis
3. Support/resistance breaks
4. Technical indicator signals
"""
        
        prompt += "\nReturn ONLY valid JSON matching the schema provided in system prompt."
        
        return prompt
    
    def _build_predictive_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build PREDICTIVE prompt - analyzes future scenarios and prepares strategies.
        This is the enhanced version that thinks ahead.
        """
        instrument_type = context.get('instrument_type', 'UNKNOWN')
        currency = context.get('currency', 'USD')
        
        prompt = f"""Current Market Context:

Instrument: {context.get('instrument', 'N/A')}
Type: {instrument_type}
Currency: {currency}
Region: {context.get('region', 'N/A')}
Current Price: {context.get('current_price', 'N/A')} {currency}

Recent OHLC Data (5-min candles): {len(context.get('ohlc_data', []))} candles
"""
        
        # Add technical indicators
        if context.get("indicators"):
            indicators = context["indicators"]
            prompt += f"""
Technical Indicators:
- RSI(5): {indicators.get('rsi5', 'N/A')}
- Support: {indicators.get('support', 'N/A')} {currency}
- Resistance: {indicators.get('resistance', 'N/A')} {currency}
"""
        
        # Add futures data (if available - for crypto)
        if context.get("futures"):
            futures = context["futures"]
            prompt += f"""
Futures Data:
- Futures Price: {futures.get('futures_price', 'N/A')} {currency}
- Volume (24h): {futures.get('volume', 'N/A')}
"""
            
            if futures.get('funding_rate') is not None:
                funding_rate = futures['funding_rate']
                prompt += f"- Funding Rate: {funding_rate * 100:.4f}%\n"
                
                # Add predictive analysis for funding rate
                if funding_rate < -0.01:
                    prompt += "  [SCENARIO] Negative funding rate suggests potential bullish reversal\n"
                elif funding_rate > 0.01:
                    prompt += "  [SCENARIO] High positive funding suggests potential bearish reversal\n"
            
            if futures.get('open_interest'):
                prompt += f"- Open Interest: {futures.get('open_interest', 'N/A')}\n"
        
        # Add options chain data (if available)
        if context.get("options_chain") and context["options_chain"].get("strikes"):
            options_chain = context["options_chain"]
            prompt += f"""
Options Chain:
- Underlying Price: {options_chain.get('underlying_price', options_chain.get('futures_price', 'N/A'))} {currency}
- Strikes Available: {len(options_chain.get('strikes', {}))}
- Expiry: {options_chain.get('expiry', 'N/A')}
"""
        
        # PREDICTIVE ANALYSIS SECTION - Key addition!
        prompt += """
=== PREDICTIVE SCENARIO ANALYSIS ===

Analyze potential FUTURE scenarios based on current data and generate PREPARATORY strategies:

1. **IF funding rate becomes extremely negative (< -0.02%)**:
   - What strategy should we prepare?
   - What conditions would trigger entry?
   - What's the risk/reward?

2. **IF price breaks above resistance**:
   - What's the expected momentum?
   - What's the target?
   - What's the stop loss?

3. **IF price breaks below support**:
   - What's the expected downside?
   - What's the target?
   - What's the stop loss?

4. **IF open interest spikes significantly**:
   - What does it indicate?
   - What strategy should we prepare?

5. **IF volume suddenly increases**:
   - What's the likely direction?
   - What strategy should we prepare?

6. **IF funding rate reverses (from positive to negative or vice versa)**:
   - What's the trading opportunity?
   - What's the strategy?

Generate rules that:
- Are READY for future scenarios (not just current conditions)
- Include "what-if" conditions that prepare for potential moves
- Have clear triggers for when scenarios materialize
- Include risk management for each scenario
"""
        
        # Generate rules based on instrument type
        if instrument_type in ["OPTIONS", "INDEX"]:
            prompt += """
Generate 3-5 high-probability options trading rules:
- 2-3 for CURRENT conditions
- 2-3 PREPARATORY rules for FUTURE scenarios (what-if conditions)
"""
        elif instrument_type.startswith("CRYPTO"):
            prompt += """
Generate 3-5 high-probability futures trading rules:
- 2-3 for CURRENT conditions (funding rate, momentum, etc.)
- 2-3 PREPARATORY rules for FUTURE scenarios:
  * IF funding rate becomes extremely negative → prepare LONG
  * IF funding rate spikes positive → prepare SHORT
  * IF price breaks key level → prepare momentum trade
  * IF volume/OI spikes → prepare breakout trade
"""
        else:
            prompt += """
Generate 3-5 high-probability trading rules:
- 2-3 for CURRENT conditions
- 2-3 PREPARATORY rules for FUTURE scenarios
"""
        
        prompt += "\nReturn ONLY valid JSON matching the schema provided in system prompt."
        prompt += "\nIMPORTANT: Include rules with 'scenario_type': 'CURRENT' or 'FUTURE' to distinguish them."
        
        return prompt
    
    def _validate_rules(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and format generated rules."""
        try:
            if not isinstance(analysis, dict):
                return None
            
            strategy_id = analysis.get("strategy_id", f"strategy_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
            valid_until = analysis.get("valid_until")
            
            # Set default expiry (5 minutes from now)
            if not valid_until:
                valid_until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            
            rules = analysis.get("rules", [])
            if not isinstance(rules, list):
                return None
            
            # Validate each rule
            valid_rules = []
            for rule in rules:
                if self._validate_rule(rule):
                    valid_rules.append(rule)
            
            if not valid_rules:
                return None
            
            return {
                "strategy_id": strategy_id,
                "valid_until": valid_until,
                "rules": valid_rules
            }
            
        except Exception as e:
            logger.error(f"Error validating rules: {e}")
            return None
    
    def _validate_rule(self, rule: Dict[str, Any]) -> bool:
        """Validate a single rule."""
        required_fields = ["name", "direction", "instrument", "conditions"]
        for field in required_fields:
            if field not in rule:
                logger.warning(f"Rule missing required field: {field}")
                return False
        
        if rule["direction"] not in ["BUY", "SELL"]:
            logger.warning(f"Invalid direction: {rule['direction']}")
            return False
        
        if not isinstance(rule["conditions"], list) or len(rule["conditions"]) == 0:
            logger.warning("Rule must have at least one condition")
            return False
        
        return True
    
    async def _store_rules(self, rules: Dict[str, Any]):
        """Store rules in Redis with TTL."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                logger.error("Redis not available, cannot store rules")
                return
        
        try:
            rules_json = json.dumps(rules)
            
            # Calculate TTL from valid_until
            valid_until_str = rules["valid_until"].replace('Z', '+00:00')
            valid_until = datetime.fromisoformat(valid_until_str)
            # Ensure both are timezone-aware
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            ttl_seconds = int((valid_until - now).total_seconds())
            
            if ttl_seconds > 0:
                await self.redis_client.setex("active_rules", ttl_seconds, rules_json)
                logger.info(f"Stored {len(rules['rules'])} rules in Redis (TTL: {ttl_seconds}s)")
            else:
                logger.warning("Rules already expired, not storing")
                
        except Exception as e:
            logger.error(f"Error storing rules: {e}")


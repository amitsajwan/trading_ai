"""Options chain data fetcher for Zerodha Kite API."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory

logger = logging.getLogger(__name__)


class OptionsChainFetcher:
    """Fetches and tracks options chain data (OI, premiums, volumes)."""
    
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory, instrument_symbol: str = "NIFTY BANK"):
        """Initialize options chain fetcher."""
        self.kite = kite
        self.market_memory = market_memory
        self.instrument_symbol = instrument_symbol
        self.bn_fut_token: Optional[int] = None
        self.options_instruments: Dict[str, int] = {}  # symbol -> token mapping
        self.options_by_strike: Dict[int, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.target_expiry: Optional[date] = None
        self._last_chain: Optional[Dict[str, Any]] = None
        self._last_fetch_ts: Optional[datetime] = None
        
    async def initialize(self):
        """Initialize by fetching instrument tokens."""
        try:
            symbol = (self.instrument_symbol or "").strip()
            if not symbol or symbol.upper() in {"BTC-USD", "BTCUSD", "BTC"}:
                logger.info("Options fetch skipped for non-NFO instrument")
                return
            sanitized_symbol = symbol.replace(" ", "").upper()
            # Map Zerodha naming anomalies / index names
            alias_map = {
                "NIFTYBANK": "BANKNIFTY",
                "BANKNIFTY": "BANKNIFTY",
                "NIFTY50": "NIFTY",
                "NIFTY": "NIFTY",
            }
            tradingsymbol_prefix = alias_map.get(sanitized_symbol, sanitized_symbol)

            nfo_instruments = await asyncio.to_thread(self.kite.instruments, "NFO")

            today = datetime.now().date()
            fut_candidates: List[Dict[str, Any]] = []
            option_candidates: List[Dict[str, Any]] = []

            for inst in nfo_instruments:
                trading_key = (inst.get("tradingsymbol") or "").upper()
                segment = inst.get("segment")
                if tradingsymbol_prefix not in trading_key:
                    continue
                expiry = inst.get("expiry")
                if not expiry or expiry < today:
                    continue
                inst_type = inst.get("instrument_type")
                if segment == "NFO-FUT" and inst_type == "FUT":
                    fut_candidates.append(inst)
                elif segment == "NFO-OPT" and inst_type in {"CE", "PE"}:
                    option_candidates.append(inst)

            if fut_candidates:
                fut_candidates.sort(key=lambda inst: inst.get("expiry"))
                self.bn_fut_token = fut_candidates[0].get("instrument_token")

            if not self.bn_fut_token:
                # Fallback to NSE index token (stable LTP reference)
                try:
                    nse = await asyncio.to_thread(self.kite.instruments, "NSE")
                    wanted_index = "NIFTY BANK" if tradingsymbol_prefix == "BANKNIFTY" else "NIFTY 50"
                    for inst in nse:
                        ts = (inst.get("tradingsymbol") or "").upper()
                        if ts == wanted_index:
                            self.bn_fut_token = inst.get("instrument_token")
                            break
                except Exception:
                    pass
            if not self.bn_fut_token:
                logger.error(f"Underlying token not found for {symbol}")
                return

            if not option_candidates:
                logger.warning(f"No options instruments found for {self.instrument_symbol}")
                return

            expiries = sorted({inst.get("expiry") for inst in option_candidates})
            self.target_expiry = expiries[0] if expiries else None

            for inst in option_candidates:
                if self.target_expiry and inst.get("expiry") != self.target_expiry:
                    continue
                strike_val = inst.get("strike")
                if strike_val is None:
                    continue
                strike = int(round(float(strike_val)))
                option_type = inst.get("instrument_type")  # CE / PE
                tradingsymbol = inst.get("tradingsymbol")
                token = inst.get("instrument_token")
                if not tradingsymbol or not token:
                    continue
                self.options_instruments[tradingsymbol] = token
                self.options_by_strike[strike][option_type] = {
                    "token": token,
                    "tradingsymbol": tradingsymbol
                }
            
            total_pairs = sum(len(opt) for opt in self.options_by_strike.values())
            logger.info(
                "Initialized options chain fetcher for %s: %d strikes (%d total contracts) expiry=%s",
                self.instrument_symbol,
                len(self.options_by_strike),
                total_pairs,
                self.target_expiry,
            )
            
        except Exception as e:
            logger.error(f"Error initializing options chain fetcher: {e}")
    
    async def fetch_options_chain(self, strikes: Optional[List[int]] = None) -> Dict[str, Any]:
        """Fetch current options chain data."""
        try:
            # Throttle fetches to once every 30 seconds to avoid rate limits
            if self._last_chain and self._last_fetch_ts:
                elapsed = (datetime.now() - self._last_fetch_ts).total_seconds()
                if elapsed < 30:
                    return self._last_chain

            if not self.bn_fut_token:
                await self.initialize()
            if not self.bn_fut_token:
                return {"available": False, "reason": "instrument_not_supported"}
            
            if not self.options_by_strike:
                await self.initialize()
            if not self.options_by_strike:
                return {"available": False, "reason": "no_options_mapping"}

            # Get futures quote
            fut_quote = await asyncio.to_thread(
                self.kite.quote,
                [self.bn_fut_token]
            )

            fut_key = str(self.bn_fut_token)
            fut_data = fut_quote.get(fut_key) or fut_quote.get(self.bn_fut_token, {})
            fut_price = fut_data.get("last_price", 0)
            
            # Get options quotes (sample strikes around current price)
            if not strikes:
                # Default: ±5 strikes around current price (rounded to nearest 100)
                base_strike = int(round(fut_price / 100) * 100)
                strikes = [base_strike + i * 100 for i in range(-5, 6)]
            
            # Build options chain data
            options_chain = {
                "futures_price": fut_price,
                "timestamp": datetime.now().isoformat(),
                "strikes": {},
                "available": True
            }
            
            # Get quotes for selected strikes (batch requests to avoid 414 error)
            # Zerodha API limit: max ~50 instruments per quote() call
            option_contracts = []

            for strike in strikes:
                contracts = self.options_by_strike.get(strike)
                if not contracts:
                    continue
                for option_type in ("CE", "PE"):
                    contract = contracts.get(option_type)
                    if not contract:
                        continue
                    option_contracts.append((option_type, strike, contract))
            
            # Batch quotes (max 40 per batch to be safe)
            batch_size = 40
            all_quotes = {}
            
            for i in range(0, len(option_contracts), batch_size):
                batch = option_contracts[i:i + batch_size]
                option_tokens = [contract["token"] for _, _, contract in batch]
                
                if option_tokens:
                    try:
                        batch_quotes = await asyncio.to_thread(self.kite.quote, option_tokens)
                        all_quotes.update(batch_quotes)
                    except Exception as e:
                        logger.warning(f"Error fetching batch {i//batch_size + 1}: {e}")
                        continue
            
            quotes = all_quotes

            if quotes:
                for (option_type, strike, contract) in option_contracts:
                    token = contract["token"]
                    token_key = str(token)
                    quote_data = quotes.get(token_key) or quotes.get(token, {})

                    if strike not in options_chain["strikes"]:
                        options_chain["strikes"][strike] = {}

                    options_chain["strikes"][strike][f"{option_type.lower()}_ltp"] = quote_data.get("last_price", 0)
                    options_chain["strikes"][strike][f"{option_type.lower()}_oi"] = quote_data.get("oi", 0)
                    options_chain["strikes"][strike][f"{option_type.lower()}_volume"] = quote_data.get("volume", 0)

            self._last_chain = options_chain
            self._last_fetch_ts = datetime.now()
            
            return options_chain
            
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return {"available": False, "reason": "fetch_error"}
    
    async def get_oi_changes(self, current_chain: Dict[str, Any], previous_chain: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate OI changes between two chain snapshots."""
        if not previous_chain:
            return {}
        
        oi_changes = {}
        
        try:
            for strike, current_data in current_chain.get("strikes", {}).items():
                prev_data = previous_chain.get("strikes", {}).get(strike, {})
                
                changes = {}
                
                for option_type in ["ce", "pe"]:
                    oi_key = f"{option_type}_oi"
                    current_oi = current_data.get(oi_key, 0)
                    prev_oi = prev_data.get(oi_key, 0)
                    
                    if prev_oi > 0:
                        change_pct = ((current_oi - prev_oi) / prev_oi) * 100
                        changes[f"{option_type}_oi_change_pct"] = change_pct
                    else:
                        changes[f"{option_type}_oi_change_pct"] = 0
                    
                    changes[oi_key] = current_oi
                
                oi_changes[strike] = changes
                
        except Exception as e:
            logger.error(f"Error calculating OI changes: {e}")
        
        return oi_changes


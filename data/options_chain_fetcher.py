"""Options chain data fetcher for Zerodha Kite API."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory

logger = logging.getLogger(__name__)


class OptionsChainFetcher:
    """Fetches and tracks options chain data (OI, premiums, volumes)."""
    
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory):
        """Initialize options chain fetcher."""
        self.kite = kite
        self.market_memory = market_memory
        self.bn_fut_token: Optional[int] = None
        self.options_instruments: Dict[str, int] = {}  # symbol -> token mapping
        
    async def initialize(self):
        """Initialize by fetching instrument tokens."""
        try:
            # Get BankNifty futures token
            instruments = await asyncio.to_thread(self.kite.instruments, "NSE")
            for inst in instruments:
                if inst.get("tradingsymbol") == "NIFTY BANK":
                    self.bn_fut_token = inst["instrument_token"]
                    break
            
            if not self.bn_fut_token:
                logger.error("BankNifty futures token not found")
                return
            
            # Get options instruments (NFO exchange)
            nfo_instruments = await asyncio.to_thread(self.kite.instruments, "NFO")
            
            # Filter for BankNifty options
            for inst in nfo_instruments:
                symbol = inst.get("tradingsymbol", "")
                if "BANKNIFTY" in symbol and ("CE" in symbol or "PE" in symbol):
                    self.options_instruments[symbol] = inst["instrument_token"]
            
            logger.info(f"Initialized options chain fetcher: {len(self.options_instruments)} options instruments")
            
        except Exception as e:
            logger.error(f"Error initializing options chain fetcher: {e}")
    
    async def fetch_options_chain(self, strikes: Optional[List[int]] = None) -> Dict[str, Any]:
        """Fetch current options chain data."""
        try:
            if not self.bn_fut_token:
                await self.initialize()
            
            # Get futures quote
            fut_quote = await asyncio.to_thread(
                self.kite.quote,
                [f"NSE:{self.bn_fut_token}"]
            )
            
            fut_data = fut_quote.get(f"NSE:{self.bn_fut_token}", {})
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
                "strikes": {}
            }
            
            # Get quotes for selected strikes (batch requests to avoid 414 error)
            # Zerodha API limit: max ~50 instruments per quote() call
            option_symbols = []
            
            for strike in strikes:
                # Find CE and PE for this strike
                for symbol, token in self.options_instruments.items():
                    if str(strike) in symbol:
                        if "CE" in symbol:
                            option_symbols.append(("CE", strike, symbol, token))
                        elif "PE" in symbol:
                            option_symbols.append(("PE", strike, symbol, token))
            
            # Batch quotes (max 40 per batch to be safe)
            batch_size = 40
            all_quotes = {}
            
            for i in range(0, len(option_symbols), batch_size):
                batch = option_symbols[i:i + batch_size]
                option_tokens = [f"NFO:{token}" for _, _, _, token in batch]
                
                if option_tokens:
                    try:
                        batch_quotes = await asyncio.to_thread(self.kite.quote, option_tokens)
                        all_quotes.update(batch_quotes)
                    except Exception as e:
                        logger.warning(f"Error fetching batch {i//batch_size + 1}: {e}")
                        continue
            
            quotes = all_quotes
            
            if quotes:
                for (option_type, strike, symbol, token) in option_symbols:
                    token_key = f"NFO:{token}"
                    quote_data = quotes.get(token_key, {})
                    
                    if strike not in options_chain["strikes"]:
                        options_chain["strikes"][strike] = {}
                    
                    options_chain["strikes"][strike][f"{option_type.lower()}_ltp"] = quote_data.get("last_price", 0)
                    options_chain["strikes"][strike][f"{option_type.lower()}_oi"] = quote_data.get("oi", 0)
                    options_chain["strikes"][strike][f"{option_type.lower()}_volume"] = quote_data.get("volume", 0)
            
            return options_chain
            
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return {}
    
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


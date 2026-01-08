"""Integration test for options chain with fake Kite."""
import pytest
from datetime import date

from market_data.api import build_options_client


class FakeKite:
    """Minimal fake Kite for testing."""
    
    def instruments(self, exchange):
        """Return fake NFO instruments."""
        if exchange == "NFO":
            return [
                {
                    "tradingsymbol": "BANKNIFTY24JAN45000CE",
                    "segment": "NFO-OPT",
                    "instrument_type": "CE",
                    "strike": 45000,
                    "expiry": date(2024, 1, 25),
                    "instrument_token": 1001,
                },
                {
                    "tradingsymbol": "BANKNIFTY24JAN45000PE",
                    "segment": "NFO-OPT",
                    "instrument_type": "PE",
                    "strike": 45000,
                    "expiry": date(2024, 1, 25),
                    "instrument_token": 1002,
                },
                {
                    "tradingsymbol": "BANKNIFTY24JANFUT",
                    "segment": "NFO-FUT",
                    "instrument_type": "FUT",
                    "expiry": date(2024, 1, 25),
                    "instrument_token": 2001,
                },
            ]
        elif exchange == "NSE":
            return [
                {
                    "tradingsymbol": "NIFTY BANK",
                    "instrument_token": 9000,
                }
            ]
        return []
    
    def quote(self, tokens):
        """Return fake quotes."""
        quotes = {}
        for token in tokens:
            if token == 2001:  # Futures
                quotes[str(token)] = {"last_price": 45050.0}
            elif token in {1001, 1002}:  # Options
                quotes[str(token)] = {
                    "last_price": 150.0 if token == 1001 else 120.0,
                    "oi": 10000,
                    "volume": 500,
                }
        return quotes


class FakeOptionsChainFetcher:
    """Fake OptionsChainFetcher matching legacy interface."""
    
    def __init__(self, kite, market_memory, instrument_symbol):
        self.kite = kite
        self.market_memory = market_memory
        self.instrument_symbol = instrument_symbol
        self.bn_fut_token = None
        self.options_by_strike = {}
        self.target_expiry = None
    
    async def initialize(self):
        """Initialize fake fetcher."""
        nfo = self.kite.instruments("NFO")
        self.target_expiry = date(2024, 1, 25)
        
        for inst in nfo:
            if inst.get("instrument_type") == "FUT":
                self.bn_fut_token = inst["instrument_token"]
            elif inst.get("instrument_type") in {"CE", "PE"}:
                strike = inst["strike"]
                option_type = inst["instrument_type"]
                if strike not in self.options_by_strike:
                    self.options_by_strike[strike] = {}
                self.options_by_strike[strike][option_type] = {
                    "token": inst["instrument_token"],
                    "tradingsymbol": inst["tradingsymbol"],
                }
    
    async def fetch_options_chain(self, strikes=None):
        """Fetch fake options chain."""
        if not self.bn_fut_token:
            return {"available": False, "reason": "not_initialized"}
        
        fut_quote = self.kite.quote([self.bn_fut_token])
        fut_price = fut_quote[str(self.bn_fut_token)]["last_price"]
        
        chain = {
            "futures_price": fut_price,
            "strikes": {},
            "available": True,
        }
        
        target_strikes = strikes or [45000]
        for strike in target_strikes:
            if strike in self.options_by_strike:
                chain["strikes"][strike] = {}
                for opt_type in ["CE", "PE"]:
                    if opt_type in self.options_by_strike[strike]:
                        token = self.options_by_strike[strike][opt_type]["token"]
                        quote = self.kite.quote([token])[str(token)]
                        chain["strikes"][strike][f"{opt_type.lower()}_ltp"] = quote["last_price"]
                        chain["strikes"][strike][f"{opt_type.lower()}_oi"] = quote["oi"]
        
        return chain


@pytest.mark.integration
@pytest.mark.asyncio
async def test_options_chain_with_fake_kite():
    """Integration test: options chain returns structured data with fake Kite."""
    kite = FakeKite()
    fetcher = FakeOptionsChainFetcher(kite, None, "NIFTY BANK")
    
    client = build_options_client(kite, fetcher)
    await client.initialize()
    
    chain = await client.fetch_options_chain(strikes=[45000])
    
    assert chain["available"] is True
    assert chain["futures_price"] == 45050.0
    assert 45000 in chain["strikes"]
    assert chain["strikes"][45000]["ce_ltp"] == 150.0
    assert chain["strikes"][45000]["pe_ltp"] == 120.0
    assert chain["strikes"][45000]["ce_oi"] == 10000


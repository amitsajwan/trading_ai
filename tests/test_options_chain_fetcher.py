"""Test suite for options chain fetcher."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date, timedelta
from data.options_chain_fetcher import OptionsChainFetcher
from data.market_memory import MarketMemory


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance."""
    kite = Mock()
    kite.instruments = Mock()
    kite.quote = Mock()
    return kite


@pytest.fixture
def mock_market_memory():
    """Mock MarketMemory instance."""
    return Mock(spec=MarketMemory)


@pytest.fixture
def sample_nfo_instruments():
    """Sample NFO instruments data."""
    today = date.today()
    expiry1 = today + timedelta(days=3)
    expiry2 = today + timedelta(days=10)
    
    return [
        # BankNifty futures
        {
            "instrument_token": 123456,
            "tradingsymbol": "BANKNIFTY26JAN24FUT",
            "name": "BANKNIFTY",
            "instrument_type": "FUT",
            "expiry": expiry1,
        },
        {
            "instrument_token": 123457,
            "tradingsymbol": "BANKNIFTY26FEB24FUT",
            "name": "BANKNIFTY",
            "instrument_type": "FUT",
            "expiry": expiry2,
        },
        # BankNifty options (nearest expiry)
        {
            "instrument_token": 200001,
            "tradingsymbol": "BANKNIFTY26JAN24C60000",
            "name": "BANKNIFTY",
            "instrument_type": "CE",
            "strike": 60000.0,
            "expiry": expiry1,
        },
        {
            "instrument_token": 200002,
            "tradingsymbol": "BANKNIFTY26JAN24P60000",
            "name": "BANKNIFTY",
            "instrument_type": "PE",
            "strike": 60000.0,
            "expiry": expiry1,
        },
        {
            "instrument_token": 200003,
            "tradingsymbol": "BANKNIFTY26JAN24C60100",
            "name": "BANKNIFTY",
            "instrument_type": "CE",
            "strike": 60100.0,
            "expiry": expiry1,
        },
        {
            "instrument_token": 200004,
            "tradingsymbol": "BANKNIFTY26JAN24P60100",
            "name": "BANKNIFTY",
            "instrument_type": "PE",
            "strike": 60100.0,
            "expiry": expiry1,
        },
        # Far expiry (should be ignored)
        {
            "instrument_token": 200005,
            "tradingsymbol": "BANKNIFTY26FEB24C60000",
            "name": "BANKNIFTY",
            "instrument_type": "CE",
            "strike": 60000.0,
            "expiry": expiry2,
        },
    ]


@pytest.mark.asyncio
async def test_initialize_banknifty(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test initialization with BANKNIFTY symbol."""
    mock_kite.instruments.return_value = sample_nfo_instruments
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "NIFTY BANK")
    await fetcher.initialize()
    
    # Should find futures token
    assert fetcher.bn_fut_token == 123456
    
    # Should map only nearest expiry options
    assert len(fetcher.options_by_strike) == 2
    assert 60000 in fetcher.options_by_strike
    assert 60100 in fetcher.options_by_strike
    
    # Check CE/PE mapping
    assert "CE" in fetcher.options_by_strike[60000]
    assert "PE" in fetcher.options_by_strike[60000]
    assert fetcher.options_by_strike[60000]["CE"]["token"] == 200001
    assert fetcher.options_by_strike[60000]["PE"]["token"] == 200002


@pytest.mark.asyncio
async def test_initialize_unsupported_symbol(mock_kite, mock_market_memory):
    """Test initialization with unsupported symbol (e.g., BTC)."""
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BTC-USD")
    await fetcher.initialize()
    
    # Should skip initialization
    assert fetcher.bn_fut_token is None
    assert len(fetcher.options_by_strike) == 0


@pytest.mark.asyncio
async def test_initialize_no_options_found(mock_kite, mock_market_memory):
    """Test initialization when no options are found."""
    mock_kite.instruments.return_value = []
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    await fetcher.initialize()
    
    assert fetcher.bn_fut_token is None
    assert len(fetcher.options_by_strike) == 0


@pytest.mark.asyncio
async def test_fetch_options_chain_success(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test successful options chain fetch."""
    mock_kite.instruments.return_value = sample_nfo_instruments
    
    # Mock quote responses
    mock_kite.quote.side_effect = [
        # Futures quote
        {
            "123456": {"last_price": 60215.45}
        },
        # Options quotes
        {
            "200001": {"last_price": 834.95, "oi": 1185780, "volume": 1310490},
            "200002": {"last_price": 426.00, "oi": 1280910, "volume": 1831200},
            "200003": {"last_price": 772.30, "oi": 139800, "volume": 623580},
            "200004": {"last_price": 464.00, "oi": 197520, "volume": 614610},
        }
    ]
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    await fetcher.initialize()
    
    chain = await fetcher.fetch_options_chain(strikes=[60000, 60100])
    
    assert chain["available"] is True
    assert chain["futures_price"] == 60215.45
    assert 60000 in chain["strikes"]
    assert 60100 in chain["strikes"]
    
    # Check CE data at 60000
    assert chain["strikes"][60000]["ce_ltp"] == 834.95
    assert chain["strikes"][60000]["ce_oi"] == 1185780
    assert chain["strikes"][60000]["ce_volume"] == 1310490
    
    # Check PE data at 60000
    assert chain["strikes"][60000]["pe_ltp"] == 426.00
    assert chain["strikes"][60000]["pe_oi"] == 1280910


@pytest.mark.asyncio
async def test_fetch_options_chain_caching(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test that options chain is cached for 30 seconds."""
    mock_kite.instruments.return_value = sample_nfo_instruments
    mock_kite.quote.side_effect = [
        {"123456": {"last_price": 60215.45}},
        {"200001": {"last_price": 834.95, "oi": 1185780, "volume": 1310490}},
    ]
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    await fetcher.initialize()
    
    # First fetch
    chain1 = await fetcher.fetch_options_chain(strikes=[60000])
    
    # Second fetch within 30 seconds - should return cached
    chain2 = await fetcher.fetch_options_chain(strikes=[60000])
    
    # Should be same instance
    assert chain1 is chain2
    
    # quote should only be called twice (once for futures, once for options)
    assert mock_kite.quote.call_count == 2


@pytest.mark.asyncio
async def test_fetch_options_chain_without_init(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test fetch when not initialized."""
    mock_kite.instruments.return_value = sample_nfo_instruments
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    # Don't call initialize
    
    # Mock for auto-init
    mock_kite.quote.side_effect = [
        {"123456": {"last_price": 60215.45}},
        {"200001": {"last_price": 834.95, "oi": 1185780, "volume": 1310490}},
    ]
    
    chain = await fetcher.fetch_options_chain(strikes=[60000])
    
    # Should auto-initialize and fetch
    assert chain["available"] is True


@pytest.mark.asyncio
async def test_fetch_options_chain_unsupported_instrument(mock_kite, mock_market_memory):
    """Test fetch for unsupported instrument."""
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BTC-USD")
    
    chain = await fetcher.fetch_options_chain()
    
    assert chain["available"] is False
    assert chain["reason"] == "instrument_not_supported"


@pytest.mark.asyncio
async def test_get_oi_changes(mock_kite, mock_market_memory):
    """Test OI change calculation."""
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    
    previous_chain = {
        "strikes": {
            60000: {
                "ce_oi": 1000000,
                "pe_oi": 900000,
            }
        }
    }
    
    current_chain = {
        "strikes": {
            60000: {
                "ce_oi": 1100000,  # +10%
                "pe_oi": 855000,   # -5%
            }
        }
    }
    
    changes = await fetcher.get_oi_changes(current_chain, previous_chain)
    
    assert 60000 in changes
    assert abs(changes[60000]["ce_oi_change_pct"] - 10.0) < 0.01
    assert abs(changes[60000]["pe_oi_change_pct"] - (-5.0)) < 0.01


@pytest.mark.asyncio
async def test_fetch_options_chain_batch_handling(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test that large strike lists are batched correctly."""
    # Create many options
    today = date.today()
    expiry = today + timedelta(days=3)
    
    extended_instruments = sample_nfo_instruments.copy()
    
    # Add 50 strikes worth of options
    for i in range(50):
        strike = 60000 + (i * 100)
        extended_instruments.extend([
            {
                "instrument_token": 300000 + (i * 2),
                "tradingsymbol": f"BANKNIFTY26JAN24C{strike}",
                "name": "BANKNIFTY",
                "instrument_type": "CE",
                "strike": float(strike),
                "expiry": expiry,
            },
            {
                "instrument_token": 300000 + (i * 2) + 1,
                "tradingsymbol": f"BANKNIFTY26JAN24P{strike}",
                "name": "BANKNIFTY",
                "instrument_type": "PE",
                "strike": float(strike),
                "expiry": expiry,
            },
        ])
    
    mock_kite.instruments.return_value = extended_instruments
    
    # Mock quote to track batch calls
    quote_calls = []
    def track_quote(tokens):
        quote_calls.append(len(tokens))
        return {str(t): {"last_price": 100, "oi": 1000, "volume": 100} for t in tokens}
    
    mock_kite.quote.side_effect = track_quote
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    await fetcher.initialize()
    
    # Request all strikes
    all_strikes = [60000 + (i * 100) for i in range(50)]
    chain = await fetcher.fetch_options_chain(strikes=all_strikes)
    
    # First call should be for futures (1 token)
    assert quote_calls[0] == 1
    
    # Subsequent calls should be batched (max 40 per batch)
    # 50 strikes * 2 (CE+PE) = 100 options
    # Should be split into 3 batches: 40, 40, 20
    assert all(count <= 40 for count in quote_calls[1:])


@pytest.mark.asyncio
async def test_fetch_options_chain_error_handling(mock_kite, mock_market_memory, sample_nfo_instruments):
    """Test error handling during fetch."""
    mock_kite.instruments.return_value = sample_nfo_instruments
    
    # Mock quote to raise exception
    mock_kite.quote.side_effect = Exception("API error")
    
    fetcher = OptionsChainFetcher(mock_kite, mock_market_memory, "BANKNIFTY")
    await fetcher.initialize()
    
    chain = await fetcher.fetch_options_chain(strikes=[60000])
    
    assert chain["available"] is False
    assert chain["reason"] == "fetch_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

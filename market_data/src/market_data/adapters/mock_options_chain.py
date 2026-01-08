"""Mock Options Chain Adapter using cached instrument data and last prices.

This adapter works for historical data and after-hours trading by using:
- Real NFO instruments from Kite
- Last traded prices (close prices) instead of live quotes
- Historical data for backtesting
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
import pandas as pd

from ..contracts import OptionsData

logger = logging.getLogger(__name__)


class MockOptionsChainAdapter(OptionsData):
    """Options chain adapter using Zerodha API.
    
    Uses real Zerodha API (kite.ltp() or kite.quote()) for live data.
    The "Mock" name is historical - it actually uses real Zerodha APIs.
    """

    def __init__(self, kite=None, instrument_symbol: str = "BANKNIFTY", use_live_quotes: bool = False):
        """Initialize options chain adapter.

        Args:
            kite: KiteConnect instance (optional, for fetching instruments)
            instrument_symbol: Underlying symbol (e.g., "BANKNIFTY", "NIFTY")
            use_live_quotes: If True, use kite.quote() for real-time bid/ask. If False, use kite.ltp() for last traded price.
        """
        self.kite = kite
        self.instrument_symbol = instrument_symbol.upper()
        self.use_live_quotes = use_live_quotes
        self._instruments_df: Optional[pd.DataFrame] = None
        self._options_df: Optional[pd.DataFrame] = None
        self._last_prices: Dict[str, Dict] = {}

    async def initialize(self) -> None:
        """Initialize by downloading and caching NFO instruments."""
        try:
            logger.info(f"Initializing MockOptionsChainAdapter for {self.instrument_symbol}")

            if self.kite is None:
                logger.warning("No kite client provided, using empty instruments")
                return

            # Download all NFO instruments
            logger.info("Downloading NFO instruments...")
            instruments = self.kite.instruments("NFO")

            # Convert to DataFrame for easier filtering
            self._instruments_df = pd.DataFrame(instruments)
            logger.info(f"Loaded {len(self._instruments_df)} NFO instruments")

            # Filter for our underlying options
            self._options_df = self._instruments_df[
                (self._instruments_df["name"] == self.instrument_symbol) &
                (self._instruments_df["instrument_type"].isin(["CE", "PE"]))
            ].copy()

            logger.info(f"Filtered {len(self._options_df)} {self.instrument_symbol} options")

            if len(self._options_df) > 0:
                # Sort by expiry and strike for better organization
                self._options_df = self._options_df.sort_values(['expiry', 'strike'])

                # Get unique expiries
                expiries = sorted(self._options_df['expiry'].unique())
                logger.info(f"Available expiries: {expiries[:3]}...")  # Show first 3

                # Get strike range
                strikes = sorted(self._options_df['strike'].unique())
                logger.info(f"Strike range: {strikes[0]} - {strikes[-1]} (interval: {strikes[1] - strikes[0] if len(strikes) > 1 else 'N/A'})")

        except Exception as e:
            logger.error(f"Failed to initialize mock options chain: {e}")
            raise

    async def fetch_options_chain(self, instrument: Optional[str] = None, expiry: Optional[str] = None,
                                 strikes: Optional[List[int]] = None) -> Dict[str, Any]:
        """Fetch options chain using cached instrument data and last prices."""

        try:
            target_instrument = instrument or self.instrument_symbol

            if self._options_df is None or len(self._options_df) == 0:
                logger.warning("No options data available, initializing...")
                if self.kite:
                    await self.initialize()
                else:
                    return self._create_empty_response("No kite client available for initialization")

            # Filter options for target instrument
            options_df = self._options_df
            if instrument and instrument.upper() != self.instrument_symbol:
                # If different instrument requested, filter from main instruments
                if self._instruments_df is not None:
                    options_df = self._instruments_df[
                        (self._instruments_df["name"] == instrument.upper()) &
                        (self._instruments_df["instrument_type"].isin(["CE", "PE"]))
                    ]
                else:
                    return self._create_empty_response(f"No data for {instrument}")

            if len(options_df) == 0:
                return self._create_empty_response(f"No options found for {target_instrument}")

            # Select expiry
            available_expiries = sorted(options_df['expiry'].unique())
            selected_expiry = expiry or available_expiries[0] if available_expiries else None

            if not selected_expiry:
                return self._create_empty_response("No expiry dates available")

            # Filter by expiry
            expiry_options = options_df[options_df['expiry'] == selected_expiry]

            if len(expiry_options) == 0:
                return self._create_empty_response(f"No options for expiry {selected_expiry}")

            # Filter by strikes if specified
            if strikes:
                expiry_options = expiry_options[expiry_options['strike'].isin(strikes)]

            # Get last prices for these options
            price_data = await self._get_last_prices(expiry_options)

            # Organize by strikes
            strikes_data = self._organize_by_strikes(expiry_options, price_data)

            return {
                "available": True,
                "instrument": target_instrument,
                "expiry": selected_expiry.isoformat() if hasattr(selected_expiry, 'isoformat') else str(selected_expiry),
                "strikes": strikes_data,
                "available_expiries": [exp.isoformat() if hasattr(exp, 'isoformat') else str(exp) for exp in available_expiries],
                "total_contracts": len(expiry_options),
                "source": "mock_cache"
            }

        except Exception as e:
            logger.error(f"Error fetching mock options chain: {e}")
            return self._create_empty_response(f"Error: {str(e)}")

    async def _get_last_prices(self, options_df: pd.DataFrame) -> Dict[str, Dict]:
        """Get prices for option contracts using real Zerodha API."""

        price_data = {}

        if self.kite is None:
            if self.use_live_quotes:
                logger.error("No kite client available for live quotes - cannot fetch real-time options data")
                raise ValueError("Kite client required for live options data")
            else:
                logger.warning("No kite client for price data - cannot fetch options prices")
                raise ValueError("Kite client required for options data")

        try:
            # Use live quotes (real-time bid/ask) for live trading, or LTP (last traded price) for historical/after-hours
            tokens = [f"NFO:{row['tradingsymbol']}" for _, row in options_df.iterrows()]

            # Process in batches to avoid API limits
            batch_size = 50
            all_price_data = {}

            for i in range(0, len(tokens), batch_size):
                batch = tokens[i:i + batch_size]
                try:
                    if self.use_live_quotes:
                        # Use quote() for real-time bid/ask prices (live trading)
                        batch_quotes = self.kite.quote(batch)
                        all_price_data.update(batch_quotes)
                        logger.debug(f"Fetched live quotes for {len(batch)} contracts")
                    else:
                        # Use ltp() for last traded price (works after hours, historical)
                        batch_ltp = self.kite.ltp(batch)
                        all_price_data.update(batch_ltp)
                        logger.debug(f"Fetched LTP for {len(batch)} contracts")
                except Exception as e:
                    logger.warning(f"Failed to get price data batch: {e}")

            # Convert to our format
            for _, option in options_df.iterrows():
                token = str(option['instrument_token'])
                kite_token = f"NFO:{option['tradingsymbol']}"

                if kite_token in all_price_data:
                    kite_data = all_price_data[kite_token]
                    # Handle both quote() and ltp() response formats
                    if self.use_live_quotes:
                        # quote() returns Quote object with depth, ohlc, etc.
                        if hasattr(kite_data, 'to_dict'):
                            kite_data = kite_data.to_dict()
                        price_data[token] = {
                            'last_price': kite_data.get('last_price', kite_data.get('ohlc', {}).get('close', 0)),
                            'bid': kite_data.get('depth', {}).get('buy', [{}])[0].get('price', 0) if kite_data.get('depth', {}).get('buy') else 0,
                            'ask': kite_data.get('depth', {}).get('sell', [{}])[0].get('price', 0) if kite_data.get('depth', {}).get('sell') else 0,
                            'volume': kite_data.get('volume', 0),
                            'oi': kite_data.get('oi', 0),
                            'timestamp': kite_data.get('timestamp', datetime.now().isoformat())
                        }
                    else:
                        # ltp() returns simple dict with last_price
                        price_data[token] = {
                            'last_price': kite_data.get('last_price', 0),
                            'volume': kite_data.get('volume', 0),
                            'oi': kite_data.get('oi', 0),
                            'timestamp': kite_data.get('timestamp', datetime.now().isoformat())
                        }
                else:
                    # No data available for this contract - skip it or log warning
                    if self.use_live_quotes:
                        logger.warning(f"No live quote data available for {kite_token} - skipping")
                    else:
                        logger.warning(f"No LTP data available for {kite_token} - skipping")
                    # Don't add dummy data - skip this contract
                    continue

            logger.info(f"Retrieved last prices for {len(price_data)} option contracts")
            return price_data

        except Exception as e:
            logger.error(f"Failed to get prices from Zerodha API: {e}")
            if self.use_live_quotes:
                raise ValueError(f"Failed to fetch live quotes from Zerodha API: {e}")
            else:
                raise ValueError(f"Failed to fetch LTP from Zerodha API: {e}")

    def _organize_by_strikes(self, options_df: pd.DataFrame, price_data: Dict[str, Dict]) -> List[Dict]:
        """Organize options data by strike prices."""

        strikes_data = []

        # Group by strike
        for strike in sorted(options_df['strike'].unique()):
            strike_options = options_df[options_df['strike'] == strike]

            strike_data = {
                "strike": int(strike),
                "CE": None,
                "PE": None
            }

            for _, option in strike_options.iterrows():
                token = str(option['instrument_token'])
                option_type = option['instrument_type']

                if token in price_data:
                    price_info = price_data[token]
                    option_data = {
                        "tradingsymbol": option['tradingsymbol'],
                        "instrument_token": option['instrument_token'],
                        "expiry": option['expiry'],
                        "strike": int(strike),
                        "option_type": option_type,
                        "last_price": price_info['last_price'],
                        "volume": price_info['volume'],
                        "oi": price_info['oi'],
                        "timestamp": price_info['timestamp']
                    }
                    strike_data[option_type] = option_data

            # Only include strikes that have at least one option
            if strike_data["CE"] or strike_data["PE"]:
                strikes_data.append(strike_data)

        return strikes_data

    def _create_empty_response(self, reason: str) -> Dict[str, Any]:
        """Create empty response with reason."""
        return {
            "available": False,
            "reason": reason,
            "instrument": self.instrument_symbol,
            "expiry": "",
            "strikes": [],
            "source": "mock_cache"
        }

    async def get_historical_data(self, instrument_token: int, from_date: str, to_date: str,
                                 interval: str = "day") -> List[Dict]:
        """Get historical data for backtesting (optional method)."""

        if self.kite is None:
            return []

        try:
            from_date_obj = date.fromisoformat(from_date)
            to_date_obj = date.fromisoformat(to_date)

            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date_obj,
                to_date=to_date_obj,
                interval=interval,
                oi=True
            )

            return data

        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []

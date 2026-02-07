"""Zerodha Options Chain Adapter using cached instrument data and real Zerodha API prices.

This adapter provides options chain data by using:
- Real NFO instruments from Zerodha Kite API
- Real prices from Zerodha API (kite.quote() for live or kite.ltp() for historical/after-hours)
- Implied volatility and Greeks calculations
- Works for both live trading and historical backtesting
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
import pandas as pd

from ..contracts import OptionsData

# Defer scipy-dependent imports to avoid blocking module load
OPTIONS_CALCULATIONS_AVAILABLE = False
calculate_option_metrics = None
time_to_expiry = None

def _lazy_load_options_calculations():
    global OPTIONS_CALCULATIONS_AVAILABLE, calculate_option_metrics, time_to_expiry
    if OPTIONS_CALCULATIONS_AVAILABLE:
        return
    try:
        from ..options_calculations import calculate_option_metrics as _calc, time_to_expiry as _tte
        calculate_option_metrics = _calc
        time_to_expiry = _tte
        OPTIONS_CALCULATIONS_AVAILABLE = True
    except Exception as e:
        OPTIONS_CALCULATIONS_AVAILABLE = False
        print("WARNING: Options calculations not available - IV and Greeks will be disabled")

logger = logging.getLogger(__name__)


class ZerodhaOptionsChainAdapter(OptionsData):
    """Options chain adapter using Zerodha API.
    
    Uses real Zerodha API (kite.ltp() or kite.quote()) for live data.
    Provides options chain with real market data for both live and historical modes.
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
    
    def _extract_underlying_symbol(self, symbol: str) -> str:
        """Extract underlying symbol from futures/options contract.
        
        Examples:
            BANKNIFTY26FEBFUT -> BANKNIFTY
            BANKNIFTY26FEB24000CE -> BANKNIFTY
            NIFTY26JANFUT -> NIFTY
            BANKNIFTY -> BANKNIFTY (already underlying)
        """
        symbol_upper = symbol.upper()
        
        # Remove common suffixes
        for suffix in ['FUT', 'CE', 'PE']:
            if suffix in symbol_upper:
                # Find the position and extract everything before it
                # Also remove date pattern like 26FEB, 27JAN, etc.
                import re
                # Match pattern: SYMBOL + DATE (YYMMMDD or YYMM) + TYPE (FUT/CE/PE)
                match = re.match(r'^([A-Z]+)\d{2}[A-Z]{3}', symbol_upper)
                if match:
                    return match.group(1)
                # Fallback: just remove the suffix
                symbol_upper = symbol_upper.replace(suffix, '')
        
        # Remove any remaining digits and return
        symbol_upper = re.sub(r'\d+', '', symbol_upper)
        return symbol_upper.strip()


    async def initialize(self) -> None:
        """Initialize by downloading and caching NFO instruments."""
        try:
            logger.info(f"Initializing ZerodhaOptionsChainAdapter for {self.instrument_symbol}")

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
            try:
                self._options_df = self._instruments_df[
                    (self._instruments_df["name"] == self.instrument_symbol) &
                    (self._instruments_df["instrument_type"].isin(["CE", "PE"]))
                ].copy()
            except Exception as e:
                logger.warning(f"Zerodha instruments dataframe missing expected columns, falling back to empty: {e}")
                self._instruments_df = pd.DataFrame()
                self._options_df = pd.DataFrame()
                return

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
            logger.warning(f"Failed to initialize Zerodha options chain (falling back to empty): {e}")
            self._instruments_df = pd.DataFrame()
            self._options_df = pd.DataFrame()
            return

    async def fetch_options_chain(self, instrument: Optional[str] = None, expiry: Optional[str] = None,
                                 strikes: Optional[List[int]] = None) -> Dict[str, Any]:
        """Fetch options chain using cached instrument data and real Zerodha API prices."""

        try:
            target_instrument = instrument or self.instrument_symbol
            
            # Extract underlying symbol from futures contract (e.g., BANKNIFTY26FEBFUT -> BANKNIFTY)
            underlying_symbol = self._extract_underlying_symbol(target_instrument)
            logger.info(f"Fetching options chain for {target_instrument}, underlying: {underlying_symbol}")

            if self._options_df is None or len(self._options_df) == 0:
                logger.warning("No options data available, initializing...")
                if self.kite:
                    await self.initialize()
                else:
                    return self._create_empty_response("No kite client available for initialization")

            # Filter options for underlying symbol (not the futures contract)
            options_df = self._options_df
            if underlying_symbol.upper() != self.instrument_symbol:
                # If different instrument requested, filter from main instruments
                if self._instruments_df is not None:
                    options_df = self._instruments_df[
                        (self._instruments_df["name"] == underlying_symbol.upper()) &
                        (self._instruments_df["instrument_type"].isin(["CE", "PE"]))
                    ]
                else:
                    return self._create_empty_response(f"No data for {underlying_symbol}")

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

            # Get underlying price for IV calculations
            underlying_price = None
            try:
                if self.kite:
                    # Try to get spot price for the underlying
                    underlying_symbol = target_instrument
                    if underlying_symbol == "BANKNIFTY":
                        spot_symbol = "NSE:NIFTY BANK"
                    elif underlying_symbol == "NIFTY":
                        spot_symbol = "NSE:NIFTY 50"
                    else:
                        spot_symbol = f"NSE:{underlying_symbol}"

                    spot_data = self.kite.ltp([spot_symbol])
                    if spot_data and spot_symbol in spot_data:
                        underlying_price = spot_data[spot_symbol].get('last_price')
                        logger.info(f"Using underlying price {underlying_price} for {underlying_symbol}")
            except Exception as e:
                logger.warning(f"Could not get underlying price for IV calculations: {e}")

            # Organize by strikes and calculate IV/Greeks
            strikes_data = self._organize_by_strikes(expiry_options, price_data, underlying_price)

            return {
                "available": True,
                "instrument": target_instrument,
                "expiry": selected_expiry.isoformat() if hasattr(selected_expiry, 'isoformat') else str(selected_expiry),
                "strikes": strikes_data,
                "available_expiries": [exp.isoformat() if hasattr(exp, 'isoformat') else str(exp) for exp in available_expiries],
                "total_contracts": len(expiry_options),
                "source": "zerodha_api"
            }

        except Exception as e:
            logger.error(f"Error fetching Zerodha options chain: {e}")
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

    def _organize_by_strikes(self, options_df: pd.DataFrame, price_data: Dict[str, Dict],
                           underlying_price: float = None) -> List[Dict]:
        """Organize options data by strike prices and calculate IV/Greeks."""

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

                    # Get expiry date
                    expiry_date = option['expiry']
                    if isinstance(expiry_date, pd.Timestamp):
                        expiry_str = expiry_date.strftime('%Y-%m-%d')
                    else:
                        expiry_str = str(expiry_date).split(' ')[0]  # Handle datetime objects

                    # Calculate option metrics (IV and Greeks) with mode awareness
                    market_price = price_info['last_price']
                    option_metrics = {}

                    if underlying_price and market_price > 0 and OPTIONS_CALCULATIONS_AVAILABLE:
                        try:
                            # Calculate time to expiry only if options calculations available
                            T = time_to_expiry(expiry_str)
                            
                            if T > 0:
                                # Determine execution mode for context-aware calculations
                                execution_mode = "LIVE"  # Default assumption
                                try:
                                    import redis
                                    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                                    mode = r.get("system:execution_mode") or "LIVE"
                                    if mode in ["LIVE", "HISTORICAL"]:
                                        execution_mode = mode
                                except Exception:
                                    pass  # Keep default LIVE mode

                                option_metrics = calculate_option_metrics(
                                    market_price=market_price,
                                    S=underlying_price,
                                    K=float(strike),
                                    T=T,
                                    option_type=option_type.lower(),
                                    mode=execution_mode,
                                    data_timestamp=price_info.get('timestamp')
                                )
                        except Exception as e:
                            logger.warning(f"Failed to calculate metrics for {option_type} {strike}: {e}")
                            option_metrics = {'calculation_note': f'Calculation failed: {str(e)}'}
                    else:
                        option_metrics = {'calculation_note': 'Options calculations not available (scipy not installed)'}

                    option_data = {
                        "tradingsymbol": option['tradingsymbol'],
                        "instrument_token": option['instrument_token'],
                        "expiry": expiry_str,
                        "strike": int(strike),
                        "option_type": option_type,
                        "last_price": price_info['last_price'],
                        "volume": price_info['volume'],
                        "oi": price_info['oi'],
                        "timestamp": price_info['timestamp'],
                        # Add IV and Greeks
                        "iv": option_metrics.get('implied_volatility'),
                        "delta": option_metrics.get('delta'),
                        "gamma": option_metrics.get('gamma'),
                        "theta": option_metrics.get('theta'),
                        "vega": option_metrics.get('vega'),
                        "rho": option_metrics.get('rho'),
                        "theoretical_price": option_metrics.get('theoretical_price'),
                        "intrinsic_value": option_metrics.get('intrinsic_value'),
                        "extrinsic_value": option_metrics.get('extrinsic_value'),
                        "calculation_note": option_metrics.get('calculation_note')
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
            "source": "zerodha_api"
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

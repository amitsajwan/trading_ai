from typing import Any, Dict, List, Optional
from schemas import Quote

class ProviderBase:
    """Abstract provider interface for broker/market-data providers.

    Implementations must provide:
    - quote(symbols: List[str]) -> Dict[str, Quote]
    - profile() -> Dict[str, Any]
    - historical_data(instrument_token, from_date, to_date, interval) -> List[Dict[str, Any]]
    """

    def quote(self, symbols: List[str]) -> Dict[str, Quote]:
        raise NotImplementedError

    def profile(self) -> Dict[str, Any]:
        raise NotImplementedError

    def historical_data(self, instrument_token: str, from_date: str, to_date: str, interval: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__

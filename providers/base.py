from typing import List, Dict, Any
from schemas import Quote


class ProviderBase:
    """Abstract provider interface for broker/market-data providers.

    Implementations must provide typed models from `schemas` (Quote, etc.).
    """

    def quote(self, symbols: List[str]) -> Dict[str, Quote]:
        raise NotImplementedError

    def profile(self) -> Dict[str, Any]:
        raise NotImplementedError

    def historical_data(self, instrument_token: str, from_date: str, to_date: str, interval: str):
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__

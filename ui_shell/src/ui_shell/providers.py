"""UI Data Provider implementations."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .contracts import (
    UIDataProvider,
    DecisionDisplay,
    PortfolioSummary,
    MarketOverview,
)

logger = logging.getLogger(__name__)


class MockEngineInterface:
    """Mock interface to engine module until it's fully implemented."""

    async def get_latest_decision(self) -> Optional[Dict[str, Any]]:
        """Mock latest decision from engine."""
        # This would normally call engine.get_latest_decision()
        # For now, return mock data
        return {
            "instrument": "NIFTY",
            "signal": "HOLD",
            "confidence": 0.65,
            "reasoning": "Market showing mixed signals, awaiting clearer trend",
            "timestamp": datetime.utcnow(),
            "technical_indicators": {
                "rsi": 52.3,
                "macd": 15.2,
                "sma_20": 22150.5
            }
        }

    async def get_portfolio_status(self) -> Dict[str, Any]:
        """Mock portfolio status."""
        return {
            "total_value": 250000.0,
            "cash_balance": 150000.0,
            "positions": {
                "NIFTY": {
                    "quantity": 10,
                    "avg_price": 22000.0,
                    "current_price": 22150.0,
                    "pnl": 1500.0
                }
            },
            "pnl_today": 1250.0,
            "pnl_total": 8500.0
        }


class EngineDataProvider(UIDataProvider):
    """Data provider that gets data from the trading engine."""

    def __init__(self, engine_interface=None):
        """Initialize with engine interface.

        Args:
            engine_interface: Interface to engine module (mock if None)
        """
        self.engine = engine_interface or MockEngineInterface()
        self._cached_decisions: List[DecisionDisplay] = []
        self._max_cache_size = 50

    async def get_latest_decision(self) -> Optional[DecisionDisplay]:
        """Get the latest trading decision from engine."""
        try:
            engine_decision = await self.engine.get_latest_decision()

            if not engine_decision:
                return None

            # Convert engine decision to UI format
            decision = DecisionDisplay(
                instrument=engine_decision.get("instrument", "UNKNOWN"),
                signal=engine_decision.get("signal", "HOLD"),
                confidence=float(engine_decision.get("confidence", 0.0)),
                reasoning=engine_decision.get("reasoning", "No reasoning provided"),
                timestamp=engine_decision.get("timestamp", datetime.utcnow()),
                technical_indicators=engine_decision.get("technical_indicators"),
                sentiment_score=engine_decision.get("sentiment_score"),
                macro_factors=engine_decision.get("macro_factors")
            )

            # Cache the decision
            self._cached_decisions.append(decision)
            if len(self._cached_decisions) > self._max_cache_size:
                self._cached_decisions.pop(0)

            return decision

        except Exception as e:
            logger.error(f"Failed to get latest decision: {e}")
            return None

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get current portfolio summary."""
        try:
            portfolio_data = await self.engine.get_portfolio_status()

            return PortfolioSummary(
                total_value=float(portfolio_data.get("total_value", 0.0)),
                cash_balance=float(portfolio_data.get("cash_balance", 0.0)),
                positions=portfolio_data.get("positions", {}),
                pnl_today=float(portfolio_data.get("pnl_today", 0.0)),
                pnl_total=float(portfolio_data.get("pnl_total", 0.0)),
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            # Return empty portfolio on error
            return PortfolioSummary(
                total_value=0.0,
                cash_balance=0.0,
                positions={},
                pnl_today=0.0,
                pnl_total=0.0,
                timestamp=datetime.utcnow()
            )

    async def get_market_overview(self) -> MarketOverview:
        """Get current market overview."""
        try:
            # This would typically get data from market data sources
            # For now, return mock data
            return MarketOverview(
                nifty_price=22150.5,
                banknifty_price=47250.8,
                market_status="OPEN",  # Would check actual market hours
                volume_24h=1500000,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to get market overview: {e}")
            return MarketOverview(
                nifty_price=0.0,
                banknifty_price=0.0,
                market_status="UNKNOWN",
                volume_24h=0,
                timestamp=datetime.utcnow()
            )

    async def get_recent_decisions(self, limit: int = 10) -> List[DecisionDisplay]:
        """Get recent trading decisions history."""
        # Return cached decisions, most recent first
        return list(reversed(self._cached_decisions[-limit:]))

    async def get_snapshot(self) -> Dict[str, Any]:
        """Get complete system snapshot for dashboard."""
        try:
            decision = await self.get_latest_decision()
            portfolio = await self.get_portfolio_summary()
            market = await self.get_market_overview()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "decision": {
                    "instrument": decision.instrument if decision else None,
                    "signal": decision.signal if decision else None,
                    "confidence": decision.confidence if decision else None,
                    "reasoning": decision.reasoning if decision else None,
                } if decision else None,
                "portfolio": {
                    "total_value": portfolio.total_value,
                    "cash_balance": portfolio.cash_balance,
                    "pnl_today": portfolio.pnl_today,
                    "pnl_total": portfolio.pnl_total,
                },
                "market": {
                    "nifty_price": market.nifty_price,
                    "banknifty_price": market.banknifty_price,
                    "market_status": market.market_status,
                    "volume_24h": market.volume_24h,
                }
            }
        except Exception as e:
            logger.error(f"Failed to get snapshot: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        # This would normally get metrics from the engine
        # For now, return mock metrics
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "trading": {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "sharpe_ratio": 0.0
            },
            "system": {
                "uptime_seconds": 0,
                "memory_usage_mb": 0,
                "cpu_usage_percent": 0.0
            },
            "performance": {
                "response_time_ms": 0,
                "throughput_tps": 0
            }
        }


__all__ = [
    "EngineDataProvider",
    "MockEngineInterface",
]

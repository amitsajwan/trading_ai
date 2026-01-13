#!/usr/bin/env python3
"""
Automatic Trading Service - Integrates Engine Analysis with User Module Trade Execution

This service demonstrates how the trading system automatically:
1. Runs 15-minute analysis cycles using the orchestrator
2. Makes trading decisions based on agent consensus
3. Executes trades through the user module with risk management
4. Manages positions and monitors P&L in real-time
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, time
from typing import Dict, Any, Optional

# Add module paths
sys.path.insert(0, 'data_niftybank/src')
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'genai_module/src')
sys.path.insert(0, 'user_module/src')
sys.path.insert(0, 'core_kernel/src')

from core_kernel.config.settings import settings
from engine_module.api import build_orchestrator
from market_data.api import build_store, build_options_client
from genai_module.api import build_llm_client
from user_module.api import build_user_module, execute_user_trade
from data.options_chain_fetcher import OptionsChainFetcher
from genai_module import LLMProviderManager
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutomaticTradingService:
    """Service that automatically executes trades based on strategy signals."""

    def __init__(self, user_id: str, instrument: str = "BANKNIFTY"):
        """Initialize the automatic trading service.

        Args:
            user_id: The user account to execute trades for
            instrument: Trading instrument (BANKNIFTY/NIFTY)
        """
        self.user_id = user_id
        self.instrument = instrument
        self.is_running = False

        # Initialize components
        self.orchestrator = None
        self.user_service = None
        self.mongo_client = None

        # Trading state
        self.last_decision_time = None
        self.open_positions = {}

    async def initialize(self):
        """Initialize all trading components."""
        logger.info("Initializing Automatic Trading Service...")

        # Initialize MongoDB
        from pymongo import MongoClient
        self.mongo_client = MongoClient(settings.mongodb_uri)

        # Initialize user module
        self.user_service = build_user_module(self.mongo_client)

        # Initialize market data components
        redis_client = None  # Use in-memory for demo
        kite = KiteConnect(api_key=os.getenv("ZERODHA_API_KEY", "demo"))
        fetcher = OptionsChainFetcher()

        market_store = build_store(redis_client=redis_client)
        options_client = build_options_client(kite=kite, fetcher=fetcher)

        # Initialize LLM
        llm_manager = LLMProviderManager()
        llm_client = build_llm_client(legacy_manager=llm_manager)

        # Initialize orchestrator with agents
        from engine_module.agents.technical_agent import TechnicalAgent
        from engine_module.agents.sentiment_agent import SentimentAgent
        from engine_module.agents.macro_agent import MacroAgent
        from engine_module.agents.execution_agent import ExecutionAgent

        agents = [
            TechnicalAgent(),
            SentimentAgent(),
            MacroAgent(),
            ExecutionAgent(paper_trading=True)  # Always paper trading for safety
        ]

        self.orchestrator = build_orchestrator(
            llm_client=llm_client,
            market_store=market_store,
            options_data=options_client,
            agents=agents
        )

        logger.info("✅ Automatic Trading Service initialized")

    def is_market_open(self) -> bool:
        """Check if Indian equity market is currently open."""
        now = datetime.now()

        # Market is only open Monday-Friday
        if now.weekday() >= 5:
            return False

        # Market hours: 9:15 AM to 3:30 PM IST
        market_open = time(9, 15, 0)
        market_close = time(15, 30, 0)

        current_time = now.time()
        return market_open <= current_time <= market_close

    async def run_analysis_cycle(self) -> Optional[Dict[str, Any]]:
        """Run a single analysis cycle and return trading decision."""
        try:
            context = {
                "instrument": self.instrument,
                "market_hours": self.is_market_open(),
                "cycle_interval": "15min",
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Running analysis cycle for {self.instrument}")

            # Get orchestrator decision
            result = await self.orchestrator.run_cycle(context)

            decision_data = {
                "decision": result.decision,
                "confidence": result.confidence,
                "strategy": result.details.get("strategy", ""),
                "reasoning": result.details.get("reasoning", ""),
                "timestamp": datetime.now().isoformat(),
                "instrument": self.instrument,
                "market_open": context["market_hours"]
            }

            logger.info(f"Analysis complete: {result.decision} (confidence: {result.confidence:.1%})")
            return decision_data

        except Exception as e:
            logger.error(f"Analysis cycle failed: {e}")
            return None

    async def execute_trade_decision(self, decision_data: Dict[str, Any]) -> bool:
        """Execute a trade based on the analysis decision."""
        try:
            decision = decision_data["decision"]
            confidence = decision_data["confidence"]
            market_open = decision_data["market_open"]

            # Only trade if confidence is high enough and market is open
            if confidence < 0.7:
                logger.info(f"Skipping trade: confidence too low ({confidence:.1%})")
                return False

            if not market_open:
                logger.info("Skipping trade: market closed")
                return False

            # Parse decision for trade execution
            if "BUY_CALL" in decision:
                await self._execute_options_trade(decision_data, "BUY", "CALL")
            elif "BUY_PUT" in decision:
                await self._execute_options_trade(decision_data, "BUY", "PUT")
            elif "SELL" in decision.upper():
                await self._execute_futures_trade(decision_data, "SELL")
            elif "BUY" in decision.upper():
                await self._execute_futures_trade(decision_data, "BUY")
            else:
                logger.info(f"No executable trade in decision: {decision}")
                return False

            return True

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return False

    async def _execute_options_trade(self, decision_data: Dict[str, Any], side: str, option_type: str):
        """Execute an options trade."""
        # For demo: fixed position size (would be calculated by risk manager)
        quantity = 25  # contracts
        current_price = 45000  # Would get from market data

        logger.info(f"Executing {side} {option_type} options trade: {quantity} contracts")

        result = await execute_user_trade(
            mongo_client=self.mongo_client,
            user_id=self.user_id,
            instrument=self.instrument,
            action=side,
            quantity=quantity,
            price=current_price,
            order_type="MARKET",
            stop_loss=current_price * 0.98,  # 2% stop loss
            take_profit=current_price * 1.05   # 5% target
        )

        if result.success:
            logger.info(f"✅ Options trade executed: {result.trade_id}")
            self.open_positions[result.trade_id] = {
                "type": "options",
                "side": side,
                "quantity": quantity,
                "entry_price": result.executed_price,
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"❌ Options trade failed: {result.message}")

    async def _execute_futures_trade(self, decision_data: Dict[str, Any], side: str):
        """Execute a futures trade."""
        # For demo: conservative position size
        quantity = 10  # contracts
        current_price = 45000  # Would get from market data

        logger.info(f"Executing {side} futures trade: {quantity} contracts")

        result = await execute_user_trade(
            mongo_client=self.mongo_client,
            user_id=self.user_id,
            instrument=self.instrument,
            action=side,
            quantity=quantity,
            price=current_price,
            order_type="MARKET",
            stop_loss=current_price * 0.97,  # 3% stop loss for futures
            take_profit=current_price * 1.08   # 8% target
        )

        if result.success:
            logger.info(f"✅ Futures trade executed: {result.trade_id}")
            self.open_positions[result.trade_id] = {
                "type": "futures",
                "side": side,
                "quantity": quantity,
                "entry_price": result.executed_price,
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"❌ Futures trade failed: {result.message}")

    async def monitor_positions(self):
        """Monitor open positions and check for exits."""
        if not self.open_positions:
            return

        try:
            # Get current prices (simplified)
            current_price = 45100  # Would get from market data

            positions_to_close = []

            for trade_id, position in self.open_positions.items():
                entry_price = position["entry_price"]
                pnl_pct = (current_price - entry_price) / entry_price

                # Check stop loss / take profit (simplified)
                if position["type"] == "options":
                    if pnl_pct <= -0.02:  # 2% stop loss
                        logger.info(f"Closing options position {trade_id}: stop loss hit")
                        positions_to_close.append((trade_id, "STOP_LOSS"))
                    elif pnl_pct >= 0.05:  # 5% target
                        logger.info(f"Closing options position {trade_id}: target hit")
                        positions_to_close.append((trade_id, "TAKE_PROFIT"))
                elif position["type"] == "futures":
                    if pnl_pct <= -0.03:  # 3% stop loss
                        logger.info(f"Closing futures position {trade_id}: stop loss hit")
                        positions_to_close.append((trade_id, "STOP_LOSS"))
                    elif pnl_pct >= 0.08:  # 8% target
                        logger.info(f"Closing futures position {trade_id}: target hit")
                        positions_to_close.append((trade_id, "TAKE_PROFIT"))

            # Close positions (simplified - would call user module)
            for trade_id, reason in positions_to_close:
                logger.info(f"Position {trade_id} closed: {reason}")
                del self.open_positions[trade_id]

        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")

    async def run_trading_cycle(self):
        """Run one complete trading cycle: analyze → decide → execute → monitor."""
        try:
            # Step 1: Run analysis
            decision = await self.run_analysis_cycle()
            if not decision:
                return

            # Step 2: Execute trade if conditions met
            if decision["decision"] not in ["HOLD", "ERROR"]:
                await self.execute_trade_decision(decision)

            # Step 3: Monitor existing positions
            await self.monitor_positions()

            # Step 4: Update last cycle time
            self.last_decision_time = decision["timestamp"]

        except Exception as e:
            logger.error(f"Trading cycle failed: {e}")

    async def start_automatic_trading(self):
        """Start the automatic trading loop."""
        self.is_running = True
        logger.info("🚀 Starting Automatic Trading Service")
        logger.info(f"User ID: {self.user_id}")
        logger.info(f"Instrument: {self.instrument}")
        logger.info("Cycle interval: 15 minutes")

        try:
            while self.is_running:
                await self.run_trading_cycle()

                # Wait 15 minutes before next cycle
                logger.info("Waiting 15 minutes until next analysis cycle...")
                await asyncio.sleep(15 * 60)  # 15 minutes

        except KeyboardInterrupt:
            logger.info("🛑 Automatic trading stopped by user")
        except Exception as e:
            logger.error(f"Automatic trading crashed: {e}")
        finally:
            self.is_running = False

    def stop(self):
        """Stop the automatic trading service."""
        logger.info("Stopping Automatic Trading Service...")
        self.is_running = False

async def main():
    """Main function to demonstrate automatic trading."""
    # Use the paper trading account we created
    user_id = "paper_trader_user_id"  # Would get from setup_paper_trading.py

    # Create trading service
    service = AutomaticTradingService(user_id=user_id, instrument="BANKNIFTY")

    try:
        # Initialize
        await service.initialize()

        # Run one demo cycle instead of full automatic trading
        logger.info("Running demo trading cycle...")
        await service.run_trading_cycle()

        logger.info("Demo cycle complete!")

    except Exception as e:
        logger.error(f"Demo failed: {e}")

if __name__ == "__main__":
    # Run demo
    asyncio.run(main())

    # For production automatic trading, use:
    # service = AutomaticTradingService(user_id="your_user_id")
    # await service.initialize()
    # await service.start_automatic_trading()


#!/usr/bin/env python3
"""
Complete Agents Demonstration - All Agents in Action

This script demonstrates all available agents running with comprehensive input/output analysis.
Shows the complete flow from data input through individual agent analysis to final orchestration.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import all agents and related classes
from engine_module.contracts import AnalysisResult, TechnicalIndicators
from engine_module.agents import (
    momentum_agent, trend_agent, mean_reversion_agent, volume_agent,
    technical_agent, enhanced_momentum_agent, fundamental_agent,
    sentiment_agent, macro_agent, bull_researcher, bear_researcher,
    research_manager, options_analysis_agent, options_strategy_agent,
    portfolio_manager, enhanced_risk_agents, execution_agent, learning_agent, review_agent
)


class ComprehensiveAgentDemonstrator:
    """Demonstrates all agents with detailed input/output analysis."""

    def __init__(self):
        self.agents = {}
        self.test_data = self._generate_comprehensive_test_data()
        self.agent_results = {}

    def _generate_comprehensive_test_data(self) -> Dict[str, Any]:
        """Generate comprehensive test data for all agent types."""
        # Base market data
        base_price = 45000
        periods = 100

        # Generate OHLC data with trend and volatility
        ohlc_data = []
        current_time = datetime.now() - timedelta(minutes=15 * periods)

        for i in range(periods):
            trend = 0.001 * i  # Slight upward trend
            volatility = np.random.normal(0, 0.005)
            price_change = trend + volatility
            close_price = base_price * (1 + price_change)

            high_price = close_price * (1 + abs(np.random.normal(0, 0.002)))
            low_price = close_price * (1 - abs(np.random.normal(0, 0.002)))
            open_price = (ohlc_data[-1]['close'] if ohlc_data else close_price) * (1 + np.random.normal(0, 0.001))

            volume = int(np.random.lognormal(10, 1))
            candle = {
                'timestamp': current_time.isoformat(),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'instrument_token': 260105
            }
            ohlc_data.append(candle)
            current_time += timedelta(minutes=15)
            base_price = close_price

        # Technical indicators
        technical_indicators = TechnicalIndicators(
            rsi=round(np.random.uniform(30, 70), 2),
            sma_20=round(base_price * (1 + np.random.normal(0, 0.01)), 2),
            sma_50=round(base_price * (1 + np.random.normal(0, 0.02)), 2),
            ema_12=round(base_price * (1 + np.random.normal(0, 0.005)), 2),
            ema_26=round(base_price * (1 + np.random.normal(0, 0.01)), 2),
            macd=round((base_price * 1.005) - (base_price * 1.01), 2),
            macd_signal=round(((base_price * 1.005) - (base_price * 1.01)) * 0.8, 2),
            adx=round(np.random.uniform(15, 35), 2),
            bb_upper=round(base_price * 1.02, 2),
            bb_middle=round(base_price, 2),
            bb_lower=round(base_price * 0.98, 2),
            volume_sma=50000,
            volume_ratio=round(np.random.uniform(0.8, 1.5), 2),
            price_change_pct=round(np.random.normal(0, 0.01), 4),
            volatility=round(np.random.uniform(0.01, 0.03), 4),
            timestamp=datetime.now().isoformat()
        )

        # Options data
        calls = [
            {'strike': 44000, 'oi': 1000, 'volume': 500, 'bid': 1200, 'ask': 1250, 'iv': 0.25},
            {'strike': 45000, 'oi': 1500, 'volume': 800, 'bid': 800, 'ask': 850, 'iv': 0.22},
            {'strike': 46000, 'oi': 800, 'volume': 300, 'bid': 450, 'ask': 480, 'iv': 0.20}
        ]
        puts = [
            {'strike': 44000, 'oi': 1200, 'volume': 600, 'bid': 350, 'ask': 380, 'iv': 0.23},
            {'strike': 45000, 'oi': 1000, 'volume': 400, 'bid': 680, 'ask': 710, 'iv': 0.21},
            {'strike': 46000, 'oi': 900, 'volume': 350, 'bid': 1100, 'ask': 1130, 'iv': 0.24}
        ]

        # Fundamental data
        fundamental_data = {
            'earnings_surprise': 0.15,  # 15% positive surprise
            'revenue_growth': 0.12,     # 12% revenue growth
            'rbi_rate': 0.065,          # 6.5% RBI rate
            'inflation_rate': 0.045     # 4.5% inflation
        }

        # Sentiment data
        sentiment_data = {
            'latest_news': [
                {'title': 'BANKNIFTY shows strong momentum', 'sentiment': 0.8},
                {'title': 'Market volatility expected to rise', 'sentiment': -0.3}
            ],
            'sentiment_score': 0.65,
            'retail_sentiment': 0.7,
            'institutional_sentiment': 0.6
        }

        # Positions data
        positions = [
            {
                'position_id': 'pos_1',
                'symbol': 'BANKNIFTY26JANFUT',
                'action': 'BUY',
                'quantity': 10,
                'entry_price': 44800,
                'current_price': 44950,
                'stop_loss': 44400,
                'take_profit': 45200,
                'status': 'active'
            }
        ]

        return {
            'ohlc': ohlc_data,
            'symbol': 'BANKNIFTY26JANFUT',
            'current_price': ohlc_data[-1]['close'],
            'technical_indicators': technical_indicators,
            'calls': calls,
            'puts': puts,
            'underlying_price': ohlc_data[-1]['close'],
            'pcr': 0.85,  # Put-call ratio
            'max_pain': 45000,
            'consensus_direction': 'BULLISH',
            'earnings_surprise': fundamental_data['earnings_surprise'],
            'revenue_growth': fundamental_data['revenue_growth'],
            'rbi_rate': fundamental_data['rbi_rate'],
            'inflation_rate': fundamental_data['inflation_rate'],
            'latest_news': sentiment_data['latest_news'],
            'sentiment_score': sentiment_data['sentiment_score'],
            'current_positions': positions,
            'has_long_position': True,
            'has_short_position': False,
            'position_count': 1,
            'account_size': 100000,
            'timestamp': datetime.now(),
            'market_hours': True
        }

    def _initialize_all_agents(self):
        """Initialize all available agents."""
        # Technical Agents
        self.agents['technical'] = technical_agent.TechnicalAgent()
        try:
            self.agents['enhanced_technical'] = enhanced_technical_agent.EnhancedTechnicalAgent()
        except:
            logger.warning("EnhancedTechnicalAgent not available")

        # Strategy Agents
        self.agents['momentum'] = momentum_agent.MomentumAgent()
        try:
            self.agents['enhanced_momentum'] = enhanced_momentum_agent.EnhancedMomentumAgent()
        except:
            logger.warning("EnhancedMomentumAgent not available")
        self.agents['trend'] = trend_agent.TrendAgent()
        self.agents['mean_reversion'] = mean_reversion_agent.MeanReversionAgent()
        self.agents['volume'] = volume_agent.VolumeAgent()

        # Fundamental Agents
        try:
            self.agents['fundamental'] = fundamental_agent.FundamentalAgent()
        except:
            logger.warning("FundamentalAgent not available")
        try:
            self.agents['sentiment'] = sentiment_agent.SentimentAgent()
        except:
            logger.warning("SentimentAgent not available")
        try:
            self.agents['macro'] = macro_agent.MacroAgent()
        except:
            logger.warning("MacroAgent not available")

        # Research Agents
        try:
            self.agents['bull_researcher'] = bull_researcher.BullResearcher()
        except:
            logger.warning("BullResearcher not available")
        try:
            self.agents['bear_researcher'] = bear_researcher.BearResearcher()
        except:
            logger.warning("BearResearcher not available")
        try:
            self.agents['research_manager'] = research_manager.ResearchManager()
        except:
            logger.warning("ResearchManager not available")

        # Options Agents
        try:
            self.agents['options_analysis'] = options_analysis_agent.OptionsAnalysisAgent()
        except:
            logger.warning("OptionsAnalysisAgent not available")
        try:
            self.agents['options_strategy'] = options_strategy_agent.OptionsStrategyAgent()
        except:
            logger.warning("OptionsStrategyAgent not available")

        # Risk & Portfolio Agents
        try:
            self.agents['portfolio_manager'] = portfolio_manager.PortfolioManagerAgent()
        except:
            logger.warning("PortfolioManagerAgent not available")
        try:
            self.agents['enhanced_risk'] = enhanced_risk_agents.EnhancedRiskAgent()
        except:
            logger.warning("EnhancedRiskAgent not available")

        # Execution & Learning Agents
        try:
            self.agents['execution'] = execution_agent.ExecutionAgent()
        except:
            logger.warning("ExecutionAgent not available")
        try:
            self.agents['learning'] = learning_agent.LearningAgent()
        except:
            logger.warning("LearningAgent not available")
        try:
            self.agents['review'] = review_agent.ReviewAgent()
        except:
            logger.warning("ReviewAgent not available")

        logger.info(f"Initialized {len(self.agents)} agents: {list(self.agents.keys())}")

    def _create_agent_context(self, agent_name: str, agent_type: str) -> Dict[str, Any]:
        """Create appropriate context for each agent type."""
        base_context = self.test_data.copy()

        # Customize context based on agent requirements
        if agent_type in ['technical', 'trend', 'mean_reversion', 'volume']:
            # Technical agents need OHLC data
            context = {
                'ohlc': base_context['ohlc'],
                'current_price': base_context['current_price'],
                'symbol': base_context['symbol']
            }
            if agent_name in ['momentum', 'enhanced_momentum']:
                context['technical_indicators'] = base_context['technical_indicators'].to_dict()
                context['technical'] = base_context['technical_indicators'].to_dict()  # For agents expecting dict access

        elif agent_type in ['fundamental']:
            context = {
                'earnings_surprise': base_context['earnings_surprise'],
                'revenue_growth': base_context['revenue_growth']
            }

        elif agent_type in ['sentiment']:
            context = {
                'latest_news': base_context['latest_news'],
                'sentiment_score': base_context['sentiment_score']
            }

        elif agent_type in ['macro']:
            context = {
                'rbi_rate': base_context['rbi_rate'],
                'inflation_rate': base_context['inflation_rate'],
                'instrument_name': base_context['symbol']
            }

        elif agent_type in ['bull_researcher', 'bear_researcher']:
            context = {
                'technical_indicators': base_context['technical_indicators'].to_dict(),
                'technical': base_context['technical_indicators'].to_dict(),  # For dict access
                'symbol': base_context['symbol'],
                'current_price': base_context['current_price']
            }

        elif agent_type in ['research_manager']:
            # This would normally get bull/bear outputs, but we'll simulate
            context = {
                'bull_output': {'decision': 'BULL_CALL_SPREAD', 'confidence': 0.7},
                'bear_output': {'decision': 'BEAR_PUT_SPREAD', 'confidence': 0.6}
            }

        elif agent_type in ['options_analysis']:
            context = {
                'calls': base_context['calls'],
                'puts': base_context['puts'],
                'underlying_price': base_context['underlying_price'],
                'pcr': base_context['pcr'],
                'max_pain': base_context['max_pain'],
                'consensus_direction': base_context['consensus_direction']
            }

        elif agent_type in ['portfolio_manager']:
            # Would normally get all agent outputs
            context = {
                'agent_outputs': {
                    'technical': {'decision': 'BUY', 'confidence': 0.7},
                    'sentiment': {'decision': 'BUY', 'confidence': 0.6},
                    'macro': {'decision': 'HOLD', 'confidence': 0.5}
                }
            }

        elif agent_type in ['enhanced_risk']:
            context = {
                'market_data': base_context['ohlc'],
                'current_positions': base_context['current_positions'],
                'technical_indicators': base_context['technical_indicators'].to_dict(),
                'technical': base_context['technical_indicators'].to_dict()  # For dict access
            }

        elif agent_type in ['execution']:
            context = {
                'final_signal': {
                    'action': 'BUY',
                    'confidence': 0.75,
                    'entry_price': base_context['current_price']
                },
                'position_size': 10,
                'entry_price': base_context['current_price'],
                'stop_loss': base_context['current_price'] * 0.98,
                'take_profit': base_context['current_price'] * 1.04,
                'current_price': base_context['current_price']
            }

        else:
            # Default context - ensure technical indicators are dict for all agents
            context = base_context.copy()
            if 'technical_indicators' in context and hasattr(context['technical_indicators'], 'to_dict'):
                context['technical'] = context['technical_indicators'].to_dict()
                context['technical_indicators'] = context['technical_indicators'].to_dict()

        return context

    async def run_agent_analysis(self, agent_name: str, agent) -> Dict[str, Any]:
        """Run analysis for a single agent and capture detailed input/output."""
        start_time = datetime.now()

        try:
            # Determine agent type for context creation
            agent_type = agent_name.lower().replace('_', '')

            # Create appropriate context
            context = self._create_agent_context(agent_name, agent_type)

            # Run analysis
            logger.info(f"Running {agent_name} analysis...")
            result = await agent.analyze(context)

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                'agent_name': agent_name,
                'agent_type': agent_type,
                'input_context': context,
                'output_result': {
                    'decision': result.decision,
                    'confidence': result.confidence,
                    'details': result.details,
                    'agent': getattr(result, 'agent', None),
                    'options_strategy': result.options_strategy
                },
                'execution_time': execution_time,
                'success': True,
                'error': None
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error in {agent_name}: {e}")

            return {
                'agent_name': agent_name,
                'agent_type': agent_type,
                'input_context': context if 'context' in locals() else {},
                'output_result': {
                    'decision': 'ERROR',
                    'confidence': 0.0,
                    'details': {'error': str(e)},
                    'agent': None,
                    'options_strategy': None
                },
                'execution_time': execution_time,
                'success': False,
                'error': str(e)
            }

    async def run_all_agents_demonstration(self) -> Dict[str, Any]:
        """Run comprehensive demonstration of all agents."""
        logger.info("=" * 80)
        logger.info("STARTING COMPREHENSIVE AGENTS DEMONSTRATION")
        logger.info("=" * 80)

        # Initialize all agents
        self._initialize_all_agents()

        # Run all agents concurrently
        logger.info(f"Running {len(self.agents)} agents concurrently...")

        tasks = []
        for agent_name, agent in self.agents.items():
            task = asyncio.create_task(self.run_agent_analysis(agent_name, agent))
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful_results = []
        failed_results = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                continue

            if result['success']:
                successful_results.append(result)
            else:
                failed_results.append(result)

        self.agent_results = {
            'successful': successful_results,
            'failed': failed_results,
            'summary': {
                'total_agents': len(self.agents),
                'successful': len(successful_results),
                'failed': len(failed_results),
                'test_data': self.test_data
            }
        }

        logger.info("=" * 80)
        logger.info(f"DEMONSTRATION COMPLETE: {len(successful_results)}/{len(self.agents)} agents successful")
        logger.info("=" * 80)

        return self.agent_results

    def generate_detailed_report(self) -> str:
        """Generate comprehensive analysis report."""
        report = []

        report.append("# 🔬 COMPREHENSIVE AGENTS ANALYSIS REPORT")
        report.append("")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Total Agents Tested:** {self.agent_results['summary']['total_agents']}")
        report.append(f"**Successful:** {self.agent_results['summary']['successful']}")
        report.append(f"**Failed:** {self.agent_results['summary']['failed']}")
        report.append("")

        # Test Data Summary
        report.append("## 📊 TEST DATA OVERVIEW")
        report.append("")
        test_data = self.agent_results['summary']['test_data']
        report.append(f"- **Symbol:** {test_data['symbol']}")
        report.append(f"- **Current Price:** ₹{test_data['current_price']:,}")
        report.append(f"- **OHLC Periods:** {len(test_data['ohlc'])} (15-min candles)")
        report.append(f"- **Technical Indicators:** RSI {test_data['technical_indicators'].rsi}, SMA20 ₹{test_data['technical_indicators'].sma_20:,}")
        report.append(f"- **Positions:** {test_data['position_count']} active ({'Long' if test_data['has_long_position'] else 'Short'})")
        report.append(f"- **Options:** {len(test_data['calls'])} calls, {len(test_data['puts'])} puts, PCR {test_data['pcr']}")
        report.append(f"- **Fundamental:** Earnings surprise {test_data['earnings_surprise']*100:.1f}%, Revenue growth {test_data['revenue_growth']*100:.1f}%")
        report.append("")

        # Agent Results by Category
        categories = {
            'Technical': ['technical', 'enhanced_technical'],
            'Strategy': ['momentum', 'enhanced_momentum', 'trend', 'mean_reversion', 'volume'],
            'Fundamental': ['fundamental', 'sentiment', 'macro'],
            'Research': ['bull_researcher', 'bear_researcher', 'research_manager'],
            'Options': ['options_analysis', 'options_strategy'],
            'Risk & Portfolio': ['portfolio_manager', 'enhanced_risk'],
            'Execution & Learning': ['execution', 'learning', 'review']
        }

        for category, agent_types in categories.items():
            report.append(f"## 🎯 {category.upper()} AGENTS")
            report.append("")

            category_results = [r for r in self.agent_results['successful']
                              if any(agent_type in r['agent_name'].lower() for agent_type in agent_types)]

            if not category_results:
                report.append("*No agents in this category available/tested*")
                report.append("")
                continue

            for result in category_results:
                report.append(f"### {result['agent_name'].upper()}")
                report.append("")

                # Input
                report.append("**INPUT CONTEXT:**")
                input_context = result['input_context']
                # Convert context to serializable format
                serializable_context = {}
                for k, v in input_context.items():
                    if k == 'ohlc':
                        serializable_context[k] = f"[{len(v)} OHLC periods]"
                    elif hasattr(v, 'to_dict'):
                        serializable_context[k] = v.to_dict()
                    elif hasattr(v, '__dict__'):
                        serializable_context[k] = str(v)
                    else:
                        try:
                            json.dumps(v)  # Test if serializable
                            serializable_context[k] = v
                        except:
                            serializable_context[k] = str(type(v).__name__)

                if len(str(serializable_context)) > 500:
                    # Truncate large inputs
                    report.append("```json")
                    report.append(json.dumps(serializable_context, indent=2))
                    report.append("```")
                else:
                    report.append("```json")
                    report.append(json.dumps(serializable_context, indent=2))
                    report.append("```")

                # Output
                report.append("**OUTPUT RESULT:**")
                output_result = result['output_result']
                report.append("```json")
                report.append(json.dumps(output_result, indent=2, default=str))
                report.append("```")

                # Performance
                report.append(f"**Performance:** {result['execution_time']:.3f}s execution time")
                report.append("")

        # Aggregation Analysis
        report.append("## 🎲 ORCHESTRATOR AGGREGATION ANALYSIS")
        report.append("")

        # Collect decisions for aggregation simulation
        decisions = {}
        for result in self.agent_results['successful']:
            decision = result['output_result']['decision']
            confidence = result['output_result']['confidence']
            decisions[result['agent_name']] = {'decision': decision, 'confidence': confidence}

        report.append("**Agent Decisions Summary:**")
        for agent, data in decisions.items():
            report.append(f"- **{agent}:** {data['decision']} ({data['confidence']:.2f})")

        # Simulate orchestrator logic
        buy_signals = [d for d in decisions.values() if d['decision'] in ['BUY', 'BULL_CALL_SPREAD']]
        sell_signals = [d for d in decisions.values() if d['decision'] in ['SELL', 'BEAR_PUT_SPREAD']]
        hold_signals = [d for d in decisions.values() if d['decision'] == 'HOLD']

        report.append("")
        report.append(f"**Signal Counts:** {len(buy_signals)} BUY, {len(sell_signals)} SELL, {len(hold_signals)} HOLD")
        report.append("")

        # Decision logic simulation
        total_agents = len(decisions)
        min_confidence = 0.6

        if buy_signals and len(buy_signals) > len(sell_signals) and len(buy_signals) >= max(2, total_agents // 2):
            avg_buy_confidence = sum(s['confidence'] for s in buy_signals) / len(buy_signals)
            if avg_buy_confidence >= min_confidence:
                final_decision = f"BUY (confidence: {avg_buy_confidence:.2f})"
            else:
                final_decision = f"HOLD (BUY signals below confidence threshold: {avg_buy_confidence:.2f} < {min_confidence})"
        elif sell_signals and len(sell_signals) > len(buy_signals) and len(sell_signals) >= max(2, total_agents // 2):
            avg_sell_confidence = sum(s['confidence'] for s in sell_signals) / len(sell_signals)
            if avg_sell_confidence >= min_confidence:
                final_decision = f"SELL (confidence: {avg_sell_confidence:.2f})"
            else:
                final_decision = f"HOLD (SELL signals below confidence threshold: {avg_sell_confidence:.2f} < {min_confidence})"
        else:
            final_decision = f"HOLD (no clear consensus: {len(buy_signals)} BUY vs {len(sell_signals)} SELL)"

        report.append(f"**Orchestrator Final Decision:** {final_decision}")

        # Failed Agents
        if self.agent_results['failed']:
            report.append("")
            report.append("## ❌ FAILED AGENTS")
            report.append("")
            for result in self.agent_results['failed']:
                report.append(f"- **{result['agent_name']}:** {result['error']}")

        report.append("")
        report.append("---")
        report.append("*This report shows the complete analysis flow for all available agents with their inputs, outputs, and performance metrics.*")

        return "\n".join(report)


async def main():
    """Main demonstration function."""
    demonstrator = ComprehensiveAgentDemonstrator()

    try:
        # Run comprehensive demonstration
        results = await demonstrator.run_all_agents_demonstration()

        # Generate detailed report
        report = demonstrator.generate_detailed_report()

        # Save report to file
        with open('AGENTS_FULL_ANALYSIS_REPORT.md', 'w', encoding='utf-8') as f:
            f.write(report)

        print("\n*** COMPREHENSIVE AGENTS DEMONSTRATION COMPLETE! ***")
        print(f"Results: {results['summary']['successful']}/{results['summary']['total_agents']} agents successful")
        print(f"Report saved to: AGENTS_FULL_ANALYSIS_REPORT.md")
        return 0

    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
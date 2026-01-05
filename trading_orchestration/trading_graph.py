"""Main trading graph with LangGraph orchestration."""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.technical_agent import TechnicalAnalysisAgent
from agents.fundamental_agent import FundamentalAnalysisAgent
from agents.sentiment_agent import SentimentAnalysisAgent
from agents.macro_agent import MacroAnalysisAgent
from agents.bull_researcher import BullResearcherAgent
from agents.bear_researcher import BearResearcherAgent
from agents.risk_agents import AggressiveRiskAgent, ConservativeRiskAgent, NeutralRiskAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.execution_agent import ExecutionAgent
import sys
from pathlib import Path
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_orchestration.state_manager import StateManager
from kiteconnect import KiteConnect
from config.settings import settings

logger = logging.getLogger(__name__)


class TradingGraph:
    """Main trading graph orchestrating all agents."""
    
    def __init__(self, kite: KiteConnect = None, market_memory=None):
        """Initialize trading graph."""
        self.kite = kite
        self.market_memory = market_memory
        
        # Initialize state manager
        self.state_manager = StateManager(market_memory) if market_memory else None
        
        # Initialize all agents
        # Set parallel groups to ensure different providers for parallel agents
        self.technical_agent = TechnicalAnalysisAgent()
        self.technical_agent._parallel_group = "analysis_parallel"  # Group for parallel analysis agents
        
        self.fundamental_agent = FundamentalAnalysisAgent()
        self.fundamental_agent._parallel_group = "analysis_parallel"
        
        self.sentiment_agent = SentimentAnalysisAgent()
        self.sentiment_agent._parallel_group = "analysis_parallel"
        
        self.macro_agent = MacroAnalysisAgent()
        self.macro_agent._parallel_group = "analysis_parallel"
        
        self.bull_researcher = BullResearcherAgent()
        self.bull_researcher._parallel_group = "researcher_parallel"  # Group for parallel researchers
        
        self.bear_researcher = BearResearcherAgent()
        self.bear_researcher._parallel_group = "researcher_parallel"
        
        self.aggressive_risk = AggressiveRiskAgent()
        self.aggressive_risk._parallel_group = "risk_parallel"  # Group for parallel risk agents
        
        self.conservative_risk = ConservativeRiskAgent()
        self.conservative_risk._parallel_group = "risk_parallel"
        
        self.neutral_risk = NeutralRiskAgent()
        self.neutral_risk._parallel_group = "risk_parallel"
        
        self.portfolio_manager = PortfolioManagerAgent()
        # Portfolio manager runs after parallel groups, no group needed
        
        self.execution_agent = ExecutionAgent(kite=kite, paper_trading=settings.paper_trading_mode)
        # Execution agent runs last, no group needed
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create graph with AgentState
        workflow = StateGraph(AgentState)
        
        # Add analysis agents (parallel execution)
        workflow.add_node("technical_analysis", self._technical_analysis_node)
        workflow.add_node("fundamental_analysis", self._fundamental_analysis_node)
        workflow.add_node("sentiment_analysis", self._sentiment_analysis_node)
        workflow.add_node("macro_analysis", self._macro_analysis_node)
        
        # Add bull vs bear debate agents
        workflow.add_node("bull_researcher", self._bull_researcher_node)
        workflow.add_node("bear_researcher", self._bear_researcher_node)
        
        # Add risk management agents (parallel execution)
        workflow.add_node("aggressive_risk", self._aggressive_risk_node)
        workflow.add_node("conservative_risk", self._conservative_risk_node)
        workflow.add_node("neutral_risk", self._neutral_risk_node)
        
        # Add portfolio manager
        workflow.add_node("portfolio_manager", self._portfolio_manager_node)
        
        # Add execution agent
        workflow.add_node("execution", self._execution_node)
        
        # Define edges
        # START → Analysis agents (parallel)
        workflow.add_edge(START, "technical_analysis")
        workflow.add_edge(START, "fundamental_analysis")
        workflow.add_edge(START, "sentiment_analysis")
        workflow.add_edge(START, "macro_analysis")
        
        # Analysis agents → Bull/Bear researchers
        workflow.add_edge("technical_analysis", "bull_researcher")
        workflow.add_edge("fundamental_analysis", "bull_researcher")
        workflow.add_edge("sentiment_analysis", "bull_researcher")
        workflow.add_edge("macro_analysis", "bull_researcher")
        
        workflow.add_edge("technical_analysis", "bear_researcher")
        workflow.add_edge("fundamental_analysis", "bear_researcher")
        workflow.add_edge("sentiment_analysis", "bear_researcher")
        workflow.add_edge("macro_analysis", "bear_researcher")
        
        # Bull/Bear → Risk management (parallel)
        workflow.add_edge("bull_researcher", "aggressive_risk")
        workflow.add_edge("bear_researcher", "aggressive_risk")
        
        workflow.add_edge("bull_researcher", "conservative_risk")
        workflow.add_edge("bear_researcher", "conservative_risk")
        
        workflow.add_edge("bull_researcher", "neutral_risk")
        workflow.add_edge("bear_researcher", "neutral_risk")
        
        # Risk agents → Portfolio manager
        workflow.add_edge("aggressive_risk", "portfolio_manager")
        workflow.add_edge("conservative_risk", "portfolio_manager")
        workflow.add_edge("neutral_risk", "portfolio_manager")
        
        # Portfolio manager → Execution
        workflow.add_edge("portfolio_manager", "execution")
        
        # Execution → END
        workflow.add_edge("execution", END)
        
        return workflow.compile()
    
    # Node functions - return partial updates to avoid concurrent update conflicts
    def _technical_analysis_node(self, state: AgentState) -> Dict[str, Any]:
        """Technical analysis node."""
        logger.info("🔵 [GRAPH] Executing technical_analysis node...")
        try:
            # Reset parallel group assignments at start of parallel execution
            # This ensures each parallel batch gets fresh provider assignments
            if hasattr(self.technical_agent.llm_manager, '_parallel_assignments'):
                if 'analysis_parallel' not in self.technical_agent.llm_manager._parallel_assignments:
                    self.technical_agent.llm_manager._parallel_assignments['analysis_parallel'] = []
            
            updated_state = self.technical_agent.process(state)
            # Get only new explanations (last one added by this agent)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] technical_analysis node completed")
            return {
                "technical_analysis": updated_state.technical_analysis,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in technical_analysis node: {e}", exc_info=True)
            raise
    
    def _fundamental_analysis_node(self, state: AgentState) -> Dict[str, Any]:
        """Fundamental analysis node."""
        logger.info("🔵 [GRAPH] Executing fundamental_analysis node...")
        try:
            updated_state = self.fundamental_agent.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] fundamental_analysis node completed")
            return {
                "fundamental_analysis": updated_state.fundamental_analysis,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in fundamental_analysis node: {e}", exc_info=True)
            raise
    
    def _sentiment_analysis_node(self, state: AgentState) -> Dict[str, Any]:
        """Sentiment analysis node."""
        logger.info("🔵 [GRAPH] Executing sentiment_analysis node...")
        try:
            updated_state = self.sentiment_agent.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] sentiment_analysis node completed")
            return {
                "sentiment_analysis": updated_state.sentiment_analysis,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in sentiment_analysis node: {e}", exc_info=True)
            raise
    
    def _macro_analysis_node(self, state: AgentState) -> Dict[str, Any]:
        """Macro analysis node."""
        logger.info("🔵 [GRAPH] Executing macro_analysis node...")
        try:
            updated_state = self.macro_agent.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] macro_analysis node completed")
            return {
                "macro_analysis": updated_state.macro_analysis,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in macro_analysis node: {e}", exc_info=True)
            raise
    
    def _bull_researcher_node(self, state: AgentState) -> Dict[str, Any]:
        """Bull researcher node."""
        logger.info("🔵 [GRAPH] Executing bull_researcher node...")
        try:
            # Reset parallel group assignments for researcher parallel execution
            if hasattr(self.bull_researcher.llm_manager, '_parallel_assignments'):
                if 'researcher_parallel' not in self.bull_researcher.llm_manager._parallel_assignments:
                    self.bull_researcher.llm_manager._parallel_assignments['researcher_parallel'] = []
            
            updated_state = self.bull_researcher.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] bull_researcher node completed")
            return {
                "bull_thesis": updated_state.bull_thesis,
                "bull_confidence": updated_state.bull_confidence,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in bull_researcher node: {e}", exc_info=True)
            raise
    
    def _bear_researcher_node(self, state: AgentState) -> Dict[str, Any]:
        """Bear researcher node."""
        logger.info("🔵 [GRAPH] Executing bear_researcher node...")
        try:
            updated_state = self.bear_researcher.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] bear_researcher node completed")
            return {
                "bear_thesis": updated_state.bear_thesis,
                "bear_confidence": updated_state.bear_confidence,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in bear_researcher node: {e}", exc_info=True)
            raise
    
    def _aggressive_risk_node(self, state: AgentState) -> Dict[str, Any]:
        """Aggressive risk node."""
        logger.info("🔵 [GRAPH] Executing aggressive_risk node...")
        try:
            # Reset parallel group assignments for risk parallel execution
            if hasattr(self.aggressive_risk.llm_manager, '_parallel_assignments'):
                if 'risk_parallel' not in self.aggressive_risk.llm_manager._parallel_assignments:
                    self.aggressive_risk.llm_manager._parallel_assignments['risk_parallel'] = []
            
            updated_state = self.aggressive_risk.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] aggressive_risk node completed")
            return {
                "aggressive_risk_recommendation": updated_state.aggressive_risk_recommendation,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in aggressive_risk node: {e}", exc_info=True)
            raise
    
    def _conservative_risk_node(self, state: AgentState) -> Dict[str, Any]:
        """Conservative risk node."""
        logger.info("🔵 [GRAPH] Executing conservative_risk node...")
        try:
            updated_state = self.conservative_risk.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] conservative_risk node completed")
            return {
                "conservative_risk_recommendation": updated_state.conservative_risk_recommendation,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in conservative_risk node: {e}", exc_info=True)
            raise
    
    def _neutral_risk_node(self, state: AgentState) -> Dict[str, Any]:
        """Neutral risk node."""
        logger.info("🔵 [GRAPH] Executing neutral_risk node...")
        try:
            updated_state = self.neutral_risk.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] neutral_risk node completed")
            return {
                "neutral_risk_recommendation": updated_state.neutral_risk_recommendation,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in neutral_risk node: {e}", exc_info=True)
            raise
    
    def _portfolio_manager_node(self, state: AgentState) -> Dict[str, Any]:
        """Portfolio manager node."""
        logger.info("🔵 [GRAPH] Executing portfolio_manager node...")
        try:
            updated_state = self.portfolio_manager.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] portfolio_manager node completed")
            return {
                "final_signal": updated_state.final_signal,
                "trend_signal": updated_state.trend_signal,  # BULLISH, BEARISH, or NEUTRAL
                "position_size": updated_state.position_size,
                "entry_price": updated_state.entry_price,
                "stop_loss": updated_state.stop_loss,
                "take_profit": updated_state.take_profit,
                "agent_explanations": new_explanations,
                # Critical: preserve audit trail (contains executive_summary + pm output)
                "decision_audit_trail": updated_state.decision_audit_trail
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in portfolio_manager node: {e}", exc_info=True)
            raise
    
    def _execution_node(self, state: AgentState) -> Dict[str, Any]:
        """Execution node."""
        logger.info("🔵 [GRAPH] Executing execution node...")
        try:
            updated_state = self.execution_agent.process(state)
            new_explanations = updated_state.agent_explanations[-1:] if updated_state.agent_explanations else []
            logger.info("✅ [GRAPH] execution node completed")
            return {
                "order_id": updated_state.order_id,
                "filled_price": updated_state.filled_price,
                "filled_quantity": updated_state.filled_quantity,
                "execution_timestamp": updated_state.execution_timestamp,
                "trade_id": updated_state.trade_id,
                "agent_explanations": new_explanations
            }
        except Exception as e:
            logger.error(f"❌ [GRAPH] Error in execution node: {e}", exc_info=True)
            raise
    
    def run(self, initial_state: AgentState = None) -> AgentState:
        """Run the trading graph."""
        if initial_state is None:
            if self.state_manager:
                try:
                    initial_state = self.state_manager.initialize_state()
                except Exception as e:
                    logger.warning(f"StateManager.initialize_state failed, falling back to default AgentState: {e}")
                    initial_state = AgentState()
            else:
                initial_state = AgentState()
        
        logger.info("Running trading graph...")
        result = self.graph.invoke(initial_state)
        
        # Convert result dict back to AgentState if needed
        if isinstance(result, dict):
            result = AgentState(**result)
        
        signal_str = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
        logger.info(f"Trading graph completed. Final signal: {signal_str}")
        
        # Store analysis results in MongoDB (even for HOLD decisions)
        self._store_analysis_results(result)
        
        return result
    
    async def arun(self, initial_state: AgentState = None) -> AgentState:
        """Run the trading graph asynchronously."""
        logger.info("=" * 60)
        logger.info("🚀 [GRAPH] Starting trading graph execution...")
        logger.info("=" * 60)
        
        if initial_state is None:
            logger.info("📊 [GRAPH] Initializing state from market data...")
            if self.state_manager:
                initial_state = self.state_manager.initialize_state()
                logger.info(f"✅ [GRAPH] State initialized: price={initial_state.current_price}, news_items={len(initial_state.latest_news)}")
            else:
                logger.warning("⚠️ [GRAPH] No state manager, using empty state")
                initial_state = AgentState()
        
        logger.info("🔄 [GRAPH] Invoking graph with LangGraph...")
        logger.info(f"📋 [GRAPH] Initial state: price={initial_state.current_price}, ohlc_1min={len(initial_state.ohlc_1min)}")
        
        try:
            result = await self.graph.ainvoke(initial_state)
            logger.info("✅ [GRAPH] Graph execution completed successfully")
        except Exception as e:
            logger.error(f"❌ [GRAPH] Graph execution failed: {e}", exc_info=True)
            raise
        
        # Convert result dict or LangGraph result into AgentState if needed
        if isinstance(result, dict):
            result = AgentState(**result)
        else:
            try:
                if not isinstance(result, AgentState):
                    state_dict = None
                    if hasattr(result, 'model_dump'):
                        try:
                            state_dict = result.model_dump()
                        except Exception:
                            state_dict = None
                    if state_dict is None and hasattr(result, 'dict'):
                        try:
                            state_dict = result.dict()
                        except Exception:
                            state_dict = None
                    if state_dict is None and hasattr(result, 'to_dict'):
                        try:
                            state_dict = result.to_dict()
                        except Exception:
                            state_dict = None
                    if state_dict is None:
                        keys = ['final_signal','trend_signal','agent_explanations','_portfolio_manager_output','decision_audit_trail','agent_decisions','current_price','ohlc_1min','technical_analysis','fundamental_analysis','sentiment_analysis','macro_analysis']
                        state_dict = {}
                        for k in keys:
                            v = getattr(result, k, None)
                            if v is not None:
                                state_dict[k] = v
                    try:
                        result = AgentState(**state_dict)
                        logger.info("[GRAPH] Converted LangGraph result to AgentState for persistence")
                    except Exception:
                        # Keep original 'result' (likely a LangGraph _RunResult) if conversion failed
                        pass
            except Exception:
                pass

        # If LangGraph returned a result without agent outputs (e.g., test shims),
        # fall back to running agents sequentially so verification can proceed.
        try:
            # Ensure we have an AgentState to inspect
            state_for_check = result if isinstance(result, AgentState) else initial_state if initial_state is not None else None
            missing_agents = True
            if state_for_check is not None:
                tech = getattr(state_for_check, 'technical_analysis', None)
                fund = getattr(state_for_check, 'fundamental_analysis', None)
                sent = getattr(state_for_check, 'sentiment_analysis', None)
                macro = getattr(state_for_check, 'macro_analysis', None)
                # Consider agent present if any of these are non-empty dicts or non-empty values
                if any([tech, fund, sent, macro]):
                    missing_agents = False
            if missing_agents:
                logger.warning("⚠️ [GRAPH] LangGraph returned no agent outputs — running agents sequentially as fallback for verification")
                # Start from a fresh or initial AgentState to run agents sequentially
                fallback_state = initial_state if initial_state is not None else AgentState()
                try:
                    # Run analysis agents
                    fallback_state = self.technical_agent.process(fallback_state)
                    fallback_state = self.fundamental_agent.process(fallback_state)
                    fallback_state = self.sentiment_agent.process(fallback_state)
                    fallback_state = self.macro_agent.process(fallback_state)
                    
                    # Run bull/bear researchers (critical for confidence and reasoning!)
                    fallback_state = self.bull_researcher.process(fallback_state)
                    fallback_state = self.bear_researcher.process(fallback_state)
                    
                    # Run risk agents
                    fallback_state = self.aggressive_risk.process(fallback_state)
                    fallback_state = self.conservative_risk.process(fallback_state)
                    fallback_state = self.neutral_risk.process(fallback_state)
                    
                    # Run portfolio manager (makes final decision)
                    fallback_state = self.portfolio_manager.process(fallback_state)
                    
                    # Use fallback_state as the result from now on
                    result = fallback_state
                except Exception as e:
                    logger.error(f"Fallback sequential agent execution failed: {e}", exc_info=True)
        except Exception:
            # Keep silent and continue with whatever result we have
            pass

        signal_str = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
        logger.info(f"Trading graph completed. Final signal: {signal_str}")
        
        # Store analysis results in MongoDB (even for HOLD decisions)
        self._store_analysis_results(result)
        
        return result
    
    def _store_analysis_results(self, state: AgentState):
        """Store agent analysis results in MongoDB."""
        try:
            from mongodb_schema import get_mongo_client, get_collection
            from config.settings import settings
            from datetime import datetime, timezone
            
            mongo_client = get_mongo_client()
            db = mongo_client[settings.mongodb_db_name]
            analysis_collection = get_collection(db, "agent_decisions")
            
            def _fmt_signal(x):
                if x is None:
                    return None
                try:
                    return x.value if hasattr(x, 'value') else str(x)
                except Exception:
                    try:
                        return str(x)
                    except Exception:
                        return None

            # If `state` is not an AgentState (e.g., LangGraph _RunResult), attempt a safe conversion
            try:
                from agents.state import AgentState
                if not isinstance(state, AgentState):
                    state_dict = None
                    if hasattr(state, 'model_dump'):
                        try:
                            state_dict = state.model_dump()
                        except Exception:
                            state_dict = None
                    if state_dict is None and hasattr(state, 'dict'):
                        try:
                            state_dict = state.dict()
                        except Exception:
                            state_dict = None
                    if state_dict is None and hasattr(state, 'to_dict'):
                        try:
                            state_dict = state.to_dict()
                        except Exception:
                            state_dict = None
                    if state_dict is None:
                        # Fallback: pull a small set of known fields
                        keys = ['final_signal','trend_signal','agent_explanations','_portfolio_manager_output','decision_audit_trail','agent_decisions','current_price','ohlc_1min','technical_analysis','fundamental_analysis','sentiment_analysis','macro_analysis']
                        state_dict = {}
                        for k in keys:
                            v = getattr(state, k, None)
                            if v is not None:
                                state_dict[k] = v
                    # Try to construct an AgentState from collected data
                    try:
                        state = AgentState(**state_dict)
                    except Exception:
                        # If conversion fails, keep original `state` and rely on safe getattr() later
                        pass
            except Exception:
                # If agents.state can't be imported or any other error occurs, continue
                pass

            signal_str = _fmt_signal(getattr(state, 'final_signal', None))
            trend_signal_str = _fmt_signal(getattr(state, 'trend_signal', None))
            
            # Get portfolio manager output (stored via update_state)
            # Portfolio manager stores output with agent_name="portfolio_manager"
            portfolio_output = {}
            if hasattr(state, '_portfolio_manager_output') and state._portfolio_manager_output:
                portfolio_output = state._portfolio_manager_output
            else:
                # Fallback: Try to extract from explanation string
                # Format: "bullish_score=X.XX, bearish_score=X.XX"
                import re
                bullish_score = 0.0
                bearish_score = 0.0
                
                agent_explanations = getattr(state, 'agent_explanations', []) or []
                for exp in agent_explanations:
                    if "Portfolio decision" in exp:
                        bullish_match = re.search(r'bullish_score=([\d.]+)', exp)
                        bearish_match = re.search(r'bearish_score=([\d.]+)', exp)
                        if bullish_match:
                            try:
                                bullish_score = float(bullish_match.group(1))
                            except ValueError:
                                pass
                        if bearish_match:
                            try:
                                bearish_score = float(bearish_match.group(1))
                            except ValueError:
                                pass
                        break
                
                portfolio_output = {
                    "signal": signal_str,
                    "trend_signal": trend_signal_str,
                    "bullish_score": bullish_score,
                    "bearish_score": bearish_score
                }
            
            # Merge in persisted PM output from audit trail (survives LangGraph reductions/copies)
            try:
                pm_from_audit = (getattr(state, 'decision_audit_trail', {}) or {}).get("portfolio_manager_output") or {}
                if isinstance(pm_from_audit, dict) and pm_from_audit:
                    portfolio_output = {**pm_from_audit, **portfolio_output}
            except Exception:
                pass

            # Determine executive summary (prefer PM output, fallback to audit trail)
            executive_summary = None
            try:
                executive_summary = portfolio_output.get("executive_summary")
                if not executive_summary:
                    executive_summary = (state.decision_audit_trail or {}).get("executive_summary")
            except Exception:
                executive_summary = None
            
            # Store analysis document
            analysis_doc = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "instrument": settings.instrument_symbol,  # Add instrument for filtering
                "instrument_name": settings.instrument_name,
                "current_price": getattr(state, 'current_price', None),
                "final_signal": signal_str,
                "trend_signal": trend_signal_str,  # BULLISH, BEARISH, or NEUTRAL
                "position_size": getattr(state, 'position_size', None),
                "entry_price": getattr(state, 'entry_price', None),
                "stop_loss": getattr(state, 'stop_loss', None),
                "take_profit": getattr(state, 'take_profit', None),
                "agent_decisions": {
                    "technical": getattr(state, 'technical_analysis', {}) or {},
                    "fundamental": getattr(state, 'fundamental_analysis', {}) or {},
                    "sentiment": getattr(state, 'sentiment_analysis', {}) or {},
                    "macro": getattr(state, 'macro_analysis', {}) or {},
                    "bull": {
                        "thesis": getattr(state, 'bull_thesis', ''),
                        "confidence": getattr(state, 'bull_confidence', 0.0)
                    },
                    "bear": {
                        "thesis": getattr(state, 'bear_thesis', ''),
                        "confidence": getattr(state, 'bear_confidence', 0.0)
                    },
                    "aggressive_risk": getattr(state, 'aggressive_risk_recommendation', {}) or {},
                    "conservative_risk": getattr(state, 'conservative_risk_recommendation', {}) or {},
                    "neutral_risk": getattr(state, 'neutral_risk_recommendation', {}) or {},
                    "portfolio_manager": portfolio_output
                },
                "agent_explanations": getattr(state, 'agent_explanations', []) or [],
                "decision_audit_trail": getattr(state, 'decision_audit_trail', {}) or {},
                "status": "ANALYSIS",  # Mark as analysis (not a trade)
                "executive_summary": executive_summary  # Store LLM-generated summary at top level
            }
            
            # If any agent returned incomplete JSON, mark analysis as INCOMPLETE and emit alert
            def _find_incomplete(d, path=None, out=None):
                if out is None:
                    out = []
                if path is None:
                    path = []
                if isinstance(d, dict):
                    if d.get('__incomplete_json'):
                        out.append('.'.join(path) or 'root')
                    for k, v in d.items():
                        if isinstance(v, (dict, list)):
                            _find_incomplete(v, path + [k], out)
                elif isinstance(d, list):
                    for i, v in enumerate(d):
                        if isinstance(v, (dict, list)):
                            _find_incomplete(v, path + [str(i)], out)
                return out
            
            incomplete_agents = _find_incomplete(analysis_doc['agent_decisions'])
            if incomplete_agents:
                analysis_doc['status'] = 'INCOMPLETE'
                # Persist list of incomplete agents for downstream visibility
                analysis_doc['incomplete_agents'] = incomplete_agents
                try:
                    alerts_collection = get_collection(db, 'alerts')
                    alerts_collection.insert_one({
                        'type': 'analysis_incomplete',
                        'agents': incomplete_agents,
                        'timestamp': datetime.now().isoformat(),
                        'message': f'Incomplete JSON from agents: {incomplete_agents}',
                        'context': {
                            'final_signal': signal_str,
                            'trend_signal': trend_signal_str
                        }
                    })
                except Exception as e:
                    logger.debug(f"Failed to write analysis incomplete alert: {e}")
            
            analysis_collection.insert_one(analysis_doc)
            logger.info(f"✅ Stored agent analysis results in MongoDB (signal: {signal_str})")
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}", exc_info=True)


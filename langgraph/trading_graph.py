"""Main trading graph with LangGraph orchestration."""

import logging
from typing import Dict, Any
try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    # Fallback if langgraph package structure is different
    import sys
    import importlib
    langgraph_module = importlib.import_module('langgraph')
    StateGraph = getattr(langgraph_module.graph, 'StateGraph')
    START = getattr(langgraph_module.graph, 'START')
    END = getattr(langgraph_module.graph, 'END')
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
from langgraph.state_manager import StateManager  # Local module
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
        self.technical_agent = TechnicalAnalysisAgent()
        self.fundamental_agent = FundamentalAnalysisAgent()
        self.sentiment_agent = SentimentAnalysisAgent()
        self.macro_agent = MacroAnalysisAgent()
        self.bull_researcher = BullResearcherAgent()
        self.bear_researcher = BearResearcherAgent()
        self.aggressive_risk = AggressiveRiskAgent()
        self.conservative_risk = ConservativeRiskAgent()
        self.neutral_risk = NeutralRiskAgent()
        self.portfolio_manager = PortfolioManagerAgent()
        self.execution_agent = ExecutionAgent(kite=kite, paper_trading=settings.paper_trading_mode)
        
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
    
    # Node functions
    def _technical_analysis_node(self, state: AgentState) -> AgentState:
        """Technical analysis node."""
        return self.technical_agent.process(state)
    
    def _fundamental_analysis_node(self, state: AgentState) -> AgentState:
        """Fundamental analysis node."""
        return self.fundamental_agent.process(state)
    
    def _sentiment_analysis_node(self, state: AgentState) -> AgentState:
        """Sentiment analysis node."""
        return self.sentiment_agent.process(state)
    
    def _macro_analysis_node(self, state: AgentState) -> AgentState:
        """Macro analysis node."""
        return self.macro_agent.process(state)
    
    def _bull_researcher_node(self, state: AgentState) -> AgentState:
        """Bull researcher node."""
        return self.bull_researcher.process(state)
    
    def _bear_researcher_node(self, state: AgentState) -> AgentState:
        """Bear researcher node."""
        return self.bear_researcher.process(state)
    
    def _aggressive_risk_node(self, state: AgentState) -> AgentState:
        """Aggressive risk node."""
        return self.aggressive_risk.process(state)
    
    def _conservative_risk_node(self, state: AgentState) -> AgentState:
        """Conservative risk node."""
        return self.conservative_risk.process(state)
    
    def _neutral_risk_node(self, state: AgentState) -> AgentState:
        """Neutral risk node."""
        return self.neutral_risk.process(state)
    
    def _portfolio_manager_node(self, state: AgentState) -> AgentState:
        """Portfolio manager node."""
        return self.portfolio_manager.process(state)
    
    def _execution_node(self, state: AgentState) -> AgentState:
        """Execution node."""
        return self.execution_agent.process(state)
    
    def run(self, initial_state: AgentState = None) -> AgentState:
        """Run the trading graph."""
        if initial_state is None:
            if self.state_manager:
                initial_state = self.state_manager.initialize_state()
            else:
                initial_state = AgentState()
        
        logger.info("Running trading graph...")
        result = self.graph.invoke(initial_state)
        logger.info(f"Trading graph completed. Final signal: {result.final_signal.value}")
        
        return result
    
    async def arun(self, initial_state: AgentState = None) -> AgentState:
        """Run the trading graph asynchronously."""
        if initial_state is None:
            if self.state_manager:
                initial_state = self.state_manager.initialize_state()
            else:
                initial_state = AgentState()
        
        logger.info("Running trading graph (async)...")
        result = await self.graph.ainvoke(initial_state)
        logger.info(f"Trading graph completed. Final signal: {result.final_signal.value}")
        
        return result


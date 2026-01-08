"""Agent Factory - Unified agent initialization with full roster.

This module provides a factory for creating and configuring all available agents
in the trading system, including:
- Analysis Tier: Technical, Sentiment, Macro, Fundamental
- Research Tier: Bull/Bear Researchers  
- Technical Specialists: Momentum, Trend, Volume, MeanReversion
- Validators: Risk, Execution

Supports weighted voting and risk veto mechanisms.
"""

import logging
from typing import Any, Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class AgentProfile(str, Enum):
    """Predefined agent profiles for different trading styles."""
    CONSERVATIVE = "conservative"  # Risk-focused with fewer aggressive agents
    BALANCED = "balanced"          # All agents with standard weights
    AGGRESSIVE = "aggressive"      # Higher weight on technical/momentum agents
    RESEARCH_HEAVY = "research"    # Include all research agents


class AgentFactory:
    """Factory for creating and managing trading agents."""
    
    def __init__(self, profile: AgentProfile = AgentProfile.BALANCED):
        """Initialize agent factory with specified profile.
        
        Args:
            profile: Trading profile determining which agents to activate
        """
        self.profile = profile
        self.agents: List[Any] = []
        
    def build_all_agents(self, **kwargs: Any) -> List[Any]:
        """Build complete agent roster based on profile.
        
        Args:
            **kwargs: Configuration parameters for agents
            
        Returns:
            List of initialized agents
        """
        agents = []
        
        # Analysis Tier - Always included (highest weight: 1.5x)
        agents.extend(self._build_analysis_tier(**kwargs))
        
        # Technical Specialists - Always included (standard weight: 1.0x)
        agents.extend(self._build_technical_specialists(**kwargs))
        
        # Research Tier - Include based on profile (lower weight: 0.5x)
        if self.profile in [AgentProfile.BALANCED, AgentProfile.RESEARCH_HEAVY]:
            agents.extend(self._build_research_tier(**kwargs))
        
        # Risk & Execution - Always included (risk has veto: 2.0x)
        agents.extend(self._build_validators(**kwargs))
        
        logger.info(f"Built {len(agents)} agents for profile: {self.profile.value}")
        self.agents = agents
        return agents
    
    def _build_analysis_tier(self, **kwargs: Any) -> List[Any]:
        """Build high-level analysis agents (Technical, Sentiment, Macro, Fundamental)."""
        agents = []
        
        try:
            from engine_module.agents.technical_agent import TechnicalAgent
            agent = TechnicalAgent()
            agent._agent_name = "TechnicalAgent"
            agents.append(agent)
            logger.debug("Added TechnicalAgent")
        except ImportError as e:
            logger.warning(f"Could not import TechnicalAgent: {e}")
        
        try:
            from engine_module.agents.sentiment_agent import SentimentAgent
            agent = SentimentAgent()
            agent._agent_name = "SentimentAgent"
            agents.append(agent)
            logger.debug("Added SentimentAgent")
        except ImportError as e:
            logger.warning(f"Could not import SentimentAgent: {e}")
        
        try:
            from engine_module.agents.macro_agent import MacroAgent
            agent = MacroAgent()
            agent._agent_name = "MacroAgent"
            agents.append(agent)
            logger.debug("Added MacroAgent")
        except ImportError as e:
            logger.warning(f"Could not import MacroAgent: {e}")
        
        try:
            from engine_module.agents.fundamental_agent import FundamentalAgent
            agent = FundamentalAgent()
            agent._agent_name = "FundamentalAgent"
            agents.append(agent)
            logger.debug("Added FundamentalAgent")
        except ImportError as e:
            logger.warning(f"Could not import FundamentalAgent: {e}")
        
        return agents
    
    def _build_technical_specialists(self, **kwargs: Any) -> List[Any]:
        """Build specialized technical agents (Momentum, Trend, Volume, MeanReversion)."""
        agents = []
        
        try:
            from engine_module.agents.momentum_agent import MomentumAgent
            agent = MomentumAgent()
            agent._agent_name = "MomentumAgent"
            agents.append(agent)
            logger.debug("Added MomentumAgent")
        except ImportError as e:
            logger.warning(f"Could not import MomentumAgent: {e}")
        
        try:
            from engine_module.agents.trend_agent import TrendAgent
            agent = TrendAgent()
            agent._agent_name = "TrendAgent"
            agents.append(agent)
            logger.debug("Added TrendAgent")
        except ImportError as e:
            logger.warning(f"Could not import TrendAgent: {e}")
        
        try:
            from engine_module.agents.volume_agent import VolumeAgent
            agent = VolumeAgent()
            agent._agent_name = "VolumeAgent"
            agents.append(agent)
            logger.debug("Added VolumeAgent")
        except ImportError as e:
            logger.warning(f"Could not import VolumeAgent: {e}")
        
        try:
            from engine_module.agents.mean_reversion_agent import MeanReversionAgent
            agent = MeanReversionAgent()
            agent._agent_name = "MeanReversionAgent"
            agents.append(agent)
            logger.debug("Added MeanReversionAgent")
        except ImportError as e:
            logger.warning(f"Could not import MeanReversionAgent: {e}")
        
        return agents
    
    def _build_research_tier(self, **kwargs: Any) -> List[Any]:
        """Build research agents (Bull/Bear researchers for contrarian views)."""
        agents = []
        
        try:
            from engine_module.agents.bull_researcher import BullResearcher
            agent = BullResearcher()
            agent._agent_name = "BullResearcher"
            agents.append(agent)
            logger.debug("Added BullResearcher")
        except ImportError as e:
            logger.warning(f"Could not import BullResearcher: {e}")
        
        try:
            from engine_module.agents.bear_researcher import BearResearcher
            agent = BearResearcher()
            agent._agent_name = "BearResearcher"
            agents.append(agent)
            logger.debug("Added BearResearcher")
        except ImportError as e:
            logger.warning(f"Could not import BearResearcher: {e}")
        
        return agents
    
    def _build_validators(self, **kwargs: Any) -> List[Any]:
        """Build validator agents (Risk with veto power, Execution)."""
        agents = []
        
        # Risk agent selection based on profile
        risk_profile = kwargs.get('risk_profile', 'neutral')
        
        try:
            from engine_module.agents.risk_agents import (
                RiskAgent, 
                ConservativeRiskAgent, 
                AggressiveRiskAgent,
                NeutralRiskAgent
            )
            
            if self.profile == AgentProfile.CONSERVATIVE:
                agent = ConservativeRiskAgent()
                agent._agent_name = "ConservativeRiskAgent"
            elif self.profile == AgentProfile.AGGRESSIVE:
                agent = AggressiveRiskAgent()
                agent._agent_name = "AggressiveRiskAgent"
            else:
                agent = NeutralRiskAgent()
                agent._agent_name = "NeutralRiskAgent"
            
            agents.append(agent)
            logger.debug(f"Added {agent._agent_name}")
        except ImportError as e:
            logger.warning(f"Could not import RiskAgent: {e}")
        
        try:
            from engine_module.agents.execution_agent import ExecutionAgent
            agent = ExecutionAgent()
            agent._agent_name = "ExecutionAgent"
            agents.append(agent)
            logger.debug("Added ExecutionAgent")
        except ImportError as e:
            logger.warning(f"Could not import ExecutionAgent: {e}")
        
        return agents
    
    def get_agent_summary(self) -> Dict[str, Any]:
        """Get summary of active agents and their configuration.
        
        Returns:
            Dictionary with agent counts and categories
        """
        if not self.agents:
            return {
                "total_agents": 0,
                "profile": self.profile.value,
                "categories": {}
            }
        
        categories = {
            "analysis": [],
            "technical_specialists": [],
            "research": [],
            "risk": [],
            "execution": []
        }
        
        for agent in self.agents:
            name = getattr(agent, '_agent_name', agent.__class__.__name__)
            
            if any(x in name.lower() for x in ['technical', 'sentiment', 'macro', 'fundamental']):
                if 'agent' in name.lower() and not any(x in name.lower() for x in ['momentum', 'trend', 'volume', 'reversion']):
                    categories["analysis"].append(name)
                else:
                    categories["technical_specialists"].append(name)
            elif any(x in name.lower() for x in ['momentum', 'trend', 'volume', 'reversion']):
                categories["technical_specialists"].append(name)
            elif any(x in name.lower() for x in ['bull', 'bear', 'research']):
                categories["research"].append(name)
            elif 'risk' in name.lower():
                categories["risk"].append(name)
            elif 'execution' in name.lower():
                categories["execution"].append(name)
        
        return {
            "total_agents": len(self.agents),
            "profile": self.profile.value,
            "categories": {k: v for k, v in categories.items() if v},
            "agent_names": [getattr(a, '_agent_name', a.__class__.__name__) for a in self.agents]
        }


def create_default_agents(profile: str = "balanced", **kwargs: Any) -> List[Any]:
    """Convenience function to create default agent roster.
    
    Args:
        profile: One of 'conservative', 'balanced', 'aggressive', 'research'
        **kwargs: Additional configuration for agents
        
    Returns:
        List of initialized agents
        
    Example:
        >>> agents = create_default_agents(profile='balanced')
        >>> # Returns 12+ agents with balanced weighting
    """
    try:
        profile_enum = AgentProfile(profile)
    except ValueError:
        logger.warning(f"Invalid profile '{profile}', defaulting to balanced")
        profile_enum = AgentProfile.BALANCED
    
    factory = AgentFactory(profile=profile_enum)
    agents = factory.build_all_agents(**kwargs)
    
    summary = factory.get_agent_summary()
    logger.info(f"Created {summary['total_agents']} agents: {summary['agent_names']}")
    
    return agents


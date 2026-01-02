"""Risk Management Agents (Aggressive, Conservative, Neutral)."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from config.settings import settings

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """Base risk management agent."""
    
    def __init__(self, agent_name: str, risk_profile: str):
        """Initialize risk agent."""
        self.risk_profile = risk_profile
        super().__init__(agent_name, self._get_default_prompt())
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return f"""You are the {self.risk_profile} Risk Management Agent.
Calculate position size, stop-loss, and leverage recommendations based on {self.risk_profile} risk profile."""
    
    def _calculate_position_size(
        self,
        account_value: float,
        current_price: float,
        risk_pct: float,
        stop_loss_pct: float
    ) -> int:
        """Calculate position size based on risk parameters."""
        # Risk amount = account_value * risk_pct
        risk_amount = account_value * (risk_pct / 100)
        
        # Stop loss amount per unit = current_price * stop_loss_pct
        stop_loss_per_unit = current_price * (stop_loss_pct / 100)
        
        # Position size = risk_amount / stop_loss_per_unit
        if stop_loss_per_unit > 0:
            position_size = int(risk_amount / stop_loss_per_unit)
        else:
            position_size = 0
        
        return position_size
    
    def process(self, state: AgentState) -> AgentState:
        """Process risk assessment."""
        logger.info(f"Processing {self.risk_profile} risk assessment...")
        
        try:
            current_price = state.current_price
            if not current_price or current_price == 0:
                logger.warning("No current price available for risk calculation")
                output = {
                    "position_size": 0,
                    "stop_loss_pct": 0.0,
                    "leverage": 1.0,
                    "risk_amount": 0.0
                }
                self.update_state(state, output, "No price data")
                return state
            
            # Get risk parameters based on profile
            if self.risk_profile == "aggressive":
                risk_pct = 3.0  # Accept 3% portfolio risk
                stop_loss_pct = 2.0  # 2% stop loss
                leverage = 1.5  # 1.5x leverage
            elif self.risk_profile == "conservative":
                risk_pct = 1.0  # Accept 1% portfolio risk
                stop_loss_pct = 1.0  # 1% stop loss
                leverage = 1.0  # No leverage
            else:  # neutral
                risk_pct = 2.0  # Accept 2% portfolio risk
                stop_loss_pct = 1.5  # 1.5% stop loss
                leverage = 1.25  # 1.25x leverage
            
            # Assume account value (in production, fetch from Kite API)
            account_value = 1000000  # Default 10 lakh
            
            # Calculate position size
            position_size = self._calculate_position_size(
                account_value,
                current_price,
                risk_pct,
                stop_loss_pct
            )
            
            # Calculate stop loss price
            # Handle both enum and string signals
            signal_str = state.final_signal.value if hasattr(state.final_signal, 'value') else str(state.final_signal)
            
            if signal_str == "BUY":
                stop_loss_price = current_price * (1 - stop_loss_pct / 100)
            elif signal_str == "SELL":
                stop_loss_price = current_price * (1 + stop_loss_pct / 100)
            else:
                stop_loss_price = current_price
            
            output = {
                "position_size": position_size,
                "stop_loss_pct": stop_loss_pct,
                "stop_loss_price": stop_loss_price,
                "leverage": leverage,
                "risk_amount": account_value * (risk_pct / 100),
                "risk_pct": risk_pct
            }
            
            explanation = f"{self.risk_profile} risk: position_size={position_size}, "
            explanation += f"stop_loss={stop_loss_pct}%, leverage={leverage}x"
            
            self.update_state(state, output, explanation)
            
        except Exception as e:
            logger.error(f"Error in {self.risk_profile} risk assessment: {e}")
            output = {
                "error": str(e),
                "position_size": 0,
                "stop_loss_pct": 0.0,
                "leverage": 1.0
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state


class AggressiveRiskAgent(RiskAgent):
    """Aggressive risk management agent."""
    
    def __init__(self):
        super().__init__("aggressive_risk", "aggressive")


class ConservativeRiskAgent(RiskAgent):
    """Conservative risk management agent."""
    
    def __init__(self):
        super().__init__("conservative_risk", "conservative")


class NeutralRiskAgent(RiskAgent):
    """Neutral risk management agent."""
    
    def __init__(self):
        super().__init__("neutral_risk", "neutral")


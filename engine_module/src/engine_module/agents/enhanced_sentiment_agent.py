"""Enhanced Sentiment Agent with comprehensive reasoning and conditional signal generation."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from .enhanced_agent import EnhancedAgent, AgentAnalysis, ConditionalSignal, AgentContext

logger = logging.getLogger(__name__)


class EnhancedSentimentAgent(EnhancedAgent):
    """Enhanced sentiment agent with natural language reasoning and conditional signals."""

    def __init__(self):
        super().__init__("EnhancedSentimentAgent")

    @property
    def agent_inputs(self) -> List[str]:
        """Document what inputs this agent requires."""
        return [
            "Latest financial news articles",
            "Sentiment scores from news analysis",
            "Market price data",
            "Trading volume data",
            "Outputs from other agents (macro analysis, technical analysis)"
        ]

    @property
    def agent_objectives(self) -> List[str]:
        """Document what this agent aims to achieve."""
        return [
            "Assess current market sentiment from news and social data",
            "Identify sentiment-driven market psychology",
            "Generate conditional signals based on sentiment shifts",
            "Provide insights for other agents about market mood",
            "Detect sentiment divergences that may signal reversals"
        ]

    @property
    def agent_methodology(self) -> str:
        """Document how this agent works."""
        return """
        I analyze news sentiment using a combination of automated sentiment scoring and contextual analysis.
        I look for patterns in news flow, sentiment trends, and correlations with price action.
        I generate conditional signals when sentiment reaches extreme levels or shows reversal patterns.
        I communicate market psychology insights to other agents for more informed decision making.
        """

    async def analyze(self, context: AgentContext) -> AgentAnalysis:
        """Perform comprehensive sentiment analysis."""
        start_time = datetime.now()

        # Extract relevant data from context
        news_data = context.news_data
        market_data = context.market_data
        technical_data = context.technical_data

        # Get data from other agents
        macro_analysis = context.agent_outputs.get("EnhancedMacroAgent", {})
        technical_analysis = context.agent_outputs.get("EnhancedTechnicalAgent", {})

        # Perform sentiment analysis
        sentiment_score = news_data.get("sentiment_score", 0.0)
        latest_news = news_data.get("latest_news", [])
        news_count = len(latest_news)

        # Analyze sentiment trends and patterns
        sentiment_trend = self._analyze_sentiment_trend(sentiment_score, latest_news)
        sentiment_extremes = self._detect_sentiment_extremes(sentiment_score, news_count)

        # Generate insights
        key_insights = self._generate_sentiment_insights(
            sentiment_score, sentiment_trend, latest_news, market_data
        )

        # Generate conditional signals
        conditional_signals = self._generate_conditional_signals(
            context, sentiment_score, sentiment_trend, sentiment_extremes
        )

        # Assess risks
        risks_identified = self._assess_sentiment_risks(
            sentiment_score, sentiment_trend, macro_analysis, technical_analysis
        )

        # Build comprehensive reasoning
        reasoning = self.build_reasoning_text(key_insights, context)
        reasoning += self._build_sentiment_specific_reasoning(
            sentiment_score, sentiment_trend, news_count, risks_identified
        )

        # Determine immediate decision (if any)
        immediate_decision, confidence = self._determine_immediate_action(
            sentiment_score, sentiment_trend, sentiment_extremes
        )

        # Prepare outputs for other agents
        outputs_for_other_agents = {
            "sentiment_score": sentiment_score,
            "sentiment_trend": sentiment_trend,
            "sentiment_extremes": sentiment_extremes,
            "market_psychology": "bullish" if sentiment_score > 0.2 else "bearish" if sentiment_score < -0.2 else "neutral",
            "sentiment_confidence": confidence,
            "sentiment_insights": key_insights[:3],  # Top 3 insights
            "sentiment_risks": risks_identified
        }

        processing_time = (datetime.now() - start_time).total_seconds()

        return AgentAnalysis(
            agent_name=self.name,
            inputs=self.agent_inputs,
            objectives=self.agent_objectives,
            methodology=self.agent_methodology,
            immediate_decision=immediate_decision,
            confidence=confidence,
            conditional_signals=conditional_signals,
            reasoning=reasoning,
            key_insights=key_insights,
            risks_identified=risks_identified,
            outputs_for_other_agents=outputs_for_other_agents,
            processing_time_seconds=processing_time,
            data_quality_score=self._assess_data_quality(context)
        )

    def _analyze_sentiment_trend(self, current_sentiment: float, news_items: List[Dict]) -> str:
        """Analyze the trend in sentiment over recent news."""
        if not news_items:
            return "insufficient_data"

        # Simple trend analysis - in real implementation, this would look at time series
        positive_count = sum(1 for item in news_items if (item.get('sentiment_score') or 0) > 0.1)
        negative_count = sum(1 for item in news_items if (item.get('sentiment_score') or 0) < -0.1)

        if positive_count > negative_count * 1.5:
            return "improving"
        elif negative_count > positive_count * 1.5:
            return "deteriorating"
        elif abs(current_sentiment) < 0.1:
            return "neutral"
        else:
            return "stable"

    def _detect_sentiment_extremes(self, sentiment_score: float, news_count: int) -> Dict[str, Any]:
        """Detect if sentiment is at extreme levels."""
        return {
            "is_extreme_bullish": sentiment_score > 0.6,
            "is_extreme_bearish": sentiment_score < -0.6,
            "is_high_confidence": abs(sentiment_score) > 0.4 and news_count >= 3,
            "sentiment_magnitude": abs(sentiment_score)
        }

    def _generate_sentiment_insights(
        self,
        sentiment_score: float,
        sentiment_trend: str,
        news_items: List[Dict],
        market_data: Dict[str, Any]
    ) -> List[str]:
        """Generate key insights from sentiment analysis."""
        insights = []

        # Sentiment level assessment
        if sentiment_score > 0.4:
            insights.append("Market sentiment is strongly bullish with positive news flow")
        elif sentiment_score > 0.1:
            insights.append("Market sentiment is mildly bullish")
        elif sentiment_score < -0.4:
            insights.append("Market sentiment is strongly bearish with negative news flow")
        elif sentiment_score < -0.1:
            insights.append("Market sentiment is mildly bearish")
        else:
            insights.append("Market sentiment is neutral with balanced news flow")

        # Trend analysis
        if sentiment_trend == "improving":
            insights.append("Sentiment is trending positive, suggesting improving market mood")
        elif sentiment_trend == "deteriorating":
            insights.append("Sentiment is trending negative, indicating worsening market psychology")

        # News volume analysis
        if len(news_items) > 10:
            insights.append("High news volume suggests significant market attention")
        elif len(news_items) < 3:
            insights.append("Limited news coverage may indicate low market activity")

        return insights

    def _generate_conditional_signals(
        self,
        context: AgentContext,
        sentiment_score: float,
        sentiment_trend: str,
        sentiment_extremes: Dict[str, Any]
    ) -> List[ConditionalSignal]:
        """Generate conditional signals based on sentiment analysis."""
        signals = []
        instrument = context.market_data.get('instrument', 'BANKNIFTY')

        # Extreme sentiment reversal signal
        if sentiment_extremes["is_extreme_bullish"] and sentiment_trend == "deteriorating":
            signals.append(self.create_conditional_signal(
                instrument=instrument,
                condition_type="sentiment_reversal",
                condition_params={
                    "sentiment_threshold": -0.2,
                    "time_window_minutes": 30,
                    "confirmation_required": "price_decline"
                },
                action="SELL",
                confidence=0.75,
                reasoning="Extreme bullish sentiment showing signs of reversal - prepare to sell on sentiment breakdown",
                priority=4
            ))

        elif sentiment_extremes["is_extreme_bearish"] and sentiment_trend == "improving":
            signals.append(self.create_conditional_signal(
                instrument=instrument,
                condition_type="sentiment_reversal",
                condition_params={
                    "sentiment_threshold": 0.2,
                    "time_window_minutes": 30,
                    "confirmation_required": "price_rally"
                },
                action="BUY",
                confidence=0.75,
                reasoning="Extreme bearish sentiment showing signs of reversal - prepare to buy on sentiment recovery",
                priority=4
            ))

        # Sentiment divergence signal
        current_price = context.market_data.get('current_price')
        if current_price and sentiment_score > 0.3 and context.market_data.get('price_change_pct', 0) < -1:
            signals.append(self.create_conditional_signal(
                instrument=instrument,
                condition_type="sentiment_divergence",
                condition_params={
                    "price_decline_threshold": -2.0,
                    "sentiment_min": 0.3,
                    "volume_confirmation": True
                },
                action="BUY",
                confidence=0.65,
                reasoning="Positive sentiment diverging from falling prices - potential buying opportunity",
                priority=3
            ))

        return signals

    def _assess_sentiment_risks(
        self,
        sentiment_score: float,
        sentiment_trend: str,
        macro_analysis: Dict[str, Any],
        technical_analysis: Dict[str, Any]
    ) -> List[str]:
        """Assess risks related to current sentiment."""
        risks = []

        # Extreme sentiment risks
        if abs(sentiment_score) > 0.6:
            risks.append("Extreme sentiment levels increase risk of sentiment-driven reversals")

        # Contrarian risks
        if sentiment_score > 0.5 and macro_analysis.get("macro_regime") == "RISK_OFF":
            risks.append("Bullish sentiment contradicts bearish macro environment")

        # Low conviction risks
        if abs(sentiment_score) < 0.1:
            risks.append("Neutral sentiment provides unclear directional guidance")

        return risks

    def _build_sentiment_specific_reasoning(
        self,
        sentiment_score: float,
        sentiment_trend: str,
        news_count: int,
        risks: List[str]
    ) -> str:
        """Build sentiment-specific reasoning text."""
        reasoning_parts = []

        reasoning_parts.append(f"Current sentiment score: {sentiment_score:.2f} "
                              f"({'bullish' if sentiment_score > 0.1 else 'bearish' if sentiment_score < -0.1 else 'neutral'}).")

        reasoning_parts.append(f"Sentiment trend: {sentiment_trend} based on analysis of {news_count} recent news items.")

        if risks:
            reasoning_parts.append(f"Identified risks: {'; '.join(risks)}.")

        return " ".join(reasoning_parts)

    def _determine_immediate_action(
        self,
        sentiment_score: float,
        sentiment_trend: str,
        sentiment_extremes: Dict[str, Any]
    ) -> tuple[Optional[str], float]:
        """Determine if immediate action is warranted."""
        # Generally avoid immediate actions - prefer conditional signals
        # Only act immediately on extreme conditions with high confidence

        if sentiment_extremes["is_extreme_bullish"] and sentiment_extremes["is_high_confidence"]:
            return "HOLD", 0.8  # Hold current positions but be cautious

        elif sentiment_extremes["is_extreme_bearish"] and sentiment_extremes["is_high_confidence"]:
            return "HOLD", 0.8  # Hold current positions but be cautious

        return None, 0.5  # No immediate action
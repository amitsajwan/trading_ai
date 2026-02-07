"""Fundamental agent implementing simple fundamental checks."""

from typing import Dict, Any
import logging

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class FundamentalAgent(Agent):
    def __init__(self):
        self._agent_name = "FundamentalAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Inspect context for fundamentals (earnings, revenue growth, valuation metrics)
        earnings_surprise = context.get("earnings_surprise")
        revenue_growth = context.get("revenue_growth")
        pe_ratio = context.get("pe_ratio")
        pb_ratio = context.get("pb_ratio")
        roe = context.get("roe")
        debt_equity = context.get("debt_equity")
        instrument_name = context.get("instrument", "COMPANY")

        # Debug logging
        # logger.info(f"FundamentalAgent: Context keys: {list(context.keys())}")
        # logger.info(f"FundamentalAgent: earnings_surprise={earnings_surprise}, revenue_growth={revenue_growth}")
        # logger.info(f"FundamentalAgent: pe_ratio={pe_ratio}, pb_ratio={pb_ratio}, roe={roe}, debt_equity={debt_equity}")

        # Check if we have any fundamental data
        has_any_data = any([
            earnings_surprise is not None,
            revenue_growth is not None,
            pe_ratio is not None,
            pb_ratio is not None,
            roe is not None,
            debt_equity is not None
        ])

        if not has_any_data:
            details = {
                "earnings_surprise": None,
                "revenue_growth": None,
                "pe_ratio": None,
                "pb_ratio": None,
                "roe": None,
                "debt_equity": None,
                "fundamental_score": 0.0,
                "note": "NO_FUNDAMENTAL_DATA_AVAILABLE",
                "data_available": False,
                "missing_data": ["earnings_surprise", "revenue_growth", "pe_ratio", "pb_ratio", "roe", "debt_equity"],
                "reasoning": "No fundamental data available for analysis",
                "analysis_summary": "Cannot perform fundamental analysis due to lack of data"
            }
            return AnalysisResult(
                decision="EXCLUDED",
                confidence=0.0,
                details=details,
                excluded=True,
                exclusion_reason="No fundamental data available (earnings, revenue, valuation metrics)"
            )

        # Generate rich natural language reasoning
        reasoning_parts = []

        # Earnings analysis
        if earnings_surprise is not None:
            if earnings_surprise > 0.10:
                reasoning_parts.append(f"Strong earnings beat of {earnings_surprise:.1f}% significantly exceeds analyst expectations, indicating robust operational performance.")
            elif earnings_surprise > 0.05:
                reasoning_parts.append(f"Positive earnings surprise of {earnings_surprise:.1f}% meets or slightly exceeds market expectations.")
            elif earnings_surprise > -0.05:
                reasoning_parts.append(f"Earnings results are in line with expectations ({earnings_surprise:.1f}%), showing consistent performance.")
            elif earnings_surprise > -0.10:
                reasoning_parts.append(f"Modest earnings disappointment of {earnings_surprise:.1f}% suggests some execution challenges.")
            else:
                reasoning_parts.append(f"Significant earnings miss of {earnings_surprise:.1f}% raises concerns about company performance.")
        else:
            reasoning_parts.append("Earnings data not available for fundamental analysis.")

        # Revenue growth analysis
        if revenue_growth is not None:
            if revenue_growth > 0.20:
                reasoning_parts.append(f"Exceptional revenue growth of {revenue_growth:.1f}% demonstrates strong top-line expansion and market share gains.")
            elif revenue_growth > 0.10:
                reasoning_parts.append(f"Solid revenue growth of {revenue_growth:.1f}% supports sustainable business development.")
            elif revenue_growth > 0.05:
                reasoning_parts.append(f"Moderate revenue growth of {revenue_growth:.1f}% indicates steady business progression.")
            elif revenue_growth > 0.02:
                reasoning_parts.append(f"Slow revenue growth of {revenue_growth:.1f}% suggests potential market saturation or competitive pressures.")
            else:
                reasoning_parts.append(f"Revenue contraction of {revenue_growth:.1f}% raises concerns about business momentum.")
        else:
            reasoning_parts.append("Revenue growth data not available for analysis.")

        # Valuation analysis
        valuation_signals = []
        if pe_ratio is not None:
            if pe_ratio > 25:
                valuation_signals.append(f"P/E ratio of {pe_ratio:.1f} appears elevated, suggesting premium valuation")
            elif pe_ratio < 15:
                valuation_signals.append(f"P/E ratio of {pe_ratio:.1f} indicates attractive valuation")
            else:
                valuation_signals.append(f"P/E ratio of {pe_ratio:.1f} reflects reasonable market valuation")
        else:
            valuation_signals.append("P/E ratio not available")

        if pb_ratio is not None:
            if pb_ratio > 3.0:
                valuation_signals.append(f"P/B ratio of {pb_ratio:.1f} suggests rich valuation relative to book value")
            elif pb_ratio < 1.5:
                valuation_signals.append(f"P/B ratio of {pb_ratio:.1f} indicates potentially undervalued assets")
            else:
                valuation_signals.append(f"P/B ratio of {pb_ratio:.1f} shows balanced valuation")
        else:
            valuation_signals.append("P/B ratio not available")

        if valuation_signals:
            reasoning_parts.append(f"Valuation metrics: {', '.join(valuation_signals)}.")

        # Quality analysis
        if roe is not None:
            if roe > 0.15:
                reasoning_parts.append(f"Return on equity of {roe:.1f}% demonstrates excellent capital efficiency and management quality.")
            elif roe > 0.10:
                reasoning_parts.append(f"Return on equity of {roe:.1f}% indicates solid capital utilization.")
            elif roe > 0.05:
                reasoning_parts.append(f"Return on equity of {roe:.1f}% suggests adequate profitability.")
            else:
                reasoning_parts.append(f"Return on equity of {roe:.1f}% raises concerns about capital efficiency.")
        else:
            reasoning_parts.append("Return on equity data not available.")

        if debt_equity is not None:
            if debt_equity > 2.0:
                reasoning_parts.append(f"Debt-to-equity ratio of {debt_equity:.2f} indicates high leverage, increasing financial risk.")
            elif debt_equity > 1.0:
                reasoning_parts.append(f"Debt-to-equity ratio of {debt_equity:.2f} shows moderate leverage.")
            elif debt_equity > 0.5:
                reasoning_parts.append(f"Debt-to-equity ratio of {debt_equity:.2f} reflects conservative financing.")
            else:
                reasoning_parts.append(f"Debt-to-equity ratio of {debt_equity:.2f} indicates very low leverage and strong balance sheet.")
        else:
            reasoning_parts.append("Debt-to-equity data not available.")

        # Decision logic with reasoning
        fundamental_score = 0.0

        # Earnings contribution
        if earnings_surprise is not None:
            if earnings_surprise > 0.05:
                fundamental_score += 0.4
            elif earnings_surprise < -0.05:
                fundamental_score -= 0.4

        # Revenue contribution
        if revenue_growth is not None:
            if revenue_growth > 0.10:
                fundamental_score += 0.3
            elif revenue_growth < 0.02:
                fundamental_score -= 0.3

        # Valuation contribution (inverse - cheap is good)
        if pe_ratio is not None and pe_ratio < 20:
            fundamental_score += 0.2
        elif pe_ratio is not None and pe_ratio > 30:
            fundamental_score -= 0.2

        # Quality contribution
        if roe is not None and roe > 0.12:
            fundamental_score += 0.2
        elif roe is not None and roe < 0.08:
            fundamental_score -= 0.2

        if debt_equity is not None and debt_equity < 1.5:
            fundamental_score += 0.1
        elif debt_equity is not None and debt_equity > 2.5:
            fundamental_score -= 0.1

        # Decision based on fundamental score
        if fundamental_score > 0.5:
            decision = "BUY"
            confidence = min(0.8, 0.4 + fundamental_score)
            reasoning_parts.append(f"BUY recommendation driven by strong fundamental metrics with composite score of {fundamental_score:.2f}.")
        elif fundamental_score < -0.3:
            decision = "SELL"
            confidence = min(0.8, 0.4 + abs(fundamental_score))
            reasoning_parts.append(f"SELL recommendation based on weak fundamental indicators with composite score of {fundamental_score:.2f}.")
        else:
            decision = "HOLD"
            confidence = 0.5
            reasoning_parts.append(f"HOLD recommended due to mixed fundamental signals with neutral composite score of {fundamental_score:.2f}.")

        # Overall assessment
        reasoning_parts.append(f"Fundamental analysis for {instrument_name} reveals {decision.lower()} opportunity with {confidence:.1f} confidence based on earnings, valuation, and quality metrics.")

        details = {
            "earnings_surprise": earnings_surprise,
            "revenue_growth": revenue_growth,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "roe": roe,
            "debt_equity": debt_equity,
            "fundamental_score": fundamental_score,
            "reasoning": " ".join(reasoning_parts),
            "analysis_summary": f"Fundamental analysis shows {decision.lower()} signal with {confidence:.1f} confidence based on earnings, valuation, and quality metrics.",
            "valuation_signals": valuation_signals if 'valuation_signals' in locals() else [],
            "quality_metrics": {
                "return_on_equity": roe,
                "debt_to_equity": debt_equity
            }
        }

        # Collect input data used for analysis
        input_data = {
            "earnings_surprise": earnings_surprise,
            "revenue_growth": revenue_growth,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "roe": roe,
            "debt_equity": debt_equity,
            "fundamental_score_calculated": True,
            "valuation_signals_count": len(valuation_signals) if 'valuation_signals' in locals() else 0
        }

        return AnalysisResult(decision=decision, confidence=confidence, details=details, input_data=input_data)


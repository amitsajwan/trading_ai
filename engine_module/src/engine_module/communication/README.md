# Communication Layer

This module provides structured communication mechanisms for trading agents, inspired by TradingAgents framework's approach to agent interaction.

## Overview

The communication layer enables:
- **Structured Reports**: Standardized format for agent analysis and reasoning
- **Debate Protocol**: Formal argumentation framework for agent debates
- **Evidence-Based Reasoning**: Clear evidence tracking and presentation
- **Confidence-Based Decisions**: Confidence-weighted decision making

## Quick Start

### Structured Reports

```python
from engine_module.communication import (
    StructuredReport,
    ReportBuilder,
    ReportEvidence,
    ReportSection,
    ReportAction,
    ReportType,
    ReportPriority,
    EvidenceType
)

# Using ReportBuilder (recommended)
builder = ReportBuilder("TechnicalAgent")
report = (builder
    .set_type(ReportType.ANALYSIS)
    .set_priority(ReportPriority.HIGH)
    .set_title("Technical Analysis Report")
    .set_summary("RSI indicates oversold conditions")
    .set_confidence(0.75)
    .add_section(
        title="RSI Analysis",
        content="RSI at 28.5 indicates oversold conditions",
        confidence=0.85,
        evidence=[
            ReportEvidence(
                type=EvidenceType.TECHNICAL_INDICATOR,
                description="RSI oversold",
                value=28.5,
                source="RSI_14",
                confidence=0.85
            )
        ]
    )
    .add_action(
        action="BUY",
        target="BANKNIFTY",
        reasoning="Oversold bounce expected",
        confidence=0.80
    )
    .build())

# Convert to markdown
markdown = report.to_markdown()
print(markdown)

# Convert to dict for serialization
report_dict = report.to_dict()
```

### Debate Protocol

```python
from engine_module.communication import (
    DebateProtocol,
    ArgumentType,
    ReportEvidence,
    EvidenceType
)

# Initialize debate protocol
protocol = DebateProtocol(max_rounds=3, min_confidence_threshold=0.6)

# Register participants
protocol.register_participant("BullResearcher", "bull")
protocol.register_participant("BearResearcher", "bear")

# Conduct debate with initial arguments
initial_arguments = {
    "BullResearcher": {
        "claim": "Market is bullish - RSI oversold indicates bounce",
        "reasoning": "RSI at 28.5, MACD bullish crossover, volume increasing",
        "confidence": 0.75,
        "evidence": [
            ReportEvidence(
                type=EvidenceType.TECHNICAL_INDICATOR,
                description="RSI oversold",
                value=28.5,
                source="RSI_14",
                confidence=0.85
            )
        ]
    },
    "BearResearcher": {
        "claim": "Market is bearish - resistance level holding",
        "reasoning": "Price rejected at 45200, volume decreasing",
        "confidence": 0.65
    }
}

# Conduct debate
result = protocol.conduct_debate(initial_arguments=initial_arguments)

print(f"Winner: {result.winner}")
print(f"Winner Confidence: {result.winner_confidence:.2%}")
print(f"Summary: {result.summary}")
print(f"Recommended Action: {result.recommended_action}")

# Submit additional arguments (rebuttals)
protocol.submit_argument(
    participant_name="BullResearcher",
    claim="Volume spike confirms bullish move",
    reasoning="Volume increased 50% on last candle",
    argument_type=ArgumentType.REBUTTAL,
    confidence=0.80,
    counter_argument_to="bear_resistance_claim"
)
```

## Structured Reports

### Report Structure

A structured report contains:
- **Metadata**: Agent name, type, priority, timestamp
- **Summary**: Executive summary
- **Sections**: Hierarchical sections with content and evidence
- **Actions**: Recommended actions with reasoning
- **Confidence**: Overall confidence score (0.0 to 1.0)

### Report Types

- `ANALYSIS`: Market analysis report
- `RECOMMENDATION`: Trading recommendation
- `WARNING`: Risk warning
- `UPDATE`: Status update
- `DEBATE_ARGUMENT`: Argument in a debate

### Report Priorities

- `CRITICAL`: Urgent action required
- `HIGH`: Important decision
- `MEDIUM`: Standard priority
- `LOW`: Informational

### Evidence Types

- `TECHNICAL_INDICATOR`: Technical analysis indicator
- `MARKET_DATA`: Raw market data
- `HISTORICAL_PATTERN`: Historical pattern match
- `FUNDAMENTAL_DATA`: Fundamental analysis data
- `SENTIMENT_DATA`: Market sentiment data
- `STATISTICAL_ANALYSIS`: Statistical analysis result
- `EXPERT_OPINION`: Expert opinion

### Example: Technical Analysis Report

```python
builder = ReportBuilder("TechnicalAgent")
report = (builder
    .set_type(ReportType.ANALYSIS)
    .set_priority(ReportPriority.HIGH)
    .set_title("Technical Analysis: Bank Nifty")
    .set_summary("RSI oversold with bullish MACD crossover")
    .set_confidence(0.75)
    
    # Add RSI section
    .add_section(
        title="RSI Analysis",
        content="RSI at 28.5 indicates oversold conditions. Historical data shows 70% bounce probability from this level.",
        confidence=0.85,
        evidence=[
            ReportEvidence(
                type=EvidenceType.TECHNICAL_INDICATOR,
                description="RSI oversold",
                value=28.5,
                source="RSI_14",
                confidence=0.85
            ),
            ReportEvidence(
                type=EvidenceType.HISTORICAL_PATTERN,
                description="Historical bounce rate from RSI < 30",
                value=0.70,
                source="Historical Analysis",
                confidence=0.75
            )
        ]
    )
    
    # Add MACD section
    .add_section(
        title="MACD Analysis",
        content="MACD line crossed above signal line, indicating bullish momentum.",
        confidence=0.70
    )
    
    # Add action recommendation
    .add_action(
        action="BUY",
        target="BANKNIFTY",
        reasoning="Oversold bounce expected with bullish momentum confirmation",
        confidence=0.75,
        urgency="scheduled",
        risk_assessment={"risk_level": "medium", "stop_loss": "2%"}
    )
    
    .build())

# Get overall confidence (weighted average)
overall_confidence = report.get_overall_confidence()
print(f"Overall Confidence: {overall_confidence:.2%}")

# Export as markdown
markdown = report.to_markdown()
print(markdown)
```

## Debate Protocol

### Debate Structure

A debate consists of:
- **Participants**: Agents with positions (e.g., "bull", "bear")
- **Rounds**: Sequential debate rounds (initial, rebuttal, closing)
- **Arguments**: Structured arguments with claims, reasoning, evidence
- **Result**: Synthesized result with winner, consensus, recommendations

### Argument Types

- `INITIAL`: Opening argument
- `REBUTTAL`: Counter-argument to opponent's claim
- `REBUTTAL_TO_REBUTTAL`: Counter to counter-argument
- `CLOSING`: Final statement

### Argument Strength

Based on confidence:
- `VERY_STRONG`: > 0.8 confidence
- `STRONG`: 0.6 - 0.8 confidence
- `MODERATE`: 0.4 - 0.6 confidence
- `WEAK`: < 0.4 confidence

### Example: Bull vs Bear Debate

```python
protocol = DebateProtocol(max_rounds=3, min_confidence_threshold=0.6)

# Register participants
bull = protocol.register_participant("BullResearcher", "bull")
bear = protocol.register_participant("BearResearcher", "bear")

# Round 1: Initial arguments
protocol.start_round(1)

bull_arg = protocol.submit_argument(
    participant_name="BullResearcher",
    claim="Market is bullish - oversold bounce expected",
    reasoning="RSI at 28.5, MACD bullish crossover",
    argument_type=ArgumentType.INITIAL,
    confidence=0.75,
    evidence=[
        ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14"
        )
    ]
)

bear_arg = protocol.submit_argument(
    participant_name="BearResearcher",
    claim="Market is bearish - resistance holding",
    reasoning="Price rejected at 45200, volume decreasing",
    argument_type=ArgumentType.INITIAL,
    confidence=0.65
)

# Round 2: Rebuttals
protocol.start_round(2)

protocol.submit_argument(
    participant_name="BullResearcher",
    claim="Volume spike confirms bullish move",
    reasoning="Volume increased 50% on last candle",
    argument_type=ArgumentType.REBUTTAL,
    confidence=0.80,
    counter_argument_to="bear_resistance_claim"
)

protocol.submit_argument(
    participant_name="BearResearcher",
    claim="Volume spike is exhaustion move",
    reasoning="High volume with small price move indicates selling",
    argument_type=ArgumentType.REBUTTAL,
    confidence=0.70,
    counter_argument_to="bull_volume_claim"
)

# Synthesize result
result = protocol._synthesize_debate()

print(f"Winner: {result.winner}")
print(f"Winner Confidence: {result.winner_confidence:.2%}")
print(f"Summary: {result.summary}")
print(f"Key Points: {result.key_points}")
print(f"Consensus: {result.consensus}")
print(f"Recommended Action: {result.recommended_action}")
```

## Integration

### With ResearchManager

```python
from engine_module.agents.research_manager import ResearchManager
from engine_module.communication import DebateProtocol

class EnhancedResearchManager(ResearchManager):
    def __init__(self, llm_client=None):
        super().__init__(llm_client)
        self.debate_protocol = DebateProtocol(max_rounds=3)
    
    async def conduct_formal_debate(self, context):
        # Get bull and bear analyses
        bull_result = await self._get_bull_analysis(context)
        bear_result = await self._get_bear_analysis(context)
        
        # Register participants
        self.debate_protocol.register_participant("BullResearcher", "bull")
        self.debate_protocol.register_participant("BearResearcher", "bear")
        
        # Submit initial arguments
        initial_arguments = {
            "BullResearcher": {
                "claim": bull_result.decision,
                "reasoning": bull_result.details.get("thesis", ""),
                "confidence": bull_result.confidence
            },
            "BearResearcher": {
                "claim": bear_result.decision,
                "reasoning": bear_result.details.get("thesis", ""),
                "confidence": bear_result.confidence
            }
        }
        
        # Conduct debate
        debate_result = self.debate_protocol.conduct_debate(
            initial_arguments=initial_arguments,
            llm_synthesizer=self.llm_client
        )
        
        return debate_result
```

### With Agents

Agents can use structured reports for their outputs:

```python
from engine_module.communication import ReportBuilder, ReportType

class EnhancedAgent(Agent):
    async def analyze(self, context):
        builder = ReportBuilder(self.name)
        
        # Build structured report
        report = (builder
            .set_type(ReportType.ANALYSIS)
            .set_summary("Market analysis complete")
            .add_section(...)
            .add_action(...)
            .build())
        
        # Convert to AnalysisResult
        return AnalysisResult(
            decision=report.actions[0].action if report.actions else "HOLD",
            confidence=report.get_overall_confidence(),
            details={"report": report.to_dict()}
        )
```

## Testing

All components have comprehensive unit tests:

```bash
# Run all communication tests
pytest engine_module/tests/unit/communication/ -v

# Run specific tests
pytest engine_module/tests/unit/communication/test_structured_reports.py -v
pytest engine_module/tests/unit/communication/test_debate_protocol.py -v
```

**Test Coverage:** 41 tests, all passing ✅

## Serialization

All components support serialization:

```python
# Report to dict
report_dict = report.to_dict()

# Debate result to dict
result_dict = debate_result.to_dict()

# Can be saved to Redis/MongoDB for persistence
```

## Best Practices

1. **Use ReportBuilder**: Prefer fluent builder interface for report construction
2. **Include Evidence**: Always include evidence for claims
3. **Set Confidence**: Provide accurate confidence scores
4. **Structured Sections**: Use hierarchical sections for clarity
5. **Debate Rounds**: Limit rounds to 2-3 for efficiency
6. **Clear Claims**: Make specific, testable claims in debates

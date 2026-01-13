"""Utility helpers for agent outputs and normalization."""
from typing import Optional
from engine_module.contracts import AnalysisResult


def standardize_analysis_result(result: AnalysisResult, agent_name: Optional[str] = None) -> AnalysisResult:
    """Ensure AnalysisResult follows a minimal contract for downstream consumers.

    - Ensures result.agent is set
    - Ensures result.details is a dict
    - Ensures result.details['agent'] is set

    Returns the possibly modified result.
    """
    if result is None:
        return result

    # Populate agent identifier
    if not getattr(result, "agent", None) and agent_name:
        result.agent = agent_name

    # Ensure details dict
    if result.details is None or not isinstance(result.details, dict):
        result.details = {}

    # Ensure agent present in details
    if 'agent' not in result.details and result.agent:
        result.details['agent'] = result.agent

    return result

import pytest
from engine_module.contracts import AnalysisResult
from engine_module.utils.agent_helpers import standardize_analysis_result


def test_standardize_analysis_result_populates_agent():
    res = AnalysisResult(decision="HOLD", confidence=0.0, details=None, agent=None)
    standardized = standardize_analysis_result(res, "TestAgent")
    assert standardized.agent == "TestAgent"
    assert isinstance(standardized.details, dict)
    assert standardized.details.get('agent') == "TestAgent"

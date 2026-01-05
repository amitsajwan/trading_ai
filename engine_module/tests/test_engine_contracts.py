from engine_module.contracts import Orchestrator, Agent, AnalysisResult


def test_analysis_result_fields():
    res = AnalysisResult(decision="hold", confidence=0.5)
    assert res.decision == "hold"
    assert res.confidence == 0.5


def test_protocols_exist():
    assert hasattr(Orchestrator, "run_cycle")
    assert hasattr(Agent, "analyze")

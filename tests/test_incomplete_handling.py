from trading_orchestration.trading_graph import TradingGraph
from agents.state import AgentState
import types


class FakeCollection:
    def __init__(self):
        self.inserted = []
    def insert_one(self, doc):
        self.inserted.append(doc)
        return types.SimpleNamespace(inserted_id='fake')

class FakeClient:
    def __init__(self, db_name, alerts_collection):
        self.db_name = db_name
        self.alerts_collection = alerts_collection
    def __getitem__(self, name):
        if name == self.db_name:
            return {'alerts': self.alerts_collection}
        raise KeyError(name)


def test_validate_json_completeness_false():
    from agents.base_agent import BaseAgent
    # Create a minimal concrete subclass to instantiate
    class ConcreteAgent(BaseAgent):
        def _get_default_prompt(self):
            return ""
        def process(self, state):
            return state
    agent = ConcreteAgent(agent_name='test')
    # Unbalanced braces
    assert not agent._validate_json_completeness('{"a": 1', {"a": 0})
    # Too few keys
    assert not agent._validate_json_completeness('{"x": 1}', {"a": 0, "b": 0, "c": 0, "d": 0})


def test_store_analysis_marks_incomplete_and_writes_alert(monkeypatch):
    # Prepare fake MongoDB
    fake_alerts = FakeCollection()
    fake_client = FakeClient('zerodha_trading', fake_alerts)

    # Monkeypatch get_mongo_client and get_collection
    import mongodb_schema
    monkeypatch.setattr(mongodb_schema, 'get_mongo_client', lambda: fake_client)
    monkeypatch.setattr(mongodb_schema, 'get_collection', lambda db, name: (fake_alerts if name == 'alerts' else FakeCollection()))

    tg = TradingGraph()
    state = AgentState()
    # Minimal fields required
    state.current_price = 100.0
    state.final_signal = 'HOLD'
    state.trend_signal = 'NEUTRAL'
    state.position_size = 0
    state.entry_price = 0
    state.stop_loss = 0
    state.take_profit = 0
    state.technical_analysis = {'summary': 'partial', '__incomplete_json': True}
    state.fundamental_analysis = {}
    state.sentiment_analysis = {}
    state.macro_analysis = {}
    state.bull_thesis = ''
    state.bull_confidence = 0
    state.bear_thesis = ''
    state.bear_confidence = 0
    state.aggressive_risk_recommendation = {}
    state.conservative_risk_recommendation = {}
    state.neutral_risk_recommendation = {}
    state._portfolio_manager_output = {}
    state.agent_explanations = []
    state.decision_audit_trail = {}

    # Call store method (should write an analysis_incomplete alert)
    tg._store_analysis_results(state)

    # Assert alert was recorded
    assert len(fake_alerts.inserted) == 1
    alert = fake_alerts.inserted[0]
    assert alert['type'] == 'analysis_incomplete'
    assert 'technical' in alert['message'] or 'technical' in str(alert['agents'])

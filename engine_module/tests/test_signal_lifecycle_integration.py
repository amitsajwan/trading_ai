import asyncio
import hashlib
import json
from datetime import datetime, timedelta

import pytest

from engine_module.signal_creator import create_signals_from_decision, save_signal_to_mongodb, sync_signals_to_monitor
from engine_module.signal_monitor import SignalMonitor
# Note: avoid importing internal schema types in this integration test to keep imports simple


from types import SimpleNamespace


def make_analysis_result(action: str, reasoning: str, confidence: float = 0.8):
    # create a lightweight object resembling AnalysisResult expected by create_signals_from_decision
    return SimpleNamespace(
        decision=action,
        confidence=confidence,
        details={"reasoning": reasoning}
    )


@pytest.mark.asyncio
async def test_full_signal_lifecycle(monkeypatch, tmp_path):
    """Integration test: create -> save -> sync -> trigger -> execute.

    Steps:
    1) Create a conditional signal (e.g., RSI > 30) and save it.
    2) Attempt to create the same signal again and ensure dedupe returns the same id.
    3) Sync signals to local SignalMonitor and simulate market ticks that satisfy the condition.
    4) Verify the signal is marked executed / monitor publishes execution event.
    """

    # Setup an in-memory SignalMonitor
    monitor = SignalMonitor()

    # Fake in-memory MongoDB (simple collection) to avoid external dependencies
    class FakeCollection:
        def __init__(self):
            self.docs = []

        def find_one(self, query, sort=None):
            # return the most recent matching doc
            matches = [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]
            if not matches:
                return None
            # sort by created_at if present
            if sort:
                return matches[-1]
            return matches[-1]

        def insert_one(self, doc):
            fake_id = f"fakeid_{len(self.docs)+1}"
            doc_copy = dict(doc)
            doc_copy["_id"] = fake_id
            self.docs.append(doc_copy)
            class R: pass
            r = R()
            r.inserted_id = fake_id
            return r

        def find(self, query):
            return [d for d in self.docs if all((k not in query) or d.get(k) == v for k, v in query.items())]

        def update_one(self, query, update):
            for d in self.docs:
                matches = True
                for k, v in query.items():
                    if k.startswith("$"):
                        matches = False
                    if d.get(k) != v:
                        matches = False
                if matches:
                    # apply $set
                    sets = update.get("$set", {})
                    d.update(sets)
                    return

    class FakeDB(dict):
        def __init__(self):
            super().__init__()
            self["signals"] = FakeCollection()

    fake_db = FakeDB()

    # Create a sample decision with a simple parsed condition (RSI > 30)
    analysis = make_analysis_result("BUY", "rsi_14 > 30")

    # Create signals from decision (instrument must be passed explicitly)
    signals = create_signals_from_decision(analysis, "TEST:1234", current_price=100.0)
    assert len(signals) == 1

    # Save first signal (using fake DB)
    signal = signals[0]
    inserted_id = await save_signal_to_mongodb(signal, fake_db)
    assert inserted_id is not None

    # Attempt duplicate: create again and verify save_signal_to_mongodb returns same id (dedupe window)
    signals2 = create_signals_from_decision(analysis, "TEST:1234", current_price=100.0)
    assert len(signals2) == 1
    dup_id = await save_signal_to_mongodb(signals2[0], fake_db)
    assert dup_id == inserted_id

    # Sync DB signals into monitor's active set
    await sync_signals_to_monitor(fake_db, monitor, instrument="TEST:1234")
    active = monitor.get_active_signals("TEST:1234")
    assert any(s.instrument == "TEST:1234" for s in active)

    # Find the active trading condition
    tc = active[0]
    assert tc.execution_mode in ("CONDITIONAL", "IMMEDIATE")

    # Replace technical service with a fake that returns indicators satisfying the condition
    class FakeTechnicalService:
        def get_indicators_dict(self, instrument):
            return {"rsi_14": 40.0, "current_price": 100.0}

    monitor._technical_service = FakeTechnicalService()

    # Run monitor check loop (this should trigger execution path)
    triggered = await monitor.check_signals(tc.instrument)

    # Ensure triggered event(s) were recorded and active list updated
    assert len(triggered) >= 1
    assert triggered[0].instrument == "TEST:1234"

    # After triggering, signal should no longer be active
    assert not monitor.get_active_signals("TEST:1234")


# end of file

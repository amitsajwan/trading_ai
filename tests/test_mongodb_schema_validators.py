from mongodb_schema import apply_schema_validators, migrate_trades_add_defaults, migrate_agents_instrument_field


class FakeDB:
    def __init__(self):
        self.commands = []
        self.updated = []
        self.collections = {}
    def command(self, cmd):
        self.commands.append(cmd)
    def get_collection(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]

class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.updates = []
    def update_many(self, q, u):
        self.updates.append((q, u))
    def find(self, q=None):
        return []
    def update_one(self, q, u):
        self.updates.append((q, u))


def test_apply_validators_and_migrations():
    db = FakeDB()
    # Should not raise
    apply_schema_validators(db)
    migrate_trades_add_defaults(db)
    migrate_agents_instrument_field(db, instrument='TEST')
    # Command calls should include collMod for trades_executed and agent_decisions
    assert any('collMod' in c for c in db.commands)
    assert 'trades_executed' in str(db.commands[0]) or 'agent_decisions' in str(db.commands[0])
    # Collections should have been accessed
    assert 'trades_executed' in db.collections
    assert 'agent_decisions' in db.collections
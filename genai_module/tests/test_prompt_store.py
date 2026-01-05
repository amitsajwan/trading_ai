import asyncio
from pathlib import Path

import pytest

from genai_module.adapters.prompt_store import FilePromptStore, PromptManagerStore


class FakePromptManager:
    def __init__(self):
        self.data = {}

    def get_prompt(self, agent_name, version=None):
        key = (agent_name, version or "latest")
        return self.data.get(key, "")

    def save_prompt(self, agent_name, prompt_text, version=None):
        key = (agent_name, version or "latest")
        self.data[key] = prompt_text

    def list_versions(self, agent_name):
        return [
            {"version": ver}
            for (agent, ver) in self.data.keys()
            if agent == agent_name
        ]


@pytest.mark.asyncio
async def test_file_prompt_store_roundtrip(tmp_path: Path):
    store = FilePromptStore(tmp_path)
    await store.save("agentA", "hello", version="v1")
    got = await store.get("agentA", version="v1")
    assert got == "hello"
    versions = await store.list_versions("agentA")
    assert "agenta__v1.txt" in versions


@pytest.mark.asyncio
async def test_prompt_manager_store_wraps_legacy():
    pm = FakePromptManager()
    store = PromptManagerStore(pm)
    await store.save("agentB", "world", version="v2")
    got = await store.get("agentB", version="v2")
    assert got == "world"
    versions = await store.list_versions("agentB")
    assert "v2" in versions

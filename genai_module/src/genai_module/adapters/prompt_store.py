"""Prompt store adapters (file-backed and legacy PromptManager wrapper)."""
import logging
from pathlib import Path
from typing import Optional, Iterable

from genai_module.contracts import PromptStore

logger = logging.getLogger(__name__)


class FilePromptStore(PromptStore):
    """Simple file-based prompt store for tests and local dev."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def get(self, agent_name: str, version: Optional[str] = None) -> str:
        path = self._path(agent_name, version)
        if path.exists():
            return path.read_text()
        raise FileNotFoundError(f"Prompt not found: {path}")

    async def save(self, agent_name: str, prompt_text: str, version: Optional[str] = None) -> str:
        path = self._path(agent_name, version)
        path.write_text(prompt_text)
        return path.name

    async def list_versions(self, agent_name: str) -> Iterable[str]:
        pattern = f"{agent_name}__*.txt"
        files = sorted(self.root.glob(pattern))
        return [f.name for f in files]

    def _path(self, agent_name: str, version: Optional[str]) -> Path:
        ver = version or "latest"
        safe_agent = agent_name.replace(" ", "_").lower()
        return self.root / f"{safe_agent}__{ver}.txt"


class PromptManagerStore(PromptStore):
    """Wrapper around legacy PromptManager (uses Mongo + files)."""

    def __init__(self, prompt_manager):
        self.pm = prompt_manager

    async def get(self, agent_name: str, version: Optional[str] = None) -> str:
        return self.pm.get_prompt(agent_name, version)

    async def save(self, agent_name: str, prompt_text: str, version: Optional[str] = None) -> str:
        self.pm.save_prompt(agent_name, prompt_text, version)
        return version or "latest"

    async def list_versions(self, agent_name: str) -> Iterable[str]:
        versions = self.pm.list_versions(agent_name)
        return [v.get("version") for v in versions if v.get("version")]


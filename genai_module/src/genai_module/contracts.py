"""LLM-facing contracts for adapters and providers."""
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable, Iterable


@dataclass
class LLMRequest:
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.2
    model: Optional[str] = None


@dataclass
class LLMResponse:
    content: str
    tokens_used: int
    cost: Optional[float] = None


@runtime_checkable
class LLMClient(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    async def estimate_cost(self, request: LLMRequest) -> float:
        ...

    async def validate(self) -> bool:
        ...


@runtime_checkable
class PromptStore(Protocol):
    async def get(self, agent_name: str, version: Optional[str] = None) -> str:
        ...

    async def save(self, agent_name: str, prompt_text: str, version: Optional[str] = None) -> str:
        ...

    async def list_versions(self, agent_name: str) -> Iterable[str]:
        ...

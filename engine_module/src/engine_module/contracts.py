"""Orchestrator and agent contracts."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any


@dataclass
class AnalysisResult:
    decision: str
    confidence: float
    details: dict[str, Any] | None = None


@runtime_checkable
class Agent(Protocol):
    async def analyze(self, context: dict[str, Any]) -> AnalysisResult:
        ...


@runtime_checkable
class Orchestrator(Protocol):
    async def run_cycle(self, context: dict[str, Any]) -> AnalysisResult:
        ...

"""Lightweight core contracts to keep modules decoupled."""
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class ComponentFactory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...


@runtime_checkable
class ServiceContainer(Protocol):
    """Minimal DI surface used across modules."""

    def get(self, name: str) -> Any:
        ...

    def register(self, name: str, factory: ComponentFactory) -> None:
        ...

    def reset(self) -> None:
        ...

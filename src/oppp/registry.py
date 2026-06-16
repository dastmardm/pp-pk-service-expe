"""A tiny generic registry so every pipeline step is pluggable by name.

Implementations register themselves under a string key; the pipeline resolves the
concrete implementation from config. Swapping a normalizer, decomposer, or
translator is therefore a config change, not a code edit (see
docs/06-implementation/tech-stack.md).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        def deco(factory: Callable[..., T]) -> Callable[..., T]:
            if name in self._factories:
                raise ValueError(f"{self._kind} '{name}' already registered")
            self._factories[name] = factory
            return factory

        return deco

    def add(self, name: str, factory: Callable[..., T]) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs) -> T:
        if name not in self._factories:
            raise KeyError(
                f"unknown {self._kind} '{name}'. available: {sorted(self._factories)}"
            )
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)

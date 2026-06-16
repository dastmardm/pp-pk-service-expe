"""Pluggable misspelling normalization (docs/03-proposed-design/misspelling-strategy.md).

A normalizer cleans an `nl_fragment` *before* value production. The interface is
fixed; the concrete strategy is a config choice. The default is a no-op so the
pipeline runs end-to-end before any strategy is chosen.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from oppp.models import GroundingHit
from oppp.registry import Registry


class NormalizationResult(BaseModel):
    normalized: str
    candidates: list[GroundingHit] = Field(default_factory=list)
    changed: bool = False
    confidence: float = 1.0
    note: str | None = None


class Normalizer(Protocol):
    def normalize(
        self, fragment: str, *, field: str, bucket: str
    ) -> NormalizationResult: ...


normalizer_registry: Registry[Normalizer] = Registry("normalizer")


def get_normalizer(name: str, **kwargs) -> Normalizer:
    return normalizer_registry.create(name, **kwargs)


# Register concrete strategies on import.
from oppp.normalize import strategies as _strategies  # noqa: E402,F401

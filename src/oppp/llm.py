"""Central LLM client factory.

Every LLM-backed stage (decompose, aggregate, the Stage-2 term selector) builds
its chat model here so credentials, provider wiring, and structured-output
behaviour live in one place. The model is created lazily from the project .env
(Portkey settings), so importing this module never requires creds — only calling
:func:`get_chat_model` does.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

_DEFAULT_SEED = 7


class LLMUnavailable(RuntimeError):
    """Raised when an LLM stage is used without creds / the optional 'llm' extra."""


@lru_cache(maxsize=8)
def get_chat_model(model: str | None = None, temperature: float = 0.0):
    """Build a LangChain chat model via Portkey. Cached per (model, temperature).

    Raises LLMUnavailable when PORTKEY_* settings are missing or the 'llm' extra
    is not installed, so callers can surface a clear error.
    """
    from oppp.config import get_settings, load_dotenv_if_present

    load_dotenv_if_present()
    s = get_settings()
    if not (s.portkey_api_key and s.portkey_endpoint):
        raise LLMUnavailable(
            "LLM stage needs PORTKEY_ENDPOINT and PORTKEY_API_KEY in .env"
        )
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:  # pragma: no cover - optional extra
        raise LLMUnavailable("install the 'llm' extra: pip install 'oppp[llm]'") from e

    return ChatOpenAI(
        api_key=s.portkey_api_key,
        base_url=s.portkey_endpoint,
        model=f"{s.portkey_provider}/{model or s.tool_model}",
        temperature=temperature,
        top_p=0,
        seed=s.llm_seed if s.llm_seed is not None else _DEFAULT_SEED,
    )


def structured(schema: type, *, model: str | None = None, temperature: float = 0.0) -> Any:
    """Chat model constrained to emit `schema` (a pydantic model) via structured output."""
    return get_chat_model(model=model, temperature=temperature).with_structured_output(schema)

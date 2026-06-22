"""Central LLM client factory.

Every LLM-backed stage (decompose, aggregate, the Stage-2 term selector) builds
its chat model here so credentials, provider wiring, and structured-output
behaviour live in one place. The model is created lazily from the project .env
(Portkey settings), so importing this module never requires creds — only calling
:func:`get_chat_model` does.

Tests stay hermetic by selecting the offline doubles of each stage rather than
mocking this module, but a fake structured-output callable can also be injected
into a stage directly (see the stage constructors).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# Fixed decoding seed for every LLM call. Determinism knobs, strongest first:
#   * temperature=0   — greedy decoding (no sampling)
#   * top_p=0         — collapse the nucleus to the single top token
#   * seed=<fixed>    — pin the provider's RNG for what randomness remains
# Even together these are best-effort, not a guarantee: hosted models still drift
# run-to-run from batched-GPU float non-associativity, MoE routing, and provider
# load-balancing. They remove every source of variance we control. Overridable via
# LLM_SEED so a run can be re-seeded deliberately.
_DEFAULT_SEED = 7


class LLMUnavailable(RuntimeError):
    """Raised when an LLM stage is used without creds / the optional 'llm' extra."""


@lru_cache(maxsize=8)
def get_chat_model(model: str | None = None, temperature: float = 0.0):
    """Build a LangChain chat model via Portkey. Cached per (model, temperature).

    Configured for maximum reproducibility the provider allows: temperature=0,
    top_p=0, and a fixed seed (see module notes). Raises LLMUnavailable with an
    actionable message when PORTKEY_* settings are missing or the 'llm' extra is not
    installed, so callers can surface a clear error instead of an import/attribute
    failure.
    """
    from oppp.config import get_settings, load_dotenv_if_present

    load_dotenv_if_present()
    s = get_settings()
    if not (s.portkey_api_key and s.portkey_endpoint):
        raise LLMUnavailable(
            "LLM stage needs PORTKEY_* settings in .env (use the offline doubles "
            "for hermetic runs: decomposer='gazetteer', aggregator='deterministic')."
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

"""Runtime configuration: where the input CSVs live and (optional) LLM/TERMite settings.

Secrets are read from the project .env only when the stage that needs them is invoked;
the deterministic core never needs them.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS_DIR = REPO_ROOT / "inputs"


class ConfigError(RuntimeError):
    """Raised when a required configuration variable is missing."""


class Settings(BaseModel):
    inputs_dir: Path = DEFAULT_INPUTS_DIR
    portkey_endpoint: str | None = None
    portkey_api_key: str | None = None
    portkey_provider: str | None = None
    tool_model: str | None = None
    llm_seed: int | None = None
    termite_home: str | None = None
    termite_auth_url: str | None = None
    termite_client_name: str | None = None
    termite_client_secret: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    inputs = Path(os.environ.get("OPPP_INPUTS_DIR", str(DEFAULT_INPUTS_DIR)))
    return Settings(
        inputs_dir=inputs,
        portkey_endpoint=os.environ.get("PORTKEY_ENDPOINT"),
        portkey_api_key=os.environ.get("PORTKEY_API_KEY"),
        portkey_provider=os.environ.get("PORTKEY_PROVIDER"),
        tool_model=os.environ.get("TOOL_MODEL"),
        llm_seed=int(os.environ["LLM_SEED"]) if os.environ.get("LLM_SEED") else None,
        termite_home=os.environ.get("TERMITE_HOME"),
        termite_auth_url=os.environ.get("TERMITE_AUTH_URL"),
        termite_client_name=os.environ.get("TERMITE_CLIENT_NAME"),
        termite_client_secret=os.environ.get("TERMITE_CLIENT_SECRET"),
    )


def load_dotenv_if_present() -> None:
    """Best-effort load of the project .env (only when a backend that needs creds is used)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env = REPO_ROOT / ".env"
    if env.exists():
        load_dotenv(env)
        get_settings.cache_clear()


def get_llm_settings() -> Settings:
    """Return settings, raising ConfigError if LLM credentials are absent."""
    load_dotenv_if_present()
    s = get_settings()
    if not (s.portkey_api_key and s.portkey_endpoint):
        raise ConfigError(
            "LLM stage requires PORTKEY_ENDPOINT and PORTKEY_API_KEY in .env"
        )
    return s


def get_termite_settings() -> Settings:
    """Return settings, raising ConfigError if TERMite credentials are absent."""
    load_dotenv_if_present()
    s = get_settings()
    if not s.termite_home:
        raise ConfigError(
            "Stage 0 requires TERMITE_HOME in .env"
        )
    return s

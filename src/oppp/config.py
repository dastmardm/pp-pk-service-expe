"""Runtime configuration: where the input CSVs live and (optional) LLM settings.

Secrets are read from the project .env only when an LLM backend is actually used;
the deterministic core never needs them.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

# Repo root = three levels up from this file (src/oppp/config.py -> repo).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS_DIR = REPO_ROOT / "inputs"


class Settings(BaseModel):
    inputs_dir: Path = DEFAULT_INPUTS_DIR
    # LLM (optional; only needed for the LangChain/DSPy backends)
    portkey_endpoint: str | None = None
    portkey_api_key: str | None = None
    portkey_provider: str | None = None
    tool_model: str | None = None
    # TERMite NER (optional; only needed for the 'termite' decomposer backend)
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
        termite_home=os.environ.get("TERMITE_HOME"),
        termite_auth_url=os.environ.get("TERMITE_AUTH_URL"),
        termite_client_name=os.environ.get("TERMITE_CLIENT_NAME"),
        termite_client_secret=os.environ.get("TERMITE_CLIENT_SECRET"),
    )


def load_dotenv_if_present() -> None:
    """Best-effort load of the project .env (only when an LLM backend is used)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env = REPO_ROOT / ".env"
    if env.exists():
        load_dotenv(env)
        get_settings.cache_clear()

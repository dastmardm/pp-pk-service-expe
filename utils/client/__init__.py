"""
Wrapper file for LLM calls
"""

from openai import OpenAI
import os
from dotenv import dotenv_values
from langchain_openai import ChatOpenAI


# Loading configuration from .env file
env_path = os.path.join(os.path.dirname(__file__),  "configurations", ".env")
config = dotenv_values(os.path.abspath(env_path))

# Portkey (OpenAI-Deployment) configuration
PORTKEY_ENDPOINT = config["PORTKEY_ENDPOINT"]          
PORTKEY_API_KEY = config["PORTKEY_API_KEY"]
PORTKEY_PROVIDER = config["PORTKEY_PROVIDER"]


def get_openai_client(langchain_compatibility: bool = True, 
                      model_name: str | None = None,
                      **kwargs) -> ChatOpenAI | OpenAI:
    """
    Args:
        langchain_compatibility: If True, returns a LangChain ChatOpenAI wrapper, otherwise returns the raw OpenAI client.
        model_name: model/deployment name.
        **kwargs: Extra args for the underlying client/wrapper. 
    """

    if not model_name:
        raise ValueError("model_name must be provided")

    resolved_model = f"{PORTKEY_PROVIDER}/{model_name}"

    if langchain_compatibility:
        return ChatOpenAI(
            api_key=PORTKEY_API_KEY,
            base_url=PORTKEY_ENDPOINT,
            model=resolved_model,
            **kwargs,
    )

    # raw client configured for OpenAI-compatible endpoint
    return OpenAI(
        api_key=PORTKEY_API_KEY,
        base_url=PORTKEY_ENDPOINT
    )

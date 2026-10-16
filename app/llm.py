"""All language model creation lives here (directive section 5).

LLM_PROVIDER: openai (default). LLM_MODEL: the agent model, used by both
Trusted Support and the baseline so the comparison is fair. JUDGE_MODEL and
ATTACKER_MODEL are used by evals through Inspect. LLM_TEMPERATURE is optional
because some models reject the parameter.
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel


class ModelNotConfigured(RuntimeError):
    pass


def chat_model(model: str | None = None) -> BaseChatModel:
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = model or os.environ.get("LLM_MODEL")
    if not model:
        raise ModelNotConfigured("Set LLM_MODEL (and the provider's API key) to run a real agent.")
    kwargs = {}
    if os.environ.get("LLM_TEMPERATURE"):
        kwargs["temperature"] = float(os.environ["LLM_TEMPERATURE"])
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, **kwargs)
    raise ModelNotConfigured(f"Unsupported LLM_PROVIDER {provider!r}")

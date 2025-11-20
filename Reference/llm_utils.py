from __future__ import annotations

from .config import AgentConfig
from .llm_client import LLMClient


def load_llm(cfg: AgentConfig) -> LLMClient:
    missing = [k for k in [cfg.azure_endpoint, cfg.azure_key, cfg.azure_deployment] if not k]
    if missing:
        raise RuntimeError("Azure OpenAI config missing. Set AZURE_OPENAI_ENDPOINT, KEY, DEPLOYMENT.")
    return LLMClient(
        endpoint=cfg.azure_endpoint,
        api_key=cfg.azure_key,
        deployment=cfg.azure_deployment,
        api_version=cfg.azure_api_version,
    )

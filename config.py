"""Central application configuration. Loads environment variables and exposes
a shared settings object plus an LLM factory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))

    langsmith_api_key: str = field(default_factory=lambda: os.getenv("LANGSMITH_API_KEY", ""))
    langsmith_tracing: bool = field(
        default_factory=lambda: os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    )
    langsmith_project: str = field(default_factory=lambda: os.getenv("LANGSMITH_PROJECT", "travel-agent"))

    google_maps_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY", ""))
    amadeus_client_id: str = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_ID", ""))
    amadeus_client_secret: str = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_SECRET", ""))

    weather_api_key: str = field(default_factory=lambda: os.getenv("WEATHER_API_KEY", ""))
    currency_api_key: str = field(default_factory=lambda: os.getenv("CURRENCY_API_KEY", ""))
    web_search_api_key: str = field(default_factory=lambda: os.getenv("WEB_SEARCH_API_KEY", ""))

    def validate_core(self) -> list[str]:
        """Return warnings for missing essential configuration. Non-fatal by design."""
        warnings = []
        if not self.gemini_api_key:
            warnings.append("GEMINI_API_KEY is not set — LLM calls will fail.")
        return warnings


settings = Settings()

# Wire LangSmith tracing via the standard env vars it reads, if enabled.
if settings.langsmith_tracing and settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)


def get_llm(temperature: float = 0.0):
    """Return a configured Gemini chat model instance.

    Raises RuntimeError (rather than crashing at import time) if no API key
    is configured, so callers can fail that single node/request gracefully.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing; cannot create LLM instance.")

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
    )
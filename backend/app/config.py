"""Application settings, loaded from the environment via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration sourced from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["dev", "prod", "test"] = "dev"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "argus"
    # Stored as a string so pydantic-settings does not JSON-decode the env value
    # before we can split on commas (see CORS_ORIGINS in .env.example).
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="cors_origins",
    )
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # --- OpenRouter (single LLM gateway; see PLAN_PART_3 §11/§12) ---------------
    # Optional so test/CI settings can be built without a key; the real
    # OpenRouterClient validates its presence on construction (fails fast there).
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_title: str = "Argus Research Copilot"
    openrouter_app_url: str | None = None  # sent as HTTP-Referer

    # Per-node default models (OpenRouter model slugs; freely changeable). A
    # ``None`` per-node override falls back to ``llm_model_default``.
    llm_model_default: str = "openai/gpt-4o-mini"
    llm_model_planner: str | None = None
    llm_model_researcher: str | None = None  # researcher does no LLM work; reserved
    llm_model_signal_extractor: str | None = None
    llm_model_analyst: str = "anthropic/claude-sonnet-4.6"
    llm_model_quality_check: str | None = None
    llm_model_reporter: str = "anthropic/claude-sonnet-4.6"
    # Follow-up chat (PLAN_PART_5 §1); falls back to llm_model_default.
    llm_model_chat: str | None = None
    # Comma-separated like cors_origins; parsed below into a list.
    llm_fallback_models_raw: str = Field(
        default="openai/gpt-4o-mini,google/gemini-2.5-flash",
        validation_alias="llm_fallback_models",
    )

    # --- Search ----------------------------------------------------------------
    tavily_api_key: str | None = None
    search_provider: Literal["tavily", "ddg"] = "tavily"

    # --- Workflow control ------------------------------------------------------
    workflow_max_research_iterations: int = 2
    workflow_node_retry_limit: int = 2
    workflow_recursion_limit: int = 30
    # Per-run soft cost cap (USD). Exceeding it mid-run fails the run with
    # ``cost_cap_exceeded`` (PLAN_PART_5 §2.1).
    workflow_max_cost_usd: float = 1.0
    fetch_timeout_seconds: float = 8.0
    fetch_max_bytes: int = 1_000_000
    fetch_concurrency: int = 4
    search_results_per_query: int = 5

    # --- Rate limiting (slowapi; disabled when env == "test") ------------------
    rate_limit_default: str = "120/minute"
    rate_limit_create_session: str = "30/minute"
    rate_limit_run: str = "5/minute"
    rate_limit_chat: str = "30/minute"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins from the environment."""
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_fallback_models(self) -> list[str]:
        """Parse the comma-separated OpenRouter fallback model slugs."""
        return [
            slug.strip()
            for slug in self.llm_fallback_models_raw.split(",")
            if slug.strip()
        ]

    def redact(self) -> dict[str, str]:
        """Return settings safe to log — secrets masked (PLAN_PART_5 §2.1).

        Any field whose name hints at a secret is reduced to a presence marker so
        config can be logged on startup without leaking keys.
        """
        secret_hints = ("key", "secret", "token", "password", "uri")
        out: dict[str, str] = {}
        for name in type(self).model_fields:
            value = getattr(self, name)
            if value is None:
                out[name] = "<unset>"
            elif any(hint in name.lower() for hint in secret_hints):
                out[name] = "<set>" if value else "<unset>"
            else:
                out[name] = str(value)
        return out

    def model_for_node(self, node: str) -> str:
        """Resolve the model slug for ``node``, falling back to the default.

        Looks up ``llm_model_<node>``; an unset (``None``) per-node override
        resolves to :attr:`llm_model_default`.
        """
        override = getattr(self, f"llm_model_{node}", None)
        return override or self.llm_model_default


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    return Settings()

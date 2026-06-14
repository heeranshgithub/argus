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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins from the environment."""
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    return Settings()

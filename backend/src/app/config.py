"""Central configuration.

Keeping settings in one module avoids scattering environment-variable reads
through routers, services, migrations, and scripts. That makes local Docker,
tests, and future deployment targets use the same configuration contract.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = "postgresql+psycopg://emguidance:emguidance@db:5432/emguidance"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:4200"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(cls, value: str) -> str:
        """Accept platform-provided PostgreSQL URLs while using the installed psycopg v3 driver."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()


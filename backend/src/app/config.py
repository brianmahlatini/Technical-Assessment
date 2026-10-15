"""Central runtime configuration.

Why this file exists:
    Every environment-specific value should have one home. Docker, tests,
    Alembic migrations, seed scripts, and the FastAPI app all import these
    settings instead of reading environment variables independently. That keeps
    configuration names stable and makes deployment changes low-risk.

Important behaviour:
    The database URL validator accepts common PostgreSQL URL forms and normalises
    them to the installed psycopg v3 SQLAlchemy driver. It also supports hosted
    database URLs that expose a `schema=...` query parameter by translating that
    into the PostgreSQL `search_path` option psycopg understands.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    # Docker compose supplies this value for containers. The default keeps local
    # commands working when they run inside the Docker network.
    database_url: str = "postgresql+psycopg://emguidance:emguidance@db:5432/emguidance"

    # All public API routes mount under one prefix so the frontend and README
    # can refer to a stable versioned base path.
    api_prefix: str = "/api/v1"

    # CORS is intentionally narrow for the assessment: the Angular dev server is
    # allowed while arbitrary browser origins are not.
    frontend_origin: str = "http://localhost:4200"

    # `.env` support makes local tweaking possible without changing committed
    # source code. Extra variables are ignored so Docker can pass unrelated env.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(cls, value: str) -> str:
        """Accept common PostgreSQL URL variants while using the installed psycopg v3 driver."""
        # SQLAlchemy needs the `+psycopg` driver name to use the dependency this
        # backend installs. Many platforms provide plain `postgresql://` URLs.
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        return cls._move_schema_query_to_search_path(value)

    @staticmethod
    def _move_schema_query_to_search_path(value: str) -> str:
        """Translate `?schema=public` URLs into a psycopg-compatible search path."""
        # Parse the URL structurally so credentials, hosts, ports, and existing
        # query parameters are preserved exactly.
        parts = urlsplit(value)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))

        # Some hosted Postgres providers append `schema=...`; psycopg expects the
        # equivalent as `options=-csearch_path=...`.
        schema = query.pop("schema", None)
        if not schema:
            return value

        # Do not overwrite an explicit options value, because an operator may
        # already have chosen a more specific search path or PostgreSQL option.
        query.setdefault("options", f"-csearch_path={schema}")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


# Instantiate once so imports receive the same validated configuration object.
settings = Settings()


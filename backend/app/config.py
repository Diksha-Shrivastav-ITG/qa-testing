from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/shopify_qa"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-to-a-random-secret-key-at-least-32-chars"

    # Admin credentials
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme"

    # External APIs
    groq_api_key: str = ""
    figma_default_token: str = ""

    # CORS – stored as a comma-separated string, exposed as a list
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Worker concurrency
    max_concurrent_runs: int = 3

    # Storage
    storage_path: str = "/app/storage"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a list, stripping whitespace."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()

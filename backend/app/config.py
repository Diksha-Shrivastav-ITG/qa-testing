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
    secret_key: str = "IuqnCXYtJ9f4w0iV8UuuQwbkGiFyBvEedzIf9GTwEXW"

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Admin credentials
    admin_email: str = "admin@itgeeks.com"
    admin_password: str = "admin123"

    # External APIs
    groq_api_key: str = ""
    figma_default_token: str = ""

    # AWS Bedrock
    aws_access_key: str = ""
    aws_bedrock_secret_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-pro-v1:0"

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

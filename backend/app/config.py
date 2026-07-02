import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


def _default_upload_dir() -> str:
    if os.getenv("VERCEL"):
        return "/tmp/deskdibs-uploads"
    return str(Path(__file__).resolve().parent.parent / "uploads")


class Settings(BaseSettings):
    database_url: str = "postgresql://deskdibs:deskdibs@localhost:5432/deskdibs"
    secret_key: str = "deskdibs-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    upload_dir: str = _default_upload_dir()
    api_base_url: str | None = None
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str = "DeskDibs Admin"
    max_booking_days_ahead: int = 14
    max_active_reservations: int = 5
    frontend_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    admin_notification_email: str | None = None
    allowed_email_domain: str = "genpact.com"
    hf_api_key: str | None = Field(default=None, validation_alias="HF_API_KEY")
    hf_model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.2",
        validation_alias="HF_MODEL",
    )
    hf_provider: str = Field(
        default="featherless-ai",
        validation_alias="HF_PROVIDER",
    )

    class Config:
        env_file = ".env"

    @field_validator("hf_model", mode="before")
    @classmethod
    def normalize_hf_model(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        # Route all Mistral-7B-Instruct aliases to v0.2, which is live on Featherless AI.
        legacy_models = {
            "mistralai/Mistral-7B-Instruct": "mistralai/Mistral-7B-Instruct-v0.2",
            "mistralai/Mistral-7B-Instruct-v0.1": "mistralai/Mistral-7B-Instruct-v0.2",
            "mistralai/Mistral-7B-Instruct-v0.3": "mistralai/Mistral-7B-Instruct-v0.2",
        }
        return legacy_models.get(cleaned, cleaned)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        cleaned = value.replace("&channel_binding=require", "").replace("channel_binding=require&", "")
        return cleaned.rstrip("&?")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_configured(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+psycopg://"))

    @property
    def using_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()

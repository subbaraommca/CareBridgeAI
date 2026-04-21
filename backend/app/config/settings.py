from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareBridge AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api"
    fhir_default_version: str = "R5"
    fhir_base_url: str = Field(
        default="http://localhost:8080/fhir",
        validation_alias=AliasChoices("FHIR_BASE_URL", "CAREBRIDGE_FHIR_BASE_URL"),
    )
    fhir_timeout_seconds: float = 10.0
    fhir_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FHIR_ACCESS_TOKEN", "CAREBRIDGE_FHIR_AUTH_TOKEN"),
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "CAREBRIDGE_GEMINI_API_KEY"),
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "CAREBRIDGE_GEMINI_MODEL"),
    )
    postgres_dsn: str = Field(
        default="postgresql://carebridge:carebridge@postgres:5432/carebridge",
        validation_alias=AliasChoices("POSTGRES_URL", "CAREBRIDGE_POSTGRES_DSN"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CAREBRIDGE_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

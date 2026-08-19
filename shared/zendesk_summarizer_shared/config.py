"""Configuration settings for Zendesk Ticket Summarizer.

Loads environment variables and .env configuration cleanly using Pydantic Settings.
Never hardcodes credentials or secrets.
"""

from functools import lru_cache
import base64
import os
from pathlib import Path
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> Path:
    """Search upwards for a .env file from current working directory or file directory."""
    current = Path.cwd().resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    
    # Fallback to file's parent structure
    file_dir = Path(__file__).resolve().parent
    for parent in [file_dir] + list(file_dir.parents):
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate

    return Path(".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Zendesk Settings
    zendesk_subdomain: str = Field(
        default="",
        alias="ZENDESK_SUBDOMAIN",
        description="Zendesk account subdomain (e.g. 'acme' for https://acme.zendesk.com)",
    )
    zendesk_email: str = Field(
        default="",
        alias="ZENDESK_EMAIL",
        description="Zendesk account email used for API authentication",
    )
    zendesk_api_token: SecretStr = Field(
        default=SecretStr(""),
        alias="ZENDESK_API_TOKEN",
        description="Zendesk API Token for authentication",
    )
    zendesk_webhook_secret: SecretStr = Field(
        default=SecretStr(""),
        alias="ZENDESK_WEBHOOK_SECRET",
        description="Zendesk Webhook Signing Secret for HMAC-SHA256 signature verification",
    )


    # Gemini AI Settings
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="GEMINI_API_KEY",
        description="Google Gemini API Key",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        alias="GEMINI_MODEL",
        description="Gemini model version for ticket summarization",
    )

    # Groq AI Settings (Alternative provider for fallback/rate limit avoidance)
    groq_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="GROQ_API_KEY",
        description="Groq Cloud API Key",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        alias="GROQ_MODEL",
        description="Groq model version (e.g. llama-3.3-70b-versatile, llama3-70b-8192)",
    )

    # LLM Provider Selection: 'gemini' (default) or 'groq'
    llm_provider: str = Field(
        default="gemini",
        alias="LLM_PROVIDER",
        description="AI provider to use for summarization: 'gemini' or 'groq'",
    )

    # Server / Runtime Settings
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE", description="Rate limit per client per minute")
    sqlite_db_path: str = Field(default="data/audit.db", alias="SQLITE_DB_PATH", description="Path to SQLite audit DB")


    @property
    def zendesk_base_url(self) -> str:
        """Construct the Zendesk REST API base URL from subdomain."""
        subdomain = self.zendesk_subdomain.strip().lower()
        if not subdomain:
            return ""
        return f"https://{subdomain}.zendesk.com"

    @property
    def zendesk_auth_header(self) -> str:
        """Construct Zendesk Basic Auth header with {email}/token:{api_token} format."""
        email = self.zendesk_email.strip()
        token = self.zendesk_api_token.get_secret_value().strip()
        if not email or not token:
            return ""
        
        credentials = f"{email}/token:{token}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    @property
    def is_zendesk_configured(self) -> bool:
        """Check if all required Zendesk credentials are provided."""
        return bool(
            self.zendesk_subdomain.strip()
            and self.zendesk_email.strip()
            and self.zendesk_api_token.get_secret_value().strip()
        )

    @property
    def is_gemini_configured(self) -> bool:
        """Check if Gemini API key is provided."""
        return bool(self.gemini_api_key.get_secret_value().strip())

    @property
    def is_groq_configured(self) -> bool:
        """Check if Groq API key is provided."""
        return bool(self.groq_api_key.get_secret_value().strip())

    @property
    def is_webhook_secret_configured(self) -> bool:
        """Check if Zendesk webhook signing secret is configured."""
        return bool(self.zendesk_webhook_secret.get_secret_value().strip())



@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached instance of application settings."""
    return Settings()


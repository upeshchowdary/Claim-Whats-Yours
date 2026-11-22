"""Application settings, read from environment variables only."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field maps to an environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    app_name: str = "Claim What's Yours API"
    database_url: str = "sqlite:///./claim_whats_yours.db"
    admin_api_token: str = ""
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    log_level: str = "INFO"
    scheme_review_max_age_days: int = 180
    rate_limit_per_minute: int = 60

    # ---------------------------------------------------------------- Groq settings
    # Three independent credential slots. Empty slots are ignored at startup.
    # Keys are server-side only and must never appear in responses, logs, or frontend.
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""

    # Optional operator-defined team labels (for observability only — never the key itself).
    groq_team_label_1: str = "slot-1"
    groq_team_label_2: str = "slot-2"
    groq_team_label_3: str = "slot-3"

    groq_enabled: bool = False
    groq_api_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama3-8b-8192"  # Fast, cheap, supports JSON mode
    groq_timeout_seconds: float = 45.0
    groq_max_retries: int = 4
    groq_max_output_tokens: int = 2000

    # Circuit-breaker: open after this many consecutive 5xx / network failures.
    groq_circuit_breaker_threshold: int = 5
    # Seconds the circuit stays open before allowing a probe request.
    groq_circuit_breaker_reset_seconds: float = 60.0

    # ---------------------------------------------------------------- Data sources
    data_gov_in_enabled: bool = False
    data_gov_in_api_key: str = ""

    # ---------------------------------------------------------------- Notifications
    notifications_enabled: bool = False
    email_provider: str = ""
    email_api_key: str = ""
    sms_provider: str = ""
    sms_api_key: str = ""

    # SMTP (for null adapter and custom configs)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""

    # ---------------------------------------------------------------- Twilio (for SMS adapter)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()

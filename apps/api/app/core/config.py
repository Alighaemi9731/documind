from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Non-secret values have sensible defaults; secrets default to an empty
    string so the application can import and start without a configured
    environment (e.g. during local development or CI).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deployment / networking
    domain: str = "localhost"
    acme_email: str = ""
    admin_email: str = ""
    image_owner: str = "documind-app"
    image_tag: str = "latest"

    # Database
    postgres_user: str = "documind"
    postgres_password: str = ""
    postgres_db: str = "documind"
    database_url: str = "postgresql+asyncpg://documind:@postgres:5432/documind"

    # Secrets / keys
    jwt_secret: str = ""
    master_key_fernet: str = ""
    operator_default_gemini_key: str = ""

    # Application behaviour
    registration_mode: str = "open"
    default_provider: str = "google"
    max_upload_mb: int = 25
    ingest_concurrency: int = 1
    enable_local_embeddings: bool = False
    grounding_min_score: float = 0.55
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Runtime
    log_level: str = "info"
    environment: str = "production"
    public_base_url: str = "https://localhost"


settings = Settings()

import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum JWT signing-secret length in bytes (>= 256-bit / 32 bytes). The app
# refuses to start with a weaker secret (see Settings.validate_secrets).
MIN_JWT_SECRET_BYTES = 32


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
    uploads_dir: str = "/data/uploads"
    # Per-user cap on simultaneously-pending ingest jobs (429 over limit).
    max_pending_ingest_per_user: int = 20
    enable_local_embeddings: bool = False
    grounding_min_score: float = 0.55
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Runtime
    log_level: str = "info"
    environment: str = "production"
    public_base_url: str = "https://localhost"

    @property
    def refresh_cookie_secure(self) -> bool:
        """Refresh/CSRF cookies are Secure unless explicitly in development.

        Tests and local HTTP development set ENVIRONMENT=development so the
        cookie is accepted over plain HTTP; production always sets Secure.
        """
        return self.environment.lower() != "development"

    def allowed_origins(self) -> set[str]:
        """Origins accepted on cookie-bearing POSTs (refresh/logout).

        Derived from PUBLIC_BASE_URL (the configured apex). Origin/Referer of
        a cookie POST must match one of these (ADR-0001 allow-list).
        """
        origins: set[str] = set()
        base = self.public_base_url.rstrip("/")
        if base.startswith("https://"):
            origins.add(base)
        if self.domain:
            origins.add(f"https://{self.domain}")
        if self.environment.lower() == "development":
            # Local HTTP dev only — never weakens production.
            if self.domain:
                origins.add(f"http://{self.domain}")
            origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
        return origins

    def validate_secrets(self) -> None:
        """Fail fast on weak/missing secrets. Call from lifespan/startup.

        The ENVIRONMENT=test skip applies ONLY when actually running under
        pytest, so a production deploy cannot bypass validation by setting
        ENVIRONMENT=test. Raises RuntimeError so a misconfigured deploy refuses
        to boot.
        """
        running_under_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
        if self.environment.lower() == "test" and running_under_pytest:
            return
        secret = self.jwt_secret or ""
        if len(secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise RuntimeError(
                "JWT_SECRET must be at least "
                f"{MIN_JWT_SECRET_BYTES} bytes (256-bit); refusing to start."
            )
        # If a Fernet master key is configured it must be valid (BYOK in Phase 4
        # depends on it). Not yet *required* to be set.
        if self.master_key_fernet:
            try:
                from cryptography.fernet import Fernet

                Fernet(self.master_key_fernet.encode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "MASTER_KEY_FERNET is not a valid Fernet key; refusing to start."
                ) from exc


settings = Settings()

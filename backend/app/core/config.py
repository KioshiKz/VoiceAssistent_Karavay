from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://karavay:karavay@localhost:5432/karavay"
    database_snapshot_path: Path = BACKEND_ROOT / "data" / "karavay.sql"
    jwt_secret: str = "change-me-local-dev"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    frontend_origin: str = "http://localhost:5173"
    initial_admin_email: str = "admin@karavay.app"
    initial_admin_password: str = "change-me-now"
    scale_port: str = "auto"
    scale_baudrate: int = 9600
    onec_odata_url: str = ""
    onec_odata_user: str = ""
    onec_odata_password: str = ""

    @field_validator("database_snapshot_path")
    @classmethod
    def resolve_snapshot_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_ROOT / value).resolve()


settings = Settings()

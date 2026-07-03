from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://karavay:karavay@localhost:5432/karavay"
    jwt_secret: str = "change-me-local-dev"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    frontend_origin: str = "http://localhost:5173"
    initial_admin_email: str = "admin@karavay.app"
    initial_admin_password: str = "change-me-now"


settings = Settings()

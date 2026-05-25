from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5433/neomarket"
    )
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = False
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    B2B_BASE_URL: str = "http://b2b:8000"
    B2B_SERVICE_KEY: str = "change-me-in-production"
    B2B_TIMEOUT_SECONDS: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

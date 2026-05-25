from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

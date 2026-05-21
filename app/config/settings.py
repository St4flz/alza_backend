from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FinanzasAPI"
    APP_ENV: str = "development"
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_SECRET_KEY: str | None = None
    API_V1_PREFIX: str = "/api/v1"

    class Config:
        env_file = ".env"

settings = Settings()
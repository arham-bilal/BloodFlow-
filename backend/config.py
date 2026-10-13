from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    RESEND_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    EMAIL_FROM: str = "BloodLink <alerts@example.com>"
    APP_BASE_URL: str = "http://localhost:5500"
    CORS_ORIGINS: str = "http://localhost:5500"
    DEFAULT_RADIUS_KM: float = 10
    MIN_DAYS_BETWEEN_DONATIONS: int = 90  # simple cool-off, NOT a medical eligibility check
    JWT_EXPIRE_MIN: int = 60
    CREATE_TABLES: bool = False
    API_DOCS_ENABLED: bool = True
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

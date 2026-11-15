from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "z-ai/glm-5.3-flash"

    # Scheduled security sweeps (audit all known systems/assets)
    AUDIT_SCHEDULE_ENABLED: bool = True
    AUDIT_SCHEDULE_SECONDS: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
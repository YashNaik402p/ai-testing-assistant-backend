from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration, loaded from environment variables / .env.
    Mirrors the deployment diagram's "AI Provider Interface" env-based switch.
    """

    # Database
    database_url: str = ""

    # Auth
    secret_key: str = "change-this-to-a-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

   
    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

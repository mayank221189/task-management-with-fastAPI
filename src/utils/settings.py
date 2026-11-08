from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DB_CONNECTION_STRING: str


settings = Settings()  # type: ignore[call-arg]
print(settings.DB_CONNECTION_STRING)

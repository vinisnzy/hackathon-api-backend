"""Configuracao da aplicacao, lida do ambiente (.env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = Field(
        default="postgresql+psycopg://frota:frota@localhost:5432/frota",
        alias="DATABASE_URL",
    )
    # O pool precisa acompanhar o threadpool do FastAPI: endpoints sincronos
    # rodam em ate 40 threads, e um pool menor vira timeout quando varios
    # carros descarregam no patio ao mesmo tempo.
    db_pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, alias="DB_MAX_OVERFLOW")


@lru_cache
def get_settings() -> Settings:
    return Settings()

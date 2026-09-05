"""Configuracao da aplicacao, lida do ambiente (.env)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = Field(
        default="postgresql+psycopg://frota:frota@localhost:5432/frota",
        alias="DATABASE_URL",
    )
    device_token: str = Field(default="", alias="DEVICE_TOKEN")

    # O pool precisa acompanhar o threadpool do FastAPI: endpoints sincronos
    # rodam em ate 40 threads, e um pool menor vira timeout quando varios
    # carros descarregam no patio ao mesmo tempo.
    db_pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, alias="DB_MAX_OVERFLOW")

    @field_validator("device_token")
    @classmethod
    def _token_obrigatorio(cls, v: str) -> str:
        # Falha fechada: com token vazio, um header vazio passaria na comparacao
        # e qualquer um poderia injetar quilometragem na prestacao de contas.
        if not v.strip():
            raise ValueError(
                "DEVICE_TOKEN nao pode ser vazio: defina-o no .env ou no ambiente."
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()

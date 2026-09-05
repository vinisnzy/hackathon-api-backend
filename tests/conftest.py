"""Fixtures de teste.

O banco e um Postgres de verdade, nao SQLite: a idempotencia depende de
ON CONFLICT sobre uma constraint nomeada e a rota e JSONB. Testar contra outro
dialeto validaria um sistema que nao e o que roda em producao.

O schema e montado com "alembic upgrade head", nao com create_all -- e o unico
jeito de pegar deriva em nome de constraint, server_default e indice.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://frota:frota@127.0.0.1:5432/frota_test"
)
os.environ.setdefault("DEVICE_TOKEN", "token-de-teste")

import datetime as dt  # noqa: E402
import uuid  # noqa: E402
from typing import Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Carro, Secretaria  # noqa: E402

TOKEN = os.environ["DEVICE_TOKEN"]


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Recria o schema do zero e aplica as migrations."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture
def db(schema: None) -> Iterator[Session]:
    """Sessao isolada: tudo que o teste grava some no fim.

    join_transaction_mode="create_savepoint" faz o commit do service virar
    release de savepoint em vez de commit real, entao o rollback externo
    limpa tudo -- inclusive o que passou por db.commit().
    """
    conn = engine.connect()
    trans = conn.begin()
    sessao = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield sessao
    finally:
        sessao.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def carro(db: Session) -> Carro:
    """Um carro cadastrado, com dispositivo conhecido."""
    secretaria = Secretaria(nome=f"SESAU-{uuid.uuid4().hex[:6]}")
    db.add(secretaria)
    db.flush()
    c = Carro(
        modelo="Gol",
        marca="Volkswagen",
        numero_frota="0157",
        placa="BAZ-1D23",
        dispositivo_id="esp32-0157",
        secretaria_id=secretaria.id,
    )
    db.add(c)
    db.flush()
    return c


def cabecalho(token: str = TOKEN) -> dict[str, str]:
    return {"X-Device-Token": token}


def posicao(
    ts: str,
    lat: float,
    lon: float,
    *,
    fix: bool = True,
    hdop: float = 1.2,
    sats: int = 9,
    vel: float = 30.0,
) -> dict:
    return {
        "ts": ts,
        "lat": lat,
        "lon": lon,
        "hdop": hdop,
        "sats": sats,
        "velKmh": vel,
        "fixValido": fix,
    }


def lote(dispositivo: str = "esp32-0157", lote_id: str = "a3f1c9", **extras) -> dict:
    """O payload do enunciado, com as tres posicoes do exemplo."""
    corpo = {
        "dispositivoId": dispositivo,
        "placa": "BAZ-1D23",
        "loteId": lote_id,
        "enviadoEm": "2026-09-05T09:41:00-03:00",
        "posicoes": [
            posicao("2026-09-05T08:12:04Z", -24.95550, -53.45520, vel=0.0),
            posicao("2026-09-05T08:12:14Z", -24.95604, -53.45712, vel=31.4, sats=10, hdop=1.1),
            posicao("2026-09-05T08:12:24Z", 0.0, 0.0, fix=False, hdop=99, sats=0, vel=0.0),
        ],
    }
    corpo.update(extras)
    return corpo

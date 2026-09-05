"""Acesso a dados de viagem. Sem regra de negocio, sem HTTP."""

import datetime as dt
import uuid
from typing import Any, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models import Carro, Viagem


def busca_por_lote(
    db: Session, carro_id: uuid.UUID, lote_id: str
) -> uuid.UUID | None:
    return db.execute(
        select(Viagem.id).where(
            Viagem.carro_id == carro_id, Viagem.lote_id == lote_id
        )
    ).scalar_one_or_none()


def insere_se_novo(db: Session, valores: dict[str, Any]) -> uuid.UUID | None:
    """INSERT ... ON CONFLICT DO NOTHING.

    Fecha a corrida entre dois reenvios simultaneos sem depender de capturar
    excecao: zero linhas de volta significa que o lote ja estava gravado. Uma
    captura generica de IntegrityError mascararia violacao de FK como
    "duplicada" -- e o dispositivo apagaria o SD de um dado que nao entrou.
    """
    stmt = (
        insert(Viagem)
        .values(**valores)
        .on_conflict_do_nothing(constraint="uq_viagem_carro_lote")
        .returning(Viagem.id)
    )
    return db.execute(stmt).scalar_one_or_none()


def _base_listagem(
    carro_id: uuid.UUID | None,
    secretaria_id: uuid.UUID | None,
    inicio: dt.datetime | None,
    fim: dt.datetime | None,
) -> Select:
    stmt = select(Viagem)
    if carro_id is not None:
        stmt = stmt.where(Viagem.carro_id == carro_id)
    if secretaria_id is not None:
        # secretaria nao esta em viagem: o filtro passa pelo carro.
        stmt = stmt.join(Carro, Carro.id == Viagem.carro_id).where(
            Carro.secretaria_id == secretaria_id
        )
    if inicio is not None:
        stmt = stmt.where(Viagem.inicio >= inicio)
    if fim is not None:
        stmt = stmt.where(Viagem.inicio <= fim)
    return stmt


def conta(
    db: Session,
    carro_id: uuid.UUID | None = None,
    secretaria_id: uuid.UUID | None = None,
    inicio: dt.datetime | None = None,
    fim: dt.datetime | None = None,
) -> int:
    base = _base_listagem(carro_id, secretaria_id, inicio, fim).subquery()
    return db.execute(select(func.count()).select_from(base)).scalar_one()


def lista(
    db: Session,
    *,
    carro_id: uuid.UUID | None = None,
    secretaria_id: uuid.UUID | None = None,
    inicio: dt.datetime | None = None,
    fim: dt.datetime | None = None,
    offset: int = 0,
    limit: int = 20,
    com_relacionamentos: bool = False,
) -> Sequence[Viagem]:
    stmt = _base_listagem(carro_id, secretaria_id, inicio, fim)
    # O desempate por id e obrigatorio: sem ele, viagens com o mesmo "inicio"
    # trocam de lugar entre paginas e o cliente ve linha repetida ou perdida.
    stmt = stmt.order_by(Viagem.inicio.desc(), Viagem.id.desc())
    if com_relacionamentos:
        stmt = stmt.options(
            selectinload(Viagem.carro).selectinload(Carro.secretaria),
            selectinload(Viagem.servidor),
        )
    return db.execute(stmt.offset(offset).limit(limit)).scalars().all()


def busca_detalhe(db: Session, viagem_id: uuid.UUID) -> Viagem | None:
    return db.execute(
        select(Viagem)
        .where(Viagem.id == viagem_id)
        .options(
            selectinload(Viagem.carro).selectinload(Carro.secretaria),
            selectinload(Viagem.servidor),
        )
    ).scalar_one_or_none()


def busca_rota(db: Session, viagem_id: uuid.UUID) -> list[dict[str, Any]] | None:
    """Le so o JSONB, sem materializar o objeto ORM."""
    return db.execute(
        select(Viagem.rota).where(Viagem.id == viagem_id)
    ).scalar_one_or_none()


def lista_com_rota(
    db: Session,
    *,
    carro_id: uuid.UUID | None = None,
    secretaria_id: uuid.UUID | None = None,
    inicio: dt.datetime | None = None,
    fim: dt.datetime | None = None,
    limit: int = 200,
) -> Sequence[Viagem]:
    """Listagem para o mapa: aqui o JSONB e carregado de proposito.

    E o unico lugar que faz undefer(rota) em varias linhas -- por isso o limite
    e menor que o da listagem tabular: 200 rotas de 300 pontos ja sao alguns
    megabytes de resposta.
    """
    from sqlalchemy.orm import undefer

    stmt = (
        _base_listagem(carro_id, secretaria_id, inicio, fim)
        .order_by(Viagem.inicio.desc(), Viagem.id.desc())
        .options(
            undefer(Viagem.rota),
            selectinload(Viagem.carro).selectinload(Carro.secretaria),
        )
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def busca_com_rota(db: Session, viagem_id: uuid.UUID) -> Viagem | None:
    from sqlalchemy.orm import undefer

    return db.execute(
        select(Viagem)
        .where(Viagem.id == viagem_id)
        .options(
            undefer(Viagem.rota),
            selectinload(Viagem.carro).selectinload(Carro.secretaria),
        )
    ).scalar_one_or_none()

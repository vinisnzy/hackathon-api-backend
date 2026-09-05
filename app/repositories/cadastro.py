"""Acesso a dados dos cadastros (secretaria, servidor, carro)."""

import uuid
from typing import Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Carro, Secretaria, Servidor

Modelo = TypeVar("Modelo", Secretaria, Servidor, Carro)


def busca(db: Session, modelo: type[Modelo], id_: uuid.UUID) -> Modelo | None:
    return db.get(modelo, id_)


def lista(
    db: Session, modelo: type[Modelo], offset: int = 0, limit: int = 50
) -> Sequence[Modelo]:
    return (
        db.execute(select(modelo).order_by(modelo.id).offset(offset).limit(limit))
        .scalars()
        .all()
    )


def conta(db: Session, modelo: type[Modelo]) -> int:
    from sqlalchemy import func

    return db.execute(select(func.count()).select_from(modelo)).scalar_one()


def busca_carro_por_dispositivo(db: Session, dispositivo_id: str) -> Carro | None:
    return db.execute(
        select(Carro).where(Carro.dispositivo_id == dispositivo_id)
    ).scalar_one_or_none()

"""Regras de CRUD dos cadastros."""

import uuid
from typing import Any, TypeVar

from psycopg import errors as pgerrors
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflito, NaoEncontrado
from app.models import Base

Modelo = TypeVar("Modelo", bound=Base)


def _traduz_integridade(exc: IntegrityError) -> Conflito:
    """Transforma violacao do banco em 409 com mensagem util."""
    orig = exc.orig
    if isinstance(orig, pgerrors.UniqueViolation):
        return Conflito("ja existe um registro com esse valor unico")
    if isinstance(orig, pgerrors.ForeignKeyViolation):
        return Conflito(
            "registro referenciado por outro (ou referencia inexistente)"
        )
    if isinstance(orig, pgerrors.NotNullViolation):
        return Conflito("campo obrigatorio ausente")
    return Conflito("violacao de integridade")


def cria(db: Session, modelo: type[Modelo], dados: dict[str, Any]) -> Modelo:
    obj = modelo(**dados)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _traduz_integridade(exc) from exc
    db.refresh(obj)
    return obj


def atualiza(
    db: Session, modelo: type[Modelo], id_: uuid.UUID, dados: dict[str, Any]
) -> Modelo:
    obj = db.get(modelo, id_)
    if obj is None:
        raise NaoEncontrado(f"{modelo.__tablename__} {id_} nao encontrado")
    for campo, valor in dados.items():
        setattr(obj, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _traduz_integridade(exc) from exc
    db.refresh(obj)
    return obj


def remove(db: Session, modelo: type[Modelo], id_: uuid.UUID) -> None:
    obj = db.get(modelo, id_)
    if obj is None:
        raise NaoEncontrado(f"{modelo.__tablename__} {id_} nao encontrado")
    db.delete(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        # FK RESTRICT: apagar um carro que tem viagens apagaria o historico de
        # quilometragem junto. O 409 e a resposta certa.
        db.rollback()
        raise _traduz_integridade(exc) from exc


def obtem(db: Session, modelo: type[Modelo], id_: uuid.UUID) -> Modelo:
    obj = db.get(modelo, id_)
    if obj is None:
        raise NaoEncontrado(f"{modelo.__tablename__} {id_} nao encontrado")
    return obj

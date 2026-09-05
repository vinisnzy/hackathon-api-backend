"""CRUD de secretaria, servidor e carro.

A API nao tem autenticacao (MVP de hackathon). A unica concessao a privacidade
e o CPF, que nao aparece na listagem (ver ServidorListItem).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Carro, Secretaria, Servidor
from app.repositories import cadastro as repo
from app.schemas.cadastro import (
    CarroIn,
    CarroOut,
    SecretariaIn,
    SecretariaOut,
    ServidorIn,
    ServidorListItem,
    ServidorOut,
)
from app.schemas.common import Erro, Page
from app.services import cadastro_service

router = APIRouter(prefix="/api", tags=["cadastros"])

CONFLITO = {409: {"model": Erro}}
NAO_ENCONTRADO = {404: {"model": Erro}}


def _pagina(db: Session, modelo, schema, page: int, size: int):
    total = repo.conta(db, modelo)
    itens = repo.lista(db, modelo, offset=(page - 1) * size, limit=size)
    return {
        "items": [schema.model_validate(i) for i in itens],
        "page": page,
        "size": size,
        "total": total,
        "pages": (total + size - 1) // size if size else 0,
    }


# ---------------------------------------------------------------- secretaria

@router.post(
    "/secretarias",
    response_model=SecretariaOut,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLITO,
)
def cria_secretaria(dados: SecretariaIn, db: Session = Depends(get_db)):
    return cadastro_service.cria(db, Secretaria, dados.model_dump())


@router.get("/secretarias", response_model=Page[SecretariaOut])
def lista_secretarias(
    db: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return _pagina(db, Secretaria, SecretariaOut, page, size)


@router.get(
    "/secretarias/{id_}", response_model=SecretariaOut, responses=NAO_ENCONTRADO
)
def obtem_secretaria(id_: uuid.UUID, db: Session = Depends(get_db)):
    return cadastro_service.obtem(db, Secretaria, id_)


@router.put(
    "/secretarias/{id_}",
    response_model=SecretariaOut,
    responses={**NAO_ENCONTRADO, **CONFLITO},
)
def atualiza_secretaria(
    id_: uuid.UUID, dados: SecretariaIn, db: Session = Depends(get_db)
):
    return cadastro_service.atualiza(db, Secretaria, id_, dados.model_dump())


@router.delete(
    "/secretarias/{id_}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NAO_ENCONTRADO, **CONFLITO},
)
def remove_secretaria(id_: uuid.UUID, db: Session = Depends(get_db)):
    cadastro_service.remove(db, Secretaria, id_)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ servidor

@router.post(
    "/servidores",
    response_model=ServidorOut,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLITO,
)
def cria_servidor(dados: ServidorIn, db: Session = Depends(get_db)):
    return cadastro_service.cria(db, Servidor, dados.model_dump())


@router.get("/servidores", response_model=Page[ServidorListItem])
def lista_servidores(
    db: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return _pagina(db, Servidor, ServidorListItem, page, size)


@router.get("/servidores/{id_}", response_model=ServidorOut, responses=NAO_ENCONTRADO)
def obtem_servidor(id_: uuid.UUID, db: Session = Depends(get_db)):
    return cadastro_service.obtem(db, Servidor, id_)


@router.put(
    "/servidores/{id_}",
    response_model=ServidorOut,
    responses={**NAO_ENCONTRADO, **CONFLITO},
)
def atualiza_servidor(
    id_: uuid.UUID, dados: ServidorIn, db: Session = Depends(get_db)
):
    return cadastro_service.atualiza(db, Servidor, id_, dados.model_dump())


@router.delete(
    "/servidores/{id_}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NAO_ENCONTRADO, **CONFLITO},
)
def remove_servidor(id_: uuid.UUID, db: Session = Depends(get_db)):
    cadastro_service.remove(db, Servidor, id_)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------- carro

@router.post(
    "/carros",
    response_model=CarroOut,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLITO,
)
def cria_carro(dados: CarroIn, db: Session = Depends(get_db)):
    return cadastro_service.cria(db, Carro, dados.model_dump())


@router.get("/carros", response_model=Page[CarroOut])
def lista_carros(
    db: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return _pagina(db, Carro, CarroOut, page, size)


@router.get("/carros/{id_}", response_model=CarroOut, responses=NAO_ENCONTRADO)
def obtem_carro(id_: uuid.UUID, db: Session = Depends(get_db)):
    return cadastro_service.obtem(db, Carro, id_)


@router.put(
    "/carros/{id_}", response_model=CarroOut, responses={**NAO_ENCONTRADO, **CONFLITO}
)
def atualiza_carro(id_: uuid.UUID, dados: CarroIn, db: Session = Depends(get_db)):
    return cadastro_service.atualiza(db, Carro, id_, dados.model_dump())


@router.delete(
    "/carros/{id_}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NAO_ENCONTRADO, **CONFLITO},
)
def remove_carro(id_: uuid.UUID, db: Session = Depends(get_db)):
    cadastro_service.remove(db, Carro, id_)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

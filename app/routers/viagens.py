"""Ingestao e leitura de viagens."""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NaoEncontrado
from app.repositories import viagem as repo
from app.schemas.common import Erro, Page
from app.schemas.geojson import FeatureCollection
from app.schemas.lote import LoteIn
from app.schemas.viagem import (
    ViagemAceitaOut,
    ViagemDetalhe,
    ViagemDuplicadaOut,
    ViagemListItem,
)
from app.services import geojson_service, viagem_service

router = APIRouter(prefix="/api/viagens", tags=["viagens"])

MAX_ROTAS_NO_MAPA = 200


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ViagemAceitaOut,
    responses={
        200: {"model": ViagemDuplicadaOut, "description": "Lote ja recebido antes"},
        422: {"model": Erro, "description": "Payload invalido"},
    },
    summary="Recebe um lote de posicoes gravado offline pelo ESP32",
)
def recebe_lote(lote: LoteIn, db: Session = Depends(get_db)) -> Any:
    resposta, criada = viagem_service.processa_lote(db, lote)
    if not criada:
        # Corpo fixo e curto: devolver JSONResponse direto evita
        # response_model=Union[...], onde a smart-union do Pydantic v2 pode
        # escolher o membro errado.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=resposta.model_dump(mode="json"),
        )
    return resposta


@router.get("", response_model=Page[ViagemListItem], summary="Lista viagens")
def lista_viagens(
    db: Session = Depends(get_db),
    carro_id: uuid.UUID | None = None,
    secretaria_id: uuid.UUID | None = None,
    inicio: dt.datetime | None = None,
    fim: dt.datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ViagemListItem]:
    total = repo.conta(db, carro_id, secretaria_id, inicio, fim)
    itens = repo.lista(
        db,
        carro_id=carro_id,
        secretaria_id=secretaria_id,
        inicio=inicio,
        fim=fim,
        offset=(page - 1) * size,
        limit=size,
    )
    return Page[ViagemListItem](
        items=[ViagemListItem.model_validate(v) for v in itens],
        page=page,
        size=size,
        total=total,
        pages=(total + size - 1) // size if size else 0,
    )


@router.get(
    "/geojson",
    response_model=FeatureCollection,
    response_model_by_alias=True,
    summary="Varias viagens em GeoJSON, para desenhar no mapa",
)
def viagens_geojson(
    db: Session = Depends(get_db),
    carro_id: uuid.UUID | None = None,
    secretaria_id: uuid.UUID | None = None,
    inicio: dt.datetime | None = None,
    fim: dt.datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_ROTAS_NO_MAPA)] = 50,
) -> FeatureCollection:
    viagens = repo.lista_com_rota(
        db,
        carro_id=carro_id,
        secretaria_id=secretaria_id,
        inicio=inicio,
        fim=fim,
        limit=limit,
    )
    return geojson_service.colecao(viagens)


@router.get(
    "/{viagem_id}",
    response_model=ViagemDetalhe,
    responses={404: {"model": Erro}},
    summary="Detalhe da viagem, sem a rota",
)
def detalhe(viagem_id: uuid.UUID, db: Session = Depends(get_db)) -> ViagemDetalhe:
    viagem = repo.busca_detalhe(db, viagem_id)
    if viagem is None:
        raise NaoEncontrado(f"viagem {viagem_id} nao encontrada")
    return ViagemDetalhe.model_validate(viagem)


@router.get(
    "/{viagem_id}/rota",
    responses={404: {"model": Erro}},
    summary="Array bruto de posicoes, como o dispositivo enviou",
)
def rota(viagem_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rota_bruta = repo.busca_rota(db, viagem_id)
    if rota_bruta is None:
        raise NaoEncontrado(f"viagem {viagem_id} nao encontrada")
    return rota_bruta


@router.get(
    "/{viagem_id}/geojson",
    response_model=FeatureCollection,
    response_model_by_alias=True,
    responses={404: {"model": Erro}},
    summary="A viagem em GeoJSON",
)
def viagem_geojson(
    viagem_id: uuid.UUID, db: Session = Depends(get_db)
) -> FeatureCollection:
    viagem = repo.busca_com_rota(db, viagem_id)
    if viagem is None:
        raise NaoEncontrado(f"viagem {viagem_id} nao encontrada")
    return geojson_service.colecao([viagem])

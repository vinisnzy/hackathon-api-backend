"""GeoJSON servido ao frontend.

A estrutura externa e rigida (RFC 7946): "type", "features", "geometry",
"LineString" e a ordem das coordenadas nao sao negociaveis. Coordenada em
GeoJSON e [longitude, latitude] -- invertida em relacao ao habito de falar
"lat, lon". Trocar a ordem coloca Cascavel na Antartida.

"properties" e livre: carrega apenas o que o frontend precisa exibir.
"""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Uma LineString exige no minimo duas posicoes (RFC 7946, secao 3.1.4).
MIN_POSICOES_LINESTRING = 2


class LineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    # [[lon, lat], ...]
    coordinates: list[Annotated[list[float], Field(min_length=2, max_length=2)]]


class PropriedadesViagem(BaseModel):
    """Campos livres, em camelCase, para o frontend desenhar o popup."""

    viagem_id: UUID = Field(serialization_alias="viagemId")
    lote_id: str = Field(serialization_alias="loteId")
    placa: str
    numero_frota: str = Field(serialization_alias="numeroFrota")
    secretaria: str
    saida_em: dt.datetime = Field(serialization_alias="saidaEm")
    chegada_em: dt.datetime = Field(serialization_alias="chegadaEm")
    distancia_gps_metros: int = Field(serialization_alias="distanciaGpsMetros")
    qtd_pontos: int = Field(serialization_alias="qtdPontos")


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: PropriedadesViagem
    geometry: LineString


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]

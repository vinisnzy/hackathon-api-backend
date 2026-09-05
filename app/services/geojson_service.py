"""Montagem do GeoJSON entregue ao frontend.

A geometria e reconstruida a partir do JSONB gravado, aplicando o mesmo filtro
de fix da ingestao. Isso e proposital: o mapa desenha exatamente o conjunto de
pontos que produziu o km_gps da coluna, e nao uma segunda versao da verdade.
"""

import datetime as dt
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from app.models import Viagem
from app.schemas.geojson import (
    MIN_POSICOES_LINESTRING,
    Feature,
    FeatureCollection,
    LineString,
    PropriedadesViagem,
)

# Armazenamento e sempre UTC; a conversao acontece so na exibicao.
FUSO_EXIBICAO = ZoneInfo("America/Sao_Paulo")


def _local(momento: dt.datetime) -> dt.datetime:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=dt.timezone.utc)
    return momento.astimezone(FUSO_EXIBICAO)


def _coordenadas(rota: Sequence[dict[str, Any]]) -> list[list[float]]:
    """[[lon, lat], ...] -- GeoJSON e longitude primeiro (RFC 7946)."""
    validas = [p for p in rota if p.get("fixValido")]
    validas.sort(key=lambda p: p["ts"])
    coords = [[float(p["lon"]), float(p["lat"])] for p in validas]

    # Uma LineString exige duas posicoes. Uma viagem com um unico ponto valido
    # e rara mas possivel (carro que ligou e desligou); repetir a coordenada
    # mantem o GeoJSON valido e o mapa desenha um ponto.
    if len(coords) == 1:
        coords.append(list(coords[0]))
    return coords


def viagem_para_feature(viagem: Viagem) -> Feature:
    return Feature(
        properties=PropriedadesViagem(
            viagem_id=viagem.id,
            lote_id=viagem.lote_id,
            placa=viagem.carro.placa,
            numero_frota=viagem.carro.numero_frota,
            secretaria=viagem.carro.secretaria.nome,
            saida_em=_local(viagem.inicio),
            chegada_em=_local(viagem.fim),
            # km_gps e Numeric(10,2); *1000 da metros inteiros exatos.
            distancia_gps_metros=int(viagem.km_gps * 1000),
            qtd_pontos=viagem.qtd_pontos,
        ),
        geometry=LineString(coordinates=_coordenadas(viagem.rota)),
    )


def colecao(viagens: Sequence[Viagem]) -> FeatureCollection:
    return FeatureCollection(features=[viagem_para_feature(v) for v in viagens])

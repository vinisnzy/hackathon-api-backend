"""Calculo geodesico da quilometragem.

Este modulo produz um numero que vai para prestacao de contas publica. Duas
regras nao negociaveis moram aqui:

1. Nenhum filtro alem dos dois especificados (fix invalido e deslocamento
   < 5 m). Filtro nao especificado altera um numero auditado: se alguem
   depois adicionar um corte por velocidade maxima "para melhorar", a
   quilometragem historica deixa de ser reproduzivel.
2. Arredondamento decimal com ROUND_HALF_UP, nunca round(). round() e
   banker's rounding sobre ponto flutuante binario: round(2.25, 1) == 2.2.
"""

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# Raio medio da Terra (IUGG), em metros.
RAIO_TERRA_M = 6_371_008.8

# Abaixo disto e ruido de GPS parado, nao deslocamento. Um carro desligado no
# patio "anda" alguns metros por minuto so pela flutuacao do sinal; sem este
# corte a frota inteira acumula quilometragem fantasma.
CORTE_RUIDO_M = 5.0

VERSAO_CALCULO = 1


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia em metros entre dois pontos sobre a esfera."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * RAIO_TERRA_M * math.asin(math.sqrt(a))


def distancia_m(coordenadas: Sequence[tuple[float, float]]) -> float:
    """Soma dos deslocamentos, ignorando os trechos menores que o corte.

    Recebe pares (lat, lon) JA ordenados por tempo. A soma corre em float e a
    quantizacao acontece uma unica vez, no fim -- quantizar por segmento
    acumularia o erro de arredondamento ponto a ponto.
    """
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(coordenadas, coordenadas[1:]):
        trecho = haversine_m(lat1, lon1, lat2, lon2)
        if trecho >= CORTE_RUIDO_M:
            total += trecho
    return total


def quantiza_km(metros: float) -> Decimal:
    """Metros -> km com 2 casas, meio para cima."""
    return Decimal(str(metros / 1000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def km_da_rota(posicoes_validas: Sequence[Any]) -> Decimal:
    """Quilometragem de uma lista de posicoes ja filtrada e ordenada."""
    coords = [(p.lat, p.lon) for p in posicoes_validas]
    return quantiza_km(distancia_m(coords))

"""Calculo de quilometragem: distancia, filtro de ruido e arredondamento.

Testes puros, sem banco -- este e o numero que vai para prestacao de contas.
"""

from decimal import Decimal

import pytest

from app.services.geo import (
    CORTE_RUIDO_M,
    distancia_m,
    haversine_m,
    quantiza_km,
)


def test_haversine_contra_distancia_conhecida():
    """Um grau de latitude no equador ~ 111,19 km sobre a esfera media."""
    d = haversine_m(0.0, 0.0, 1.0, 0.0)
    assert d == pytest.approx(111_194.9, abs=1.0)


def test_haversine_e_simetrico():
    a = haversine_m(-24.95550, -53.45520, -24.95604, -53.45712)
    b = haversine_m(-24.95604, -53.45712, -24.95550, -53.45520)
    assert a == pytest.approx(b)


def test_trecho_real_de_cascavel():
    """Os dois primeiros pontos do lote de exemplo distam ~200 m."""
    d = haversine_m(-24.95550, -53.45520, -24.95604, -53.45712)
    assert 195.0 < d < 210.0


def test_carro_parado_nao_acumula_quilometragem():
    """Jitter de GPS parado deve somar exatamente zero.

    Este e o caso que motiva o corte: sem ele, um carro desligado no patio
    acumula quilometragem fantasma na prestacao de contas.
    """
    jitter = [
        (-24.955500, -53.455200),
        (-24.955512, -53.455208),
        (-24.955498, -53.455195),
        (-24.955505, -53.455210),
        (-24.955493, -53.455199),
    ]
    # Nenhum passo do jitter chega perto do corte.
    for p1, p2 in zip(jitter, jitter[1:]):
        assert haversine_m(*p1, *p2) < CORTE_RUIDO_M

    assert distancia_m(jitter) == 0.0
    assert quantiza_km(distancia_m(jitter)) == Decimal("0.00")


def test_corte_ignora_apenas_o_trecho_curto():
    """Um trecho longo continua contando mesmo cercado de ruido."""
    pontos = [
        (-24.955500, -53.455200),
        (-24.955505, -53.455203),  # ruido, < 5 m
        (-24.960000, -53.460000),  # deslocamento real
        (-24.960004, -53.460002),  # ruido, < 5 m
    ]
    real = haversine_m(-24.955505, -53.455203, -24.960000, -53.460000)
    assert distancia_m(pontos) == pytest.approx(real)


def test_ponto_unico_tem_distancia_zero():
    assert distancia_m([(-24.9555, -53.4552)]) == 0.0
    assert distancia_m([]) == 0.0


def test_arredondamento_e_meio_para_cima():
    """ROUND_HALF_UP, nao o banker's rounding do round().

    125 m = 0,125 km -- um dos poucos valores exatos em binario, entao o
    empate e real: round() vai para o par (0,12) e a prestacao de contas
    espera 0,13. Em 2,675 o erro aparece pelo outro motivo, a representacao
    binaria ficar logo abaixo do meio.
    """
    assert quantiza_km(125.0) == Decimal("0.13")
    assert round(0.125, 2) == 0.12  # o comportamento que estamos evitando

    assert quantiza_km(2675.0) == Decimal("2.68")
    assert round(2.675, 2) == 2.67


def test_quantizacao_acontece_uma_vez_so():
    """Somar em float e quantizar no fim, nao quantizar por segmento."""
    passo = 1234.5  # metros
    pontos_m = [passo] * 3
    esperado = quantiza_km(sum(pontos_m))
    por_segmento = sum(quantiza_km(m) for m in pontos_m)
    assert esperado == Decimal("3.70")
    # Quantizar cedo perde um centesimo por segmento: 3 x 1,23 = 3,69.
    assert por_segmento == Decimal("3.69")

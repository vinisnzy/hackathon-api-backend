"""Descarte de leituras sem fix de GPS.

Sem fix, o modulo emite lat=0, lon=0 -- a "Ilha Nula", no golfo da Guine, a
uns 9.500 km de Cascavel. Um unico desses pontos numa rota dobra a
quilometragem da frota. O ponto e descartado do calculo, mas continua no JSONB
bruto: e o registro que sustenta a auditoria.
"""

from decimal import Decimal

from sqlalchemy import select

from app.models import Viagem
from app.services.geo import km_da_rota
from tests.conftest import lote, posicao


def test_ponto_sem_fix_nao_entra_na_quilometragem(client, carro, db):
    r = client.post("/api/viagens", json=lote())
    assert r.status_code == 201

    corpo = r.json()
    assert corpo["pontos_recebidos"] == 3
    assert corpo["pontos_validos"] == 2

    # Os dois pontos validos distam ~200 m. Se a Ilha Nula tivesse entrado, o
    # numero passaria de 9.000 km.
    km = Decimal(str(corpo["km_gps"]))
    assert km < Decimal("1.00"), f"Ilha Nula entrou no calculo: {km} km"
    assert km == Decimal("0.20")


def test_rota_bruta_preserva_o_ponto_descartado(client, carro, db):
    """O descarte e do calculo, nao do registro."""
    client.post("/api/viagens", json=lote())

    viagem = db.execute(select(Viagem)).scalar_one()
    rota = db.execute(select(Viagem.rota)).scalar_one()

    assert len(rota) == 3
    assert viagem.qtd_pontos == 2
    assert viagem.qtd_pontos_recebidos == 3

    invalido = [p for p in rota if not p["fixValido"]]
    assert len(invalido) == 1
    assert invalido[0]["lat"] == 0.0 and invalido[0]["lon"] == 0.0
    assert invalido[0]["sats"] == 0


def test_inicio_e_fim_ignoram_o_ponto_sem_fix(client, carro, db):
    """A posicao invalida e a ULTIMA do lote: se contasse, "fim" seria ela."""
    client.post("/api/viagens", json=lote())
    viagem = db.execute(select(Viagem)).scalar_one()

    assert viagem.inicio.isoformat() == "2026-09-05T08:12:04+00:00"
    # 08:12:14 (ultimo VALIDO), nao 08:12:24 (o sem fix).
    assert viagem.fim.isoformat() == "2026-09-05T08:12:14+00:00"


def test_lote_inteiro_sem_fix_e_rejeitado(client, carro):
    """Sem nenhuma posicao valida nao ha quilometragem apuravel.

    Devolve 422: o dispositivo mantem o dado no SD. E a escolha consciente --
    aceitar criaria uma viagem sem inicio, fim nem distancia na prestacao de
    contas.
    """
    corpo = lote()
    corpo["posicoes"] = [
        posicao("2026-09-05T08:12:04Z", 0.0, 0.0, fix=False),
        posicao("2026-09-05T08:12:14Z", 0.0, 0.0, fix=False),
    ]
    r = client.post("/api/viagens", json=corpo)
    assert r.status_code == 422
    assert r.json()["ok"] is False
    assert "fixValido" in r.json()["erro"]


def test_quilometragem_e_reproduzivel_a_partir_da_rota_gravada(client, carro, db):
    """Auditoria: recalcular pelo JSONB tem de dar o numero exato da coluna.

    E por isso que lat/lon sao arredondados a 6 casas ANTES do calculo e
    gravados ja arredondados. Se o calculo usasse o valor cru e o banco
    guardasse o arredondado, um auditor chegaria a outro numero.
    """
    client.post("/api/viagens", json=lote())

    viagem = db.execute(select(Viagem)).scalar_one()
    rota = db.execute(select(Viagem.rota)).scalar_one()

    class _P:
        def __init__(self, d):
            self.lat, self.lon, self.ts = d["lat"], d["lon"], d["ts"]

    validos = sorted(
        (_P(p) for p in rota if p["fixValido"]), key=lambda p: p.ts
    )
    assert km_da_rota(validos) == viagem.km_gps

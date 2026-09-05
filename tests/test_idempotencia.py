"""Reenvio nao pode duplicar quilometragem.

O dispositivo so apaga o cartao SD ao receber ok:true. Quando o ACK se perde na
volta, ele reenvia o mesmo lote no proximo contato -- entao o reenvio e o caso
comum, nao a excecao. Sem idempotencia a frota inteira contabiliza o dobro.
"""

from sqlalchemy import func, select

from app.models import Viagem
from tests.conftest import cabecalho, lote


def test_primeiro_envio_cria_a_viagem(client, carro):
    r = client.post("/api/viagens", json=lote(), headers=cabecalho())
    assert r.status_code == 201, r.text

    corpo = r.json()
    assert corpo["ok"] is True
    assert corpo["lote_id"] == "a3f1c9"
    assert corpo["pontos_recebidos"] == 3
    assert corpo["pontos_validos"] == 2
    assert "duplicada" not in corpo


def test_reenvio_devolve_200_duplicada_sem_gravar(client, carro, db):
    primeira = client.post("/api/viagens", json=lote(), headers=cabecalho())
    assert primeira.status_code == 201

    segunda = client.post("/api/viagens", json=lote(), headers=cabecalho())
    assert segunda.status_code == 200
    assert segunda.json() == {"ok": True, "lote_id": "a3f1c9", "duplicada": True}

    total = db.execute(
        select(func.count()).select_from(Viagem).where(Viagem.carro_id == carro.id)
    ).scalar_one()
    assert total == 1


def test_reenvio_nao_altera_a_quilometragem_gravada(client, carro, db):
    """km_gps e congelado: o reenvio nao pode recalcular nem sobrescrever."""
    client.post("/api/viagens", json=lote(), headers=cabecalho())
    km_original = db.execute(select(Viagem.km_gps)).scalar_one()

    # Mesmo loteId, mas com uma posicao a mais: o dado novo e ignorado.
    corpo = lote()
    corpo["posicoes"].append(
        {
            "ts": "2026-09-05T08:30:00Z",
            "lat": -24.99,
            "lon": -53.49,
            "hdop": 1.0,
            "sats": 11,
            "velKmh": 40.0,
            "fixValido": True,
        }
    )
    r = client.post("/api/viagens", json=corpo, headers=cabecalho())
    assert r.status_code == 200
    assert r.json()["duplicada"] is True

    assert db.execute(select(Viagem.km_gps)).scalar_one() == km_original
    assert db.execute(select(Viagem.qtd_pontos_recebidos)).scalar_one() == 3


def test_lotes_diferentes_do_mesmo_carro_convivem(client, carro, db):
    assert client.post(
        "/api/viagens", json=lote(lote_id="aaa111"), headers=cabecalho()
    ).status_code == 201
    assert client.post(
        "/api/viagens", json=lote(lote_id="bbb222"), headers=cabecalho()
    ).status_code == 201

    total = db.execute(select(func.count()).select_from(Viagem)).scalar_one()
    assert total == 2


def test_a_constraint_e_por_carro(client, carro, db):
    """O mesmo loteId em carros diferentes nao colide.

    loteId e gerado pelo dispositivo, entao dois ESP32 podem sortear o mesmo
    hex. A unicidade e do par (carro, lote), nao do lote sozinho.
    """
    from app.models import Carro

    outro = Carro(
        modelo="Uno",
        marca="Fiat",
        numero_frota="0158",
        placa="XYZ-9K88",
        dispositivo_id="esp32-0158",
        secretaria_id=carro.secretaria_id,
    )
    db.add(outro)
    db.flush()

    assert client.post(
        "/api/viagens", json=lote(lote_id="mesmo"), headers=cabecalho()
    ).status_code == 201
    assert client.post(
        "/api/viagens",
        json=lote(dispositivo="esp32-0158", lote_id="mesmo"),
        headers=cabecalho(),
    ).status_code == 201

    assert db.execute(select(func.count()).select_from(Viagem)).scalar_one() == 2

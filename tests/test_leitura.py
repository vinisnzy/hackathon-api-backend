"""Endpoints de leitura: listagem, detalhe e rota bruta."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm.exc import DetachedInstanceError

from app.models import Viagem
from tests.conftest import cabecalho, lote


def _cria(client, lote_id="a3f1c9", dispositivo="esp32-0157") -> str:
    r = client.post(
        "/api/viagens", json=lote(dispositivo=dispositivo, lote_id=lote_id),
        headers=cabecalho(),
    )
    assert r.status_code == 201, r.text
    return r.json()["viagem_id"]


def test_listagem_pagina_e_conta(client, carro):
    for i in range(5):
        _cria(client, lote_id=f"lote{i}")

    r = client.get("/api/viagens?page=1&size=2")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 5
    assert corpo["pages"] == 3
    assert len(corpo["items"]) == 2


def test_listagem_nao_devolve_a_rota(client, carro):
    """A coluna JSONB nao pode entrar na listagem: viraria megabytes."""
    _cria(client)
    item = client.get("/api/viagens").json()["items"][0]
    assert "rota" not in item


def test_paginacao_nao_repete_nem_perde_linha(client, carro):
    """Todas as viagens tem o mesmo "inicio" -- sem desempate por id, a ordem
    entre paginas seria arbitraria e uma linha apareceria duas vezes."""
    for i in range(6):
        _cria(client, lote_id=f"lote{i}")

    vistos = []
    for pagina in (1, 2, 3):
        vistos += [i["id"] for i in client.get(f"/api/viagens?page={pagina}&size=2").json()["items"]]

    assert len(vistos) == 6
    assert len(set(vistos)) == 6


def test_filtro_por_secretaria(client, carro, db):
    from app.models import Carro, Secretaria

    outra = Secretaria(nome="SEMED")
    db.add(outra)
    db.flush()
    outro_carro = Carro(
        modelo="Strada", marca="Fiat", numero_frota="0201", placa="QQQ-1A11",
        dispositivo_id="esp32-0201", secretaria_id=outra.id,
    )
    db.add(outro_carro)
    db.flush()

    _cria(client, lote_id="l1")
    _cria(client, lote_id="l2", dispositivo="esp32-0201")

    r = client.get(f"/api/viagens?secretaria_id={carro.secretaria_id}").json()
    assert r["total"] == 1
    assert r["items"][0]["lote_id"] == "l1"


def test_filtro_por_intervalo(client, carro):
    _cria(client)
    dentro = client.get(
        "/api/viagens?inicio=2026-09-05T00:00:00Z&fim=2026-09-06T00:00:00Z"
    ).json()
    fora = client.get(
        "/api/viagens?inicio=2026-01-01T00:00:00Z&fim=2026-01-02T00:00:00Z"
    ).json()
    assert dentro["total"] == 1
    assert fora["total"] == 0


def test_detalhe_traz_carro_servidor_e_secretaria(client, carro):
    viagem_id = _cria(client)
    corpo = client.get(f"/api/viagens/{viagem_id}").json()

    assert corpo["carro"]["placa"] == "BAZ-1D23"
    assert corpo["carro"]["dispositivo_id"] == "esp32-0157"
    assert corpo["carro"]["secretaria"]["nome"].startswith("SESAU")
    # Sem cracha RFID no contrato atual, o condutor fica nulo.
    assert corpo["servidor"] is None
    assert "rota" not in corpo


def test_detalhe_inexistente_devolve_404(client, carro):
    r = client.get("/api/viagens/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_rota_devolve_o_array_bruto(client, carro):
    viagem_id = _cria(client)
    rota = client.get(f"/api/viagens/{viagem_id}/rota").json()

    assert isinstance(rota, list) and len(rota) == 3
    assert set(rota[0]) == {"ts", "lat", "lon", "hdop", "sats", "velKmh", "fixValido"}
    # Inclusive o descartado: e o registro de auditoria.
    assert any(p["fixValido"] is False for p in rota)


def test_rota_de_viagem_inexistente_devolve_404(client, carro):
    r = client.get("/api/viagens/00000000-0000-0000-0000-000000000000/rota")
    assert r.status_code == 404


def test_rota_e_deferida_no_orm(client, carro, db):
    """deferred_raiseload: acesso acidental a rota levanta, nao emite SELECT.

    Sem isso, adicionar "rota" a um schema de listagem faria N+1 consultas ao
    JSONB sem ninguem perceber -- so ficaria lento.
    """
    _cria(client)
    viagem = db.execute(select(Viagem)).scalar_one()
    with pytest.raises(Exception) as exc:
        _ = viagem.rota
    assert "raiseload" in str(exc.value).lower() or isinstance(
        exc.value, DetachedInstanceError
    )

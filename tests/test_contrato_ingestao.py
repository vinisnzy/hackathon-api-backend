"""Contrato de resposta da ingestao.

O firmware toma uma decisao destrutiva com base nestes status: so apaga o
cartao SD com ok:true. Qualquer outra coisa significa "guarde e reenvie".
"""

from sqlalchemy import func, select

from app.models import Viagem
from tests.conftest import cabecalho, lote, posicao


def test_token_invalido_devolve_401(client, carro):
    r = client.post("/api/viagens", json=lote(), headers=cabecalho("errado"))
    assert r.status_code == 401
    assert r.json()["ok"] is False


def test_token_ausente_devolve_401_e_nao_422(client, carro):
    """Header faltando e falha de autenticacao, nao de payload.

    O padrao do FastAPI para header obrigatorio ausente seria 422, o que
    mandaria o dispositivo tentar consertar o payload para sempre.
    """
    r = client.post("/api/viagens", json=lote())
    assert r.status_code == 401


def test_401_vence_payload_quebrado(client, carro, db):
    """Token errado responde 401 mesmo com o corpo invalido.

    A verificacao roda em middleware, antes do roteamento -- entao o servidor
    tambem nao bufferiza o dump de SD de quem nao esta autenticado.
    """
    r = client.post("/api/viagens", json={"lixo": True}, headers=cabecalho("errado"))
    assert r.status_code == 401
    assert db.execute(select(func.count()).select_from(Viagem)).scalar_one() == 0


def test_dispositivo_desconhecido_devolve_404_e_nao_cria_carro(client, carro, db):
    from app.models import Carro

    antes = db.execute(select(func.count()).select_from(Carro)).scalar_one()
    r = client.post(
        "/api/viagens", json=lote(dispositivo="esp32-fantasma"), headers=cabecalho()
    )
    assert r.status_code == 404
    assert r.json()["ok"] is False
    assert db.execute(select(func.count()).select_from(Carro)).scalar_one() == antes


def test_erro_sempre_traz_o_campo_ok(client, carro):
    """Um unico caminho de parse no firmware.

    Sem os handlers, o FastAPI devolveria {"detail": ...} nos erros e o
    dispositivo teria de tratar dois formatos.
    """
    respostas = [
        client.post("/api/viagens", json=lote(), headers=cabecalho("errado")),
        client.post("/api/viagens", json=lote(dispositivo="nao-existe"), headers=cabecalho()),
        client.post("/api/viagens", json={}, headers=cabecalho()),
        client.get("/api/viagens/00000000-0000-0000-0000-000000000000"),
    ]
    for r in respostas:
        assert r.json()["ok"] is False, r.text


def test_lista_de_posicoes_vazia_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"] = []
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 422


def test_latitude_fora_de_faixa_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"][0]["lat"] = -91.0
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 422


def test_longitude_fora_de_faixa_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"][0]["lon"] = 181.0
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 422


def test_timestamp_de_1970_e_422(client, carro):
    """ESP32 sem fix de relogio emite epoch zero.

    Aceitar contamina inicio/fim e o registro passa a dizer que a prefeitura
    rodou em 1970.
    """
    corpo = lote()
    corpo["posicoes"][0]["ts"] = "1970-01-01T00:00:00Z"
    r = client.post("/api/viagens", json=corpo, headers=cabecalho())
    assert r.status_code == 422


def test_campo_desconhecido_na_posicao_e_422(client, carro):
    """extra="forbid": um campo novo do firmware nao pode sumir calado."""
    corpo = lote()
    corpo["posicoes"][0]["altitude"] = 720.0
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 422


def test_posicoes_fora_de_ordem_sao_ordenadas(client, carro, db):
    """Um SD remontado apos falha de energia pode entregar blocos trocados.

    A rota crua guarda a ordem de chegada; inicio, fim e km_gps usam a ordem
    cronologica.
    """
    corpo = lote()
    corpo["posicoes"] = [
        posicao("2026-09-05T08:12:14Z", -24.95604, -53.45712),
        posicao("2026-09-05T08:12:04Z", -24.95550, -53.45520),
    ]
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 201

    viagem = db.execute(select(Viagem)).scalar_one()
    assert viagem.inicio.isoformat() == "2026-09-05T08:12:04+00:00"
    assert viagem.fim.isoformat() == "2026-09-05T08:12:14+00:00"

    rota = db.execute(select(Viagem.rota)).scalar_one()
    assert rota[0]["ts"] == "2026-09-05T08:12:14Z"  # ordem de chegada preservada


def test_placa_divergente_nao_bloqueia_mas_fica_registrada(client, carro, db):
    """Erro de cadastro em campo nao pode travar a ingestao para sempre.

    O dispositivo e a fonte da identidade; a placa informada vira auditoria.
    """
    corpo = lote()
    corpo["placa"] = "OUT-R000"
    assert client.post("/api/viagens", json=corpo, headers=cabecalho()).status_code == 201

    viagem = db.execute(select(Viagem)).scalar_one()
    assert viagem.placa_informada == "OUT-R000"
    assert viagem.carro_id == carro.id


def test_km_gps_sai_como_numero_e_nao_string(client, carro):
    """O contrato mostra "km_gps": 27.4, um numero JSON.

    Decimal e o tipo interno (e o que garante o arredondamento contabil), mas
    Pydantic o serializaria como string sem o serializer.
    """
    import json

    r = client.post("/api/viagens", json=lote(), headers=cabecalho())
    bruto = json.loads(r.text)
    assert isinstance(bruto["km_gps"], float), r.text
    assert bruto["km_gps"] == 0.20

    item = json.loads(client.get("/api/viagens").text)["items"][0]
    assert isinstance(item["km_gps"], float)

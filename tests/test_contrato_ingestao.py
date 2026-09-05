"""Contrato de resposta da ingestao.

O firmware toma uma decisao destrutiva com base nestes status: so apaga o
cartao SD com ok:true. Qualquer outra coisa significa "guarde e reenvie".
"""

from sqlalchemy import func, select

from app.models import Viagem
from tests.conftest import lote, posicao


def test_dispositivo_novo_e_cadastrado_na_hora(client, carro, db):
    """Sem cadastro previo: o lote nunca e recusado por falta de carro.

    O dispositivo e a fonte da identidade. Um lote que chegasse de um ESP32
    ainda nao cadastrado seria reenviado para sempre, e a viagem se perderia.
    """
    from app.models import Carro

    antes = db.execute(select(func.count()).select_from(Carro)).scalar_one()
    r = client.post(
        "/api/viagens", json=lote(dispositivo="esp32-9999", lote_id="novo")
    )
    assert r.status_code == 201, r.text
    assert db.execute(select(func.count()).select_from(Carro)).scalar_one() == antes + 1

    novo = db.execute(
        select(Carro).where(Carro.dispositivo_id == "esp32-9999")
    ).scalar_one()
    assert novo.numero_frota == "9999"  # extraido do slug
    assert novo.secretaria_id is not None


def test_carro_criado_nao_duplica_no_segundo_lote(client, carro, db):
    from app.models import Carro

    client.post("/api/viagens", json=lote(dispositivo="esp32-7777", lote_id="l1"))
    client.post("/api/viagens", json=lote(dispositivo="esp32-7777", lote_id="l2"))

    carros = db.execute(
        select(func.count()).select_from(Carro).where(
            Carro.dispositivo_id == "esp32-7777"
        )
    ).scalar_one()
    assert carros == 1


def test_placa_ja_usada_nao_quebra_o_auto_cadastro(client, carro, db):
    """O carro do fixture ja tem BAZ-1D23; um dispositivo novo informando a
    mesma placa nao pode estourar o indice unico."""
    from app.models import Carro

    r = client.post(
        "/api/viagens", json=lote(dispositivo="esp32-0002", lote_id="x1")
    )
    assert r.status_code == 201, r.text

    novo = db.execute(
        select(Carro).where(Carro.dispositivo_id == "esp32-0002")
    ).scalar_one()
    assert novo.placa == "esp32-0002"  # caiu para o id do dispositivo


def test_erro_sempre_traz_o_campo_ok(client, carro):
    """Um unico caminho de parse no firmware.

    Sem os handlers, o FastAPI devolveria {"detail": ...} nos erros e o
    dispositivo teria de tratar dois formatos.
    """
    respostas = [
        client.post("/api/viagens", json={}),
        client.get("/api/viagens/00000000-0000-0000-0000-000000000000"),
    ]
    for r in respostas:
        assert r.json()["ok"] is False, r.text


def test_payload_quebrado_nao_grava_nada(client, carro, db):
    r = client.post("/api/viagens", json={"lixo": True})
    assert r.status_code == 422
    assert db.execute(select(func.count()).select_from(Viagem)).scalar_one() == 0


def test_lista_de_posicoes_vazia_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"] = []
    assert client.post("/api/viagens", json=corpo).status_code == 422


def test_latitude_fora_de_faixa_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"][0]["lat"] = -91.0
    assert client.post("/api/viagens", json=corpo).status_code == 422


def test_longitude_fora_de_faixa_e_422(client, carro):
    corpo = lote()
    corpo["posicoes"][0]["lon"] = 181.0
    assert client.post("/api/viagens", json=corpo).status_code == 422


def test_timestamp_de_1970_e_422(client, carro):
    """ESP32 sem fix de relogio emite epoch zero.

    Aceitar contamina inicio/fim e o registro passa a dizer que a prefeitura
    rodou em 1970.
    """
    corpo = lote()
    corpo["posicoes"][0]["ts"] = "1970-01-01T00:00:00Z"
    r = client.post("/api/viagens", json=corpo)
    assert r.status_code == 422


def test_campo_desconhecido_na_posicao_e_422(client, carro):
    """extra="forbid": um campo novo do firmware nao pode sumir calado."""
    corpo = lote()
    corpo["posicoes"][0]["altitude"] = 720.0
    assert client.post("/api/viagens", json=corpo).status_code == 422


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
    assert client.post("/api/viagens", json=corpo).status_code == 201

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
    assert client.post("/api/viagens", json=corpo).status_code == 201

    viagem = db.execute(select(Viagem)).scalar_one()
    assert viagem.placa_informada == "OUT-R000"
    assert viagem.carro_id == carro.id


def test_km_gps_sai_como_numero_e_nao_string(client, carro):
    """O contrato mostra "km_gps": 27.4, um numero JSON.

    Decimal e o tipo interno (e o que garante o arredondamento contabil), mas
    Pydantic o serializaria como string sem o serializer.
    """
    import json

    r = client.post("/api/viagens", json=lote())
    bruto = json.loads(r.text)
    assert isinstance(bruto["km_gps"], float), r.text
    assert bruto["km_gps"] == 0.20

    item = json.loads(client.get("/api/viagens").text)["items"][0]
    assert isinstance(item["km_gps"], float)

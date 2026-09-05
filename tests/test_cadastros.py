"""CRUD de secretaria, servidor e carro."""

import uuid


def test_ciclo_completo_de_secretaria(client):
    criada = client.post("/api/secretarias", json={"nome": "SEMOB"})
    assert criada.status_code == 201
    id_ = criada.json()["id"]

    assert client.get(f"/api/secretarias/{id_}").json()["nome"] == "SEMOB"

    atualizada = client.put(f"/api/secretarias/{id_}", json={"nome": "SEMOB-2"})
    assert atualizada.json()["nome"] == "SEMOB-2"

    assert client.delete(f"/api/secretarias/{id_}").status_code == 204
    assert client.get(f"/api/secretarias/{id_}").status_code == 404


def test_nome_de_secretaria_duplicado_e_409(client):
    client.post("/api/secretarias", json={"nome": "SESAU-unica"})
    r = client.post("/api/secretarias", json={"nome": "SESAU-unica"})
    assert r.status_code == 409
    assert r.json()["ok"] is False


def test_apagar_secretaria_com_carro_e_409(client, carro):
    """FK RESTRICT: apagar a secretaria levaria junto o historico do carro."""
    r = client.delete(f"/api/secretarias/{carro.secretaria_id}")
    assert r.status_code == 409


def test_apagar_carro_com_viagem_e_409(client, carro):
    from tests.conftest import cabecalho, lote

    client.post("/api/viagens", json=lote(), headers=cabecalho())
    r = client.delete(f"/api/carros/{carro.id}")
    assert r.status_code == 409


def test_cpf_e_normalizado_para_digitos(client, carro):
    r = client.post(
        "/api/servidores",
        json={
            "nome": "Fulano de Tal",
            "cpf": "111.222.333-44",
            "matricula": "18432",
            "cargo": "Motorista",
            "secretaria_id": str(carro.secretaria_id),
        },
    )
    assert r.status_code == 201
    assert r.json()["cpf"] == "11122233344"


def test_cpf_formatado_e_cru_colidem(client, carro):
    """Sem a normalizacao, os dois entrariam como servidores diferentes."""
    base = {
        "nome": "Fulano",
        "matricula": "1",
        "cargo": "Motorista",
        "secretaria_id": str(carro.secretaria_id),
    }
    assert client.post("/api/servidores", json={**base, "cpf": "11122233344"}).status_code == 201
    r = client.post(
        "/api/servidores", json={**base, "matricula": "2", "cpf": "111.222.333-44"}
    )
    assert r.status_code == 409


def test_listagem_de_servidores_nao_expoe_cpf(client, carro):
    """LGPD: um GET aberto nao publica CPF de servidor municipal."""
    client.post(
        "/api/servidores",
        json={
            "nome": "Fulano",
            "cpf": "11122233344",
            "matricula": "18432",
            "cargo": "Motorista",
            "secretaria_id": str(carro.secretaria_id),
        },
    )
    item = client.get("/api/servidores").json()["items"][0]
    assert "cpf" not in item
    assert item["nome"] == "Fulano"


def test_placa_e_normalizada_para_maiusculas(client, carro):
    r = client.post(
        "/api/carros",
        json={
            "modelo": "Saveiro",
            "marca": "VW",
            "numero_frota": "0300",
            "placa": " abc-1d23 ",
            "dispositivo_id": "esp32-0300",
            "secretaria_id": str(carro.secretaria_id),
        },
    )
    assert r.status_code == 201
    assert r.json()["placa"] == "ABC-1D23"


def test_dispositivo_duplicado_e_409(client, carro):
    """Dois carros com o mesmo ESP32 tornariam a origem da viagem ambigua."""
    r = client.post(
        "/api/carros",
        json={
            "modelo": "Gol", "marca": "VW", "numero_frota": "0999",
            "placa": "ZZZ-9Z99", "dispositivo_id": "esp32-0157",
            "secretaria_id": str(carro.secretaria_id),
        },
    )
    assert r.status_code == 409


def test_secretaria_inexistente_no_carro_e_409(client):
    r = client.post(
        "/api/carros",
        json={
            "modelo": "Gol", "marca": "VW", "numero_frota": "0001",
            "placa": "AAA-1A11", "dispositivo_id": "esp32-x",
            "secretaria_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 409

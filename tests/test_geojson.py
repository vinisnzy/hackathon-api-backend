"""Contrato GeoJSON servido ao frontend.

A estrutura externa e rigida (RFC 7946). O erro classico e inverter a ordem
das coordenadas: GeoJSON e [longitude, latitude], nao [lat, lon]. Trocar
coloca Cascavel na Antartida, e o mapa "quase funciona" -- o pior tipo de bug.
"""

from tests.conftest import cabecalho, lote, posicao


def _cria(client) -> str:
    r = client.post("/api/viagens", json=lote(), headers=cabecalho())
    assert r.status_code == 201, r.text
    return r.json()["viagem_id"]


def test_estrutura_externa_e_a_do_contrato(client, carro):
    viagem_id = _cria(client)
    fc = client.get(f"/api/viagens/{viagem_id}/geojson").json()

    assert fc["type"] == "FeatureCollection"
    assert isinstance(fc["features"], list) and len(fc["features"]) == 1

    feature = fc["features"][0]
    assert set(feature) == {"type", "properties", "geometry"}
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "LineString"
    assert set(feature["geometry"]) == {"type", "coordinates"}


def test_coordenadas_sao_lon_lat_nessa_ordem(client, carro):
    viagem_id = _cria(client)
    coords = client.get(f"/api/viagens/{viagem_id}/geojson").json()["features"][0][
        "geometry"
    ]["coordinates"]

    assert coords == [[-53.4552, -24.9555], [-53.45712, -24.95604]]
    for lon, lat in coords:
        # Cascavel/PR: longitude ~ -53, latitude ~ -24.
        assert -54 < lon < -53, "longitude fora do Parana: ordem invertida?"
        assert -25 < lat < -24, "latitude fora do Parana: ordem invertida?"


def test_geometria_exclui_o_ponto_sem_fix(client, carro):
    viagem_id = _cria(client)
    coords = client.get(f"/api/viagens/{viagem_id}/geojson").json()["features"][0][
        "geometry"
    ]["coordinates"]

    assert len(coords) == 2  # o lote tem 3 posicoes; uma sem fix
    assert [0.0, 0.0] not in coords


def test_properties_traz_os_campos_do_frontend(client, carro):
    viagem_id = _cria(client)
    props = client.get(f"/api/viagens/{viagem_id}/geojson").json()["features"][0][
        "properties"
    ]

    assert set(props) == {
        "viagemId",
        "loteId",
        "placa",
        "numeroFrota",
        "secretaria",
        "saidaEm",
        "chegadaEm",
        "distanciaGpsMetros",
        "qtdPontos",
    }
    assert props["viagemId"] == viagem_id
    assert props["loteId"] == "a3f1c9"
    assert props["placa"] == "BAZ-1D23"
    assert props["numeroFrota"] == "0157"
    assert props["qtdPontos"] == 2
    assert props["distanciaGpsMetros"] == 200  # 0,20 km


def test_horarios_saem_no_fuso_de_sao_paulo(client, carro):
    """Armazenado em UTC, exibido em America/Sao_Paulo.

    08:12:04Z e 05:12:04 em Cascavel.
    """
    viagem_id = _cria(client)
    props = client.get(f"/api/viagens/{viagem_id}/geojson").json()["features"][0][
        "properties"
    ]

    assert props["saidaEm"] == "2026-09-05T05:12:04-03:00"
    assert props["chegadaEm"] == "2026-09-05T05:12:14-03:00"


def test_linestring_com_um_ponto_valido_repete_a_coordenada(client, carro):
    """RFC 7946 exige duas posicoes numa LineString.

    Um carro que ligou e desligou gera um ponto so; repetir mantem o GeoJSON
    valido e o mapa desenha um ponto em vez de quebrar.
    """
    corpo = lote()
    corpo["posicoes"] = [posicao("2026-09-05T08:12:04Z", -24.9555, -53.4552)]
    viagem_id = client.post("/api/viagens", json=corpo, headers=cabecalho()).json()[
        "viagem_id"
    ]

    coords = client.get(f"/api/viagens/{viagem_id}/geojson").json()["features"][0][
        "geometry"
    ]["coordinates"]
    assert coords == [[-53.4552, -24.9555], [-53.4552, -24.9555]]


def test_colecao_com_varias_viagens(client, carro):
    client.post("/api/viagens", json=lote(lote_id="l1"), headers=cabecalho())
    client.post("/api/viagens", json=lote(lote_id="l2"), headers=cabecalho())

    fc = client.get("/api/viagens/geojson").json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    assert {f["properties"]["loteId"] for f in fc["features"]} == {"l1", "l2"}


def test_colecao_vazia_continua_sendo_featurecollection(client, carro):
    fc = client.get("/api/viagens/geojson").json()
    assert fc == {"type": "FeatureCollection", "features": []}


def test_geojson_filtra_por_carro(client, carro, db):
    from app.models import Carro

    outro = Carro(
        modelo="Uno", marca="Fiat", numero_frota="0158", placa="XYZ-9K88",
        dispositivo_id="esp32-0158", secretaria_id=carro.secretaria_id,
    )
    db.add(outro)
    db.flush()

    client.post("/api/viagens", json=lote(lote_id="l1"), headers=cabecalho())
    client.post(
        "/api/viagens",
        json=lote(dispositivo="esp32-0158", lote_id="l2"),
        headers=cabecalho(),
    )

    fc = client.get(f"/api/viagens/geojson?carro_id={carro.id}").json()
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"]["loteId"] == "l1"

# API de Telemetria de Frota

Backend que recebe rotas de GPS gravadas **offline** por dispositivos ESP32
instalados nos veículos da prefeitura e as entrega prontas para o mapa.

Não há comunicação em tempo real: o dispositivo grava a viagem inteira no cartão
SD e descarrega o lote quando o carro volta ao pátio.

---

## O problema que este backend resolve

**O dispositivo só apaga o cartão SD quando recebe `ok: true`.** Se o ACK se
perde na volta, ele reenvia o mesmo lote no próximo contato. Isso faz do reenvio
o caso comum, não a exceção — e sem idempotência a frota inteira contabiliza
quilometragem em dobro.

Três decisões seguem daí:

| Decisão | Por quê |
|---|---|
| `UNIQUE (carro_id, lote_id)` + `ON CONFLICT DO NOTHING` | A idempotência mora no banco, não só na aplicação. Dois reenvios simultâneos não criam duas viagens. |
| `km_gps` congelado na gravação | O número vai para prestação de contas pública. Recalcular na exibição faria a quilometragem de uma viagem antiga mudar sozinha. |
| Rota bruta preservada em JSONB | Se alguém questionar a quilometragem, existe o registro exato do que o dispositivo enviou — e dá para recalcular e chegar no mesmo número. |

### As duas mentiras do GPS

O cálculo aplica **exatamente dois** filtros, ambos especificados:

1. **Posições sem fix são descartadas.** Sem fix o módulo emite `lat: 0, lon: 0`
   — a "Ilha Nula", no golfo da Guiné, a uns 9.500 km de Cascavel. Um único
   desses pontos numa rota dobraria a quilometragem do mês.
2. **Trechos com deslocamento menor que 5 m são ignorados.** Carro parado gera
   jitter de sinal; sem o corte, um veículo desligado no pátio "roda"
   quilômetros.

Nenhum outro filtro é aplicado — nem por `hdop`, nem por `sats`, nem por
velocidade máxima. Filtro não especificado altera um número auditado: se alguém
adicionar um corte "para melhorar", a quilometragem histórica deixa de ser
reproduzível. A coluna `versao_calculo` existe para que a regra possa mudar no
futuro sem tornar o histórico inexplicável.

---

## Subir

### Docker

```bash
cp .env.example .env
docker compose up --build
```

A API sobe em `http://localhost:8000`. As migrations rodam no entrypoint do
contêiner, nunca no import da aplicação — rodar no import faria cada worker do
uvicorn tentar migrar em paralelo.

### Local

```bash
make install                       # cria .venv e instala
createdb frota && createdb frota_test
cp .env.example .env               # ajuste DATABASE_URL
make migrate
make run                           # http://localhost:8000/docs
```

### Testes

```bash
make test
```

A suíte roda contra um **Postgres de verdade**, não SQLite: a idempotência
depende de `ON CONFLICT` sobre uma constraint nomeada, e a rota é `JSONB`. O
schema de teste é montado com `alembic upgrade head` — é o único jeito de pegar
deriva em nome de constraint, `server_default` e índice.

---

## Contrato: dispositivo → API

```http
POST /api/viagens
```

> **A API nao tem autenticacao.** E um MVP de hackathon: qualquer um que
> alcance a rede pode gravar viagens e ler os cadastros. Antes de ir para
> producao isso precisa mudar -- a ingestao e o unico endpoint que escreve
> quilometragem usada em prestacao de contas.

```json
{
  "dispositivoId": "esp32-0157",
  "placa": "BAZ-1D23",
  "loteId": "a3f1c9",
  "enviadoEm": "2026-09-05T09:41:00-03:00",
  "posicoes": [
    { "ts": "2026-09-05T08:12:04Z", "lat": -24.95550, "lon": -53.45520,
      "hdop": 1.2, "sats": 9, "velKmh": 0.0, "fixValido": true },
    { "ts": "2026-09-05T08:12:24Z", "lat": 0.0, "lon": 0.0,
      "hdop": 99, "sats": 0, "velKmh": 0.0, "fixValido": false }
  ]
}
```

### Respostas

| Status | Corpo | O que o dispositivo faz |
|---|---|---|
| **201** | `{"ok": true, "viagem_id": "...", "lote_id": "bc9e12", "pontos_recebidos": 41, "pontos_validos": 40, "km_gps": 0.87}` | Apaga o SD |
| **200** | `{"ok": true, "lote_id": "bc9e12", "duplicada": true}` | Apaga o SD (já estava gravado) |
| **422** | `{"ok": false, "erro": "...", "detalhes": [...]}` | Mantém e reenvia |

Todo erro carrega o campo `ok`. O padrão do FastAPI seria `{"detail": ...}`, sem
`ok` — o firmware teria dois caminhos de parse.

O `dispositivoId` **não precisa estar cadastrado**. Se for a primeira vez que
aquele ESP32 aparece, a API cria o carro na hora, com a placa que veio no lote e
o número de frota extraído do slug (`esp32-0157` → `0157`). Modelo, marca e
secretaria nascem como "Não informado" e podem ser completados depois pelo CRUD.
Exigir cadastro prévio faria o dispositivo reenviar o mesmo lote para sempre e a
viagem se perderia.

### Validações que devolvem 422

- `lat` fora de −90..90, `lon` fora de −180..180
- `posicoes` vazio ou acima de 50.000 posições
- `ts` anterior a 2020 (ESP32 sem fix de relógio emite 1970) ou mais de um dia
  no futuro
- campo desconhecido numa posição (`extra="forbid"`: um campo novo do firmware
  não pode sumir calado)
- lote sem nenhuma posição com `fixValido: true` — sem isso não há
  quilometragem apurável

---

## Contrato: API → frontend (GeoJSON)

```http
GET /api/viagens/{id}/geojson
GET /api/viagens/geojson?carro_id=&secretaria_id=&inicio=&fim=&limit=
```

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "viagemId": "b1f129f4-...", "loteId": "a3f1c9",
      "placa": "BAZ-1D23", "numeroFrota": "0157", "secretaria": "SESAU",
      "saidaEm": "2026-09-05T05:12:04-03:00",
      "chegadaEm": "2026-09-05T05:12:14-03:00",
      "distanciaGpsMetros": 200, "qtdPontos": 2
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [[-53.4552, -24.9555], [-53.45712, -24.95604]]
    }
  }]
}
```

**Coordenada em GeoJSON é `[longitude, latitude]`** (RFC 7946) — invertida em
relação ao hábito de dizer "lat, lon". Trocar a ordem coloca Cascavel na
Antártida e o mapa "quase funciona", que é o pior tipo de bug.

Timestamps são armazenados em UTC e convertidos para `America/Sao_Paulo` apenas
na exibição.

A geometria é reconstruída a partir do JSONB gravado aplicando o mesmo filtro de
fix da ingestão: o mapa desenha exatamente o conjunto de pontos que produziu o
`km_gps` da coluna, e não uma segunda versão da verdade.

---

## Demais endpoints

| Método | Rota | Nota |
|---|---|---|
| `GET` | `/health` | Liveness puro, não toca o banco |
| `GET` | `/health/db` | Readiness, faz `SELECT 1` |
| `GET` | `/api/viagens` | Paginado, filtros `carro_id`, `secretaria_id`, `inicio`, `fim`. **Sem** a rota |
| `GET` | `/api/viagens/{id}` | Carro, servidor e secretaria aninhados. **Sem** a rota |
| `GET` | `/api/viagens/{id}/rota` | Array bruto, para auditoria |
| `GET` `POST` `PUT` `DELETE` | `/api/secretarias`, `/api/servidores`, `/api/carros` | CRUD completo |

`viagem` **não** tem `PUT`, `PATCH` nem `DELETE`: é um livro-razão append-only, e
é isso que faz "`km_gps` congelado" ser uma garantia e não uma intenção.

A coluna `rota` é `deferred_raiseload`: acesso acidental levanta erro em vez de
emitir um `SELECT` por linha, então o JSONB nunca vaza para a listagem.

`GET /api/servidores` não retorna CPF. Como a API é aberta, um endpoint que
publicasse CPF de servidor municipal exporia dado pessoal a quem alcançasse a
rede. O detalhe individual (`GET /api/servidores/{id}`) ainda retorna.

---

## Estrutura

```
app/
  core/        config, database, errors
  models/      SQLAlchemy 2.0 declarativo
  schemas/     Pydantic v2: lote (entrada), geojson (saída), viagem, cadastro
  repositories/  acesso a dados, sem regra de negócio
  services/    geo (Haversine), viagem_service (ingestão), geojson_service
  routers/     health, viagens, cadastros
alembic/       migrations
tests/         pytest contra Postgres real
```

Fluxo de dependência: `routers → services → repositories → models`. Router não
contém regra; repository não conhece HTTP.

---

## Stack

Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · pydantic-settings ·
Alembic · psycopg 3 (síncrono) · PostgreSQL 16 · pytest.

## Configuração

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` |

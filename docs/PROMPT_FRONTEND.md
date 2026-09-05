# Prompt — Painel do Gestor de Frota (frontend)

> Cole o conteúdo abaixo (a partir de "## Contexto") numa nova sessão do Claude Code,
> num repositório vazio para o frontend.

---

## Contexto

Construa o **painel web do gestor** de uma frota municipal. O backend já existe,
está rodando e é a **única fonte de dados reais de viagens**. Todo o resto é
mockado.

A frota são carros da prefeitura com um ESP32 + GPS que grava a rota **offline**
no cartão SD durante a viagem e descarrega o lote inteiro quando o carro volta ao
pátio. Não há rastreamento em tempo real — o painel mostra o que já aconteceu.

## Stack obrigatória

- **React + TypeScript + Vite**
- **React Router** para navegação
- **Leaflet** + **react-leaflet** para os mapas (tiles do OpenStreetMap)
- **Recharts** para gráficos
- CSS puro ou CSS Modules — **sem** Tailwind, sem biblioteca de componentes
- Sem gerenciador de estado global: `useState` / `useEffect` / hooks próprios bastam
- Sem login, sem cadastro, sem autenticação — o painel abre direto no dashboard

## Conectando na API

O backend roda em `http://localhost:8000` e **não envia cabeçalhos CORS**.
Chamar direto do navegador é bloqueado. Configure o proxy do Vite:

```ts
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
```

No código, chame sempre caminhos relativos: `fetch('/api/viagens')`.

A API **não exige token nem header nenhum**. Todas as chamadas são `GET` simples,
sem body.

---

## Contrato da API — respostas reais, capturadas do backend rodando

### `GET /api/viagens?page=&size=&carro_id=&secretaria_id=&inicio=&fim=`

Listagem paginada. `size` máximo 100. `inicio`/`fim` são ISO-8601 e filtram pelo
início da viagem.

```json
{
  "items": [{
    "id": "873f8a5f-fff0-4e56-8b1d-da187fd551cd",
    "carro_id": "92ae80a2-31f1-44a6-9b2b-72107dec55a5",
    "servidor_id": null,
    "lote_id": "bc9e12",
    "inicio": "2026-09-05T22:02:01Z",
    "fim": "2026-09-05T22:03:01Z",
    "km_gps": 0.87,
    "qtd_pontos": 40,
    "qtd_pontos_recebidos": 41,
    "recebida_em": "2026-09-05T22:40:13.277498Z"
  }],
  "page": 1, "size": 20, "total": 1, "pages": 1
}
```

### `GET /api/viagens/{id}`

Detalhe, com carro e secretaria aninhados.

```json
{
  "id": "873f8a5f-...", "carro_id": "92ae80a2-...", "servidor_id": null,
  "lote_id": "bc9e12",
  "inicio": "2026-09-05T22:02:01Z", "fim": "2026-09-05T22:03:01Z",
  "km_gps": 0.87, "qtd_pontos": 40, "qtd_pontos_recebidos": 41,
  "recebida_em": "2026-09-05T22:40:13.277498Z",
  "placa_informada": "BAZ-1D23",
  "odometro_inicio": null, "odometro_fim": null,
  "versao_calculo": 1, "enviado_em": "2026-09-05T22:03:01Z",
  "carro": {
    "id": "92ae80a2-...", "modelo": "Nao informado", "marca": "Nao informada",
    "numero_frota": "0157", "placa": "BAZ-1D23", "dispositivo_id": "esp32-0157",
    "secretaria": { "id": "8a8b7df4-...", "nome": "Nao informada" }
  },
  "servidor": null
}
```

### `GET /api/viagens/{id}/geojson` e `GET /api/viagens/geojson`

O primeiro devolve 1 feature; o segundo devolve N e aceita os mesmos filtros da
listagem, mais `limit` (padrão 50, máx 200). **Este é o formato que vai no mapa.**

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "viagemId": "873f8a5f-...", "loteId": "bc9e12",
      "placa": "BAZ-1D23", "numeroFrota": "0157", "secretaria": "Nao informada",
      "saidaEm": "2026-09-05T19:02:01-03:00",
      "chegadaEm": "2026-09-05T19:03:01-03:00",
      "distanciaGpsMetros": 870, "qtdPontos": 40
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [[-53.4552, -24.9553], [-53.455037, -24.955162]]
    }
  }]
}
```

⚠️ **Coordenada GeoJSON é `[longitude, latitude]`** (RFC 7946), invertida em
relação ao que o Leaflet espera (`[lat, lng]`). O `<GeoJSON>` do react-leaflet já
converte sozinho. Se você for ler `coordinates` na mão, **inverta**, senão a rota
aparece na Antártida.

Horários em `properties` já vêm convertidos para America/Sao_Paulo (`-03:00`).

### `GET /api/viagens/{id}/rota`

Array bruto de posições, **incluindo as inválidas**. É a fonte para a análise de
paradas — o GeoJSON não carrega dado por ponto.

```json
[
  { "ts": "2026-09-05T22:02:01Z", "lat": -24.9553, "lon": -53.4552,
    "hdop": 0.9, "sats": 9, "velKmh": 32.0, "fixValido": true },
  { "ts": "2026-09-05T22:02:37Z", "lat": 0.0, "lon": 0.0,
    "hdop": 99.0, "sats": 0, "velKmh": 0.0, "fixValido": false }
]
```

⚠️ **Descarte sempre `fixValido: false` antes de qualquer cálculo ou desenho.**
Sem fix, o GPS emite `lat: 0, lon: 0` — a "Ilha Nula", no golfo da Guiné. Um
único desses pontos numa rota de Cascavel adiciona ~9.500 km. Os timestamps são
UTC; converta para America/Sao_Paulo na exibição.

### `GET /api/carros` e `GET /api/secretarias`

Mesmo envelope paginado. Carro: `{ id, modelo, marca, numero_frota, placa,
dispositivo_id, secretaria_id }`. Secretaria: `{ id, nome }`.

⚠️ Carros criados automaticamente pela ingestão vêm com `modelo: "Nao informado"`,
`marca: "Nao informada"` e secretaria `"Nao informada"`. **Trate isso**: quando o
campo for "Nao informado"/"Nao informada", use o valor mockado no lugar.

---

## O que é real e o que é mock — leia com atenção

| Dado | Origem |
|---|---|
| Viagens, rotas, GeoJSON, km, horários, qtd de pontos | **API real** |
| Carros e secretarias (identidade: placa, frota, dispositivo) | **API real**, enriquecida com mock |
| Condutor de cada viagem | **Mock** — a API sempre devolve `servidor: null` |
| Destino declarado | **Mock** — não existe na API |
| Estado do óleo, manutenções, hodômetro | **Mock** — não existem na API |
| Disponibilidade "em viagem agora" | **Derivado** — ver regra abaixo |

**Não invente endpoints.** Os que existem são exatamente os listados acima. Tudo
que não estiver ali é mock em arquivo local (`src/mocks/`).

### Como ligar mock a dado real

Crie `src/mocks/frota.ts` com uma fila de carros indexada por **placa**:

```ts
export const MOCK_CARROS: Record<string, MockCarro> = {
  'BAZ-1D23': {
    modelo: 'Gol 1.0', marca: 'Volkswagen', ano: 2021,
    secretaria: 'SESAU',
    hodometro: 84228,
    oleo: { kmUltimaTroca: 79000, intervaloKm: 10000 },
    manutencao: {
      ultimaPreventiva: '2026-05-12',
      intervaloDias: 180,
      kmUltimaPreventiva: 76500,
      intervaloKmPreventiva: 15000,
    },
    condutorPadrao: 'mat-18432',
  },
  // ... uns 10 a 14 carros, placas variadas, estados de manutenção variados:
  // alguns em dia, um perto do limite, dois vencidos, um com óleo crítico
}
```

E `src/mocks/condutores.ts` com ~10 servidores
(`{ matricula, nome, cargo, secretaria, cnhValidade }`).

**Cada viagem real recebe um condutor de forma determinística** (nunca aleatória —
o painel não pode mudar a cada refresh). Use um hash simples do `lote_id`:

```ts
const idx = [...viagem.lote_id].reduce((a, c) => a + c.charCodeAt(0), 0)
const condutor = CONDUTORES[idx % CONDUTORES.length]
```

O destino declarado segue a mesma lógica, sorteado de uma lista fixa de destinos
plausíveis ("UBS Cascavel Velho", "Hospital Municipal", "Almoxarifado Central",
"Escola Padre Carlos", "Secretaria de Obras"...).

Para placas que aparecerem na API sem entrada no mock, gere dados
pseudo-aleatórios **determinísticos a partir da placa**, para nunca quebrar.

---

## Regras de cálculo

### Paradas ("quanto tempo ficou parado em cada local")

Sobre o array de `/rota`, já filtrado por `fixValido`:

1. Marque como *parado* todo ponto com `velKmh < 3`.
2. Agrupe pontos parados **consecutivos**.
3. O grupo vira uma parada se durar **≥ 60 segundos** (`ts` do último menos o do primeiro).
4. Local da parada = centroide (média de lat/lon do grupo).
5. Exiba: horário de chegada, duração formatada (`4 min 12 s`) e coordenadas.
   Rotule com um nome de local mockado quando o centroide cair a menos de 300 m
   de um ponto conhecido na lista de destinos; senão, mostre as coordenadas.

No mapa da viagem, marque cada parada com um círculo cujo raio cresce com a
duração.

### Disponibilidade da frota

A API não tem conceito de "em viagem agora" — as viagens chegam só depois que o
carro volta. Defina assim, e **deixe a regra visível na interface** com um
tooltip:

- **Em viagem**: recebeu viagem cuja `fim` está nas últimas 2 horas
- **Disponível**: qualquer outro carro sem alerta de manutenção vencida
- **Indisponível**: manutenção preventiva vencida ou óleo em estado crítico

Mostre o total e a quebra **por secretaria**.

### Alertas

Combine mock e real:

| Alerta | Severidade | Origem |
|---|---|---|
| Manutenção preventiva vencida | alta | mock |
| Óleo vencido (km desde a troca > intervalo) | alta | mock |
| Manutenção vence em ≤ 15 dias ou ≤ 1.000 km | média | mock |
| Carro sem nenhuma viagem há mais de 15 dias | média | real |
| Viagem iniciada fora do expediente (antes das 6h ou depois das 20h) | média | real |
| Viagem com mais de 10% de posições sem fix (`1 - qtd_pontos/qtd_pontos_recebidos`) | baixa | real |

### Indicadores gerenciais

- Km total no período e número de viagens
- Km por secretaria (barras)
- Viagens por dia (linha)
- Top 5 carros por quilometragem (barras horizontais)
- % de disponibilidade da frota (donut ou barra)
- Tempo médio parado por viagem

---

## Telas

### 1. Dashboard (`/`)

- Linha de KPIs: km total, viagens no período, carros disponíveis / total, alertas abertos
- Painel de alertas, ordenado por severidade, cada item clicável levando ao carro
- Gráficos de indicadores
- Mapa com **todas as rotas do período** (`GET /api/viagens/geojson`), cada rota
  numa cor, com popup mostrando placa, condutor, km e horário
- Filtro de período (últimos 7 / 30 dias / intervalo customizado) e por secretaria,
  aplicado a tudo na página

### 2. Frota (`/carros`)

Tabela com busca e ordenação: **placa**, modelo, número de frota, secretaria,
condutor padrão, hodômetro, **estado do óleo** (badge ok / atenção / crítico),
**última preventiva**, **próxima preventiva** (data e km, com contagem de dias
restantes), status de disponibilidade.

Busca por placa, modelo ou condutor. Filtro por secretaria e por status.

### 3. Detalhe do carro (`/carros/:placa`)

- Ficha completa, com os blocos de óleo e manutenção em destaque
- Histórico de viagens do carro (usa `carro_id` no filtro da API)
- Mapa com as rotas recentes desse carro
- Mini-indicadores: km no mês, número de viagens, tempo médio parado

### 4. Viagens (`/viagens`)

Tabela paginada com: data/hora de saída e chegada, placa, **condutor**,
**destino**, **quilometragem**, duração, secretaria. Filtros por período, carro,
secretaria e condutor. Clique abre o detalhe.

### 5. Detalhe da viagem (`/viagens/:id`)

- Mapa grande com a rota desenhada a partir do GeoJSON, marcador verde na saída e
  vermelho na chegada
- Cabeçalho com condutor, destino, placa, km, saída e chegada
- **Lista de paradas**, com duração de cada uma
- Perfil de velocidade ao longo do tempo (gráfico de linha, a partir de `/rota`)
- Aviso quando houver posições descartadas: *"3 de 41 posições descartadas por
  falta de sinal de GPS"*

### 6. Busca de condutor por horário (`/condutores`)

> "Quem estava dirigindo o carro X às 14h30 do dia tal?"

Formulário com **data + hora** e, opcionalmente, carro ou secretaria. Busca todas
as viagens cujo intervalo `[inicio, fim]` contém o instante informado e mostra:
condutor, placa, destino, onde o veículo estava naquele momento (interpole a
posição pelo `ts` mais próximo em `/rota`) e um mini-mapa com o ponto destacado.

Quando não houver viagem naquele instante, diga com todas as letras que **nenhum
veículo estava em viagem** — não devolva resultado vazio sem explicação.

---

## Design

Deliberadamente básico e limpo. Nada de gradientes, sombras pesadas ou animação
decorativa.

- Fundo `#f5f6f8`, cartões brancos, borda `1px solid #e1e4e8`, raio 6px
- Texto principal `#1f2328`, secundário `#656d76`
- Ação/destaque: azul `#0969da`
- Estados: verde `#1a7f37`, âmbar `#9a6700`, vermelho `#cf222e`
- Fonte do sistema (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`)
- Layout: barra lateral fixa de 220px com a navegação, conteúdo à direita
- Tabelas com zebra discreta e cabeçalho fixo
- Badges de status: fundo claro da cor + texto na cor escura, **nunca só cor** —
  sempre com rótulo em texto, para quem não distingue cores

Responsivo o suficiente para não quebrar em 1280px. Mobile não é prioridade.

## Estrutura sugerida

```
src/
  api/           client.ts (fetch tipado), viagens.ts, carros.ts
  types/         api.ts (tipos do contrato), dominio.ts
  mocks/         frota.ts, condutores.ts, destinos.ts
  lib/           paradas.ts, alertas.ts, disponibilidade.ts, formato.ts
  components/    Mapa, TabelaViagens, CardKPI, Badge, FiltroPeriodo, ...
  pages/         Dashboard, Frota, CarroDetalhe, Viagens, ViagemDetalhe, Condutores
```

Tipe o contrato da API em `types/api.ts` **exatamente como documentado acima** —
inclusive `servidor_id: null` e `odometro_inicio: number | null`.

## Critérios de aceite

1. `npm install && npm run dev` sobe sem erro.
2. Com o backend no ar, o dashboard mostra as viagens reais e desenha as rotas.
3. Com o backend **fora do ar**, o app não quebra: mostra um aviso claro de que a
   API está indisponível e mantém as telas de frota funcionando com os mocks.
4. Nenhuma posição com `fixValido: false` aparece em mapa, cálculo de parada ou
   perfil de velocidade.
5. Nenhuma rota aparece fora do Paraná (teste de ordem de coordenadas).
6. O condutor de uma viagem é sempre o mesmo entre recarregamentos.
7. Todos os horários exibidos estão em America/Sao_Paulo.
8. A busca por condutor num horário sem viagem explica que não houve viagem.

## Primeiro passo

Antes de escrever componente, gere os mocks e a camada `api/` + `types/`, e
imprima no console o resultado de `GET /api/viagens` para confirmar que o proxy
está funcionando. Depois construa Dashboard → Viagens → Detalhe da viagem →
Frota → Detalhe do carro → Condutores, nessa ordem.

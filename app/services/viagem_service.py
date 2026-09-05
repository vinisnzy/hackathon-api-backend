"""Ingestao de um lote do ESP32.

A ordem dos passos importa e esta comentada abaixo. O ponto central: o
dispositivo so apaga o cartao SD ao receber ok:true, entao qualquer resposta
que nao seja 200/201 significa "o dado continua no carro e volta depois".
"""

import datetime as dt
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import LoteSemFixValido
from app.models import Carro, Secretaria
from app.repositories import cadastro as repo_cadastro
from app.repositories import viagem as repo_viagem
from app.schemas.lote import LoteIn, PosicaoIn
from app.schemas.viagem import ViagemAceitaOut, ViagemDuplicadaOut
from app.services.geo import VERSAO_CALCULO, km_da_rota


def _posicoes_validas(posicoes: list[PosicaoIn]) -> list[PosicaoIn]:
    """Descarta leituras sem fix.

    Sem fix o modulo emite lat=0, lon=0 -- a "Ilha Nula", no golfo da Guine.
    Um unico desses pontos numa rota de Cascavel adiciona cerca de 10.000 km
    a viagem. Este e o unico filtro alem do corte de ruido de 5 m: qualquer
    outro (hdop, sats, velocidade maxima) mudaria um numero auditado sem
    estar especificado.
    """
    return [p for p in posicoes if p.fix_valido]


SECRETARIA_PADRAO = "Nao informada"


def _numero_de_frota(dispositivo_id: str) -> str:
    """Extrai o numero do slug do dispositivo: "esp32-0157" -> "0157"."""
    digitos = re.findall(r"\d+", dispositivo_id)
    return digitos[-1] if digitos else dispositivo_id[:30]


def _secretaria_padrao(db: Session) -> Secretaria:
    """Secretaria coringa para os carros criados automaticamente."""
    existente = db.execute(
        select(Secretaria).where(Secretaria.nome == SECRETARIA_PADRAO)
    ).scalar_one_or_none()
    if existente is not None:
        return existente
    nova = Secretaria(nome=SECRETARIA_PADRAO)
    db.add(nova)
    db.flush()
    return nova


def _placa_livre(db: Session, candidata: str | None, dispositivo_id: str) -> str:
    """Placa para o carro novo, sem colidir com o indice unico.

    Usa a que o dispositivo informou; se ela ja pertence a outro carro, cai
    para o proprio id do dispositivo, que e unico por definicao.
    """
    if candidata:
        candidata = candidata.strip().upper()[:10]
        ja_existe = db.execute(
            select(Carro.id).where(Carro.placa == candidata)
        ).scalar_one_or_none()
        if ja_existe is None:
            return candidata
    return dispositivo_id[:10]


def _resolve_carro(db: Session, lote: LoteIn) -> Carro:
    """Acha o carro do dispositivo, criando um se ainda nao existir.

    O cadastro previo nao e exigido: o dispositivo e a fonte da identidade e
    um lote nunca e recusado por falta de cadastro. O carro criado aqui nasce
    com os dados que vieram no proprio lote e pode ser completado depois pelo
    CRUD (modelo, marca, secretaria de verdade).
    """
    carro = repo_cadastro.busca_carro_por_dispositivo(db, lote.dispositivo_id)
    if carro is not None:
        return carro

    carro = Carro(
        modelo="Nao informado",
        marca="Nao informada",
        numero_frota=_numero_de_frota(lote.dispositivo_id),
        placa=_placa_livre(db, lote.placa, lote.dispositivo_id),
        dispositivo_id=lote.dispositivo_id,
        secretaria_id=_secretaria_padrao(db).id,
    )
    db.add(carro)
    db.flush()
    return carro


def processa_lote(db: Session, lote: LoteIn) -> tuple[ViagemAceitaOut | ViagemDuplicadaOut, bool]:
    """Executa a ingestao. Devolve (resposta, criada)."""

    # 1. Resolver o dispositivo, cadastrando o carro na hora se for a
    #    primeira vez que ele aparece.
    carro = _resolve_carro(db, lote)

    # 2. Idempotencia por consulta previa: o caminho comum de um reenvio nao
    #    paga o custo de um INSERT que vai falhar.
    if repo_viagem.busca_por_lote(db, carro.id, lote.lote_id) is not None:
        return ViagemDuplicadaOut(lote_id=lote.lote_id), False

    # 3. Filtrar posicoes sem fix.
    validas = _posicoes_validas(lote.posicoes)
    if not validas:
        raise LoteSemFixValido(
            "nenhuma posicao com fixValido=true: lote sem quilometragem apuravel"
        )

    # 4. Ordenar por tempo. O dispositivo grava em ordem, mas um SD remontado
    #    apos falha de energia pode entregar blocos fora de sequencia -- e
    #    Haversine sobre pontos embaralhados vira zigue-zague.
    ordenadas = sorted(validas, key=lambda p: p.ts)

    # 5. Quilometragem, congelada aqui e nunca recalculada na exibicao.
    km = km_da_rota(ordenadas)

    # 6. Gravar. A rota vai crua e completa (inclusive o que foi descartado):
    #    e o registro que sustenta a auditoria.
    valores: dict[str, Any] = {
        "carro_id": carro.id,
        "servidor_id": None,
        "lote_id": lote.lote_id,
        "placa_informada": lote.placa,
        "rota": [p.para_json() for p in lote.posicoes],
        "inicio": ordenadas[0].ts,
        "fim": ordenadas[-1].ts,
        "km_gps": km,
        "qtd_pontos": len(ordenadas),
        "qtd_pontos_recebidos": len(lote.posicoes),
        "versao_calculo": VERSAO_CALCULO,
        "enviado_em": lote.enviado_em,
    }

    viagem_id = repo_viagem.insere_se_novo(db, valores)
    if viagem_id is None:
        # Perdeu a corrida para outro reenvio simultaneo: o dado esta gravado,
        # entao o dispositivo pode apagar o SD do mesmo jeito.
        db.rollback()
        return ViagemDuplicadaOut(lote_id=lote.lote_id), False

    db.commit()

    return (
        ViagemAceitaOut(
            viagem_id=viagem_id,
            lote_id=lote.lote_id,
            pontos_recebidos=len(lote.posicoes),
            pontos_validos=len(ordenadas),
            km_gps=km,
        ),
        True,
    )

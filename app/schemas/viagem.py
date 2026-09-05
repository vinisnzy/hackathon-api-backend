"""Respostas de ingestao e de leitura de viagem."""

import datetime as dt
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class KmComoNumero(BaseModel):
    """Serializa km_gps como numero JSON, nao como string.

    O Decimal e mantido no banco e em memoria -- e o que garante o
    arredondamento contabil. Mas Pydantic serializa Decimal como string por
    padrao, e o contrato pede numero ("km_gps": 27.4). Com Numeric(10,2) o
    maior valor possivel tem 10 digitos significativos, bem dentro do que um
    double representa sem perda.
    """

    @field_serializer("km_gps", when_used="json", check_fields=False)
    def _km_como_float(self, valor: Decimal) -> float:
        return float(valor)


class ViagemAceitaOut(KmComoNumero):
    """ACK de sucesso (201). So com isto o dispositivo apaga o cartao SD."""

    ok: bool = True
    viagem_id: UUID
    lote_id: str
    pontos_recebidos: int
    pontos_validos: int
    km_gps: Decimal


class ViagemDuplicadaOut(BaseModel):
    """ACK de reenvio (200). Nada foi gravado; o SD pode ser apagado."""

    ok: bool = True
    lote_id: str
    duplicada: bool = True


class SecretariaAninhada(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str


class CarroAninhado(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    modelo: str
    marca: str
    numero_frota: str
    placa: str
    dispositivo_id: str
    secretaria: SecretariaAninhada


class ServidorAninhado(BaseModel):
    """Sem CPF de proposito: o detalhe da viagem e consumido pelo mapa."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    matricula: str
    cargo: str


class ViagemListItem(KmComoNumero):
    """Item da listagem. Sem a coluna rota."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    carro_id: UUID
    servidor_id: UUID | None
    lote_id: str
    inicio: dt.datetime
    fim: dt.datetime
    km_gps: Decimal
    qtd_pontos: int
    qtd_pontos_recebidos: int
    recebida_em: dt.datetime


class ViagemDetalhe(ViagemListItem):
    """Detalhe com carro, servidor e secretaria aninhados. Sem a rota."""

    placa_informada: str | None
    odometro_inicio: int | None
    odometro_fim: int | None
    versao_calculo: int
    enviado_em: dt.datetime | None
    carro: CarroAninhado
    servidor: ServidorAninhado | None

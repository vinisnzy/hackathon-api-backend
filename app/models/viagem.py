"""A viagem: um lote de posicoes gravado offline e descarregado no patio.

E um livro-razao append-only. Nao ha PUT, PATCH nem DELETE em viagem: e isso
que faz "km_gps congelado" ser uma garantia e nao uma intencao. O numero vai
para prestacao de contas publica e nao pode mudar depois de gravado.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.carro import Carro
    from app.models.servidor import Servidor


class Viagem(UUIDPrimaryKey, Base):
    __tablename__ = "viagem"
    __table_args__ = (
        # A idempotencia mora aqui, no banco, e nao so na aplicacao: e esta
        # constraint que o ON CONFLICT usa para transformar um reenvio numa
        # resposta 200 em vez de duplicar a quilometragem.
        UniqueConstraint("carro_id", "lote_id", name="uq_viagem_carro_lote"),
        Index("ix_viagem_carro_inicio", "carro_id", "inicio"),
        Index("ix_viagem_inicio", "inicio"),
    )

    carro_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("carro.id", ondelete="RESTRICT"), nullable=False
    )
    # Previsto para quando houver cracha RFID. O contrato atual do dispositivo
    # nao identifica o condutor, entao hoje fica sempre nulo.
    servidor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("servidor.id", ondelete="RESTRICT"), nullable=True
    )

    lote_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # A placa que o dispositivo afirmou ter. Guardada para auditoria: se ela
    # divergir da cadastrada, ha erro de configuracao em campo, mas a ingestao
    # nao e barrada (ver viagem_service).
    placa_informada: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Array cru, exatamente como chegou, INCLUSIVE as posicoes sem fix. E o que
    # sustenta a auditoria: da para recalcular km_gps a partir daqui.
    # deferred_raiseload garante que este JSONB nunca vaze para a listagem --
    # acesso acidental levanta erro em vez de emitir um SELECT por linha.
    rota: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, deferred=True, deferred_raiseload=True
    )

    inicio: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fim: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    km_gps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Posicoes com fix valido (as que desenham a linha e alimentam o calculo).
    qtd_pontos: Mapped[int] = mapped_column(Integer, nullable=False)
    # Tamanho do array bruto recebido, incluindo o que foi descartado.
    qtd_pontos_recebidos: Mapped[int] = mapped_column(Integer, nullable=False)

    # Versao da regra de calculo. Um byte que permite mudar o algoritmo no
    # futuro sem tornar o historico inexplicavel na prestacao de contas.
    versao_calculo: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="1"
    )

    # Mantidos por constarem em ENTIDADES. O contrato atual do dispositivo nao
    # envia hodometro, entao permanecem nulos.
    odometro_inicio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odometro_fim: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relogio do dispositivo (pode estar torto).
    enviado_em: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Relogio do banco: autoritativo para "quando a prefeitura recebeu".
    recebida_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    carro: Mapped["Carro"] = relationship(lazy="raise")
    servidor: Mapped["Servidor | None"] = relationship(lazy="raise")

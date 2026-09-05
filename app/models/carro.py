import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.secretaria import Secretaria


class Carro(UUIDPrimaryKey, Base):
    __tablename__ = "carro"
    __table_args__ = (Index("ix_carro_secretaria_id", "secretaria_id"),)

    modelo: Mapped[str] = mapped_column(String(80), nullable=False)
    marca: Mapped[str] = mapped_column(String(80), nullable=False)
    numero_frota: Mapped[str] = mapped_column(String(30), nullable=False)
    placa: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)

    # Slug do ESP32 embarcado ("esp32-0157"). Fica separado do PK de proposito:
    # um dispositivo queima e e trocado; o carro continua o mesmo, e o historico
    # de viagens precisa continuar apontando para ele.
    dispositivo_id: Mapped[str] = mapped_column(
        String(60), nullable=False, unique=True, index=True
    )

    secretaria_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("secretaria.id", ondelete="RESTRICT"), nullable=False
    )

    secretaria: Mapped["Secretaria"] = relationship(back_populates="carros")

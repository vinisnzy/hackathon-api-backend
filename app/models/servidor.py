import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.secretaria import Secretaria


class Servidor(UUIDPrimaryKey, Base):
    __tablename__ = "servidor"

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    # Guardado com digitos apenas (normalizado no schema), senao "111.222.333-44"
    # e "11122233344" convivem e o indice unico nao serve para nada.
    cpf: Mapped[str] = mapped_column(String(11), nullable=False, unique=True)
    matricula: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    cargo: Mapped[str] = mapped_column(String(120), nullable=False)
    secretaria_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("secretaria.id", ondelete="RESTRICT"), nullable=False
    )

    secretaria: Mapped["Secretaria"] = relationship(back_populates="servidores")

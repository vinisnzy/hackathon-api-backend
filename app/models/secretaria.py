import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.carro import Carro
    from app.models.servidor import Servidor


class Secretaria(UUIDPrimaryKey, Base):
    __tablename__ = "secretaria"

    nome: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    carros: Mapped[list["Carro"]] = relationship(back_populates="secretaria")
    servidores: Mapped[list["Servidor"]] = relationship(back_populates="secretaria")

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Secretaria {self.nome}>"

"""Base declarativa e mixin de identidade."""

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKey:
    """PK UUID gerada na aplicacao.

    Gerar do lado Python (e nao com gen_random_uuid()) deixa o id disponivel
    antes do flush, o que simplifica montar respostas dentro da transacao.
    """

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

"""Envelopes reutilizados pelas respostas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int
    pages: int


class Erro(BaseModel):
    """Envelope unico de erro.

    O dispositivo decide pelo campo "ok". O 401/404/422 padrao do FastAPI
    devolve {"detail": ...}, sem "ok" -- o firmware teria dois caminhos de
    parse. Todos os erros da API passam a ter este formato.
    """

    ok: bool = False
    erro: str
    detalhes: list[dict] | None = None

"""Schemas de CRUD para secretaria, servidor e carro."""

import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_NAO_DIGITO = re.compile(r"\D")


class SecretariaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: Annotated[str, Field(min_length=1, max_length=120)]


class SecretariaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str


class ServidorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, Field(min_length=1, max_length=150)]
    cpf: Annotated[str, Field(min_length=11, max_length=14)]
    matricula: Annotated[str, Field(min_length=1, max_length=30)]
    cargo: Annotated[str, Field(min_length=1, max_length=120)]
    secretaria_id: UUID

    @field_validator("cpf")
    @classmethod
    def _somente_digitos(cls, v: str) -> str:
        # Normaliza antes do indice unico, senao "111.222.333-44" e
        # "11122233344" entram os dois como servidores diferentes.
        digitos = _NAO_DIGITO.sub("", v)
        if len(digitos) != 11:
            raise ValueError("cpf deve ter 11 digitos")
        return digitos


class ServidorOut(BaseModel):
    """Detalhe do servidor. Inclui CPF."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    cpf: str
    matricula: str
    cargo: str
    secretaria_id: UUID


class ServidorListItem(BaseModel):
    """Item de listagem SEM CPF.

    Um GET aberto que devolve CPF de servidor municipal e exposicao de dado
    pessoal (LGPD). "Autenticacao de frontend fora de escopo" nao cobre isso.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    matricula: str
    cargo: str
    secretaria_id: UUID


class CarroIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelo: Annotated[str, Field(min_length=1, max_length=80)]
    marca: Annotated[str, Field(min_length=1, max_length=80)]
    numero_frota: Annotated[str, Field(min_length=1, max_length=30)]
    placa: Annotated[str, Field(min_length=7, max_length=10)]
    dispositivo_id: Annotated[str, Field(min_length=1, max_length=60)]
    secretaria_id: UUID

    @field_validator("placa")
    @classmethod
    def _normaliza_placa(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("dispositivo_id")
    @classmethod
    def _normaliza_dispositivo(cls, v: str) -> str:
        return v.strip()


class CarroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    modelo: str
    marca: str
    numero_frota: str
    placa: str
    dispositivo_id: str
    secretaria_id: UUID

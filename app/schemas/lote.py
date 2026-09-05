"""Contrato de entrada: o lote que o ESP32 descarrega ao voltar ao patio."""

import datetime as dt
from typing import Annotated, Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# Um ESP32 que liga sem fix de GPS nao tem relogio: emite 1970 (epoch zero) ou
# 2000 (epoch do RTC). Aceitar isso contamina inicio/fim da viagem inteira, e o
# registro passa a dizer que a prefeitura rodou em 1970.
TS_MINIMO = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
# Folga de um dia cobre relogio adiantado do dispositivo sem aceitar lixo.
TOLERANCIA_FUTURO = dt.timedelta(days=1)

# 6 casas decimais ~ 11 cm. Muito abaixo do corte de ruido de 5 m, entao
# arredondar aqui nao muda a quilometragem -- mas garante que o valor gravado
# no JSONB e exatamente o valor usado no calculo.
CASAS_COORDENADA = 6

MAX_POSICOES = 50_000


class PosicaoIn(BaseModel):
    """Uma leitura do GPS.

    extra="forbid": campo desconhecido vira 422 em vez de sumir calado. Se o
    firmware passar a mandar algo novo, e melhor descobrir por um erro do que
    por um dado que nunca chegou ao banco.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ts: AwareDatetime
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    hdop: float | None = Field(default=None, ge=0)
    sats: int | None = Field(default=None, ge=0)
    vel_kmh: float | None = Field(default=None, ge=0, alias="velKmh")
    fix_valido: bool = Field(alias="fixValido")

    @field_validator("ts")
    @classmethod
    def _ts_plausivel(cls, v: dt.datetime) -> dt.datetime:
        v = v.astimezone(dt.timezone.utc)
        if v < TS_MINIMO:
            raise ValueError(
                f"ts anterior a {TS_MINIMO.date()}: dispositivo sem fix de relogio"
            )
        limite = dt.datetime.now(dt.timezone.utc) + TOLERANCIA_FUTURO
        if v > limite:
            raise ValueError("ts no futuro: relogio do dispositivo adiantado")
        return v

    @field_validator("lat", "lon")
    @classmethod
    def _arredonda_coordenada(cls, v: float) -> float:
        return round(v, CASAS_COORDENADA)

    def para_json(self) -> dict[str, Any]:
        """Forma canonica gravada no JSONB, em camelCase como chegou."""
        return self.model_dump(mode="json", by_alias=True)


class LoteIn(BaseModel):
    """O corpo do POST /api/viagens."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dispositivo_id: str = Field(alias="dispositivoId", min_length=1, max_length=60)
    placa: str | None = Field(default=None, max_length=10)
    lote_id: str = Field(alias="loteId", min_length=1, max_length=64)
    enviado_em: AwareDatetime | None = Field(default=None, alias="enviadoEm")
    posicoes: list[PosicaoIn] = Field(min_length=1, max_length=MAX_POSICOES)

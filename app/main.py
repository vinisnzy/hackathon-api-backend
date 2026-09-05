"""Aplicacao FastAPI."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import ErroDominio
from app.core.security import DeviceTokenMiddleware
from app.routers import cadastros, health, viagens

settings = get_settings()

app = FastAPI(
    title="API de Telemetria de Frota",
    version="1.0.0",
    description=(
        "Recebe lotes de posicoes GPS gravados offline por dispositivos ESP32 "
        "instalados nos veiculos da prefeitura e os disponibiliza para o mapa."
    ),
)

# Antes do roteamento: um dispositivo sem token nao chega a ter seu corpo lido.
app.add_middleware(
    DeviceTokenMiddleware,
    token=settings.device_token,
    prefixos=("/api/viagens", "/api/viagens/"),
)


# O dispositivo decide pelo campo "ok". Sem estes handlers, 401/404/422 sairiam
# no formato {"detail": ...} do FastAPI e o firmware teria dois caminhos de
# parse -- um para sucesso e outro para erro.


@app.exception_handler(ErroDominio)
def erro_dominio(_: Request, exc: ErroDominio) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={"ok": False, "erro": exc.mensagem}
    )


@app.exception_handler(HTTPException)
def erro_http(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "erro": str(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
def erro_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "erro": "payload invalido",
            # jsonable via mode="json" nao se aplica: errors() ja e serializavel
            # exceto por excecoes em "ctx", removidas aqui.
            "detalhes": [
                {k: v for k, v in e.items() if k != "ctx"} for e in exc.errors()
            ],
        },
    )


app.include_router(health.router)
app.include_router(viagens.router)
app.include_router(cadastros.router)

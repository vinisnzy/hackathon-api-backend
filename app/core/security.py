"""Autenticacao do dispositivo.

A verificacao acontece em middleware ASGI, antes do roteamento e antes de
qualquer leitura do corpo. Um dispositivo nao autenticado nao faz o servidor
bufferizar um dump de cartao SD inteiro na memoria -- que e o pior caso deste
endpoint, ja que o payload legitimo chega a dezenas de milhares de posicoes.

Como o middleware roda antes da validacao do corpo, um token invalido devolve
401 mesmo quando o payload tambem esta quebrado. Isso importa: o dispositivo
so apaga o SD com ok:true, e 401 e a resposta correta para "seu token esta
errado", nao 422.
"""

import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

HEADER_TOKEN = "x-device-token"


def token_confere(recebido: str | None, esperado: str) -> bool:
    if not recebido:
        return False
    # compare_digest levanta TypeError em str nao-ASCII (viraria 500 num header
    # com lixo); comparar bytes evita isso e mantem o tempo constante.
    return secrets.compare_digest(recebido.encode("utf-8"), esperado.encode("utf-8"))


class DeviceTokenMiddleware:
    """Exige X-Device-Token nas rotas de ingestao."""

    def __init__(self, app: ASGIApp, *, token: str, prefixos: tuple[str, ...]) -> None:
        self.app = app
        self.token = token
        self.prefixos = prefixos

    def _protegido(self, scope: Scope) -> bool:
        if scope.get("method") != "POST":
            return False
        caminho = scope.get("path", "")
        return any(
            caminho == p or caminho == p.rstrip("/") for p in self.prefixos
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._protegido(scope):
            await self.app(scope, receive, send)
            return

        recebido = Request(scope).headers.get(HEADER_TOKEN)
        if not token_confere(recebido, self.token):
            resposta = JSONResponse(
                status_code=401,
                content={"ok": False, "erro": "X-Device-Token ausente ou invalido"},
            )
            await resposta(scope, receive, send)
            return

        await self.app(scope, receive, send)

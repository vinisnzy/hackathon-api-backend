"""Excecoes de dominio. Os routers as traduzem para HTTP."""


class ErroDominio(Exception):
    status_code = 400

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class DispositivoNaoCadastrado(ErroDominio):
    status_code = 404


class LoteSemFixValido(ErroDominio):
    status_code = 422


class NaoEncontrado(ErroDominio):
    status_code = 404


class Conflito(ErroDominio):
    status_code = 409

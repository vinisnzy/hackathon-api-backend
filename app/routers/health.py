from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness puro.

    Nao toca o banco de proposito: um /health que cai junto com uma piscada de
    conexao tira o servico inteiro do balanceador sem necessidade.
    """
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: confirma que o banco responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "banco": "ok"}

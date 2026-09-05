#!/bin/sh
# As migrations rodam aqui, no entrypoint -- nunca no import da aplicacao.
# Rodar no import faria cada worker do uvicorn tentar migrar em paralelo, e
# faria a suite de testes migrar um banco que ela mesma ja preparou.
set -e

echo "Aguardando o banco..."
until python -c "
import os, sys
import psycopg
try:
    psycopg.connect(os.environ['DATABASE_URL'].replace('+psycopg', '')).close()
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done

echo "Aplicando migrations..."
alembic upgrade head

exec "$@"

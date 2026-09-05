.PHONY: install migrate test run seed compose-up compose-down

install:
	uv venv --python 3.11 .venv
	uv pip install --python .venv/bin/python -e ".[dev]"

migrate:
	.venv/bin/alembic upgrade head

test:
	DATABASE_URL=postgresql+psycopg://frota:frota@127.0.0.1:5432/frota_test \
	.venv/bin/pytest -q

run:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v

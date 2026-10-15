.PHONY: api web test lint demo docker
api:
	python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
web:
	cd apps/web && corepack pnpm dev
test:
	python -m pytest apps/api/tests
	cd apps/web && corepack pnpm test
lint:
	python -m ruff check apps/api scripts
	python -m ruff format --check apps/api scripts
	python -m mypy apps/api/app
	cd apps/web && corepack pnpm typecheck && corepack pnpm lint && corepack pnpm format:check
demo:
	python scripts/run_demo.py
docker:
	docker compose up --build

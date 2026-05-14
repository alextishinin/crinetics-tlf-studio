.PHONY: dev build test-api test-ui shell down logs

dev:
	docker compose up

build:
	docker compose build

test-api:
	cd backend && uv run pytest

test-ui:
	cd frontend && npm test --if-present

shell:
	docker compose exec api bash

down:
	docker compose down

logs:
	docker compose logs -f

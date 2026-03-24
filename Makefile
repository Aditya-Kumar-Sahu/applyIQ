COMPOSE ?= docker compose

.PHONY: backend-test frontend-build migrate compose-up compose-down

backend-test:
	$(COMPOSE) run --rm backend python -m pytest tests

frontend-build:
	$(COMPOSE) run --rm frontend npm run build

migrate:
	$(COMPOSE) run --rm backend alembic upgrade head

compose-up:
	$(COMPOSE) up --build backend frontend db redis

compose-down:
	$(COMPOSE) down

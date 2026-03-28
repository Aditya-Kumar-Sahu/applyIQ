COMPOSE ?= docker compose
PROD_COMPOSE ?= docker compose -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: backend-test frontend-build migrate compose-up compose-down phase-check prod-build prod-up prod-down

backend-test:
	$(COMPOSE) run --rm --build backend python -m pytest tests

frontend-build:
	$(COMPOSE) run --rm --build frontend npm run build

migrate:
	$(COMPOSE) run --rm --build backend alembic upgrade head

compose-up:
	$(COMPOSE) up --build backend frontend db redis

compose-down:
	$(COMPOSE) down

phase-check:
	$(COMPOSE) run --rm --build backend alembic upgrade head
	$(COMPOSE) run --rm --build backend python -m pytest tests
	$(COMPOSE) run --rm --build frontend npm run build

prod-build:
	$(PROD_COMPOSE) build backend
	$(PROD_COMPOSE) build worker
	$(PROD_COMPOSE) build beat
	$(PROD_COMPOSE) build frontend

prod-up:
	$(PROD_COMPOSE) up -d

prod-down:
	$(PROD_COMPOSE) down

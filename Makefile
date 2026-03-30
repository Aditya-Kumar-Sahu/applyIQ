COMPOSE ?= docker compose
PROD_COMPOSE ?= docker compose -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: dev worker beat test test-unit test-integration backend-test frontend-build migrate compose-up compose-down phase-check prod-build prod-up prod-down logs shell

dev:
	$(COMPOSE) up --build

worker:
	$(COMPOSE) exec backend celery -A app.worker worker --loglevel=info

beat:
	$(COMPOSE) exec backend celery -A app.worker beat --loglevel=info

test:
	$(COMPOSE) run --rm --build backend python -m pytest tests -v --tb=short

test-unit:
	$(COMPOSE) run --rm --build backend python -m pytest tests/unit -v

test-integration:
	$(COMPOSE) run --rm --build backend python -m pytest tests/integration -v

backend-test:
	$(MAKE) test

frontend-build:
	$(COMPOSE) run --rm --build frontend npm run build

migrate:
	$(COMPOSE) run --rm --build backend alembic upgrade head

compose-up:
	$(MAKE) dev

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

logs:
	$(COMPOSE) logs -f backend worker

shell:
	$(COMPOSE) exec backend python

PYTHON ?= python

.PHONY: backend-test backend-run compose-up compose-down

backend-test:
	$(PYTHON) -m pytest backend/tests

backend-run:
	cd backend && uvicorn app.main:app --reload

compose-up:
	docker compose up --build

compose-down:
	docker compose down

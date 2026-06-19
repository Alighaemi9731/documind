SHELL := /bin/bash
COMPOSE := docker compose --env-file .env -f deploy/docker-compose.yml
COMPOSE_DEV := docker compose --env-file .env -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml
API := apps/api
WEB := apps/web
VENV := $(API)/.venv

.DEFAULT_GOAL := help
.PHONY: help up down dev logs ps pull config migrate makemigration backup restore \
        api-venv api-install api-lint api-fmt api-test web-install web-lint web-build \
        web-test install lint test fmt bootstrap-admin

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

## --- docker lifecycle ---
up: ## Start the production stack
	$(COMPOSE) up -d
down: ## Stop the stack
	$(COMPOSE) down
dev: ## Build + start the dev stack (published ports)
	$(COMPOSE_DEV) up -d --build
logs: ## Tail service logs
	$(COMPOSE) logs -f --tail=120
ps: ## List services
	$(COMPOSE) ps
pull: ## Pull pinned images
	$(COMPOSE) pull
config: ## Validate compose config
	$(COMPOSE) config -q && echo "compose OK"

## --- database ---
migrate: ## Apply Alembic migrations (in the api container)
	$(COMPOSE) exec api alembic upgrade head
makemigration: ## Create a migration: make makemigration m="message"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"
backup: ## Backup db + uploads + caddy_data
	bash deploy/backup/backup.sh
restore: ## Restore: make restore db=path vol=path
	bash deploy/backup/restore.sh "$(db)" "$(vol)"

## --- backend (local dev) ---
api-venv: ## Create the api virtualenv (python3.12)
	python3.12 -m venv $(VENV)
api-install: api-venv ## Install api deps incl. dev extras
	$(VENV)/bin/pip install -U pip && $(VENV)/bin/pip install -e "$(API)[dev]"
api-lint: ## ruff check + ruff format --check + mypy
	cd $(API) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
api-fmt: ## Format backend (ruff)
	cd $(API) && .venv/bin/ruff format . && .venv/bin/ruff check --fix .
api-test: ## Run backend tests
	cd $(API) && .venv/bin/pytest -q

## --- frontend (local dev) ---
web-install: ## Install web deps
	cd $(WEB) && npm install
web-lint: ## eslint + prettier check + tsc
	cd $(WEB) && npm run lint && npm run format:check && npm run typecheck
web-build: ## Production build
	cd $(WEB) && npm run build
web-test: ## Playwright smoke test
	cd $(WEB) && RUN_E2E=1 npm test

## --- aggregate ---
install: api-install web-install ## Install backend + frontend
lint: api-lint web-lint ## Lint everything
test: api-test ## Run unit tests
fmt: api-fmt ## Format code

## --- ops ---
bootstrap-admin: ## Create the bootstrap admin (ADMIN_EMAIL from .env)
	$(COMPOSE) exec api python -m app.cli bootstrap-admin --email "$(ADMIN_EMAIL)"

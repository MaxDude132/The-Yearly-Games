export UV_PYTHON ?= 3.13
export DJANGO_SETTINGS_MODULE ?= config.settings

PORT ?= 8150
MANAGE = uv run python manage.py

# Local Postgres in Docker, for checking the app against the production database engine.
POSTGRES_PORT ?= 5452
POSTGRES_URL = postgres://yearly:yearly@localhost:$(POSTGRES_PORT)/yearly_games

# The production image, run locally with the Docker Postgres and S3 server (compose.yaml).
IMAGE ?= the-yearly-games

# Railway Infrastructure as Code (.railway/railway.py). `uv run` puts the project environment first on
# PATH, so the CLI's python3 finds railway_sdk. Every target checks the linked project first: a parent
# folder may be linked to another project, and plan/apply act on whatever project is linked.
RAILWAY_PROJECT = the-yearly-games
RAILWAY = uv run railway

.DEFAULT_GOAL := help

.PHONY: help install css migrate content messages setup dev run test lint format clean \
	db-up db-down test-postgres docker-build docker-run docker-down \
	railway-init railway-check infra-plan infra-apply infra-apply-ci ci

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the Python dependencies and the Tailwind binary (no Node needed)
	uv sync
	$(MANAGE) tailwind install

css: ## Build the Tailwind stylesheet (minified)
	$(MANAGE) tailwind build

migrate: ## Create or update the database tables
	$(MANAGE) migrate

content: ## Load (or reload) items, story lines and questions from the fixtures
	$(MANAGE) load_content

messages: ## Compile the interface translations (.po to .mo)
	$(MANAGE) compilemessages --ignore=.venv

setup: install css messages migrate content ## First-time setup: dependencies, CSS, translations, database, content

dev: ## Dev server on http://localhost:$(PORT) + Tailwind watcher + browser reload (see Procfile.tailwind)
	$(MANAGE) tailwind dev

run: css ## Dev server only, on http://localhost:$(PORT)
	$(MANAGE) runserver 127.0.0.1:$(PORT)

test: messages ## Run the tests on SQLite (includes thousands of simulated games)
	$(MANAGE) test

db-up: ## Start a local Postgres in Docker (port $(POSTGRES_PORT))
	docker compose up -d --wait postgres

db-down: ## Stop the local Postgres (keeps its data)
	docker compose stop postgres

test-postgres: messages db-up ## Run the tests on the local Postgres, like production
	DATABASE_URL=$(POSTGRES_URL) $(MANAGE) test

docker-build: ## Build the production image (the one Railway builds)
	docker build -t $(IMAGE) .

docker-run: db-up ## Run the production image on http://localhost:8160 with the local Postgres and S3 server
	docker compose up -d s3
	uv run python scripts/create_local_bucket.py
	docker compose --profile app up --build web

docker-down: ## Stop everything compose.yaml started (keeps the data)
	docker compose --profile app stop

railway-init: ## Create the Railway project and link this folder to it (once)
	railway init --name $(RAILWAY_PROJECT)

railway-check: ## Fail unless this folder is linked to the $(RAILWAY_PROJECT) Railway project
	@linked="$$(railway status --json 2>/dev/null | uv run python -c 'import json, sys; print(json.load(sys.stdin).get("name", ""))' 2>/dev/null)"; \
	if [ "$$linked" != "$(RAILWAY_PROJECT)" ]; then \
		printf 'This folder is linked to the Railway project "%s", not "%s".\nRun `make railway-init` (first time) or `railway link --project %s`.\n' "$$linked" "$(RAILWAY_PROJECT)" "$(RAILWAY_PROJECT)"; \
		exit 1; \
	fi

infra-plan: railway-check ## Preview what .railway/railway.py would change in Railway (changes nothing)
	$(RAILWAY) config plan

infra-apply: railway-check ## Apply .railway/railway.py to Railway, after showing the plan and asking
	$(RAILWAY) config apply

# No --confirm-destructive on purpose: a change that would delete or detach something (the bucket,
# the database, a variable) makes the apply fail, and then it has to be applied by hand with infra-apply.
infra-apply-ci: railway-check ## (CI) Apply .railway/railway.py without asking; fails on destructive changes
	$(RAILWAY) config apply --yes

ci: lint test ## Everything CI checks before applying the infrastructure

lint: ## Check the code style
	uv run ruff check .
	uv run ruff format --check .

format: ## Format the code and apply safe lint fixes
	uv run ruff check --fix .
	uv run ruff format .

clean: ## Delete the local SQLite database, uploaded photos, built CSS and caches
	rm -rf db.sqlite3 media .ruff_cache theme/static/css/dist
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +

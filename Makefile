export UV_PYTHON ?= 3.13
export DJANGO_SETTINGS_MODULE ?= config.settings

PORT ?= 8150
MANAGE = uv run python manage.py

# Local Postgres in Docker, for checking the app against the production database engine.
POSTGRES_PORT ?= 5452
POSTGRES_URL = postgres://yearly:yearly@localhost:$(POSTGRES_PORT)/yearly_games

# The production image, run locally against the Docker Postgres.
IMAGE ?= the-yearly-games
DOCKER_PORT ?= 8160

.DEFAULT_GOAL := help

.PHONY: help install css migrate content messages setup dev run test lint format clean \
	db-up db-down test-postgres docker-build docker-run

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

docker-run: docker-build db-up ## Run the production image on http://localhost:$(DOCKER_PORT) with the local Postgres
	docker run --rm -it -p $(DOCKER_PORT):8000 \
		-e PORT=8000 \
		-e DJANGO_SECRET_KEY=local-docker-only \
		-e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
		-e DJANGO_HTTPS=0 \
		-e DATABASE_URL=postgres://yearly:yearly@host.docker.internal:$(POSTGRES_PORT)/yearly_games \
		$(IMAGE) sh -c "python manage.py migrate && python manage.py load_content && exec gunicorn"

lint: ## Check the code style
	uv run ruff check .
	uv run ruff format --check .

format: ## Format the code and apply safe lint fixes
	uv run ruff check --fix .
	uv run ruff format .

clean: ## Delete the local SQLite database, uploaded photos, built CSS and caches
	rm -rf db.sqlite3 media .ruff_cache theme/static/css/dist
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +

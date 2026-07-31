.DEFAULT_GOAL := help
PY ?= python
VENV := .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
endif

.PHONY: help bootstrap install lint fmt typecheck check validate doctor \
        bench bench-quick bench-chunking offline report site site-dev \
        docker docker-run clean distclean build

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Create the venv and install everything for development
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev,all]"
	@echo "Next: cp .env.example .env, fill it in, then 'make doctor'"

install: ## Install the package in editable mode
	$(BIN)/python -m pip install -e ".[dev]"

lint: ## Ruff
	$(BIN)/python -m ruff check src

fmt: ## Ruff autofix + format
	$(BIN)/python -m ruff check --fix src
	$(BIN)/python -m ruff format src

typecheck: ## mypy
	$(BIN)/python -m mypy src/ragarena

check: lint typecheck validate ## Everything CI runs

validate: ## Check the bundled dataset labels
	$(BIN)/ragarena validate --dataset meridian

doctor: ## Verify config and provider connectivity
	$(BIN)/ragarena doctor

bench: ## Full suite, hosted providers
	$(BIN)/ragarena bench --suite default --out results

bench-quick: ## Four strategies, ten questions, no judge
	$(BIN)/ragarena bench --suite quick --limit 10 --no-judge --out results

bench-chunking: ## Chunking sweep
	$(BIN)/ragarena bench --suite chunking --out results

offline: ## Full suite with zero API keys (local CPU models, no judge)
	$(BIN)/ragarena bench --suite default --no-judge \
		--embed-provider fastembed --rerank-provider crossencoder --out results

report: ## Re-render HTML + site JSON from a saved run: make report RUN=results/x.json
	$(BIN)/ragarena report $(RUN)

build: ## Build the wheel and sdist
	$(BIN)/python -m pip install --upgrade hatchling build
	$(BIN)/python -m build

site: ## Build the leaderboard site
	cd site && npm ci && npm run build

site-dev: ## Run the leaderboard site locally
	cd site && npm install && npm run dev

docker: ## Build the container image
	docker build -t ragarena:local .

docker-run: ## Run a quick benchmark in the container
	docker run --rm --env-file .env -v "$(CURDIR)/results:/work/results" ragarena:local

clean: ## Remove caches and build artefacts
	rm -rf build dist *.egg-info .mypy_cache .ruff_cache .ragarena_cache .cache_*
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

distclean: clean ## Also remove the venv and node_modules
	rm -rf $(VENV) site/node_modules site/.next

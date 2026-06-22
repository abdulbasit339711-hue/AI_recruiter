# AI-Recruiter — start/stop all servers
#
# Quick start:
#   make start      # run backend + frontend + voice agent together (Ctrl-C stops all)
#   make stop       # kill anything left listening on the dev ports
#
# Individual servers:
#   make backend    # FastAPI   -> http://127.0.0.1:8000
#   make frontend   # Next.js   -> http://localhost:3000
#   make voice      # Pipecat interview server (runner.py) -> http://127.0.0.1:7860

.DEFAULT_GOAL := help

# ---- Config -----------------------------------------------------------------
PYTHON ?= python
BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000
PIPECAT_DIR := voice-agent/server
LOG_DIR := logs

# ---- Aggregate targets ------------------------------------------------------
.PHONY: start
start: ## Start backend, frontend and voice agent together (Ctrl-C stops all)
	@echo "Starting all servers — press Ctrl-C to stop them all."
	@mkdir -p $(LOG_DIR)
	@trap 'echo; echo "Stopping..."; kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory backend  2>&1 | awk '{print "[backend ] " $$0; fflush()}' & \
	$(MAKE) --no-print-directory frontend 2>&1 | awk '{print "[frontend] " $$0; fflush()}' & \
	$(MAKE) --no-print-directory voice    2>&1 | awk '{print "[voice   ] " $$0; fflush()}' & \
	wait

# ---- Individual servers -----------------------------------------------------
.PHONY: backend
backend: ## Run the FastAPI backend (uvicorn, auto-reload)
	PYTHONUNBUFFERED=1 $(PYTHON) -m uvicorn app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

.PHONY: frontend
frontend: ## Run the Next.js frontend dev server
	cd frontend && npm run dev -- --port $(FRONTEND_PORT)

.PHONY: voice
voice: ## Run the Pipecat interview server (runner.py on :7860 — NOT bot.py)
	cd $(PIPECAT_DIR) && uv run runner.py

# ---- Setup / install --------------------------------------------------------
.PHONY: install
install: ## Install backend, frontend and voice-agent dependencies
	pip install -r requirements.txt
	cd frontend && npm install
	cd $(PIPECAT_DIR) && uv sync

# ---- Housekeeping -----------------------------------------------------------
.PHONY: stop
stop: ## Free the dev ports (backend + frontend) if a server is left running
	-@lsof -ti tcp:$(BACKEND_PORT)  | xargs -r kill 2>/dev/null || true
	-@lsof -ti tcp:$(FRONTEND_PORT) | xargs -r kill 2>/dev/null || true
	@echo "Freed ports $(BACKEND_PORT) and $(FRONTEND_PORT)."

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

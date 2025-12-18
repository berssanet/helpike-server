# Helpike Backend - Makefile
# ===========================
# Remote: make up / make down (runs directly on Python)
# Local Dev: make docker-up / make docker-down (uses Docker)

.PHONY: help up down install logs status clean docker-up docker-down docker-logs setup

# Configuration
PYTHON := python3
PIP := pip3
APP := app.py
PORT := 5001
LOG_FILE := /tmp/helpike.log
PID_FILE := /tmp/helpike.pid
VENV_DIR := .venv

# Colors for output
GREEN := \033[0;32m
RED := \033[0;31m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help
	@echo "Helpike Backend - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Remote/Production:"
	@echo "  make up        - Install deps and start server"
	@echo "  make down      - Stop server"
	@echo "  make status    - Check if server is running"
	@echo "  make logs      - View server logs"
	@echo "  make install   - Install dependencies only"
	@echo ""
	@echo "Local Development (Docker):"
	@echo "  make docker-up   - Start with Docker Compose"
	@echo "  make docker-down - Stop Docker containers"
	@echo "  make docker-logs - View Docker logs"
	@echo ""
	@echo "Utilities:"
	@echo "  make setup     - First-time setup (venv + deps)"
	@echo "  make clean     - Remove temp files and caches"
	@echo "  make test      - Run tests"

# ============================================
# REMOTE/PRODUCTION COMMANDS (no Docker)
# ============================================

install: ## Install Python dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	@$(PIP) install -r requirements.txt -q
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

check-deps: ## Check if required tools are installed
	@echo "$(YELLOW)Checking dependencies...$(NC)"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "$(RED)Error: python3 not found$(NC)"; exit 1; }
	@command -v $(PIP) >/dev/null 2>&1 || { echo "$(RED)Error: pip3 not found$(NC)"; exit 1; }
	@command -v /usr/local/bin/ffmpeg >/dev/null 2>&1 || { echo "$(YELLOW)Warning: ffmpeg not found at /usr/local/bin/ffmpeg$(NC)"; }
	@echo "$(GREEN)✓ All dependencies available$(NC)"

up: check-deps install ## Start the server (production mode)
	@echo "$(YELLOW)Starting Helpike server...$(NC)"
	@# Kill any existing process
	@-pkill -f "$(PYTHON) $(APP)" 2>/dev/null || true
	@sleep 1
	@# Create directories if they don't exist
	@mkdir -p uploads converted
	@# Start server with nohup
	@nohup $(PYTHON) $(APP) > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@sleep 2
	@# Verify it started
	@if curl -s http://localhost:$(PORT)/health > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Server started successfully on port $(PORT)$(NC)"; \
		echo "$(GREEN)  PID: $$(cat $(PID_FILE))$(NC)"; \
		echo "$(GREEN)  Logs: $(LOG_FILE)$(NC)"; \
	else \
		echo "$(RED)✗ Failed to start server. Check logs:$(NC)"; \
		cat $(LOG_FILE); \
		exit 1; \
	fi

down: ## Stop the server
	@echo "$(YELLOW)Stopping Helpike server...$(NC)"
	@-pkill -f "$(PYTHON) $(APP)" 2>/dev/null || true
	@-rm -f $(PID_FILE) 2>/dev/null || true
	@echo "$(GREEN)✓ Server stopped$(NC)"

restart: down up ## Restart the server

status: ## Check server status
	@if pgrep -f "$(PYTHON) $(APP)" > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Server is RUNNING$(NC)"; \
		echo "  PID: $$(pgrep -f '$(PYTHON) $(APP)')"; \
		curl -s http://localhost:$(PORT)/health 2>/dev/null && echo ""; \
	else \
		echo "$(RED)✗ Server is NOT running$(NC)"; \
	fi

logs: ## View server logs
	@if [ -f $(LOG_FILE) ]; then \
		tail -f $(LOG_FILE); \
	else \
		echo "$(RED)No log file found at $(LOG_FILE)$(NC)"; \
	fi

logs-last: ## View last 50 lines of logs
	@if [ -f $(LOG_FILE) ]; then \
		tail -50 $(LOG_FILE); \
	else \
		echo "$(RED)No log file found$(NC)"; \
	fi

# ============================================
# LOCAL DEVELOPMENT (Docker)
# ============================================

docker-up: ## Start with Docker Compose (local dev)
	@echo "$(GREEN)Starting with Docker Compose...$(NC)"
	@docker-compose up -d --build
	@echo "$(GREEN)✓ Docker containers started$(NC)"

docker-down: ## Stop Docker containers
	@echo "$(YELLOW)Stopping Docker containers...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ Docker containers stopped$(NC)"

docker-logs: ## View Docker logs
	@docker-compose logs -f

docker-build: ## Build Docker image
	@docker-compose build

# ============================================
# SETUP & UTILITIES
# ============================================

setup: ## First-time setup with virtual environment
	@echo "$(GREEN)Setting up Helpike Backend...$(NC)"
	@# Create virtual environment if it doesn't exist
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@# Install dependencies
	@$(VENV_DIR)/bin/pip install --upgrade pip -q
	@$(VENV_DIR)/bin/pip install -r requirements.txt -q
	@# Create directories
	@mkdir -p uploads converted
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "To activate the virtual environment:"
	@echo "  source $(VENV_DIR)/bin/activate"
	@echo ""
	@echo "To start the server:"
	@echo "  make up"

clean: ## Remove temporary files and caches
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@rm -rf __pycache__ .pytest_cache
	@rm -rf uploads/* converted/*
	@rm -f $(LOG_FILE) $(PID_FILE)
	@echo "$(GREEN)✓ Cleaned$(NC)"

test: ## Run tests
	@$(PYTHON) -m pytest tests/ -v

# GPU/NVENC check
check-gpu: ## Check if NVIDIA GPU is available
	@echo "$(YELLOW)Checking GPU...$(NC)"
	@if command -v nvidia-smi >/dev/null 2>&1; then \
		nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv; \
		echo ""; \
		echo "$(GREEN)✓ GPU available$(NC)"; \
	else \
		echo "$(RED)✗ nvidia-smi not found$(NC)"; \
	fi

# Check FFmpeg encoders
check-ffmpeg: ## Check available FFmpeg encoders
	@echo "$(YELLOW)Checking FFmpeg encoders...$(NC)"
	@/usr/local/bin/ffmpeg -encoders 2>/dev/null | grep -E "(av1|nvenc)" || echo "No AV1/NVENC encoders found"

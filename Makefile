.PHONY: help up down logs seed lint test

help:          ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up:            ## Start all services via docker-compose
	docker-compose up --build -d

down:          ## Stop all services
	docker-compose down

logs:          ## Tail logs for all services
	docker-compose logs -f

seed:          ## Seed Supabase with fake data
	cd crm && python db/seed.py

lint-crm:      ## Lint CRM backend
	cd crm && ruff check . && mypy .

lint-channel:  ## Lint Channel service
	cd channel && ruff check . && mypy .

lint-frontend: ## Lint Next.js frontend
	cd frontend && npm run lint

lint: lint-crm lint-channel lint-frontend  ## Lint everything

test-crm:      ## Run CRM unit tests
	cd crm && pytest tests/ -v

test-channel:  ## Run Channel service tests
	cd channel && pytest tests/ -v

test: test-crm test-channel  ## Run all tests

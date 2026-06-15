# Orbit — Development Guide

## Getting Started

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| Docker | Latest (for Redis) |
| Git | Latest |

### First-time setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/orbit
cd orbit

# 2. Copy env files and fill in your keys
cp crm/.env.example crm/.env
cp channel/.env.example channel/.env
cp frontend/.env.local.example frontend/.env.local
```

### Running with Docker (recommended)

```bash
make up        # builds & starts all services
make logs      # tail logs
make down      # stop everything
```

Services:
- CRM API: http://localhost:8000
- Channel API: http://localhost:8001
- Frontend: http://localhost:3000 (start separately)

### Running manually

```bash
# Terminal 1 — Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2 — CRM API
cd crm && python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 3 — CRM Celery Worker
cd crm && venv\Scripts\activate
celery -A celery_app worker --loglevel=info --queues=crm

# Terminal 4 — Channel API
cd channel && python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Terminal 5 — Channel Celery Worker
cd channel && venv\Scripts\activate
celery -A celery_app worker --loglevel=info --queues=channel

# Terminal 6 — Frontend
cd frontend && npm install && npm run dev
```

### Database setup

1. Go to your Supabase project → SQL Editor
2. Paste the contents of `crm/db/schema.sql` and run
3. Seed the database: `cd crm && python db/seed.py`

## Project Structure

```
orbit/
├── crm/               # CRM Backend (FastAPI + Celery)
├── channel/           # Channel Service stub (FastAPI + Celery)
├── frontend/          # Next.js 14 App Router frontend
├── docs/              # Documentation
├── docker-compose.yml
├── Makefile
└── README.md
```

## Coding Conventions

### Python (crm/ and channel/)
- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy`
- All public functions must have docstrings
- Pydantic models in `models/`, business logic in `services/`, route handlers stay thin

### TypeScript / Next.js (frontend/)
- Strict TypeScript (`strict: true` in tsconfig)
- All API calls go through `lib/api.ts`
- Types defined in `types/index.ts` — keep in sync with Python models
- Server Components by default; mark `"use client"` only when needed

### Git workflow
- Branch naming: `feat/<feature>`, `fix/<bug>`, `chore/<task>`
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
- PRs require passing lint + tests

## Environment Variables

See `crm/.env.example`, `channel/.env.example`, `frontend/.env.local.example` for all variables.

**Required for dev:**
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — from Supabase dashboard
- `GROQ_API_KEY` — from console.groq.com (free tier works)
- `REDIS_URL` — `redis://localhost:6379/0` for local Docker Redis

## Running Tests

```bash
make test          # run all tests
make test-crm      # CRM tests only
make test-channel  # Channel tests only
```

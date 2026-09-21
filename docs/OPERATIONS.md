# SmartHire AI operations runbook

This runbook covers the current repository's local demo and Compose deployment paths. It is intentionally not a cloud-provider runbook: deployment, TLS, secrets, backups, monitoring, and data-retention controls must be supplied by the operator.

## Operating modes

| Mode | Database | Seed data | Intended use |
| --- | --- | --- | --- |
| Local demo | SQLite | `DEMO_MODE=true` calls `seed_demo()` at API startup | UI review, development, browser workflows |
| Local non-demo | SQLite or PostgreSQL | No fixture seed | Application/API development with explicit data |
| Compose | PostgreSQL + Redis | Only if enabled in the supplied `.env` | Integration-style local deployment |
| Production settings | PostgreSQL required | Demo mode rejected | Requires additional operational controls before launch |

`backend/app/core/config.py` is the source of truth for the production startup gate. It rejects production startup unless demo mode is disabled, the secret is at least 32 characters, the database URL uses PostgreSQL, the frontend URL uses HTTPS, and OpenAI plus SMTP are configured.

## Local start and health checks

```bash
# root
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example backend/.env

# terminal 1
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2
cd frontend
npm ci
npm run dev -- --port 5173
```

Check the API and documentation:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","demo":true,"ai_mode":"Demo"}

# Open in a browser
# http://localhost:5173
# http://localhost:8000/api/docs
```

The health response reports whether demo mode is enabled and whether the API sees an OpenAI key. It is not an authentication or database readiness proof. The Uvicorn startup log is the authoritative signal that the lifespan table creation/seed step completed.

## Demo reset and fixture behavior

The local SQLite path is relative to the process working directory. With the manual command above, the default database is `backend/smarthire.db`.

```bash
# Stop the API first.
rm -f backend/smarthire.db
cd backend
DEMO_MODE=true ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`seed_demo()` returns without changes if the `acme` tenant already exists. Reset the database when you need the original fictional fixtures. Do not use this reset procedure against a real customer database.

The seeded accounts are:

- recruiter/admin: `alex@acme.design` / `DemoPass2026!`
- candidate: `sarah.chen@example.com` / `DemoPass2026!`
- workspace slug: `acme`

These credentials are development fixtures. Rotate all secrets and remove demo data before any shared or public environment.

## Environment configuration

`.env.example` documents the available settings. For a manual API process, place the file at `backend/.env`; for Compose, place it at the repository root as `.env`.

| Variable | Used by | Operational note |
| --- | --- | --- |
| `ENVIRONMENT` | settings | `production` enables the startup gate |
| `DEMO_MODE` | startup, demo auth, seed, token delivery | Must be `false` for production |
| `SECRET_KEY` | JWT signing | Use a unique 32+ character secret outside demos |
| `DATABASE_URL` | SQLAlchemy/Alembic | SQLite for demo; PostgreSQL for production/RLS |
| `FRONTEND_URL` | email links and Stripe callbacks | Must be HTTPS in production |
| `CORS_ORIGINS` | FastAPI CORS | Use exact browser origins, not a wildcard |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | provider boundary | Empty key selects clearly labeled demo behavior |
| `REDIS_URL` | Celery and production rate limiting | Required by the worker and production limiter |
| `SMTP_*` / `EMAIL_FROM` | Celery email task | Verification/reset delivery is not durable without an outbox |
| `STRIPE_*` | Checkout and webhook | Use a recurring price and validate webhook delivery |
| `POSTGRES_PASSWORD` / `APP_DB_PASSWORD` | Compose/init script | Replace examples and plan real rotation |

## Compose runbook

```bash
cp .env.example .env
# Set real local values in .env; keep FRONTEND_URL=http://localhost:8080 for local Compose.
docker compose up --build
```

Startup order is:

1. PostgreSQL initializes its owner database and the `infra/init-db.sh` script creates the restricted application role on first initialization.
2. `migrate` builds the backend image and runs `alembic upgrade head` as the PostgreSQL owner.
3. Redis becomes healthy.
4. `api` and `worker` use the restricted PostgreSQL role.
5. `web` serves the compiled frontend on port 8080 and proxies `/api` to the API service.

Useful commands:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f migrate
docker compose down
```

The Compose stack stores PostgreSQL and Redis in named volumes. `docker compose down -v` deletes those volumes and all local data; use it only for a deliberate local reset.

## Database and migration operations

Local development creates SQLAlchemy tables during the API lifespan when `ENVIRONMENT` is not `production`. Compose uses Alembic explicitly. For a disposable SQLite migration check:

```bash
cd backend
DATABASE_URL=sqlite+aiosqlite:///./migration-test.db \
DEMO_MODE=false \
../.venv/bin/alembic upgrade head
```

For PostgreSQL, run migrations with the owner connection and run the API with the restricted application role. The migration enables and forces RLS on every table that has `tenant_id`. Never infer PostgreSQL RLS behavior from SQLite.

The repository includes a deliberately direct RLS check for a disposable PostgreSQL database:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://OWNER:PASSWORD@localhost:5432/TEST_DB \
DEMO_MODE=false \
../.venv/bin/alembic upgrade head

RLS_DATABASE_URL=postgresql://OWNER:PASSWORD@localhost:5432/TEST_DB \
../.venv/bin/python tests/check_postgres_rls.py
```

The RLS script must be run with a non-owner/non-superuser application role for the strongest check. Do not run the command against a customer's database; its fixtures are intended to be rolled back in a disposable test database.

## Email worker operations

When SMTP is configured, verification and reset routes enqueue `send_email`:

```bash
cd backend
../.venv/bin/celery -A app.tasks.email.celery worker --loglevel=info --concurrency=2
```

The task uses STARTTLS, optional SMTP authentication, and retries `OSError` failures with backoff up to three times. A missing or invalid SMTP configuration should be treated as an operational failure. The current queue call occurs before the request transaction commits; add a transactional outbox before requiring commit/delivery consistency.

## Stripe operations

Configure `STRIPE_SECRET_KEY`, `STRIPE_PRO_PRICE_ID`, and `STRIPE_WEBHOOK_SECRET`. The UI calls Checkout only for a tenant admin. The webhook endpoint rejects missing configuration, oversized payloads, invalid signatures, and then retrieves canonical subscription state before changing the tenant plan.

For local Stripe CLI forwarding:

```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
```

Use test mode and a disposable workspace. The displayed Pro price is UI copy; the configured Stripe recurring price is the source of billing truth.

## Verification before a release

Run the same checks used by CI:

```bash
# backend
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
cd backend
../.venv/bin/pytest -q
../.venv/bin/python -m compileall -q app

# frontend
cd ../frontend
npm ci
npm run lint
npm run build

# browser workflows; make python resolve to .venv
PATH="$(pwd)/../.venv/bin:$PATH" npm run test:e2e
```

The browser configuration starts the API with a separate SQLite `e2e.db` and starts Vite when no servers are being reused. For a clean run, stop local servers and remove `backend/e2e.db` first. Set `BROWSER_PATH` if Chromium is not installed in the Playwright cache.

Current local verification for this branch: 16 backend tests passed, Ruff check/format passed, frontend Prettier lint passed, the strict TypeScript/Vite build passed, and 4 browser workflows passed. Docker builds, live provider calls, and real SMTP delivery were not part of those checks.

## Troubleshooting

### The UI says it cannot connect to SmartHire

1. `curl http://localhost:8000/api/health`.
2. Confirm Uvicorn is listening on port 8000 and the frontend on 5173.
3. Check that the Vite proxy target is `http://127.0.0.1:8000` for local development.
4. In Compose, check `docker compose logs api migrate web` and verify the migration completed.

### Demo data is missing or stale

Stop the API, remove the correct SQLite file relative to its process working directory, and restart with `DEMO_MODE=true`. The seed is idempotent and will not replace an existing `acme` tenant.

### Login succeeds but API requests become unauthorized

Access tokens expire after 15 minutes. The browser attempts refresh through the HTTP-only cookie. A logout, password reset, revoked refresh token, wrong workspace, or changed `token_version` intentionally invalidates the session. Check cookie path `/api/auth`, frontend/API origin, and server logs; do not put refresh tokens in frontend storage.

### Resume upload fails

Use a text-based PDF or a DOCX under 5 MB. PDFs over 25 pages, invalid signatures, malformed DOCX ZIPs, oversized ZIP expansion, and documents with no extractable text are rejected by design. Originals are not retained.

### Billing or email appears disabled

The demo runs without Stripe, Redis, or SMTP credentials. Billing returns a configuration error until Stripe keys and a recurring price are set. Email action tokens are returned only in demo mode; production requires SMTP and a worker.

## Incident and data boundaries

The code logs request errors through the API server but does not ship metrics, traces, or alerts. Operators must add monitoring for API 5xx, provider latency/errors, Celery queue age, database saturation, refresh-token reuse, and tenant-level cost anomalies. There is no built-in backup/restore automation, object-storage quarantine, antivirus scan, OCR, retention scheduler, or candidate deletion/export workflow. Treat those as launch blockers for real applicant data.

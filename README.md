# SmartHire AI

**Better matches. Meaningful conversations. Great hires.**

A runnable, multi-tenant recruitment and interview-preparation MVP based on the supplied SmartHire specification. Includes a responsive recruiter workspace, candidate portal, FastAPI backend, adaptive LangGraph interviews, PostgreSQL row-level security, and a zero-key local demo.

> **Scope:** This is an end-to-end MVP and deployment foundation, not a claim that every advanced phase is complete or that the system has been certified production-ready. The implementation status and remaining hardening work are explicit below. Demo users, resumes, scores, and conversations are fictional.

## Start locally

Requires **Python 3.12+** (also tested locally with 3.11) and **Node 22+**.

```bash
# At the repository root
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example backend/.env

# Terminal 1
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2, from the repository root
cd frontend
npm ci
npm run dev -- --port 5173
```

Open **http://localhost:5173**. The first visit opens the demo recruiter workspace automatically when `DEMO_MODE=true`. No OpenAI, Stripe, Redis, or PostgreSQL account is necessary for this mode. SQLite is created and seeded on startup.

- **Recruiter:** `alex@acme.design`
- **Candidate:** `sarah.chen@example.com`
- **Demo password:** `DemoPass2026!`
- **Workspace slug:** `acme`
- Use the **bottom-left profile menu → Try candidate view** to switch roles.
- **API docs:** http://localhost:8000/api/docs (or `/api/docs` through the frontend).
- Sign out to create a fresh company workspace or a candidate account. Candidates join an existing workspace by slug; this version is not a cross-company job marketplace.

All browser API calls use relative `/api` URLs. Vite proxies these to the API, so remote previews do not send a user's browser to `localhost`. Local fonts are bundled; the main app does not depend on a Google Fonts connection.

## Try the full workflow

1. **Recruiter → Post a job.** Set the title, description, required skills, location, salary, and visibility.
2. **Profile → Try candidate view → My resume.** Upload a text-based PDF or DOCX (5 MB maximum).
3. **Browse jobs → Apply.** The latest resume is attached and the match score is calculated. Duplicate applications are blocked.
4. **My dashboard → Practice interview.** Answer five role-specific questions. Brief answers prompt a deeper follow-up in demo mode. You can close and resume an unfinished conversation.
5. **Finish → Scorecard.** Review strengths and improvement areas, inspect the transcript, or download the report.
6. **Switch to recruiter.** Filter candidates by name, role, status, or match score. Open profiles, shortlist candidates, and review their interviews.
7. Explore **Analytics**, CSV exports, workspace activity, **Team members**, and **Settings**. Jobs can be edited, saved as drafts, or closed while preserving applications.

## Docker + PostgreSQL + Redis

```bash
cp .env.example .env
# For Docker's browser URL, set FRONTEND_URL=http://localhost:8080 in .env.
docker compose up --build
```

Open **http://localhost:8080**. Compose provides:

- PostgreSQL with a distinct **schema-owner** and **non-owner application role**;
- a one-shot Alembic migration container, which completes before the API starts;
- FastAPI, Redis, and a Celery email worker;
- multi-stage frontend build served by an unprivileged Nginx container;
- durable database and Redis volumes.

The database and Redis are not published to host ports. `infra/init-db.sh` creates the restricted application role only on initial database creation. Changing its password in `.env` does not rotate the password in an existing database; perform a real DB credential rotation instead.

**Never deploy the example passwords or demo fixtures to a public environment.** Dockerfiles and Compose are supplied; image builds could not be executed in the development sandbox because Docker was unavailable. PostgreSQL migrations and RLS were separately exercised against a real PostgreSQL server.

## Implemented

| Area | Status |
| --- | --- |
| Recruiter dashboard | Live metrics, period filters, application chart, hiring funnel, top matches, active jobs |
| Candidate portal | Workspace job browsing, apply, application history, resume management, interview history |
| Authentication | Signup/login, bcrypt hashes, 15-minute access JWT, 7-day rotating refresh cookie, logout, email verification, reset flow |
| Session security | Access token held in memory; refresh token HTTP-only, SameSite Strict, Secure in production; reset/logout immediately invalidate existing access tokens |
| Tenancy | Explicit tenant filtering plus transaction-local PostgreSQL RLS context; candidate ownership checks within each tenant |
| Roles | Tenant admin, recruiter, candidate; server-side permission checks |
| Jobs | Create, read, update, close, draft status, free-plan limit of 3 active jobs |
| Resumes | PDF/DOCX validation, size/page/ZIP-expansion limits, structured extraction; original document is not retained |
| Matching | Optional OpenAI embeddings + cosine similarity; transparent keyword-overlap baseline without credentials |
| Interviews | Real LangGraph StateGraph, adaptive text Q&A, persistent state, optimistic turn checks, one unfinished session per application |
| Reports | Stored transcripts, typed scorecards, downloadable JSON feedback, recruiter CSV exports |
| Audit trail | Login, workspace changes, job changes, status transitions, resume upload, interview completion, UI export requests |
| Email | Celery task with SMTP/TLS delivery, retries; wired to verification and password reset |
| Billing integration | Optional Stripe Checkout, signed subscription webhooks, canonical-state plan updates; not live without configured credentials |
| Delivery | Dockerfiles, Nginx, Compose, Alembic, GitHub Actions, API tests, browser tests, RLS verification script |

### Demo AI vs connected AI

The UI labels the active mode in the workspace footer. These are intentionally **not equivalent**:

| | No OpenAI key | `OPENAI_API_KEY` configured |
| --- | --- | --- |
| Resume parsing | Known-skill keyword extraction; experience/education left empty | Native structured output validated against a Pydantic schema |
| Match score | Percentage of required skills found | `text-embedding-3-small` vectors with cosine similarity |
| Questions | Role/skill templates, follow-ups based on answer length | Contextual adaptive questions from JD, resume, and prior answers |
| Evaluation | Demonstration heuristic based on word count | Structured feedback on relevance, specificity, and technical depth |
| Scorecard | Clearly labeled demo coaching feedback | Contextual structured report, with human-review recommendation |

Seeded scores are fictional fixture values, not the result of either matching algorithm. Decorative metric sparklines are illustrative; the main application chart and numeric metrics are calculated from the database. Percentage change is undefined when the prior period is empty and is shown as “New activity.”

AI outputs never execute code, call privileged tools, or make final hiring decisions. Resume/JD/answer text is treated as untrusted data, control characters are stripped, and prompts separate instructions from documents. These are defenses in depth, **not a guarantee against prompt injection**. Connected AI sends resume and interview content to OpenAI; get appropriate consent and review retention/DPA requirements before using real applicant data.

## Connect integrations

### OpenAI

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (default `gpt-4o-mini`) in `backend/.env` or the root Docker `.env`, then restart the API. The implementation uses native Pydantic structured output and `text-embedding-3-small`. Provider failures return actionable 502 errors without silently substituting fake results.

Embeddings are currently computed directly for each application. The schema includes an embedding field for extension, but embeddings are **not persisted or indexed in Qdrant/Chroma yet**. Score percentages are similarity signals, not calibrated probabilities of hiring success.

### Email

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_FROM`; run Redis and:

```bash
cd backend
celery -A app.tasks.email.celery worker --loglevel=info
```

Set `FRONTEND_URL` to the real browser origin so email links work. In demo mode only, one-time verification/reset tokens are returned to support local flows without an email account; the demo signup screen verifies its returned token automatically. Production never returns those tokens. A reliable production rollout should add a transactional email outbox and a resend-verification flow.

### Stripe test mode

Configure `STRIPE_SECRET_KEY`, `STRIPE_PRO_PRICE_ID` (a recurring price), and `STRIPE_WEBHOOK_SECRET`.

```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
```

Subscribe to `customer.subscription.created`, `.updated`, and `.deleted`. Webhooks validate the signature and retrieve the canonical subscription to avoid stale delivery ordering. Configure product pricing in Stripe; the $49 displayed in the interface is a product placeholder and should match the configured price before launch. The seeded demo workspace is already Pro; create a fresh Free workspace to exercise checkout. Enterprise, downgrade flows, and the customer billing portal are not implemented.

## Tests and checks

```bash
# Backend, from repository root
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
cd backend
../.venv/bin/pytest -q

# Frontend
cd ../frontend
npm ci
npm run lint
npm run build
npx playwright install --with-deps chromium
# Ensure `python` resolves to the project virtualenv, then:
PATH="$(pwd)/../.venv/bin:$PATH" npm run test:e2e
```

Playwright starts the API and frontend if they are not already running. Existing local servers are reused outside CI, so tests will create/close a test job and add practice interviews to your demo. Run against a fresh database for repeatable fixture expectations. Optional `BROWSER_PATH` selects an existing Chromium executable.

**Verified locally:** 16 Python tests, 4 browser workflows, strict TypeScript production build, desktop/mobile rendering, and real PostgreSQL RLS checks. The PostgreSQL API flow was also exercised under a non-owner role, including seeding, signup, token rotation, and a completed interview. External OpenAI/Stripe/SMTP calls were not live-tested because no provider credentials were supplied.

The database-level RLS test deliberately issues **unscoped SQL** as a non-owner/non-superuser, checks empty context and cross-tenant reads/updates/inserts, and rolls back its fixtures:

```bash
# Use a disposable PostgreSQL database, never a real customer's database.
cd backend
DATABASE_URL=postgresql+asyncpg://OWNER:PASSWORD@localhost:5432/TEST_DB \
  DEMO_MODE=false alembic upgrade head
RLS_DATABASE_URL=postgresql://OWNER:PASSWORD@localhost:5432/TEST_DB \
  python tests/check_postgres_rls.py
```

GitHub Actions runs formatting/lint, unit/integration tests, a PostgreSQL RLS job, a strict frontend build, browser workflows, and container builds. Deployment is deliberately not wired to an unspecified hosting account.

## Security and production gate

`ENVIRONMENT=production` refuses startup unless:

- `DEMO_MODE=false`;
- `SECRET_KEY` is at least 32 characters;
- `DATABASE_URL` uses PostgreSQL;
- `FRONTEND_URL` uses HTTPS;
- OpenAI and SMTP are configured.

Before deploying:

1. Use a **fresh production database** without demo accounts. Disable demo mode before its first startup.
2. Generate unique secrets and load them from a secret manager. Example DB passwords must be replaced. Use URL-safe DB passwords or URL-encode them in connection strings.
3. Run migrations using the owner. Run requests/workers using the **restricted non-owner role**. Superuser credentials bypass RLS even with `FORCE ROW LEVEL SECURITY`.
4. Put Nginx behind a managed TLS load balancer or configure TLS directly. Do not expose the API, DB, or Redis publicly. The supplied Compose file is a local deployment stack, not a TLS setup.
5. Set exact `CORS_ORIGINS`, SMTP sender DNS, Stripe callback settings, and the browser `FRONTEND_URL`.
6. Restrict the API's trusted proxy network before enabling forwarded-header handling. The supplied command intentionally ignores proxy headers: behind Nginx, IP auth limits are conservative/shared until this is configured. Production rate-limit counters use Redis; AI operations also have per-tenant limits.
7. Add database backups and restore drills, dependency vulnerability scanning, request-body limits at the gateway, budget monitoring, retention/deletion workflows, and accessibility/security review.
8. Complete the remaining roadmap, load-test realistic traffic, and validate score quality before claiming scale or hiring validity.

SQLite verifies application-level isolation only. It has no RLS. The provided PostgreSQL check is essential, not optional evidence to infer from SQLite tests.

## Remaining roadmap / intentional limitations

- Cross-company candidate identity and a public, cross-tenant job marketplace.
- Super-admin tenant/plan console, recruiter invitations, granular permission policies, and enterprise API keys.
- Qdrant/Chroma semantic retrieval, persisted/cacheable embeddings, async resume parsing/scoring, and durable interview checkpoint workers.
- WebSocket/streamed token delivery, audio/video interviews, scheduling, and calendar integration. Current interviews are adaptive **request/response text**.
- Interview and shortlist email notifications beyond account verification/reset; notification read-state is currently browser-session state.
- Dedicated subscription/event tables, billing portal/downgrades, enterprise billing, and usage metering. The MVP stores the current plan/customer on the tenant.
- Blob/object storage, antivirus scanning, OCR, candidate data deletion/export consent controls, and configurable retention. Originals are currently discarded after extraction; structured resume data is retained.
- DB-side pagination for large workspaces (the UI paginates a fetched list), real Redis caching, and race-proof subscription quota counters.
- Prometheus/Grafana/Sentry, structured provider diagnostics, semantic evaluation datasets, k6/Locust load testing, and deployment to a chosen cloud account.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the trust model, state machine, and scale-up design.

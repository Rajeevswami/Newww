# SmartHire AI architecture

This document describes the architecture implemented in this repository. It distinguishes current behavior from scale-up ideas so that the demo is not mistaken for a production-certified hiring system.

## Runtime topology

```text
Browser
  React + TypeScript + TanStack Query
          │ same-origin /api
          ▼
Nginx (Compose) or Vite proxy (development)
          │
          ▼
FastAPI application
  ├── auth + tenant onboarding
  ├── jobs / resumes / applications
  ├── analytics / audit activity
  ├── LangGraph interviews
  └── Stripe boundary
          │                    │
          ▼                    ▼
PostgreSQL + RLS              OpenAI (optional)
(SQLite in demo mode)         embeddings + structured output
          │
          ▼
Celery + Redis (optional) → SMTP verification/reset email
```

`backend/app/main.py` creates the FastAPI application, installs CORS and response security headers, creates local tables outside production, optionally seeds the demo tenant, and mounts the auth, core, and billing routers under `/api`. The frontend calls relative `/api` URLs. In development, `frontend/vite.config.ts` proxies those requests to the API; in Compose, Nginx proxies them to the `api` service.

The browser does not connect directly to the database, Redis, or OpenAI. Provider keys are read by the backend settings object and are not part of the frontend bundle. Fonts are bundled through `@fontsource-variable`, so the main app does not need a Google Fonts request.

## Application boundaries

### Frontend

- `frontend/src/App.tsx` owns the session, in-memory access token, hash-based page navigation, role switcher, global search, modal state, and top-level queries.
- `frontend/src/pages/Dashboard.tsx` renders recruiter overview metrics, charts, funnel, matched candidates, and active jobs.
- `frontend/src/pages/Workspace.tsx` renders job forms/details, candidate search/details, interview lists/details, analytics, resume upload, and the candidate dashboard.
- `frontend/src/pages/Settings.tsx` renders workspace settings, team, billing, security/help content.
- `frontend/src/api/client.ts` centralizes relative fetch calls, refresh-on-401 behavior, typed response shapes, and CSV export.
- `frontend/src/styles.css` contains the responsive UI system, light theme, focus states, reduced-motion rules, modal treatment, and mobile navigation.

The client uses TanStack Query for server data. It intentionally keeps the access JWT in a module variable rather than local storage. A refresh cookie is sent by the browser with `credentials: include`.

### Backend

- `backend/app/api/auth.py` handles signup, login, refresh rotation, logout, current-user lookup, demo login, verification, and password reset.
- `backend/app/api/core.py` handles jobs, applications, resume extraction/upload, interviews, analytics, activity, workspace updates, and team listing.
- `backend/app/api/billing.py` creates Stripe Checkout sessions and validates subscription webhooks when configured.
- `backend/app/models/entities.py` defines tenants, users, jobs, resumes, applications, interviews, refresh/action tokens, and audit logs.
- `backend/app/services/seed.py` creates reproducible fictional fixtures only when `DEMO_MODE=true`.
- `backend/app/tasks/email.py` is a Celery task that sends verification/reset email through SMTP with retry-on-`OSError` behavior.

The API adds an explicit `tenant_id` predicate to tenant-owned queries. `current_user()` derives the tenant from the signed access token, loads the user within that tenant, checks the token version, and sets the request tenant context.

## Tenant trust boundary

1. Signup creates a new tenant only for a `tenant_admin`. Candidate signup resolves an existing public workspace slug and cannot self-assign a recruiter/admin role.
2. Every tenant-owned model has a `tenant_id` foreign key and tenant/id index. API dependencies enforce role checks (`tenant_admin`, recruiter, candidate).
3. PostgreSQL migrations enable and force row-level security on every table with `tenant_id`. The policy compares `tenant_id` with the transaction-local `app.tenant_id` setting.
4. The application also filters tenant IDs in every private query and constrains joined users, jobs, and resumes to the same tenant. Candidate routes add user ownership checks for resumes, applications, and interviews.
5. SQLite has no RLS. Local tests therefore validate application-level isolation; `backend/tests/check_postgres_rls.py` is the explicit database-level check for a disposable PostgreSQL database.
6. A PostgreSQL superuser or `BYPASSRLS` role can bypass RLS. This is why Compose separates the migration owner from the restricted application role.

Tenant scope is a company boundary, not a replacement for role or ownership authorization.

## Authentication lifecycle

```text
signup/login
    │
    ├── short-lived access JWT (15 minutes, browser memory)
    └── refresh JWT (7 days, HTTP-only SameSite cookie)
             │
             └── only SHA-256 digest stored in refresh_tokens

refresh → atomically revoke old digest → issue replacement cookie
logout / password reset → revoke refresh rows + increment token_version
```

Access and refresh tokens carry signed user/tenant context and a token type. Refresh rotation updates the old row before issuing a replacement. Access validation checks the token version against the user row, so logout and password reset invalidate existing access tokens. Passwords use bcrypt directly. Verification and reset action tokens are signed, purpose-specific, hashed in the database, expire after one hour, and are single-use.

The current email enqueue happens before the request transaction commits. A transactional outbox is an explicit production follow-up, not an existing guarantee.

## Resume and matching lifecycle

1. Candidate upload accepts only `.pdf` or `.docx` and caps the request at 5 MB.
2. PDF signatures, page count, DOCX ZIP structure, and ZIP expansion are checked before extraction. Text extraction runs in a threadpool. Scanned or otherwise unreadable documents are rejected.
3. The original bytes are not persisted. Parsed JSON is stored on `resumes.parsed_json`.
4. Without an OpenAI key, parsing searches a fixed known-skill list and leaves experience/education empty. With a key, the provider asks for a Pydantic `ParsedResume` object.
5. Applying stores the resume ID used for that application. Later resume uploads do not mutate the old application snapshot.
6. Matching uses required-skill overlap in demo mode or two `text-embedding-3-small` vectors and cosine similarity when OpenAI is configured. The current code computes embeddings per request; it does not persist or index them.

Uploaded resume and interview content is application data, not an instruction source. Connected provider prompts explicitly separate the task from supplied documents and forbid protected-attribute or autonomous-hiring behavior.

## Interview state machine

`backend/app/ai/interview.py` compiles a LangGraph `StateGraph`:

```text
START
  ├─ no answer → ask_question → END (await browser)
  └─ answer → evaluate_answer
                    ├─ question_count < 5 → ask_question → END
                    └─ question_count >= 5 → generate_scorecard → END
```

State contains role/resume context, conversation history, topics, question count, current evaluation, evaluation history, and scorecard. `start_interview` persists the initial question. Each answer requires the expected turn count; `answer()` atomically claims an in-progress row as `processing` before running the graph, preventing a stale concurrent answer from spending another provider call. The partial unique index prevents two unfinished interviews for one application.

Demo mode evaluates answer length and produces clearly labeled coaching feedback. Connected mode uses structured evaluation and scorecard responses. The UI describes the result as guidance and human-review support; it is not a final hiring decision.

The graph runs inside the request transaction. This keeps the MVP flow simple but holds a database connection while a provider call is in flight. A queued durable interview job/outbox is the scale-up path.

## Metrics, audit, and exports

Recruiter analytics queries tenant-scoped rows and calculates period metrics, six chart buckets, and current-stage-or-later funnel values. Rejected rows remain in the applied count and do not contribute to later funnel stages. Dashboard sparkline points are illustrative UI values; primary metric cards and charts use API data.

Sensitive mutations supported by the API write `AuditLog` rows, including login, workspace/job changes, status changes, resume upload, interview completion, and export requests. Passwords, token values, and raw resume text are not written to audit details. CSV and JSON exports are initiated in the browser; the CSV helper records an export event.

## Delivery and security posture

- Development: Uvicorn + Vite + SQLite, with demo seeding enabled by default.
- Compose: owner-only migration, restricted API/worker role, PostgreSQL RLS, Redis, Celery, and unprivileged Nginx.
- Nginx: same-origin `/api` proxy, 6 MB upload cap, security headers, local asset caching, and a narrowly scoped Swagger CDN policy.
- Production settings refuse startup unless demo mode is off, a 32-character secret exists, PostgreSQL is used, HTTPS frontend URL is set, and OpenAI/SMTP are configured.
- The repository does not provide TLS termination, secret management, backups, monitoring, malware scanning, OCR, retention/deletion workflows, or a cloud deployment.

See [OPERATIONS.md](OPERATIONS.md) for commands, runbooks, verification, and incident boundaries.

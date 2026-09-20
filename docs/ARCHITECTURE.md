# Architecture and decisions

## Runtime

```text
Browser / React + TypeScript + TanStack Query
          │ same-origin HTTPS /api
          ▼
Nginx (production image) or Vite proxy (development)
          │
          ▼
FastAPI modular monolith
  ├── Authentication + workspace onboarding
  ├── Jobs / resumes / applications / analytics
  ├── LangGraph interview service
  └── Stripe webhook + checkout boundary
          │                  │
          ▼                  ▼
PostgreSQL + RLS        OpenAI, when configured
(SQLite in local demo)
          │
          ▼
Celery + Redis → SMTP verification / reset email
```

The browser never connects directly to the database, Redis, or OpenAI. Provider credentials never enter frontend bundles. API documentation is served under `/api/docs`. React UI primitives and responsive styling are bespoke CSS, rather than a shadcn/Tailwind dependency; they include keyboard-focus handling, labeled forms, modal focus trapping, reduced-motion styling, and mobile navigation. An independent WCAG contrast/a11y audit is still needed.

## Tenant trust boundary

- `tenant_id` is derived from a signed access token, then validated against the actual user row. Workspace IDs in request bodies cannot change the authenticated scope.
- Workspace signup resolves a tenant by public slug. Candidate signup cannot grant recruiter/admin roles. Tenant-admin signup creates a **new** tenant; it cannot elevate someone in an existing workspace.
- Before tenant-scoped queries, the API sets `set_config('app.tenant_id', tenant_id, true)` in the request transaction. Transaction-local scope prevents tenant context leaking across pooled connections.
- Every tenant-owned table has `tenant_id`, a tenant/id index, and a PostgreSQL policy with both `USING` and `WITH CHECK`. `FORCE ROW LEVEL SECURITY` is enabled by migration.
- Application queries additionally filter tenant IDs. Joins explicitly constrain each involved tenant. Candidates have a second, within-tenant ownership check on applications, resumes, and interviews.
- Tenants themselves are not globally exposed through a listing endpoint. The non-owner application DB role can resolve workspace identity for signup/login; administrative profile routes fetch only the authenticated tenant.
- Superusers and `BYPASSRLS` roles still bypass RLS. This is why migration and application credentials are separate.
- Tenant context alone is not candidate authorization. RLS is a company boundary; role and user checks remain mandatory.

## Authentication

Access JWTs expire after 15 minutes and remain in browser memory. Refresh JWTs contain signed tenant context plus a random nonce, expire after seven days, and are delivered only in an HTTP-only cookie. Their full values are SHA-256 hashed in the DB. Refresh updates the old token atomically before issuing the replacement. Reuse is denied. Token-version checks let password reset/logout invalidate existing access tokens immediately. Logout revokes all refresh tokens for that account.

Verification/reset action tokens are purpose-specific, signed, hash-stored, one-hour, single-use tokens. Token delivery is queued to SMTP. The current queue enqueue occurs before the request transaction commits; production delivery should use a transactional outbox to guarantee commit-before-send and durable retry bookkeeping.

Bcrypt is used directly, avoiding Passlib's compatibility issues with newer bcrypt releases. JWT is implemented with PyJWT rather than python-jose. Password length is bounded in UTF-8 bytes because bcrypt truncates after 72 bytes.

## Interview state machine

`backend/app/ai/interview.py` compiles an actual LangGraph `StateGraph`:

```text
START ── new session ───────────────► ask_question ──► END (await user)
  │
  └── submitted answer ──► evaluate_answer
                              │ conditional route_next
                              ├── fewer than 5 questions ─► ask_question ─► END
                              └── 5 questions ─► generate_scorecard ─► END
```

State carries `resume_context`, `job_context`, `conversation_history`, `topics_covered`, `question_count`, the current answer/evaluation, all evaluations, and the final scorecard. State/transcript are persisted after each request, so sessions survive process restarts. Each answer submits its expected turn. An atomic claim and a unique partial index prevent stale/double answers and concurrent unfinished sessions. The graph runs inside the request transaction; this is correct for the MVP but holds a DB connection during provider latency. A durable job/outbox model is the next step.

There is no psychological confidence score inferred from text. Evaluation addresses relevance, specificity, and technical depth. Recommendations explicitly support human review, not automatic rejection or hiring. Demo scoring is transparently not evidence of ability.

## Resume and matching lifecycle

1. Candidate uploads a PDF/DOCX, validated by extension, signatures, size, and archive expansion.
2. Text extraction runs off the event loop. Scanned PDFs without text are rejected with a useful error.
3. Structured parsing uses OpenAI native Pydantic output or the documented demo keyword extractor.
4. Only parsed JSON is persisted; originals are discarded. No public file URLs expose candidate PII.
5. Applying snapshots the **resume ID** in the application. Later uploads do not silently rewrite old applications.
6. Matching compares resume and JD using embeddings/cosine similarity when configured. Demo mode computes required-skill overlap. No hidden LLM call is made without an API key.

At scale, store originals privately in S3, use expiring signed URLs and a malware-scanning quarantine, enqueue parse/embedding jobs, persist embedding/version metadata, and index per-tenant payloads in Qdrant. Recheck tenant scope before returning vector-search results; a vector filter is not the sole authorization boundary.

## Metrics and audit

Dashboard aggregates are computed from the authenticated tenant's actual rows. Period filters use UTC dates and six buckets. Funnel bars represent **current stage or later**, not historic events. Rejected candidates remain in the Applied count but do not contribute to later stages. Current activity is not a measure of processing time or a scientifically validated quality signal.

Audit rows cover login and the sensitive mutations currently supported. Sensitive tokens/passwords and raw resume text are not logged. The simple notification view reads recent audit entries; durable per-recipient read state and separate notification preferences remain future work.

## Scale-up / release sequence

1. Security/privacy review, bias evaluation, gold-set semantic tests, calibrated matching thresholds.
2. DB-side pagination and bounded analytics queries; read replicas/PgBouncer where justified by measured load.
3. Transactional outbox, queued parsing/scoring, independent workers, idempotent job retries.
4. Redis cache keyed by tenant + resource + version, with tenant-aware invalidation.
5. Qdrant indexes and embedding model versioning; protect all search payloads with tenant filters and DB verification.
6. Authenticated streaming transport with per-user concurrency limits, connection expiry, and cancellation.
7. Prometheus request/provider latency + error metrics, queue-depth alerts, privacy-safe Sentry tracing, Grafana dashboards.
8. Golden-path load tests and backup recovery drills. Only then publish scale/SLO claims.
9. Split services only when team/deployment needs justify it; the present routers/providers form extraction seams.

Suggested initial alerts: elevated API 5xx, OpenAI timeouts, growing Celery queue age, DB connection saturation, refresh-token reuse spikes, and sustained tenant-level cost anomalies. Monitoring infrastructure is a design, not a running integration in this repo.

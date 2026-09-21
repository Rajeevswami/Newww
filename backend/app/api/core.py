import io
import secrets
import zipfile
from datetime import timedelta
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from pypdf import PdfReader
from docx import Document
from starlette.concurrency import run_in_threadpool
from app.models.entities import (
    ApiKey,
    Job,
    User,
    Resume,
    Application,
    Interview,
    AuditLog,
    Tenant,
    now,
)
from app.core.database import Session, get_db
from app.core.security import (
    admin,
    candidate,
    current_user,
    digest,
    recruiter,
    require_scopes,
    user_from_access_token,
)
from app.core.config import settings
from app.schemas.requests import (
    AnswerInput,
    ApiKeyInput,
    InterviewInput,
    JobInput,
    StatusInput,
    WorkspaceInput,
)
from app.ai.interview import (
    evaluate_answer,
    generate_scorecard,
    interview_graph,
    route_next,
    stream_ask_question,
)
from app.api.auth import limiter
from app.tasks.ai import parse_resume_task, score_application_task


def tenant_limit_key(request: Request):
    return getattr(request.state, "tenant_id", request.client.host if request.client else "unknown")


router = APIRouter(tags=["Workspace"])


def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


async def owned(db, model, key, user):
    result = await db.scalar(
        select(model).where(model.id == key, model.tenant_id == user.tenant_id)
    )
    if not result:
        raise HTTPException(404, "Record not found")
    return result


def audit(db, user, action, details=None):
    db.add(
        AuditLog(tenant_id=user.tenant_id, user_id=user.id, action=action, details=details or {})
    )


def interview_payload(row):
    return {k: v for k, v in serialize(row).items() if k != "state_json"}


@router.get("/jobs")
async def jobs(user=Depends(require_scopes("jobs:read")), db=Depends(get_db)):
    query = select(Job).where(Job.tenant_id == user.tenant_id)
    if user.role == "candidate":
        query = query.where(Job.status == "active")
    rows = (await db.scalars(query.order_by(Job.created_at.desc()))).all()
    counts = dict(
        (
            await db.execute(
                select(Application.job_id, func.count())
                .where(Application.tenant_id == user.tenant_id)
                .group_by(Application.job_id)
            )
        ).all()
    )
    return [serialize(j) | {"applicants": counts.get(j.id, 0)} for j in rows]


@router.post("/jobs", status_code=201)
async def create_job(data: JobInput, user=Depends(recruiter), db=Depends(get_db)):
    tenant = await db.get(Tenant, user.tenant_id)
    count = await db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.tenant_id == user.tenant_id, Job.status == "active")
    )
    if tenant.plan == "Free" and count >= 3 and data.status == "active":
        raise HTTPException(
            403, "The Free plan includes 3 active jobs. Close a job or upgrade your plan."
        )
    row = Job(tenant_id=user.tenant_id, **data.model_dump())
    db.add(row)
    await db.flush()
    audit(db, user, "job.created", {"title": row.title})
    return serialize(row)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = await owned(db, Job, job_id, user)
    if user.role == "candidate" and row.status != "active":
        raise HTTPException(404, "Job not found")
    return serialize(row)


@router.put("/jobs/{job_id}")
async def edit_job(job_id: str, data: JobInput, user=Depends(recruiter), db=Depends(get_db)):
    row = await owned(db, Job, job_id, user)
    if row.status != "active" and data.status == "active":
        tenant = await db.get(Tenant, user.tenant_id)
        count = await db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.tenant_id == user.tenant_id, Job.status == "active")
        )
        if tenant.plan == "Free" and count >= 3:
            raise HTTPException(403, "The Free plan includes 3 active jobs")
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    audit(db, user, "job.updated", {"job_id": job_id})
    return serialize(row)


@router.delete("/jobs/{job_id}")
async def archive_job(job_id: str, user=Depends(recruiter), db=Depends(get_db)):
    row = await owned(db, Job, job_id, user)
    row.status = "closed"
    audit(db, user, "job.closed", {"job_id": job_id})
    return {"ok": True}


async def application_rows(db, user, job_id=None):
    query = (
        select(Application, User, Job, Resume)
        .join(User, Application.user_id == User.id)
        .join(Job, Application.job_id == Job.id)
        .join(Resume, Application.resume_id == Resume.id)
        .where(
            Application.tenant_id == user.tenant_id,
            User.tenant_id == user.tenant_id,
            Job.tenant_id == user.tenant_id,
            Resume.tenant_id == user.tenant_id,
        )
    )
    if user.role == "candidate":
        query = query.where(Application.user_id == user.id)
    if job_id:
        query = query.where(Application.job_id == job_id)
    rows = (await db.execute(query.order_by(Application.match_score.desc()))).all()
    return [
        serialize(a)
        | {
            "name": u.name,
            "email": u.email,
            "job_title": j.title,
            "department": j.department,
            "resume": r.parsed_json,
        }
        for a, u, j, r in rows
    ]


@router.get("/applications")
async def applications(user=Depends(current_user), db=Depends(get_db)):
    return await application_rows(db, user)


@router.get("/applications/{application_id}")
async def get_application(application_id: str, user=Depends(current_user), db=Depends(get_db)):
    rows = await application_rows(db, user)
    row = next((item for item in rows if item["id"] == application_id), None)
    if not row:
        raise HTTPException(404, "Record not found")
    return row


@router.get("/jobs/{job_id}/matches")
async def matches(job_id: str, user=Depends(recruiter), db=Depends(get_db)):
    await owned(db, Job, job_id, user)
    return await application_rows(db, user, job_id)


@router.patch("/applications/{application_id}")
async def set_status(
    application_id: str, data: StatusInput, user=Depends(recruiter), db=Depends(get_db)
):
    row = await owned(db, Application, application_id, user)
    row.status = data.status
    audit(db, user, "application.status_changed", {"application_id": row.id, "status": data.status})
    return serialize(row)


@router.post("/applications/{job_id}/apply", status_code=201)
@limiter.limit("30/minute", key_func=tenant_limit_key)
async def apply(request: Request, job_id: str, user=Depends(candidate), db=Depends(get_db)):
    job = await owned(db, Job, job_id, user)
    if job.status != "active":
        raise HTTPException(400, "This job is not accepting applications")
    if not user.is_verified and not settings.demo_mode:
        raise HTTPException(403, "Verify your email before applying")
    resume = await db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id, Resume.tenant_id == user.tenant_id)
        .order_by(Resume.created_at.desc())
    )
    if not resume:
        raise HTTPException(400, "Upload your resume before applying")
    if await db.scalar(
        select(Application.id).where(
            Application.tenant_id == user.tenant_id,
            Application.job_id == job_id,
            Application.user_id == user.id,
        )
    ):
        raise HTTPException(409, "You have already applied to this job")
    if resume.status != "ready":
        raise HTTPException(409, "Your resume is still being processed. Try again in a moment.")
    row = Application(
        tenant_id=user.tenant_id,
        user_id=user.id,
        resume_id=resume.id,
        job_id=job_id,
        match_score=None,
        status="scoring",
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "You have already applied to this job")
    audit(db, user, "application.created", {"title": job.title})
    await db.commit()
    score_application_task.delay(row.id, user.tenant_id)
    return serialize(row)


MAX_UPLOAD = 5 * 1024 * 1024


def extract_document(data, filename):
    if filename.endswith(".pdf"):
        if not data.startswith(b"%PDF-"):
            raise ValueError("The file is not a valid PDF")
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > 25:
            raise ValueError("Resumes must be 25 pages or fewer")
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("The file is not a valid DOCX")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(x.file_size for x in archive.infolist()) > 20 * 1024 * 1024:
            raise ValueError("Document expands beyond the size limit")
        if "word/document.xml" not in archive.namelist():
            raise ValueError("Invalid DOCX document")
    return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)


@router.post("/resumes/upload", status_code=202)
@limiter.limit("30/minute", key_func=tenant_limit_key)
async def upload_resume(
    request: Request, file: UploadFile = File(...), user=Depends(candidate), db=Depends(get_db)
):
    filename = (file.filename or "").split("/")[-1].split("\\")[-1][:255]
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(422, "Please upload a PDF or DOCX file")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Resume must be smaller than 5 MB")
    try:
        text = await run_in_threadpool(extract_document, data, filename.lower())
    except Exception:
        raise HTTPException(
            422, "Unable to read this file. Use a text-based PDF or DOCX, up to 25 pages and 5 MB."
        )
    if len(text.strip()) < 30:
        raise HTTPException(422, "No readable text found. Scanned PDFs are not supported.")
    row = Resume(
        tenant_id=user.tenant_id,
        user_id=user.id,
        filename=filename,
        parsed_json={
            "name": user.name,
            "skills": [],
            "experience": [],
            "education": [],
            "summary": "Parsing resume…",
        },
        status="pending",
    )
    db.add(row)
    await db.flush()
    audit(db, user, "resume.uploaded")
    await db.commit()
    parse_resume_task.delay(row.id, user.tenant_id, text, user.name)
    return serialize(row)


@router.get("/resumes")
async def my_resumes(user=Depends(candidate), db=Depends(get_db)):
    return [
        serialize(r)
        for r in (
            await db.scalars(
                select(Resume)
                .where(Resume.tenant_id == user.tenant_id, Resume.user_id == user.id)
                .order_by(Resume.created_at.desc())
            )
        ).all()
    ]


@router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = await owned(db, Resume, resume_id, user)
    if user.role == "candidate" and row.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    return serialize(row)


async def check_interview(db, key, user):
    row = await owned(db, Interview, key, user)
    application = await owned(db, Application, row.application_id, user)
    if user.role == "candidate" and application.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    return row


@router.get("/interviews")
async def list_interviews(user=Depends(current_user), db=Depends(get_db)):
    query = (
        select(Interview, Application, User, Job)
        .join(Application, Interview.application_id == Application.id)
        .join(User, Application.user_id == User.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Interview.tenant_id == user.tenant_id,
            Application.tenant_id == user.tenant_id,
            User.tenant_id == user.tenant_id,
            Job.tenant_id == user.tenant_id,
        )
    )
    if user.role == "candidate":
        query = query.where(Application.user_id == user.id)
    rows = (await db.execute(query.order_by(Interview.started_at.desc()))).all()
    return [
        {k: v for k, v in serialize(i).items() if k != "state_json"}
        | {"name": u.name, "job_title": j.title}
        for i, a, u, j in rows
    ]


@router.post("/interviews/start", status_code=201)
@limiter.limit("30/minute", key_func=tenant_limit_key)
async def start_interview(
    request: Request, data: InterviewInput, user=Depends(candidate), db=Depends(get_db)
):
    application = await owned(db, Application, data.application_id, user)
    if application.user_id != user.id:
        raise HTTPException(404, "Application not found")
    existing = await db.scalar(
        select(Interview).where(
            Interview.tenant_id == user.tenant_id,
            Interview.application_id == application.id,
            Interview.status == "in_progress",
        )
    )
    if existing:
        return {k: v for k, v in serialize(existing).items() if k != "state_json"}
    job = await owned(db, Job, application.job_id, user)
    resume = await owned(db, Resume, application.resume_id, user)
    try:
        state = await interview_graph.ainvoke(
            {
                "resume_context": resume.parsed_json,
                "job_context": {
                    "title": job.title,
                    "description": job.description,
                    "required_skills": job.required_skills,
                },
                "conversation_history": [],
                "topics_covered": [],
                "question_count": 0,
            }
        )
    except Exception:
        raise HTTPException(502, "The interview assistant is unavailable. Please retry.")
    row = Interview(
        tenant_id=user.tenant_id,
        application_id=application.id,
        state_json=state,
        transcript_json=state["conversation_history"],
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            409, "An interview was just started. Refresh your interview list to resume it."
        )
    return {k: v for k, v in serialize(row).items() if k != "state_json"}


@router.get("/interviews/{interview_id}")
async def get_interview(interview_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = await check_interview(db, interview_id, user)
    return interview_payload(row)


@router.websocket("/interviews/{interview_id}/stream")
async def stream_interview(websocket: WebSocket, interview_id: str):
    await websocket.accept()
    token = websocket.query_params.get("access_token") or ""
    async with Session() as db:
        try:
            user = await user_from_access_token(token, db)
            if user.role != "candidate":
                await websocket.send_json({"type": "error", "detail": "Candidate access required"})
                await websocket.close(code=1008)
                return
            row = await check_interview(db, interview_id, user)
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "detail": exc.detail})
            await websocket.close(code=1008)
            return
        try:
            payload = await websocket.receive_json()
            answer_text = str(payload.get("answer") or "")
            expected_count = int(payload.get("expected_count") or 0)
            if len(answer_text) < 5 or expected_count < 1 or expected_count > 5:
                await websocket.send_json({"type": "error", "detail": "A valid answer is required"})
                await websocket.close(code=1008)
                return
            if row.status != "in_progress":
                await websocket.send_json(
                    {"type": "error", "detail": "This interview is already complete"}
                )
                await websocket.close(code=1008)
                return
            if row.state_json["question_count"] != expected_count:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "This answer was already submitted. Reload the interview.",
                    }
                )
                await websocket.close(code=1008)
                return
            claimed = (
                await db.execute(
                    update(Interview)
                    .where(
                        Interview.id == row.id,
                        Interview.tenant_id == user.tenant_id,
                        Interview.status == "in_progress",
                        Interview.turn == expected_count,
                    )
                    .values(status="processing")
                    .returning(Interview.id)
                )
            ).first()
            if not claimed:
                await websocket.send_json(
                    {"type": "error", "detail": "An answer is already being processed"}
                )
                await websocket.close(code=1008)
                return
            try:
                state = row.state_json | {"answer": answer_text}
                state = state | await evaluate_answer(state)
                if route_next(state) == "generate_scorecard":
                    state = state | await generate_scorecard(state)
                else:

                    async def on_token(token_text):
                        await websocket.send_json({"type": "token", "text": token_text})

                    state = state | await stream_ask_question(state, on_token)
            except Exception:
                await websocket.close(code=1011)
                return
            row.state_json, row.transcript_json = state, state["conversation_history"]
            row.turn = state["question_count"]
            row.status = "completed" if state.get("complete") else "in_progress"
            if state.get("complete"):
                row.scorecard_json, row.ended_at = state["scorecard"], now()
                audit(db, user, "interview.completed")
                await websocket.send_json(
                    {"type": "done", "interview": jsonable_encoder(interview_payload(row))}
                )
            else:
                await websocket.send_json(
                    {"type": "done", "interview": jsonable_encoder(interview_payload(row))}
                )
            await db.commit()
        except WebSocketDisconnect:
            await db.rollback()
        except Exception:
            await db.rollback()
            await websocket.close(code=1011)


@router.post("/interviews/{interview_id}/answer")
@limiter.limit("30/minute", key_func=tenant_limit_key)
async def answer(
    request: Request,
    interview_id: str,
    data: AnswerInput,
    user=Depends(candidate),
    db=Depends(get_db),
):
    row = await check_interview(db, interview_id, user)
    if row.status != "in_progress":
        raise HTTPException(409, "This interview is already complete")
    if row.state_json["question_count"] != data.expected_count:
        raise HTTPException(409, "This answer was already submitted. Reload the interview.")
    # Claim the current turn atomically. A concurrent request cannot spend another LLM call.
    claimed = (
        await db.execute(
            update(Interview)
            .where(
                Interview.id == row.id,
                Interview.tenant_id == user.tenant_id,
                Interview.status == "in_progress",
                Interview.turn == data.expected_count,
            )
            .values(status="processing")
            .returning(Interview.id)
        )
    ).first()
    if not claimed:
        raise HTTPException(409, "An answer is already being processed")
    try:
        state = await interview_graph.ainvoke(row.state_json | {"answer": data.answer})
    except Exception:
        raise HTTPException(
            502, "The interview assistant is unavailable. Your answer was not saved; please retry."
        )
    row.state_json, row.transcript_json = state, state["conversation_history"]
    row.turn = state["question_count"]
    row.status = "completed" if state.get("complete") else "in_progress"
    if state.get("complete"):
        row.scorecard_json, row.ended_at = state["scorecard"], now()
        audit(db, user, "interview.completed")
    return {k: v for k, v in serialize(row).items() if k != "state_json"}


@router.get("/interviews/{interview_id}/scorecard")
async def get_scorecard(interview_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = await check_interview(db, interview_id, user)
    if not row.scorecard_json:
        raise HTTPException(409, "The interview is not complete yet")
    return row.scorecard_json


@router.get("/dashboard/recruiter/analytics")
async def analytics(
    days: int = Query(default=30, ge=7, le=90), user=Depends(recruiter), db=Depends(get_db)
):
    all_apps = (
        await db.scalars(select(Application).where(Application.tenant_id == user.tenant_id))
    ).all()
    all_jobs = (await db.scalars(select(Job).where(Job.tenant_id == user.tenant_id))).all()
    all_interviews = (
        await db.scalars(select(Interview).where(Interview.tenant_id == user.tenant_id))
    ).all()
    cutoff = (now() - timedelta(days=days)).date()
    apps = [a for a in all_apps if a.created_at.date() >= cutoff]
    prior = [
        a
        for a in all_apps
        if (now() - timedelta(days=days * 2)).date() <= a.created_at.date() < cutoff
    ]
    series = []
    for n in range(6):
        start = cutoff + timedelta(days=round(days * n / 6))
        end = cutoff + timedelta(days=round(days * (n + 1) / 6))
        bucket = [
            a
            for a in apps
            if start <= a.created_at.date() < end + (timedelta(days=1) if n == 5 else timedelta())
        ]
        series.append(
            {
                "date": start.strftime("%b %d"),
                "applications": len(bucket),
                "shortlisted": len([a for a in bucket if a.status in ("Shortlisted", "Hired")]),
            }
        )
    scored = [a for a in apps if a.match_score is not None]
    advanced = {
        "New": 0,
        "scoring": 0,
        "Screening": 1,
        "Interview": 2,
        "Shortlisted": 3,
        "Hired": 4,
        "Rejected": -1,
    }
    funnel = [
        {
            "name": name,
            "value": len([a for a in apps if advanced[a.status] >= idx]) if idx else len(apps),
        }
        for idx, name in enumerate(["Applied", "Screened", "Interview", "Shortlisted", "Hired"])
    ]
    completed = [
        i for i in all_interviews if i.status == "completed" and i.started_at.date() >= cutoff
    ]
    return {
        "active_jobs": len([j for j in all_jobs if j.status == "active"]),
        "applications": len(apps),
        "application_change": (
            round((len(apps) - len(prior)) / len(prior) * 100) if prior else None
        ),
        "interviews": len([i for i in all_interviews if i.started_at.date() >= cutoff]),
        "average_match": round(sum(a.match_score for a in scored) / max(1, len(scored)), 1),
        "shortlisted": len([a for a in apps if a.status == "Shortlisted"]),
        "completed_interviews": len(completed),
        "series": series,
        "funnel": funnel,
        "new_jobs": len([j for j in all_jobs if j.created_at.date() >= cutoff]),
        "ai_mode": "OpenAI" if settings.openai_api_key else "Demo",
    }


@router.get("/dashboard/candidate/history")
async def history(user=Depends(candidate), db=Depends(get_db)):
    return {
        "applications": await application_rows(db, user),
        "interviews": await list_interviews(user, db),
    }


@router.get("/activity")
async def activity(user=Depends(recruiter), db=Depends(get_db)):
    rows = (
        await db.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == user.tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(25)
        )
    ).all()
    return [serialize(r) for r in rows]


@router.put("/workspace")
async def workspace(data: WorkspaceInput, user=Depends(admin), db=Depends(get_db)):
    tenant = await db.get(Tenant, user.tenant_id)
    tenant.name = data.name
    audit(db, user, "workspace.updated")
    return {"name": tenant.name}


def serialize_api_key(row, raw=None):
    data = {
        "id": row.id,
        "name": row.name,
        "scopes": row.scopes,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
        "revoked": row.revoked,
        "key_preview": f"sk_{row.tenant_id[:8]}…{row.id[:4]}",
    }
    if raw:
        data["key"] = raw
    return data


@router.post("/api-keys", status_code=201)
async def create_api_key(data: ApiKeyInput, user=Depends(admin), db=Depends(get_db)):
    raw = f"sk_{user.tenant_id}.{secrets.token_urlsafe(32)}"
    row = ApiKey(
        tenant_id=user.tenant_id,
        name=data.name,
        key_hash=digest(raw),
        scopes=data.scopes,
    )
    db.add(row)
    await db.flush()
    audit(db, user, "api_key.created", {"name": row.name, "scopes": row.scopes})
    return serialize_api_key(row, raw)


@router.get("/api-keys")
async def list_api_keys(user=Depends(admin), db=Depends(get_db)):
    rows = (
        await db.scalars(
            select(ApiKey)
            .where(ApiKey.tenant_id == user.tenant_id)
            .order_by(ApiKey.created_at.desc())
        )
    ).all()
    return [serialize_api_key(row) for row in rows]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user=Depends(admin), db=Depends(get_db)):
    row = await owned(db, ApiKey, key_id, user)
    row.revoked = True
    audit(db, user, "api_key.revoked", {"api_key_id": row.id})
    return {"ok": True}


@router.get("/team")
async def team(user=Depends(recruiter), db=Depends(get_db)):
    rows = (
        await db.scalars(
            select(User).where(User.tenant_id == user.tenant_id, User.role != "candidate")
        )
    ).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in rows]


@router.post("/activity/export")
async def export_audit(user=Depends(recruiter), db=Depends(get_db)):
    audit(db, user, "data.exported")
    return {"ok": True}

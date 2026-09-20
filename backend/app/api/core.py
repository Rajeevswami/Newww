import io
import zipfile
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from pypdf import PdfReader
from docx import Document
from starlette.concurrency import run_in_threadpool
from app.models.entities import Job, User, Resume, Application, Interview, AuditLog, Tenant, now
from app.core.database import get_db
from app.core.security import current_user, recruiter, admin, candidate
from app.core.config import settings
from app.schemas.requests import JobInput, StatusInput, InterviewInput, AnswerInput, WorkspaceInput
from app.ai.provider import parse_resume, match_resume
from app.ai.interview import interview_graph
from app.api.auth import limiter


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


@router.get("/jobs")
async def jobs(user=Depends(current_user), db=Depends(get_db)):
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
    try:
        score = await match_resume(resume.parsed_json, job)
    except Exception:
        raise HTTPException(502, "Matching is temporarily unavailable. Please try again.")
    row = Application(
        tenant_id=user.tenant_id,
        user_id=user.id,
        resume_id=resume.id,
        job_id=job_id,
        match_score=score,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "You have already applied to this job")
    audit(db, user, "application.created", {"title": job.title})
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


@router.post("/resumes/upload", status_code=201)
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
    try:
        parsed = await parse_resume(text, user.name)
    except Exception:
        raise HTTPException(502, "Resume parsing is unavailable. Please try again.")
    row = Resume(tenant_id=user.tenant_id, user_id=user.id, filename=filename, parsed_json=parsed)
    db.add(row)
    await db.flush()
    audit(db, user, "resume.uploaded")
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
    return {k: v for k, v in serialize(row).items() if k != "state_json"}


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
    advanced = {
        "New": 0,
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
        "average_match": round(sum(a.match_score for a in apps) / max(1, len(apps)), 1),
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

import asyncio
import json
import threading
from sqlalchemy import select
from app.core.config import settings
from app.core.database import Session, scope_db
from app.models.entities import Application, Job, Resume
from app.ai.provider import embed_texts, match_resume, parse_resume
from app.tasks.celery_app import celery


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict = {}

    def runner():
        try:
            box["result"] = asyncio.run(coro)
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


async def parse_resume_job(resume_id: str, tenant_id: str, text: str, name: str):
    async with Session() as db:
        await scope_db(db, tenant_id)
        row = await db.scalar(
            select(Resume).where(Resume.id == resume_id, Resume.tenant_id == tenant_id)
        )
        if not row:
            return
        try:
            parsed = await parse_resume(text, name)
            row.parsed_json = parsed
            if settings.openai_api_key:
                from app.ai.vectors import ensure_collections, upsert_resume_vector

                vectors = await embed_texts([json.dumps(parsed)])
                row.embedding = vectors[0]
                ensure_collections()
                upsert_resume_vector(tenant_id, resume_id, row.user_id, vectors[0])
            row.status = "ready"
        except Exception:
            row.status = "failed"
            row.parsed_json = {
                "name": name,
                "skills": [],
                "experience": [],
                "education": [],
                "summary": "Resume parsing failed. Please upload the file again.",
            }
        await db.commit()


async def score_application_job(application_id: str, tenant_id: str):
    async with Session() as db:
        await scope_db(db, tenant_id)
        row = await db.scalar(
            select(Application).where(
                Application.id == application_id, Application.tenant_id == tenant_id
            )
        )
        if not row:
            return
        resume = await db.scalar(
            select(Resume).where(Resume.id == row.resume_id, Resume.tenant_id == tenant_id)
        )
        job = await db.scalar(select(Job).where(Job.id == row.job_id, Job.tenant_id == tenant_id))
        if not resume or not job:
            row.status = "New"
            await db.commit()
            return
        try:
            row.match_score = await match_resume(
                resume.parsed_json,
                job,
                tenant_id=tenant_id,
                resume_id=resume.id,
                user_id=row.user_id,
            )
            row.status = "New"
        except Exception:
            row.match_score = 0
            row.status = "New"
        await db.commit()


@celery.task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def parse_resume_task(resume_id: str, tenant_id: str, text: str, name: str):
    run_async(parse_resume_job(resume_id, tenant_id, text, name))


@celery.task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def score_application_task(application_id: str, tenant_id: str):
    run_async(score_application_job(application_id, tenant_id))

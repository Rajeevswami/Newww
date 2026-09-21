import io
import pytest
from docx import Document
from conftest import demo
from app.ai.provider import cosine_similarity

JOB = {
    "title": "Quality Engineer",
    "description": "Help our team build reliable software and write thoughtful automated tests.",
    "required_skills": ["Python", "SQL"],
    "department": "Engineering",
}


async def signup(client, workspace, role="tenant_admin", email="admin@example.com"):
    response = await client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "CorrectHorse123!",
            "name": "Test Person",
            "workspace": workspace,
            "company": "Test Company",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, response.json()


async def test_auth_and_rotation(client):
    assert (await client.get("/api/jobs")).status_code == 401
    response = await client.post("/api/auth/demo")
    old = client.cookies.get("refresh_token")
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await client.post("/api/auth/refresh")).status_code == 200
    assert client.cookies.get("refresh_token") != old
    # An already-used refresh token cannot issue a new session.
    client.cookies.clear()
    assert (
        await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    ).status_code == 401


async def test_job_crud_and_role_permissions(client):
    recruiter = await demo(client)
    candidate = await demo(client, "candidate")
    assert (await client.post("/api/jobs", headers=candidate, json=JOB)).status_code == 403
    response = await client.post("/api/jobs", headers=recruiter, json=JOB)
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert (
        await client.put(
            f"/api/jobs/{job_id}", headers=recruiter, json=JOB | {"title": "Senior QA Engineer"}
        )
    ).json()["title"] == "Senior QA Engineer"
    assert (await client.delete(f"/api/jobs/{job_id}", headers=recruiter)).status_code == 200
    assert (await client.get(f"/api/jobs/{job_id}", headers=candidate)).status_code == 404
    assert (await client.get(f"/api/jobs/{job_id}", headers=recruiter)).json()["status"] == "closed"


async def test_tenant_isolation_for_all_private_resources(client):
    admin_a = await demo(client)
    jobs_a = (await client.get("/api/jobs", headers=admin_a)).json()
    apps_a = (await client.get("/api/applications", headers=admin_a)).json()
    interview_a = (await client.get("/api/interviews", headers=admin_a)).json()[0]
    admin_b, _ = await signup(client, "other-co")
    assert (await client.get("/api/jobs", headers=admin_b)).json() == []
    assert (await client.get("/api/applications", headers=admin_b)).json() == []
    assert (await client.get("/api/interviews", headers=admin_b)).json() == []
    assert (await client.get("/api/activity", headers=admin_b)).json() == []
    assert (await client.get("/api/dashboard/recruiter/analytics", headers=admin_b)).json()[
        "applications"
    ] == 0
    for endpoint in [
        f"/jobs/{jobs_a[0]['id']}",
        f"/jobs/{jobs_a[0]['id']}/matches",
        f"/resumes/{apps_a[0]['resume_id']}",
        f"/interviews/{interview_a['id']}",
        f"/interviews/{interview_a['id']}/scorecard",
    ]:
        assert (await client.get("/api" + endpoint, headers=admin_b)).status_code == 404
    assert (
        await client.put(f"/api/jobs/{jobs_a[0]['id']}", headers=admin_b, json=JOB)
    ).status_code == 404
    assert (await client.delete(f"/api/jobs/{jobs_a[0]['id']}", headers=admin_b)).status_code == 404
    assert (
        await client.patch(
            f"/api/applications/{apps_a[0]['id']}", headers=admin_b, json={"status": "Hired"}
        )
    ).status_code == 404


async def test_candidate_cannot_read_other_candidate(client):
    admin = await demo(client)
    rows = (await client.get("/api/applications", headers=admin)).json()
    other = next(a for a in rows if a["name"] != "Sarah Chen")
    interviews = (await client.get("/api/interviews", headers=admin)).json()
    other_interview = next(i for i in interviews if i["name"] != "Sarah Chen")
    candidate = await demo(client, "candidate")
    assert (
        await client.get(f"/api/resumes/{other['resume_id']}", headers=candidate)
    ).status_code == 404
    assert (
        await client.get(f"/api/interviews/{other_interview['id']}", headers=candidate)
    ).status_code == 404
    assert (
        await client.post(
            "/api/interviews/start", headers=candidate, json={"application_id": other["id"]}
        )
    ).status_code == 404
    assert (
        await client.get("/api/dashboard/recruiter/analytics", headers=candidate)
    ).status_code == 403
    assert (await client.get("/api/team", headers=candidate)).status_code == 403
    assert all(
        a["name"] == "Sarah Chen"
        for a in (await client.get("/api/applications", headers=candidate)).json()
    )


async def test_resume_upload_apply_and_duplicate(client):
    candidate = await demo(client, "candidate")
    assert (
        await client.post(
            "/api/resumes/upload",
            headers=candidate,
            files={"file": ("bad.exe", b"test", "application/octet-stream")},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/resumes/upload",
            headers=candidate,
            files={"file": ("bad.pdf", b"%PDF-notvalid", "application/pdf")},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/resumes/upload",
            headers=candidate,
            files={"file": ("huge.pdf", b"0" * (5 * 1024 * 1024 + 1), "application/pdf")},
        )
    ).status_code == 413
    doc = Document()
    doc.add_paragraph(
        "Sarah Chen. Experienced Python developer with SQL, FastAPI, Docker, and React skills. Five years of product engineering."
    )
    output = io.BytesIO()
    doc.save(output)
    response = await client.post(
        "/api/resumes/upload",
        headers=candidate,
        files={
            "file": (
                "resume.docx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "pending"
    resume = await client.get(f"/api/resumes/{response.json()['id']}", headers=candidate)
    assert resume.status_code == 200, resume.text
    assert resume.json()["status"] == "ready"
    assert "Python" in resume.json()["parsed_json"]["skills"]
    apps = (await client.get("/api/applications", headers=candidate)).json()
    jobs = (await client.get("/api/jobs", headers=candidate)).json()
    job = next(j for j in jobs if j["id"] not in [a["job_id"] for a in apps])
    response = await client.post(f"/api/applications/{job['id']}/apply", headers=candidate)
    assert response.status_code == 201, response.text
    assert response.json()["status"] in ("scoring", "New")
    polled = await client.get(f"/api/applications/{response.json()['id']}", headers=candidate)
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "New"
    assert 0 <= polled.json()["match_score"] <= 100
    assert (
        await client.post(f"/api/applications/{job['id']}/apply", headers=candidate)
    ).status_code == 409


async def test_full_interview_graph_and_scorecard(client):
    candidate = await demo(client, "candidate")
    app = (await client.get("/api/applications", headers=candidate)).json()[0]
    start = await client.post(
        "/api/interviews/start", headers=candidate, json={"application_id": app["id"]}
    )
    assert start.status_code == 201, start.text
    interview = start.json()
    same = await client.post(
        "/api/interviews/start", headers=candidate, json={"application_id": app["id"]}
    )
    assert same.json()["id"] == interview["id"]
    endpoint = f"/api/interviews/{interview['id']}"
    assert (await client.get(endpoint + "/scorecard", headers=candidate)).status_code == 409
    for n in range(1, 6):
        result = await client.post(
            endpoint + "/answer",
            headers=candidate,
            json={
                "answer": "I interviewed customers, evaluated alternatives, worked with engineering, and measured the results of a successful product release.",
                "expected_count": n,
            },
        )
        assert result.status_code == 200, result.text
        assert len(result.json()["transcript_json"]) == (n * 2 + 1 if n < 5 else 10)
        if n == 1:
            assert (
                await client.post(
                    endpoint + "/answer",
                    headers=candidate,
                    json={"answer": "repeated stale answer", "expected_count": n},
                )
            ).status_code == 409
    assert result.json()["status"] == "completed"
    card = await client.get(endpoint + "/scorecard", headers=candidate)
    assert card.status_code == 200
    assert card.json()["mode"] == "Demo"
    assert 0 <= card.json()["overall_score"] <= 100
    assert (
        await client.post(
            endpoint + "/answer",
            headers=candidate,
            json={"answer": "one more answer", "expected_count": 5},
        )
    ).status_code == 409


async def test_shortlisting_and_input_validation(client):
    admin = await demo(client)
    row = (await client.get("/api/applications", headers=admin)).json()[0]
    assert (
        await client.patch(
            f"/api/applications/{row['id']}", headers=admin, json={"status": "Hired"}
        )
    ).json()["status"] == "Hired"
    assert (
        await client.patch(
            f"/api/applications/{row['id']}", headers=admin, json={"status": "unknown"}
        )
    ).status_code == 422
    assert (
        await client.post("/api/jobs", headers=admin, json=JOB | {"required_skills": [""]})
    ).status_code == 422
    assert (
        await client.get("/api/dashboard/recruiter/analytics?days=10000", headers=admin)
    ).status_code == 422


async def test_email_verification_and_password_reset(client):
    headers, account = await signup(client, "new-company")
    token = account["verification_token"]
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 400
    assert (await client.get("/api/auth/me", headers=headers)).json()["is_verified"] is True
    result = await client.post(
        "/api/auth/forgot-password", json={"email": "admin@example.com", "workspace": "new-company"}
    )
    reset = result.json()["reset_token"]
    assert (
        await client.post(
            "/api/auth/reset-password", json={"token": reset, "password": "NewPassword123!"}
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/auth/reset-password", json={"token": reset, "password": "OtherPassword123!"}
        )
    ).status_code == 400
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    login = {
        "email": "admin@example.com",
        "workspace": "new-company",
        "password": "CorrectHorse123!",
    }
    assert (await client.post("/api/auth/login", json=login)).status_code == 401
    assert (
        await client.post("/api/auth/login", json=login | {"password": "NewPassword123!"})
    ).status_code == 200


async def test_free_plan_active_job_limit(client):
    admin, _ = await signup(client, "free-plan")
    for _ in range(3):
        assert (await client.post("/api/jobs", headers=admin, json=JOB)).status_code == 201
    assert (await client.post("/api/jobs", headers=admin, json=JOB)).status_code == 403
    draft = await client.post("/api/jobs", headers=admin, json=JOB | {"status": "draft"})
    assert draft.status_code == 201
    assert (
        await client.put("/api/jobs/" + draft.json()["id"], headers=admin, json=JOB)
    ).status_code == 403


async def test_cross_workspace_candidate_application(client):
    admin = await demo(client)
    job = (await client.get("/api/jobs", headers=admin)).json()[0]
    await signup(client, "candidate-co")
    headers, _ = await signup(
        client, "candidate-co", role="candidate", email="candidate@example.com"
    )
    assert (
        await client.post("/api/applications/" + job["id"] + "/apply", headers=headers)
    ).status_code == 404
    assert (await client.get("/api/jobs", headers=headers)).json() == []


async def test_logout_revokes_refresh(client):
    headers = await demo(client)
    token = client.cookies.get("refresh_token")
    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={token}"})
    ).status_code == 401


@pytest.mark.parametrize(
    "left,right,expected",
    [([1, 0], [1, 0], 1), ([1, 0], [0, 1], 0), ([0, 0], [0, 0], 0), ([], [], 0), ([1], [1, 0], 0)],
)
def test_cosine_similarity(left, right, expected):
    assert cosine_similarity(left, right) == expected


async def test_api_key_lifecycle_scopes_and_super_admin(client):
    recruiter = await demo(client)
    candidate = await demo(client, "candidate")
    created = await client.post(
        "/api/api-keys", headers=recruiter, json={"name": "ci-reader", "scopes": ["jobs:read"]}
    )
    assert created.status_code == 201, created.text
    raw = created.json()["key"]
    assert raw.startswith("sk_")
    listed = (await client.get("/api/api-keys", headers=recruiter)).json()
    assert raw not in str(listed)
    assert listed[0]["key_preview"].startswith("sk_")
    key_headers = {"Authorization": f"Bearer {raw}"}
    assert (await client.get("/api/jobs", headers=key_headers)).status_code == 200
    assert (await client.post("/api/jobs", headers=key_headers, json=JOB)).status_code == 403
    assert (
        await client.post(
            "/api/api-keys", headers=candidate, json={"name": "nope", "scopes": ["*"]}
        )
    ).status_code == 403
    assert (await client.get("/api/admin/tenants", headers=recruiter)).status_code == 403
    headers, _ = await signup(client, "ops-console")
    from sqlalchemy import select
    from app.core.database import Session
    from app.models.entities import User

    async with Session() as db:
        user = await db.scalar(select(User).where(User.email == "admin@example.com"))
        user.role = "super_admin"
        await db.commit()
    tenants = await client.get("/api/admin/tenants", headers=headers)
    assert tenants.status_code == 200, tenants.text
    assert len(tenants.json()) >= 2
    acme = next(row for row in tenants.json() if row["slug"] == "acme")
    patched = await client.patch(
        f"/api/admin/tenants/{acme['id']}/plan", headers=headers, json={"plan": "Enterprise"}
    )
    assert patched.status_code == 200
    assert patched.json()["plan"] == "Enterprise"


async def test_interview_websocket_streams_a_demo_question(client):
    import asyncio
    from starlette.testclient import TestClient
    from app.main import app as asgi_app

    candidate = await demo(client, "candidate")
    application = (await client.get("/api/applications", headers=candidate)).json()[0]
    start = await client.post(
        "/api/interviews/start", headers=candidate, json={"application_id": application["id"]}
    )
    assert start.status_code == 201, start.text
    token = candidate["Authorization"].split(" ", 1)[1]
    interview_id = start.json()["id"]

    def exchange():
        test_client = TestClient(asgi_app)
        with test_client.websocket_connect(
            f"/api/interviews/{interview_id}/stream?access_token={token}"
        ) as socket:
            socket.send_json(
                {
                    "answer": "I interviewed customers, evaluated alternatives, worked with engineering, and measured the results of a successful product release.",
                    "expected_count": 1,
                }
            )
            messages = []
            while True:
                payload = socket.receive_json()
                messages.append(payload)
                if payload.get("type") in {"done", "error"}:
                    break
            return messages

    messages = await asyncio.to_thread(exchange)
    assert messages, "websocket returned no messages"
    assert any(item.get("type") == "token" and item.get("text") for item in messages), messages
    done = messages[-1]
    assert done["type"] == "done"
    assert done["interview"]["status"] == "in_progress"
    assert len(done["interview"]["transcript_json"]) == 3


async def test_metrics_endpoint_is_public(client):
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text or "python_" in response.text


def test_qdrant_match_never_returns_another_tenant_resume():
    from app.ai.vectors import (
        ensure_collections,
        reset_client,
        search_resumes,
        upsert_resume_vector,
    )

    reset_client()
    ensure_collections()
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    vector_a = [0.05] * 1536
    vector_b = [0.95] * 1536
    vector_a[0] = 1.0
    vector_b[1] = 1.0
    upsert_resume_vector(tenant_a, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "user-a", vector_a)
    upsert_resume_vector(tenant_b, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "user-b", vector_b)
    hits = search_resumes(tenant_a, vector_b, limit=20)
    payloads = [hit.payload or {} for hit in hits]
    assert all(item.get("tenant_id") == tenant_a for item in payloads)
    assert all(item.get("resume_id") != "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" for item in payloads)
    own = search_resumes(tenant_a, vector_a, limit=5)
    assert own and own[0].payload["resume_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

"""Fictional, reproducible fixtures, only enabled by DEMO_MODE."""

import random
from datetime import timedelta
from sqlalchemy import select
from app.core.database import Session, scope_db
from app.core.security import hash_password
from app.models.entities import Tenant, User, Job, Resume, Application, Interview, AuditLog, now


async def seed_demo():
    rng = random.Random(42)
    async with Session() as db:
        if await db.scalar(select(Tenant.id).where(Tenant.slug == "acme")):
            return
        tenant = Tenant(name="Acme Studio", slug="acme", plan="Pro")
        db.add(tenant)
        await db.flush()
        await scope_db(db, tenant.id)
        password = hash_password("DemoPass2026!")
        admin = User(
            tenant_id=tenant.id,
            name="Alex Morgan",
            email="alex@acme.design",
            hashed_password=password,
            role="tenant_admin",
            is_verified=True,
        )
        db.add(admin)
        db.add(
            User(
                tenant_id=tenant.id,
                name="Jamie Wilson",
                email="jamie@acme.design",
                hashed_password=password,
                role="recruiter",
                is_verified=True,
            )
        )
        specs = [
            (
                "Senior Product Designer",
                "Design",
                ["Figma", "User research", "Design systems", "Prototyping"],
                "$120k – $160k",
                "San Francisco, CA",
            ),
            (
                "Frontend Developer",
                "Engineering",
                ["React", "TypeScript", "CSS", "Git"],
                "$110k – $150k",
                "Remote",
            ),
            (
                "Product Manager",
                "Product",
                ["Product strategy", "Analytics", "Agile", "Leadership"],
                "$130k – $170k",
                "New York, NY",
            ),
            (
                "Backend Engineer",
                "Engineering",
                ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "$120k – $165k",
                "Remote",
            ),
            (
                "UX Researcher",
                "Design",
                ["User research", "Analytics", "Communication"],
                "$100k – $140k",
                "Austin, TX",
            ),
            (
                "Growth Marketing Manager",
                "Marketing",
                ["Analytics", "Communication", "Product strategy"],
                "$100k – $135k",
                "Remote",
            ),
            (
                "DevOps Engineer",
                "Engineering",
                ["AWS", "Docker", "Python", "Git"],
                "$130k – $175k",
                "Remote",
            ),
            (
                "Brand Designer",
                "Design",
                ["Figma", "UI design", "Communication"],
                "$90k – $125k",
                "San Francisco, CA",
            ),
            (
                "Data Analyst",
                "Data",
                ["SQL", "Python", "Analytics"],
                "$100k – $145k",
                "New York, NY",
            ),
            (
                "Customer Success Lead",
                "Operations",
                ["Communication", "Leadership", "Analytics"],
                "$85k – $120k",
                "Remote",
            ),
            (
                "Full Stack Developer",
                "Engineering",
                ["React", "Node.js", "TypeScript", "PostgreSQL"],
                "$120k – $170k",
                "Remote",
            ),
            (
                "Design Engineer",
                "Design",
                ["React", "Figma", "CSS", "Design systems"],
                "$125k – $170k",
                "San Francisco, CA",
            ),
        ]
        jobs = []
        for i, (title, department, skills, salary, location) in enumerate(specs):
            job = Job(
                tenant_id=tenant.id,
                title=title,
                department=department,
                required_skills=skills,
                salary=salary,
                location=location,
                experience_level="Senior" if i % 3 == 0 else "Mid-level",
                description=f"We're looking for a thoughtful {title} to join Acme Studio and help build products people love. You will collaborate with a cross-functional team, own meaningful projects, and turn complex challenges into simple, useful experiences.\n\nWhat you'll do\n• Lead projects from discovery to delivery\n• Partner with design, engineering, and product teams\n• Share your work, give feedback, and help the team grow\n\nWhat you'll bring\n• Hands-on experience with {', '.join(skills)}\n• A portfolio of impactful work and a collaborative mindset\n• Clear communication and a curiosity for learning",
                created_at=now() - timedelta(days=3 + i),
            )
            db.add(job)
            jobs.append(job)
        await db.flush()
        names = [
            "Sarah Chen",
            "Michael Johnson",
            "Emily Davis",
            "David Kim",
            "Jessica Williams",
            "James Miller",
            "Olivia Brown",
            "Daniel Wilson",
            "Sophie Martin",
            "Ryan Patel",
            "Emma Thompson",
            "Lucas Garcia",
            "Ava Robinson",
            "Ethan Lee",
            "Mia Anderson",
            "Noah Taylor",
            "Isabella Thomas",
            "Liam Jackson",
            "Charlotte White",
            "Benjamin Harris",
            "Amelia Clark",
            "Mason Lewis",
            "Harper Walker",
            "Elijah Hall",
            "Evelyn Allen",
            "Oliver Young",
            "Abigail King",
            "Henry Wright",
            "Ella Scott",
            "Alexander Green",
            "Scarlett Adams",
            "William Baker",
            "Grace Nelson",
            "Jack Carter",
            "Chloe Mitchell",
            "Sebastian Perez",
            "Victoria Roberts",
            "Owen Turner",
            "Riley Phillips",
            "Gabriel Campbell",
            "Aria Parker",
            "Leo Evans",
            "Lily Edwards",
            "Samuel Collins",
            "Zoe Stewart",
            "Julian Morris",
            "Nora Rogers",
            "Caleb Reed",
        ]
        applications = []
        for i, name in enumerate(names):
            user = User(
                tenant_id=tenant.id,
                name=name,
                email=name.lower().replace(" ", ".") + "@example.com",
                hashed_password=password,
                role="candidate",
                is_verified=True,
            )
            db.add(user)
            await db.flush()
            primary = jobs[i % len(jobs)]
            resume = Resume(
                tenant_id=tenant.id,
                user_id=user.id,
                filename=name.replace(" ", "_") + "_Resume.pdf",
                parsed_json={
                    "name": name,
                    "skills": primary.required_skills + ["Communication", "Leadership"],
                    "experience": [
                        f"{3 + i % 6} years of experience in {primary.department.lower()}",
                        "Collaborated with cross-functional teams to launch customer-focused products",
                    ],
                    "education": ["Bachelor’s degree · Class of 2018"],
                    "summary": f"A curious and collaborative {primary.title.lower()} with a passion for creating meaningful product experiences.",
                },
            )
            db.add(resume)
            await db.flush()
            for k in range(3 if i < 40 else 2):
                job = jobs[(i + k * 3) % len(jobs)]
                status = (
                    ["Shortlisted", "Interview", "New", "Screening", "Shortlisted"][i]
                    if i < 5 and k == 0
                    else rng.choices(
                        ["New", "Screening", "Interview", "Shortlisted", "Hired", "Rejected"],
                        [27, 20, 18, 18, 7, 10],
                    )[0]
                )
                app = Application(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    resume_id=resume.id,
                    job_id=job.id,
                    match_score=98 - i * 2 if i < 5 and k == 0 else rng.randint(58, 89),
                    status=status,
                    created_at=now() - timedelta(days=rng.randrange(30), hours=rng.randrange(20)),
                )
                db.add(app)
                applications.append((app, user, job))
        await db.flush()
        for i, (app, user, job) in enumerate(applications[:24]):
            transcript = [
                {
                    "role": "assistant",
                    "content": f"Tell me about a project that demonstrates your fit for the {job.title} role.",
                },
                {
                    "role": "user",
                    "content": "I led a cross-functional initiative to simplify our onboarding experience. We started by interviewing twelve customers, identified the largest friction points, and tested three prototypes. I owned the interaction design and collaborated with engineering on implementation. The result was a 24% improvement in completion rate.",
                },
                {
                    "role": "assistant",
                    "content": "How did you decide which problems to prioritize?",
                },
                {
                    "role": "user",
                    "content": "We balanced customer impact, confidence in our evidence, and engineering effort. I facilitated a workshop to align the team, then ran a small experiment to validate the highest-priority hypothesis before committing to a larger build.",
                },
            ]
            card = {
                "overall_score": rng.randint(72, 96),
                "strengths": [
                    "Clear, structured communication",
                    "Evidence-based decision making",
                    "Strong cross-functional collaboration",
                ],
                "weaknesses": [
                    "Explore technical trade-offs in more depth",
                    "Add more examples of handling ambiguity",
                ],
                "recommendation": "Ready for recruiter review",
                "summary": f"{user.name} demonstrated a thoughtful approach to problem solving, with specific examples and measurable outcomes. A follow-up conversation could explore technical depth and collaboration in more detail.",
                "mode": "Demo fixture — not a real assessment",
            }
            db.add(
                Interview(
                    tenant_id=tenant.id,
                    application_id=app.id,
                    transcript_json=transcript,
                    scorecard_json=card,
                    state_json={},
                    status="completed",
                    started_at=now() - timedelta(days=i % 12, hours=2),
                    ended_at=now() - timedelta(days=i % 12, hours=1),
                )
            )
        for i, (action, details) in enumerate(
            [
                ("application.created", {"name": "Sarah Chen", "title": "Senior Product Designer"}),
                ("interview.completed", {"name": "Michael Johnson"}),
                ("job.created", {"title": "Frontend Developer"}),
                ("application.status_changed", {"name": "Emily Davis", "status": "Shortlisted"}),
            ]
        ):
            db.add(
                AuditLog(
                    tenant_id=tenant.id,
                    user_id=admin.id,
                    action=action,
                    details=details,
                    created_at=now() - timedelta(minutes=15 + i * 45),
                )
            )
        await db.commit()

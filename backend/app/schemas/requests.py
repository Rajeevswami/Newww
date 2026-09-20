from typing import Literal
from pydantic import BaseModel, Field, EmailStr, field_validator


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    workspace: str = Field(default="acme", pattern=r"^[a-z0-9-]{2,80}$")

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode()) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return value


class Signup(Login):
    name: str = Field(min_length=2, max_length=100)
    company: str = Field(default="", max_length=100)
    role: Literal["tenant_admin", "candidate"] = "tenant_admin"


class JobInput(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    department: str = Field(default="Engineering", max_length=100)
    description: str = Field(min_length=30, max_length=15000)
    required_skills: list[str] = Field(min_length=1, max_length=30)
    experience_level: Literal["Entry-level", "Mid-level", "Senior", "Lead"] = "Mid-level"
    location: str = Field(default="Remote", max_length=100)
    employment_type: Literal["Full-time", "Part-time", "Contract"] = "Full-time"
    salary: str = Field(default="", max_length=100)
    status: Literal["active", "draft", "closed"] = "active"

    @field_validator("required_skills")
    @classmethod
    def skills_valid(cls, skills):
        if any(not s.strip() or len(s) > 60 for s in skills):
            raise ValueError("Skills must be 1–60 characters")
        return list(dict.fromkeys(s.strip() for s in skills))


class StatusInput(BaseModel):
    status: Literal["New", "Screening", "Interview", "Shortlisted", "Hired", "Rejected"]


class InterviewInput(BaseModel):
    application_id: str


class AnswerInput(BaseModel):
    answer: str = Field(min_length=5, max_length=6000)
    expected_count: int = Field(ge=1, le=5)


class EmailInput(BaseModel):
    email: EmailStr
    workspace: str = Field(pattern=r"^[a-z0-9-]{2,80}$")


class TokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class ResetInput(TokenInput):
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode()) > 72:
            raise ValueError("Password too long")
        return value


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)

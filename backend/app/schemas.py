"""Request/response schemas shared across routers and the service layer.

Kept in one module (rather than co-located with routers) so the service layer
can type-hint against them without creating a router -> service -> router import
cycle.
"""

from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    username: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None


class AuthLoginIn(BaseModel):
    email: EmailStr
    password: str


class RealtimeIn(BaseModel):
    username: str
    mode: str  # persona | interview
    persona_id: str | None = None
    track: str | None = "sde"
    role: str | None = "SDE"
    focus: str | None = "dsa"
    difficulty: str | None = "medium"
    company_id: str | None = None
    company_name: str | None = None
    candidate_note: str | None = None
    hints_enabled: bool = True


class ChatIn(BaseModel):
    username: str
    mode: str
    persona_id: str | None = None
    track: str | None = "sde"
    role: str | None = "SDE"
    focus: str | None = "dsa"
    difficulty: str | None = "medium"
    company_id: str | None = None
    company_name: str | None = None
    candidate_note: str | None = None
    hints_enabled: bool = True
    session_id: str | None = None
    use_resume: bool = False
    job_description: str | None = None
    history: list[dict] = []  # [{role, text}]
    message: str


class SaveConversationIn(BaseModel):
    username: str
    mode: str
    persona_id: str | None = None
    title: str | None = None
    transcript: list[dict] = []


class GradeIn(BaseModel):
    username: str
    track: str | None = "sde"
    role: str = "SDE"
    focus: str = "dsa"
    difficulty: str = "medium"
    company_id: str | None = None
    company_name: str | None = None
    transcript: list[dict] = []
    session_id: str | None = None


class CoachingIn(BaseModel):
    role: str = "SDE"
    track: str | None = "sde"
    focus: str = "dsa"
    difficulty: str = "medium"
    transcript: list[dict] = []
    report: dict | None = None
    session_id: str | None = None

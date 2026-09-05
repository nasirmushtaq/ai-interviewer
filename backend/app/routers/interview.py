"""Interview interaction endpoints: realtime voice sessions, the text-chat
fallback, grading and post-interview coaching. All orchestration lives in
:mod:`app.interview_service`; these handlers only adapt HTTP <-> service calls."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import auth, interview_service
from .. import db as database
from ..config import settings
from ..ratelimit import limiter
from ..schemas import ChatIn, CoachingIn, GradeIn, RealtimeIn

router = APIRouter(tags=["interview"])


@router.post("/api/realtime/session")
async def realtime_session(body: RealtimeIn, db: Session = Depends(database.get_db)):
    return await interview_service.create_realtime_session(db, body)


@router.post("/api/chat")
@limiter.limit(settings.RATE_LIMIT_LLM)
def chat(
    request: Request,
    body: ChatIn,
    db: Session = Depends(database.get_db),
    authed: database.User | None = Depends(auth.optional_user),
):
    return {"reply": interview_service.generate_chat_reply(db, body, authed)}


@router.post("/api/interview/grade")
@limiter.limit(settings.RATE_LIMIT_LLM)
def grade(
    request: Request,
    body: GradeIn,
    db: Session = Depends(database.get_db),
    authed: database.User | None = Depends(auth.optional_user),
):
    return interview_service.grade_session(db, body, authed)


@router.post("/api/interview/coaching")
@limiter.limit(settings.RATE_LIMIT_LLM)
def coaching(request: Request, body: CoachingIn, db: Session = Depends(database.get_db)):
    """Post-interview coaching: model answers for weak questions, key concepts to
    study, and a recommended next drill. Generated on demand."""
    return interview_service.generate_coaching(db, body)

"""Persist a persona conversation and extract long-term memories from it."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import db as database
from .. import interview_service
from ..dependencies import get_or_create_user
from ..schemas import SaveConversationIn

router = APIRouter(tags=["conversations"])


@router.post("/api/conversations")
def save_conversation(body: SaveConversationIn, db: Session = Depends(database.get_db)):
    user = get_or_create_user(db, body.username)
    return interview_service.save_conversation(db, body, user)

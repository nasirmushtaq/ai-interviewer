"""Resume endpoints: upload/parse, fetch summary and clear."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import db as database
from .. import resume as resume_mod
from ..dependencies import require_user

router = APIRouter(prefix="/api/resume", tags=["resume"])

_MAX_RESUME_BYTES = 5 * 1024 * 1024


@router.post("/upload")
async def resume_upload(
    file: UploadFile = File(...),
    user: database.User = Depends(require_user("Log in to upload your resume.")),
    db: Session = Depends(database.get_db),
):
    data = await file.read()
    if len(data) > _MAX_RESUME_BYTES:
        raise HTTPException(413, "Resume too large (max 5MB).")
    text = resume_mod.extract_text(file.filename or "", data)
    if not text.strip():
        raise HTTPException(400, "Could not read any text from that file. Try a PDF or DOCX.")
    summary = resume_mod.summarize(text)
    user.resume_text = text[:20000]
    user.resume_summary = summary
    db.commit()
    return {"summary": summary, "chars": len(text)}


@router.get("")
def resume_get(user: database.User = Depends(require_user("Log in to view your resume."))):
    return {
        "has_resume": bool(user.resume_summary),
        "summary": user.resume_summary or "",
    }


@router.delete("")
def resume_clear(
    user: database.User = Depends(require_user("Log in first.")),
    db: Session = Depends(database.get_db),
):
    user.resume_text = None
    user.resume_summary = None
    db.commit()
    return {"ok": True}

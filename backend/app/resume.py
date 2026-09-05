"""Resume parsing (PDF/DOCX/text) + an AI-extracted profile summary used to
tailor interview questions to the candidate's real experience."""

import io

from . import openai_service as ai


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _from_pdf(data)
    if name.endswith(".docx"):
        return _from_docx(data)
    # Fallback: treat as plain text.
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()


def _from_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()


SUMMARY_SYSTEM = (
    "You extract a concise interview-prep profile from a candidate's resume. "
    "Return a short plain-text summary (no JSON) with: years of experience, key "
    "skills/technologies, notable projects/systems they built, domains, and 2-3 "
    "areas an interviewer should probe based on their background. Keep it under "
    "180 words. If the text is not a resume, say so briefly."
)


def summarize(resume_text: str) -> str:
    if not resume_text.strip():
        return ""
    if not ai.has_key():
        return "(resume saved; AI summary unavailable — no API key)"
    try:
        return ai.chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": resume_text[:8000]},
            ]
        ).strip()
    except Exception as e:
        return f"(summary failed: {e})"


def interview_resume_block(resume_summary: str | None, job_description: str | None) -> str:
    """Prompt fragment injected into the interviewer so it tailors questions."""
    if not resume_summary and not job_description:
        return ""
    parts = ["\n\nCANDIDATE CONTEXT — tailor the interview to this:"]
    if resume_summary:
        parts.append(f"Resume profile:\n{resume_summary}")
    if job_description:
        parts.append(f"Target role / job description:\n{job_description[:1500]}")
    parts.append(
        "Ask some questions that connect to the candidate's actual experience and "
        "projects, and to the requirements of the target role. Probe claims on "
        "their resume ('you built X — walk me through the hardest part'). Keep it "
        "realistic; don't just read the resume back to them."
    )
    return "\n".join(parts)

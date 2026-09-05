from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from .config import settings


def _normalized_db_url(url: str) -> str:
    """PaaS providers often hand out `postgres://...`; SQLAlchemy 2 + psycopg3
    wants `postgresql+psycopg://...`. Normalize so any of these 'just work'."""
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DB_URL = _normalized_db_url(settings.DATABASE_URL)
_is_sqlite = DB_URL.startswith("sqlite")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # Optional real-auth fields (nullable so legacy/guest users still work).
    email: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Billing: interview credits bought, and how many interviews used (free quota).
    interview_credits: Mapped[int] = mapped_column(Integer, default=0)
    interviews_used: Mapped[int] = mapped_column(Integer, default=0)
    # Resume-driven interviews: parsed resume text + AI-extracted profile summary.
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    memories: Mapped[list["Memory"]] = relationship(back_populates="user")
    reports: Mapped[list["InterviewReport"]] = relationship(back_populates="user")


class Purchase(Base):
    """A credit-pack order. Created when a user starts checkout; marked 'paid'
    ONLY by a signature-verified provider webhook (the source of truth), which
    then grants credits. Clients cannot mark it paid."""

    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # razorpay | cashfree
    provider_order_id: Mapped[str] = mapped_column(String(120), index=True)
    pack_id: Mapped[str] = mapped_column(String(40))
    credits: Mapped[int] = mapped_column(Integer)  # credits this pack grants
    amount: Mapped[int] = mapped_column(Integer)  # in paise (smallest unit)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    status: Mapped[str] = mapped_column(String(20), default="created")  # created|paid|failed
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship()


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(30))  # "persona" | "interview"
    persona_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="Conversation")
    transcript: Mapped[list] = mapped_column(JSON, default=list)  # [{role, text}]
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="conversations")


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    persona_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fact: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="memories")


class Session(Base):
    """A live interview/persona session that a web OR native client drives,
    and that the media service attaches camera/screen observations to."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # uuid hex
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(30))  # "persona" | "interview"
    persona_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    track: Mapped[str | None] = mapped_column(String(60), nullable=True)
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    focus: Mapped[str | None] = mapped_column(String(80), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(40), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|ended
    hints_enabled: Mapped[bool] = mapped_column(default=True)
    transcript: Mapped[list] = mapped_column(JSON, default=list)  # [{role, text}]
    # Coding round: the active problem and the latest submission result.
    problem: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    code_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Design round: latest whiteboard/diagram snapshot summary + image handled via
    # observations; final diagram data URL kept for the report.
    diagram_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured architecture graph (components + edges) from the whiteboard, and
    # the AI's latest structured reading of it (for adaptive questioning).
    diagram_model: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diagram_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Comprehensive-interview coverage state (checklist items + statuses).
    coverage_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship()
    observations: Mapped[list["Observation"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    hints: Mapped[list["Hint"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Hint(Base):
    """One hint the candidate requested during a session. Tiered and score-costing."""

    __tablename__ = "hints"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1 nudge..3 partial
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    question_context: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship(back_populates="hints")


class Observation(Base):
    """One AI-vision reading of a sampled camera and/or screen frame."""

    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # "camera" | "screen"
    note: Mapped[str] = mapped_column(Text)  # what the AI saw
    flags: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["looking_away"]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship(back_populates="observations")


class InterviewReport(Base):
    __tablename__ = "interview_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(80))
    track: Mapped[str | None] = mapped_column(String(60), nullable=True)
    focus: Mapped[str] = mapped_column(String(80))
    difficulty: Mapped[str] = mapped_column(String(40))
    company: Mapped[str | None] = mapped_column(String(120), nullable=True)
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    hint_penalty: Mapped[int] = mapped_column(Integer, default=0)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    improvements: Mapped[list] = mapped_column(JSON, default=list)
    rubric: Mapped[list] = mapped_column(JSON, default=list, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reports")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

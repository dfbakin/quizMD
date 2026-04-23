import asyncio
import datetime as dt
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, quizzes, groups, assignments, students

logger = logging.getLogger(__name__)

# How often the background sweep wakes up. Kept conservative because the work
# per tick is bounded by `expired AND submitted_at IS NULL`, which is small.
SWEEP_INTERVAL_SECONDS = int(os.environ.get("ATTEMPT_SWEEP_INTERVAL_SECONDS", "30"))


def sweep_expired_attempts_once(db_factory=None, now: dt.datetime | None = None) -> int:
    """Auto-grade every attempt whose snapshot deadline has passed.

    Returns the number of attempts that were graded. Pure function over a
    DB session factory to keep it trivially unit-testable.
    """
    from app.database import SessionLocal
    from app.models import Attempt
    from app.api.students import _auto_grade_expired

    factory = db_factory or SessionLocal
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    db = factory()
    graded = 0
    try:
        expired = (
            db.query(Attempt)
            .filter(
                Attempt.submitted_at.is_(None),
                Attempt.deadline_at < now,
            )
            .all()
        )
        for att in expired:
            try:
                _auto_grade_expired(att, db, now=now)
                graded += 1
            except Exception:
                logger.exception("sweep: auto_grade failed for attempt %s", att.id)
                db.rollback()
        if graded:
            logger.info("sweep: auto-graded %d expired attempt(s)", graded)
    finally:
        db.close()
    return graded


async def _sweep_expired_attempts_loop() -> None:
    """Periodically auto-grade attempts whose snapshot deadline has passed.

    Without this, expired-but-unsubmitted attempts would only get graded the
    next time *someone* hits an endpoint that touches them. With it, the
    server is the sole authority for "this attempt is over now."
    """
    while True:
        try:
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
            await asyncio.to_thread(sweep_expired_attempts_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sweep: unexpected error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import engine, Base
    import app.models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)

    sweep_task: asyncio.Task | None = None
    if SWEEP_INTERVAL_SECONDS > 0:
        sweep_task = asyncio.create_task(_sweep_expired_attempts_loop())

    try:
        yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()
            try:
                await sweep_task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Quiz Core", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(groups.router)
app.include_router(assignments.router)
app.include_router(students.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

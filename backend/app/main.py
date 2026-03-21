from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, quizzes, groups, assignments, students


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import engine, Base
    import app.models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    yield


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

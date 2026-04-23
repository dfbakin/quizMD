from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Teacher, Quiz
from app.api.deps import get_current_teacher
from app.services.quiz_importer import import_quiz, reimport_quiz
from app.schemas.schemas import QuizSummary, QuizDetail, QuestionOutTeacher

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


def _quiz_to_summary(q: Quiz) -> QuizSummary:
    return QuizSummary(
        id=q.id,
        title=q.title,
        time_limit_minutes=q.time_limit_minutes,
        shuffle_questions=q.shuffle_questions,
        shuffle_answers=q.shuffle_answers,
        question_count=len(q.questions),
        created_at=q.created_at,
    )


def _quiz_to_detail(q: Quiz) -> QuizDetail:
    return QuizDetail(
        id=q.id,
        title=q.title,
        time_limit_minutes=q.time_limit_minutes,
        shuffle_questions=q.shuffle_questions,
        shuffle_answers=q.shuffle_answers,
        question_count=len(q.questions),
        created_at=q.created_at,
        source_md=q.source_md,
        questions=[QuestionOutTeacher.model_validate(qn) for qn in q.questions],
    )


@router.post("/import", response_model=QuizDetail, status_code=201)
async def import_quiz_endpoint(
    file: UploadFile = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    try:
        quiz = import_quiz(content, teacher.id, db)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return _quiz_to_detail(quiz)


@router.get("", response_model=list[QuizSummary])
def list_quizzes(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    quizzes = db.query(Quiz).filter(Quiz.teacher_id == teacher.id).order_by(Quiz.created_at.desc()).all()
    return [_quiz_to_summary(q) for q in quizzes]


@router.get("/{quiz_id}", response_model=QuizDetail)
def get_quiz(
    quiz_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    return _quiz_to_detail(quiz)


@router.post("/{quiz_id}/reimport", response_model=QuizDetail)
async def reimport_quiz_endpoint(
    quiz_id: int,
    file: UploadFile = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    content = (await file.read()).decode("utf-8")
    try:
        updated = reimport_quiz(quiz_id, content, db)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return _quiz_to_detail(updated)


@router.delete("/{quiz_id}", status_code=204)
def delete_quiz(
    quiz_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    db.delete(quiz)
    db.commit()

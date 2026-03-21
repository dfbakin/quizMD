"""Orchestrates parsing a .quiz.md string and persisting it to the database."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Quiz, Question, Option
from app.parser import parse_quiz


def import_quiz(source_md: str, teacher_id: int, db: Session) -> Quiz:
    parsed = parse_quiz(source_md)

    quiz = Quiz(
        title=parsed.title,
        source_md=parsed.source_md,
        time_limit_minutes=parsed.time_limit,
        shuffle_questions=parsed.shuffle_questions,
        shuffle_answers=parsed.shuffle_answers,
        teacher_id=teacher_id,
    )
    db.add(quiz)
    db.flush()

    for pq in parsed.questions:
        question = Question(
            quiz_id=quiz.id,
            order_index=pq.order_index,
            q_type=pq.q_type,
            title=pq.title,
            body_md=pq.body_md,
            explanation_md=pq.explanation_md,
            accepted_answers=pq.accepted_answers if pq.accepted_answers else None,
            points=pq.points,
        )
        db.add(question)
        db.flush()

        for po in pq.options:
            option = Option(
                question_id=question.id,
                order_index=po.order_index,
                text_md=po.text_md,
                is_correct=po.is_correct,
            )
            db.add(option)

    db.commit()
    db.refresh(quiz)
    return quiz


def reimport_quiz(quiz_id: int, source_md: str, db: Session) -> Quiz:
    """Re-import replaces all questions atomically."""
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise ValueError(f"Quiz {quiz_id} not found")

    parsed = parse_quiz(source_md)

    for q in list(quiz.questions):
        db.delete(q)
    db.flush()

    quiz.title = parsed.title
    quiz.source_md = parsed.source_md
    quiz.time_limit_minutes = parsed.time_limit
    quiz.shuffle_questions = parsed.shuffle_questions
    quiz.shuffle_answers = parsed.shuffle_answers

    for pq in parsed.questions:
        question = Question(
            quiz_id=quiz.id,
            order_index=pq.order_index,
            q_type=pq.q_type,
            title=pq.title,
            body_md=pq.body_md,
            explanation_md=pq.explanation_md,
            accepted_answers=pq.accepted_answers if pq.accepted_answers else None,
            points=pq.points,
        )
        db.add(question)
        db.flush()

        for po in pq.options:
            option = Option(
                question_id=question.id,
                order_index=po.order_index,
                text_md=po.text_md,
                is_correct=po.is_correct,
            )
            db.add(option)

    db.commit()
    db.refresh(quiz)
    return quiz

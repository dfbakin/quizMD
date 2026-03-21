"""Tests for database models and quiz importer round-trip."""

import pytest
from sqlalchemy.orm import Session

from tests.conftest import (
    create_test_teacher,
    create_test_group,
    create_test_student,
    create_test_quiz,
    create_test_assignment,
    SAMPLE_QUIZ_MD,
)
from app.services.quiz_importer import import_quiz, reimport_quiz


class TestModelCreation:
    def test_create_teacher(self, db: Session):
        t = create_test_teacher(db)
        assert t.id is not None
        assert t.username == "teacher1"

    def test_create_group(self, db: Session):
        t = create_test_teacher(db)
        g = create_test_group(db, t.id)
        assert g.id is not None
        assert g.teacher_id == t.id

    def test_create_student(self, db: Session):
        t = create_test_teacher(db)
        g = create_test_group(db, t.id)
        s = create_test_student(db, g.id)
        assert s.id is not None
        assert s.group_id == g.id


class TestQuizImportRoundTrip:
    def test_import_creates_quiz(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        assert quiz.id is not None
        assert quiz.title == "Тестовый квиз"
        assert quiz.time_limit_minutes == 10

    def test_import_creates_questions(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        assert len(quiz.questions) == 3

    def test_question_types_persisted(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        types = [q.q_type for q in quiz.questions]
        assert types == ["single", "multiple", "short"]

    def test_options_persisted(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        q1 = quiz.questions[0]
        assert len(q1.options) == 3
        correct = [o for o in q1.options if o.is_correct]
        assert len(correct) == 1
        assert "B" in correct[0].text_md

    def test_short_answer_persisted(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        q3 = quiz.questions[2]
        assert q3.accepted_answers == ["42"]

    def test_explanation_persisted(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        assert quiz.questions[0].explanation_md == "Пояснение."
        assert quiz.questions[1].explanation_md is None
        assert quiz.questions[2].explanation_md == "42."

    def test_source_md_stored(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        assert quiz.source_md == SAMPLE_QUIZ_MD


class TestReimport:
    def test_reimport_replaces_questions(self, db: Session):
        t = create_test_teacher(db)
        quiz = import_quiz(SAMPLE_QUIZ_MD, t.id, db)
        assert len(quiz.questions) == 3

        updated_md = SAMPLE_QUIZ_MD.replace("Тестовый квиз", "Обновлённый квиз")
        reimported = reimport_quiz(quiz.id, updated_md, db)

        assert reimported.id == quiz.id
        assert reimported.title == "Обновлённый квиз"
        assert len(reimported.questions) == 3
        assert reimported.questions[0].quiz_id == quiz.id

    def test_reimport_nonexistent_raises(self, db: Session):
        with pytest.raises(ValueError, match="not found"):
            reimport_quiz(9999, SAMPLE_QUIZ_MD, db)


class TestAssignment:
    def test_create_assignment(self, db: Session):
        t = create_test_teacher(db)
        g = create_test_group(db, t.id)
        quiz = create_test_quiz(db, t.id)
        a = create_test_assignment(db, quiz.id, g.id)
        assert a.id is not None
        assert a.quiz_id == quiz.id
        assert a.group_id == g.id
        assert a.results_visible is False

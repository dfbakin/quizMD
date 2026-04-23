#!/usr/bin/env python3
"""Seed the database with test data for local development.

Run from the project root:
    python scripts/seed_data.py

Requires DATABASE_URL env var or backend/.env to be set.
"""
import datetime as dt
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

# Support both local (project_root/backend/app) and Docker (/app/app) layouts
backend_dir = project_root / "backend"
if backend_dir.exists():
    sys.path.insert(0, str(backend_dir))
    os.chdir(backend_dir)
else:
    sys.path.insert(0, str(project_root))
    os.chdir(project_root)

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./quiz.db"

from app.database import engine, Base, SessionLocal
from app.models import Teacher, Student, Group, Assignment
from app.auth.passwords import hash_password
from app.services.quiz_importer import import_quiz

import app.models  # noqa: F401


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(Teacher).filter(Teacher.username == "teacher").first():
        print("Seed data already exists, skipping.")
        db.close()
        return

    teacher = Teacher(
        username="teacher",
        password_hash=hash_password("teacher123"),
        display_name="Преподаватель",
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    print(f"Created teacher: teacher / teacher123")

    group_a = Group(name="11А", teacher_id=teacher.id)
    group_b = Group(name="11Б", teacher_id=teacher.id)
    db.add_all([group_a, group_b])
    db.commit()
    db.refresh(group_a)
    db.refresh(group_b)
    print(f"Created groups: 11А (id={group_a.id}), 11Б (id={group_b.id})")

    students = []
    for i in range(1, 21):
        g = group_a if i <= 10 else group_b
        s = Student(
            username=f"student{i:02d}",
            password_hash=hash_password("quiz2026"),
            display_name=f"Ученик {i:02d}",
            group_id=g.id,
        )
        students.append(s)
    db.add_all(students)
    db.commit()
    print(f"Created 20 students (student01..student20 / quiz2026)")

    quiz_path = project_root / "quizzes" / "test_example.quiz.md"
    if quiz_path.exists():
        source = quiz_path.read_text(encoding="utf-8")
        quiz = import_quiz(source, teacher.id, db)
        print(f"Imported quiz: '{quiz.title}' ({len(quiz.questions)} questions)")

        import secrets
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        duration = 24 * 60
        start_window = 24 * 60
        assignment = Assignment(
            quiz_id=quiz.id,
            group_id=group_a.id,
            starts_at=now - dt.timedelta(minutes=5),
            ends_at=now - dt.timedelta(minutes=5) + dt.timedelta(minutes=start_window),
            start_window_minutes=start_window,
            duration_minutes=duration,
            results_visible=False,
            share_code=secrets.token_urlsafe(6),
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        print(f"Created assignment: quiz -> 11А, active for 24h (id={assignment.id})")
    else:
        print(f"Quiz file not found at {quiz_path}, skipping quiz import.")

    db.close()
    print("\nSeed complete! You can now:")
    print("  1. Log in as teacher:  teacher / teacher123")
    print("  2. Log in as student:  student01 / quiz2026")


if __name__ == "__main__":
    main()

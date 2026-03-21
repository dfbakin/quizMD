"""Auto-grading logic for quiz answers.

Scoring rules:
  - single choice: correct if exactly the right option is selected
  - multiple choice: all-or-nothing (must select exactly the correct set)
  - short answer: exact match against accepted answers (whitespace-stripped)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GradeResult:
    is_correct: bool
    points_awarded: int


def grade_answer(
    *,
    q_type: str,
    selected_option_ids: list[int] | None,
    correct_option_ids: list[int] | None,
    text_answer: str | None,
    accepted_answers: list[str] | None,
    points: int,
) -> GradeResult:
    if q_type in ("single", "multiple"):
        return _grade_choice(selected_option_ids, correct_option_ids, points)
    if q_type == "short":
        return _grade_short(text_answer, accepted_answers, points)
    return GradeResult(is_correct=False, points_awarded=0)


def _grade_choice(
    selected: list[int] | None,
    correct: list[int] | None,
    points: int,
) -> GradeResult:
    if not selected or not correct:
        return GradeResult(is_correct=False, points_awarded=0)
    is_correct = set(selected) == set(correct)
    return GradeResult(is_correct=is_correct, points_awarded=points if is_correct else 0)


def _grade_short(
    text_answer: str | None,
    accepted: list[str] | None,
    points: int,
) -> GradeResult:
    if not text_answer or not text_answer.strip() or not accepted:
        return GradeResult(is_correct=False, points_awarded=0)
    cleaned = text_answer.strip()
    is_correct = cleaned in accepted
    return GradeResult(is_correct=is_correct, points_awarded=points if is_correct else 0)

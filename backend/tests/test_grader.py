"""TDD tests for the grading service. Written BEFORE the implementation."""

import pytest

from app.services.grader import grade_answer


class TestSingleChoice:
    def test_correct(self):
        result = grade_answer(
            q_type="single",
            selected_option_ids=[2],
            correct_option_ids=[2],
            text_answer=None,
            accepted_answers=None,
            points=1,
        )
        assert result.is_correct is True
        assert result.points_awarded == 1

    def test_incorrect(self):
        result = grade_answer(
            q_type="single",
            selected_option_ids=[1],
            correct_option_ids=[2],
            text_answer=None,
            accepted_answers=None,
            points=1,
        )
        assert result.is_correct is False
        assert result.points_awarded == 0

    def test_no_answer(self):
        result = grade_answer(
            q_type="single",
            selected_option_ids=None,
            correct_option_ids=[2],
            text_answer=None,
            accepted_answers=None,
            points=1,
        )
        assert result.is_correct is False
        assert result.points_awarded == 0

    def test_custom_points(self):
        result = grade_answer(
            q_type="single",
            selected_option_ids=[5],
            correct_option_ids=[5],
            text_answer=None,
            accepted_answers=None,
            points=3,
        )
        assert result.points_awarded == 3


class TestMultipleChoice:
    def test_all_correct(self):
        result = grade_answer(
            q_type="multiple",
            selected_option_ids=[1, 3],
            correct_option_ids=[1, 3],
            text_answer=None,
            accepted_answers=None,
            points=2,
        )
        assert result.is_correct is True
        assert result.points_awarded == 2

    def test_partial_is_wrong(self):
        result = grade_answer(
            q_type="multiple",
            selected_option_ids=[1],
            correct_option_ids=[1, 3],
            text_answer=None,
            accepted_answers=None,
            points=2,
        )
        assert result.is_correct is False
        assert result.points_awarded == 0

    def test_extra_selection_is_wrong(self):
        result = grade_answer(
            q_type="multiple",
            selected_option_ids=[1, 2, 3],
            correct_option_ids=[1, 3],
            text_answer=None,
            accepted_answers=None,
            points=2,
        )
        assert result.is_correct is False
        assert result.points_awarded == 0

    def test_order_independent(self):
        result = grade_answer(
            q_type="multiple",
            selected_option_ids=[3, 1],
            correct_option_ids=[1, 3],
            text_answer=None,
            accepted_answers=None,
            points=1,
        )
        assert result.is_correct is True

    def test_no_answer(self):
        result = grade_answer(
            q_type="multiple",
            selected_option_ids=None,
            correct_option_ids=[1, 3],
            text_answer=None,
            accepted_answers=None,
            points=1,
        )
        assert result.is_correct is False


class TestShortAnswer:
    def test_exact_match(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer="60",
            accepted_answers=["60"],
            points=1,
        )
        assert result.is_correct is True

    def test_wrong_answer(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer="61",
            accepted_answers=["60"],
            points=1,
        )
        assert result.is_correct is False

    def test_multiple_accepted(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer="москва",
            accepted_answers=["Москва", "москва"],
            points=1,
        )
        assert result.is_correct is True

    def test_whitespace_stripped(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer="  60  ",
            accepted_answers=["60"],
            points=1,
        )
        assert result.is_correct is True

    def test_no_answer(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer=None,
            accepted_answers=["60"],
            points=1,
        )
        assert result.is_correct is False

    def test_empty_string_answer(self):
        result = grade_answer(
            q_type="short",
            selected_option_ids=None,
            correct_option_ids=None,
            text_answer="",
            accepted_answers=["60"],
            points=1,
        )
        assert result.is_correct is False

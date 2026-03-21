"""TDD tests for the .quiz.md parser.

Written BEFORE the implementation. These define the parser's contract.
"""

import pytest

from app.parser import parse_quiz, ParsedQuiz, ParsedQuestion, ParsedOption


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SINGLE_CHOICE_QUIZ = """\
---
title: "Тест: одиночный выбор"
time_limit: 15
shuffle_questions: true
shuffle_answers: false
---

### Простой вопрос

Какой ответ правильный?

- [ ] Неправильный A
- [x] Правильный B
- [ ] Неправильный C

> Пояснение к ответу.
"""

MULTIPLE_CHOICE_QUIZ = """\
---
title: "Тест: множественный выбор"
---

### Множественный выбор

Выберите все верные варианты:

- [x] Верный 1
- [ ] Неверный 2
- [x] Верный 3
- [ ] Неверный 4

> Пояснение: 1 и 3 верны.
"""

SHORT_ANSWER_QUIZ = """\
---
title: "Тест: краткий ответ"
---

### Краткий ответ

Сколько будет 2 + 2?

answer: 4

> Пояснение: 2 + 2 = 4.
"""

SHORT_ANSWER_MULTIPLE_ACCEPTED = """\
---
title: "Тест: несколько принимаемых ответов"
---

### Разные формы ответа

Как называется столица России?

answer: Москва, москва
"""

MIXED_QUIZ = """\
---
title: "Смешанный тест"
time_limit: 30
shuffle_questions: true
shuffle_answers: true
---

### Вопрос 1 (одиночный)

Один правильный:

- [ ] A
- [x] B
- [ ] C

> Пояснение 1.

---

### Вопрос 2 (множественный)

Несколько правильных:

- [x] X
- [x] Y
- [ ] Z

---

### Вопрос 3 (краткий)

Напишите число:

answer: 42

> Ответ 42.
"""

CODE_BLOCK_QUIZ = """\
---
title: "Тест с кодом"
---

### Вопрос с кодом

Что выведет программа?

```cpp
#include <iostream>
int main() {
    std::cout << 42;
    return 0;
}
```

- [ ] Ничего
- [x] 42
- [ ] Ошибку компиляции

> Программа выведет 42.
"""

LATEX_QUIZ = """\
---
title: "Тест с формулами"
---

### Формулы в вопросе

Чему равно $C_{10}^3$?

- [ ] $720$
- [x] $120$
- [ ] $90$

> $C_{10}^3 = \\frac{10!}{3! \\cdot 7!} = 120$.
"""

NO_EXPLANATION_QUIZ = """\
---
title: "Без пояснений"
---

### Вопрос без пояснения

Выберите:

- [ ] A
- [x] B
- [ ] C
"""

MINIMAL_FRONTMATTER = """\
---
title: "Минимальный"
---

### Вопрос

Текст?

- [x] Да
- [ ] Нет
"""

MULTI_LINE_EXPLANATION = """\
---
title: "Многострочное пояснение"
---

### Вопрос

Текст?

- [x] Да
- [ ] Нет

> Строка 1.
> Строка 2.
> Строка 3.
"""

DISPLAY_MATH_QUIZ = """\
---
title: "Блочная формула"
---

### Вопрос с блочной формулой

Рассмотрим:

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$

Верна ли формула?

- [x] Да
- [ ] Нет
"""

SHORT_ANSWER_NO_EXPLANATION = """\
---
title: "Краткий без пояснения"
---

### Число

Ответьте числом:

answer: 100
"""

MULTIPLE_CODE_BLOCKS = """\
---
title: "Два блока кода"
---

### Сравните

Первый:

```python
x = 1
```

Второй:

```python
x = 2
```

Какой присвоит 2?

- [ ] Первый
- [x] Второй
"""

QUIZ_WITH_POINTS = """\
---
title: "С баллами"
---

### Лёгкий вопрос

points: 1

Да или нет?

- [x] Да
- [ ] Нет

---

### Сложный вопрос

points: 3

Напишите ответ:

answer: 42

> Ответ 42.
"""


# ---------------------------------------------------------------------------
# Tests: frontmatter parsing
# ---------------------------------------------------------------------------

class TestFrontmatter:
    def test_all_fields(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        assert quiz.title == "Тест: одиночный выбор"
        assert quiz.time_limit == 15
        assert quiz.shuffle_questions is True
        assert quiz.shuffle_answers is False

    def test_defaults(self):
        quiz = parse_quiz(MINIMAL_FRONTMATTER)
        assert quiz.title == "Минимальный"
        assert quiz.time_limit is None
        assert quiz.shuffle_questions is False
        assert quiz.shuffle_answers is False

    def test_partial_frontmatter(self):
        quiz = parse_quiz(MULTIPLE_CHOICE_QUIZ)
        assert quiz.title == "Тест: множественный выбор"
        assert quiz.time_limit is None
        assert quiz.shuffle_questions is False
        assert quiz.shuffle_answers is False


# ---------------------------------------------------------------------------
# Tests: question type inference
# ---------------------------------------------------------------------------

class TestQuestionTypeInference:
    def test_single_choice(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        assert len(quiz.questions) == 1
        q = quiz.questions[0]
        assert q.q_type == "single"

    def test_multiple_choice(self):
        quiz = parse_quiz(MULTIPLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert q.q_type == "multiple"

    def test_short_answer(self):
        quiz = parse_quiz(SHORT_ANSWER_QUIZ)
        q = quiz.questions[0]
        assert q.q_type == "short"


# ---------------------------------------------------------------------------
# Tests: single choice questions
# ---------------------------------------------------------------------------

class TestSingleChoice:
    def test_question_text(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert "Какой ответ правильный?" in q.body_md

    def test_title(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert q.title == "Простой вопрос"

    def test_options_count(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert len(q.options) == 3

    def test_correct_option(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        correct = [o for o in q.options if o.is_correct]
        assert len(correct) == 1
        assert "Правильный B" in correct[0].text_md

    def test_incorrect_options(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        incorrect = [o for o in q.options if not o.is_correct]
        assert len(incorrect) == 2

    def test_option_order(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert q.options[0].order_index == 0
        assert q.options[1].order_index == 1
        assert q.options[2].order_index == 2

    def test_explanation(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert q.explanation_md == "Пояснение к ответу."


# ---------------------------------------------------------------------------
# Tests: multiple choice questions
# ---------------------------------------------------------------------------

class TestMultipleChoice:
    def test_correct_options(self):
        quiz = parse_quiz(MULTIPLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        correct = [o for o in q.options if o.is_correct]
        assert len(correct) == 2
        texts = {o.text_md for o in correct}
        assert "Верный 1" in texts
        assert "Верный 3" in texts

    def test_incorrect_options(self):
        quiz = parse_quiz(MULTIPLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        incorrect = [o for o in q.options if not o.is_correct]
        assert len(incorrect) == 2


# ---------------------------------------------------------------------------
# Tests: short answer questions
# ---------------------------------------------------------------------------

class TestShortAnswer:
    def test_accepted_answers_single(self):
        quiz = parse_quiz(SHORT_ANSWER_QUIZ)
        q = quiz.questions[0]
        assert q.accepted_answers == ["4"]

    def test_accepted_answers_multiple(self):
        quiz = parse_quiz(SHORT_ANSWER_MULTIPLE_ACCEPTED)
        q = quiz.questions[0]
        assert q.accepted_answers == ["Москва", "москва"]

    def test_no_options(self):
        quiz = parse_quiz(SHORT_ANSWER_QUIZ)
        q = quiz.questions[0]
        assert len(q.options) == 0

    def test_body_text(self):
        quiz = parse_quiz(SHORT_ANSWER_QUIZ)
        q = quiz.questions[0]
        assert "Сколько будет 2 + 2?" in q.body_md

    def test_no_explanation(self):
        quiz = parse_quiz(SHORT_ANSWER_NO_EXPLANATION)
        q = quiz.questions[0]
        assert q.explanation_md is None


# ---------------------------------------------------------------------------
# Tests: mixed quiz (multiple question types)
# ---------------------------------------------------------------------------

class TestMixedQuiz:
    def test_question_count(self):
        quiz = parse_quiz(MIXED_QUIZ)
        assert len(quiz.questions) == 3

    def test_types(self):
        quiz = parse_quiz(MIXED_QUIZ)
        types = [q.q_type for q in quiz.questions]
        assert types == ["single", "multiple", "short"]

    def test_order_indices(self):
        quiz = parse_quiz(MIXED_QUIZ)
        indices = [q.order_index for q in quiz.questions]
        assert indices == [0, 1, 2]

    def test_frontmatter_with_mixed(self):
        quiz = parse_quiz(MIXED_QUIZ)
        assert quiz.time_limit == 30
        assert quiz.shuffle_questions is True
        assert quiz.shuffle_answers is True

    def test_explanation_present_and_absent(self):
        quiz = parse_quiz(MIXED_QUIZ)
        assert quiz.questions[0].explanation_md == "Пояснение 1."
        assert quiz.questions[1].explanation_md is None
        assert quiz.questions[2].explanation_md == "Ответ 42."


# ---------------------------------------------------------------------------
# Tests: code blocks
# ---------------------------------------------------------------------------

class TestCodeBlocks:
    def test_code_preserved_in_body(self):
        quiz = parse_quiz(CODE_BLOCK_QUIZ)
        q = quiz.questions[0]
        assert "```cpp" in q.body_md
        assert "std::cout << 42;" in q.body_md
        assert "```" in q.body_md

    def test_options_still_parsed(self):
        quiz = parse_quiz(CODE_BLOCK_QUIZ)
        q = quiz.questions[0]
        assert len(q.options) == 3
        correct = [o for o in q.options if o.is_correct]
        assert len(correct) == 1
        assert "42" in correct[0].text_md

    def test_multiple_code_blocks(self):
        quiz = parse_quiz(MULTIPLE_CODE_BLOCKS)
        q = quiz.questions[0]
        assert q.body_md.count("```python") == 2
        assert "x = 1" in q.body_md
        assert "x = 2" in q.body_md


# ---------------------------------------------------------------------------
# Tests: LaTeX passthrough
# ---------------------------------------------------------------------------

class TestLatex:
    def test_inline_latex_in_body(self):
        quiz = parse_quiz(LATEX_QUIZ)
        q = quiz.questions[0]
        assert "$C_{10}^3$" in q.body_md

    def test_inline_latex_in_options(self):
        quiz = parse_quiz(LATEX_QUIZ)
        q = quiz.questions[0]
        assert any("$720$" in o.text_md for o in q.options)
        assert any("$120$" in o.text_md for o in q.options)

    def test_latex_in_explanation(self):
        quiz = parse_quiz(LATEX_QUIZ)
        q = quiz.questions[0]
        assert "$C_{10}^3" in q.explanation_md

    def test_display_math_in_body(self):
        quiz = parse_quiz(DISPLAY_MATH_QUIZ)
        q = quiz.questions[0]
        assert "$$" in q.body_md
        assert "\\sum_{i=1}^{n}" in q.body_md


# ---------------------------------------------------------------------------
# Tests: explanations
# ---------------------------------------------------------------------------

class TestExplanations:
    def test_no_explanation(self):
        quiz = parse_quiz(NO_EXPLANATION_QUIZ)
        q = quiz.questions[0]
        assert q.explanation_md is None

    def test_multiline_explanation(self):
        quiz = parse_quiz(MULTI_LINE_EXPLANATION)
        q = quiz.questions[0]
        assert "Строка 1." in q.explanation_md
        assert "Строка 2." in q.explanation_md
        assert "Строка 3." in q.explanation_md


# ---------------------------------------------------------------------------
# Tests: points
# ---------------------------------------------------------------------------

class TestPoints:
    def test_default_points(self):
        quiz = parse_quiz(SINGLE_CHOICE_QUIZ)
        q = quiz.questions[0]
        assert q.points == 1

    def test_custom_points(self):
        quiz = parse_quiz(QUIZ_WITH_POINTS)
        assert quiz.questions[0].points == 1
        assert quiz.questions[1].points == 3


# ---------------------------------------------------------------------------
# Tests: full example file
# ---------------------------------------------------------------------------

class TestFullExample:
    def test_parse_example_file(self):
        import pathlib
        example = pathlib.Path(__file__).parent.parent.parent / "quizzes" / "test_example.quiz.md"
        if not example.exists():
            pytest.skip("Example file not found")
        content = example.read_text(encoding="utf-8")
        quiz = parse_quiz(content)
        assert quiz.title == "Перестановки, размещения, сочетания, next permutation, ПСП"
        assert quiz.time_limit == 30
        assert len(quiz.questions) == 6

    def test_example_question_types(self):
        import pathlib
        example = pathlib.Path(__file__).parent.parent.parent / "quizzes" / "test_example.quiz.md"
        if not example.exists():
            pytest.skip("Example file not found")
        content = example.read_text(encoding="utf-8")
        quiz = parse_quiz(content)
        types = [q.q_type for q in quiz.questions]
        assert types == ["single", "single", "single", "multiple", "short", "single"]

    def test_example_code_block_preserved(self):
        import pathlib
        example = pathlib.Path(__file__).parent.parent.parent / "quizzes" / "test_example.quiz.md"
        if not example.exists():
            pytest.skip("Example file not found")
        content = example.read_text(encoding="utf-8")
        quiz = parse_quiz(content)
        code_q = quiz.questions[5]
        assert "```cpp" in code_q.body_md
        assert "swap(a[pos], a[j]);" in code_q.body_md


# ---------------------------------------------------------------------------
# Tests: edge cases / error handling
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_quiz("")

    def test_no_frontmatter_raises(self):
        with pytest.raises(ValueError):
            parse_quiz("### Question\n\n- [x] Yes\n- [ ] No\n")

    def test_no_title_raises(self):
        with pytest.raises(ValueError):
            parse_quiz("---\ntime_limit: 10\n---\n\n### Q\n\n- [x] A\n- [ ] B\n")

    def test_no_questions_raises(self):
        with pytest.raises(ValueError):
            parse_quiz("---\ntitle: Empty\n---\n")

    def test_question_no_answers_raises(self):
        with pytest.raises(ValueError):
            parse_quiz("---\ntitle: Bad\n---\n\n### Q\n\nJust text, no answers.\n")

    def test_whitespace_in_answers_trimmed(self):
        src = "---\ntitle: Trim\n---\n\n### Q\n\nText?\n\n- [ ]   Spaced A  \n- [x]   Spaced B  \n"
        quiz = parse_quiz(src)
        assert quiz.questions[0].options[0].text_md == "Spaced A"
        assert quiz.questions[0].options[1].text_md == "Spaced B"

    def test_short_answer_whitespace_trimmed(self):
        src = "---\ntitle: Trim\n---\n\n### Q\n\nText?\n\nanswer:   42  \n"
        quiz = parse_quiz(src)
        assert quiz.questions[0].accepted_answers == ["42"]

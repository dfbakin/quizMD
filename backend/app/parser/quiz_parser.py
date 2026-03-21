"""Parser for .quiz.md files.

Converts a Markdown string with YAML frontmatter into structured quiz data.
Question types are auto-inferred:
  - Checkboxes with exactly one [x]  -> single choice
  - Checkboxes with multiple [x]     -> multiple choice
  - `answer:` line (no checkboxes)   -> short answer
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


@dataclass
class ParsedOption:
    text_md: str
    is_correct: bool
    order_index: int


@dataclass
class ParsedQuestion:
    title: str
    body_md: str
    q_type: str  # "single" | "multiple" | "short"
    options: list[ParsedOption] = field(default_factory=list)
    accepted_answers: list[str] = field(default_factory=list)
    explanation_md: str | None = None
    order_index: int = 0
    points: int = 1


@dataclass
class ParsedQuiz:
    title: str
    questions: list[ParsedQuestion] = field(default_factory=list)
    time_limit: int | None = None
    shuffle_questions: bool = False
    shuffle_answers: bool = False
    source_md: str = ""


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_CHECKBOX_RE = re.compile(r"^-\s+\[([ xX])\]\s+(.+)$")
_ANSWER_RE = re.compile(r"^answer:\s*(.+)$")
_POINTS_RE = re.compile(r"^points:\s*(\d+)\s*$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)")
_FENCE_RE = re.compile(r"^```")


def parse_quiz(source: str) -> ParsedQuiz:
    if not source or not source.strip():
        raise ValueError("Empty quiz source")

    frontmatter, body = _split_frontmatter(source)
    meta = yaml.safe_load(frontmatter)
    if not isinstance(meta, dict) or "title" not in meta:
        raise ValueError("Frontmatter must contain 'title'")

    quiz = ParsedQuiz(
        title=meta["title"],
        time_limit=meta.get("time_limit"),
        shuffle_questions=meta.get("shuffle_questions", False),
        shuffle_answers=meta.get("shuffle_answers", False),
        source_md=source,
    )

    raw_sections = _split_into_sections(body)
    if not raw_sections:
        raise ValueError("Quiz has no questions")

    for idx, section in enumerate(raw_sections):
        question = _parse_question(section, idx)
        quiz.questions.append(question)

    return quiz


def _split_frontmatter(source: str) -> tuple[str, str]:
    m = _FRONTMATTER_RE.match(source)
    if not m:
        raise ValueError("Missing or malformed YAML frontmatter (must start with ---)")
    frontmatter = m.group(1)
    body = source[m.end():]
    return frontmatter, body


def _split_into_sections(body: str) -> list[str]:
    """Split body by `---` horizontal rules into question sections.

    Must be careful not to split inside fenced code blocks.
    """
    sections: list[str] = []
    current_lines: list[str] = []
    in_fence = False

    for line in body.split("\n"):
        stripped = line.strip()

        if _FENCE_RE.match(stripped) and not in_fence:
            in_fence = True
            current_lines.append(line)
            continue
        if in_fence:
            if _FENCE_RE.match(stripped):
                in_fence = False
            current_lines.append(line)
            continue

        if stripped == "---":
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append(section_text)
            current_lines = []
        else:
            current_lines.append(line)

    remaining = "\n".join(current_lines).strip()
    if remaining:
        sections.append(remaining)

    return [s for s in sections if _HEADING_RE.search(s)]


def _parse_question(section: str, order_index: int) -> ParsedQuestion:
    lines = section.split("\n")

    title = _extract_title(lines)
    points = _extract_points(lines)
    explanation = _extract_explanation(lines)
    options, option_lines_set = _extract_options(lines)
    accepted_answers, answer_line_idx = _extract_short_answers(lines)

    body_md = _build_body(lines, option_lines_set, answer_line_idx, explanation is not None)

    q_type = _infer_type(options, accepted_answers)
    if q_type is None:
        raise ValueError(f"Question '{title}' has no answers (no checkboxes and no answer: line)")

    return ParsedQuestion(
        title=title,
        body_md=body_md,
        q_type=q_type,
        options=options,
        accepted_answers=accepted_answers,
        explanation_md=explanation,
        order_index=order_index,
        points=points,
    )


def _extract_title(lines: list[str]) -> str:
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            return m.group(1).strip()
    return "Untitled"


def _extract_points(lines: list[str]) -> int:
    for line in lines:
        m = _POINTS_RE.match(line.strip())
        if m:
            return int(m.group(1))
    return 1


def _extract_explanation(lines: list[str]) -> str | None:
    """Extract blockquote lines from the END of the section."""
    explanation_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            if explanation_lines:
                break
            continue
        m = _BLOCKQUOTE_RE.match(stripped)
        if m:
            explanation_lines.append(m.group(1))
        else:
            break

    if not explanation_lines:
        return None

    explanation_lines.reverse()
    return "\n".join(explanation_lines).strip() or None


def _extract_options(lines: list[str]) -> tuple[list[ParsedOption], set[int]]:
    options: list[ParsedOption] = []
    line_indices: set[int] = set()
    in_fence = False

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        m = _CHECKBOX_RE.match(stripped)
        if m:
            is_correct = m.group(1).lower() == "x"
            text = m.group(2).strip()
            options.append(ParsedOption(
                text_md=text,
                is_correct=is_correct,
                order_index=len(options),
            ))
            line_indices.add(idx)

    return options, line_indices


def _extract_short_answers(lines: list[str]) -> tuple[list[str], int | None]:
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        m = _ANSWER_RE.match(stripped)
        if m:
            raw = m.group(1)
            answers = [a.strip() for a in raw.split(",")]
            return answers, idx
    return [], None


def _build_body(
    lines: list[str],
    option_line_indices: set[int],
    answer_line_idx: int | None,
    has_explanation: bool,
) -> str:
    """Build the question body, excluding options, answer line, explanation, title, and points."""
    body_lines: list[str] = []
    explanation_start = _find_explanation_start(lines) if has_explanation else None
    in_fence = False
    title_found = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if _FENCE_RE.match(stripped):
            in_fence = not in_fence

        if not title_found and _HEADING_RE.match(line):
            title_found = True
            continue

        if not in_fence and _POINTS_RE.match(stripped):
            continue

        if idx in option_line_indices:
            continue

        if idx == answer_line_idx:
            continue

        if explanation_start is not None and idx >= explanation_start:
            continue

        body_lines.append(line)

    return "\n".join(body_lines).strip()


def _find_explanation_start(lines: list[str]) -> int | None:
    """Find the first line index of the trailing blockquote."""
    last_bq_start = None
    in_bq_block = False

    for idx in range(len(lines) - 1, -1, -1):
        stripped = lines[idx].strip()
        if not stripped:
            if in_bq_block:
                continue
            if last_bq_start is not None:
                break
            continue
        if _BLOCKQUOTE_RE.match(stripped):
            last_bq_start = idx
            in_bq_block = True
        else:
            break

    return last_bq_start


def _infer_type(
    options: list[ParsedOption],
    accepted_answers: list[str],
) -> str | None:
    if options:
        correct_count = sum(1 for o in options if o.is_correct)
        return "multiple" if correct_count > 1 else "single"
    if accepted_answers:
        return "short"
    return None

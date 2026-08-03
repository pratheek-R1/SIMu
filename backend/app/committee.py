"""The investment committee.

Questions are templated against the student's own submitted thesis so the
interaction is about their reasoning rather than a generic prompt. Priya's
question is the provenance question -- it is the one the fiction is built
around, and (Open Issue 4) the answer to it is now actually read.
"""

from __future__ import annotations

from typing import Any

from .sim import parameters as P

PARTNERS = (
    {
        "name": "Ana Behl",
        "title": "Managing Partner",
        "question": "You chose {vars}. Which of these is the strongest signal, and why?",
    },
    {
        "name": "Vikram Sood",
        "title": "Principal",
        "question": (
            "What is the minimum threshold on {top_var} that would make you pass "
            "on a deal?"
        ),
    },
    {
        "name": "Rashi Patel",
        "title": "Partner",
        "question": "If you are wrong about your thesis, what is the most likely way you are wrong?",
    },
    {
        "name": "David Chen",
        "title": "CFO",
        "question": (
            "How does your thesis account for capital efficiency? Give me a number "
            "you would hold a company to."
        ),
    },
    {
        "name": "Priya Sharma",
        "title": "Head of Risk",
        "question": (
            "Before we go further -- where did the portfolio history you worked "
            "from actually come from, and what is not in it?"
        ),
    },
)


def build(variables: list[str] | None) -> list[dict[str, Any]]:
    labels = [P.FEATURE_LABELS.get(v, v) for v in (variables or [])]
    vars_text = ", ".join(labels) if labels else "your variables"
    top_var = labels[0] if labels else "your top variable"
    return [
        {
            "index": i,
            "name": p["name"],
            "title": p["title"],
            "question": p["question"].format(vars=vars_text, top_var=top_var),
        }
        for i, p in enumerate(PARTNERS)
    ]


N_PARTNERS = len(PARTNERS)

"""Combinatorial company-name generation.

Names are fabricated, not borrowed. Real trademarked names were considered and
rejected: the simulation randomly assigns invented financials, board minutes and
failure outcomes to every company, and attaching that to a real, identifiable
business -- especially marking a currently-operating company as "wound down" --
is a defamation / false-light risk that does not require intent, since the
assignment is random.

The construction mirrors how Indian startups actually name themselves (Swiggy,
Groww, Meesho): a short Hindi/Sanskrit root plus a startup-style suffix, with
"startup spelling" transforms applied probabilistically.
"""

from __future__ import annotations

import numpy as np

ROOTS = (
    "Arth", "Vichaar", "Nirman", "Prayog", "Setu", "Drishti", "Kavach", "Manthan",
    "Udaan", "Sankalp", "Tarang", "Pragati", "Chetna", "Nayan", "Vistaar", "Aadhar",
    "Sutra", "Yukti", "Prakash", "Antar", "Bindu", "Chakra", "Dhara", "Gyaan",
    "Jyoti", "Kalpa", "Lakshya", "Medha", "Niyam", "Ojas", "Parv", "Rachna",
    "Samvad", "Tattva", "Urja", "Vahan", "Shakti", "Bhoomi", "Kshitij", "Nivesh",
    "Pathik", "Sarthi", "Vritti", "Anant", "Bodhi", "Charan", "Dwar", "Grahak",
    "Hansa", "Indra", "Jaal", "Kosh", "Lehar", "Mudra", "Neer", "Prerna",
    "Rekha", "Saral", "Tulya", "Varsha",
)

SUFFIXES = (
    "ly", "fy", "io", "hub", "lab", "ai", "tech", "x", "os", "va",
    "rx", "go", "up", "on", "do", "wise", "grid", "flow", "base", "works",
    "mint", "loop", "core", "path", "yard", "wave",
)


def _transform(rng: np.random.Generator, name: str) -> str:
    """Apply startup-spelling transforms probabilistically."""
    roll = rng.random()
    if roll < 0.18 and "s" in name[1:]:
        idx = name.index("s", 1)
        name = name[:idx] + "z" + name[idx + 1 :]
    elif roll < 0.34 and "i" in name[1:]:
        idx = name.index("i", 1)
        name = name[:idx] + "y" + name[idx + 1 :]
    elif roll < 0.50 and name[-1] in "aeiou":
        name = name + name[-1]
    elif roll < 0.62:
        for vowel in "aeiou":
            if vowel in name[1:]:
                idx = name.index(vowel, 1)
                name = name[: idx + 1] + vowel + name[idx + 1 :]
                break
    return name


def generate_names(count: int, seed: int) -> list[str]:
    """Return `count` unique company names, deterministic in `seed`.

    Raises if the combinatorial space cannot supply `count` unique names, rather
    than silently emitting duplicates -- duplicate names would let a student
    conflate two different companies' records.
    """
    rng = np.random.default_rng(seed)
    seen: set[str] = set()
    out: list[str] = []

    pairs = [(r, s) for r in ROOTS for s in SUFFIXES]
    rng.shuffle(pairs)  # type: ignore[arg-type]

    # Pass 1: plain root+suffix. Pass 2+: apply spelling transforms to widen the
    # space until we have enough.
    for attempt in range(6):
        for root, suffix in pairs:
            base = root + suffix
            name = base if attempt == 0 else _transform(rng, base)
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
            if len(out) == count:
                return out

    raise ValueError(
        f"name space exhausted: produced {len(out)} unique names, needed {count}"
    )


def is_single_word(name: str) -> bool:
    """Every generated name is single-word; the `oneWordName` Class D flag
    is drawn independently and rendered as a company attribute, not derived from
    the string. Kept here so the distinction is documented where it matters."""
    return " " not in name

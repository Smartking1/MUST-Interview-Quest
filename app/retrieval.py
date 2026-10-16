"""Policy retrieval with section IDs (policy/policy.md and policy/faq.md only).

The corpus is 18 short sections, so this is plain lexical scoring with no
embeddings and no network. Results always include the table of contents so
the model can open a section by ID when the customer's wording does not
match the document's (for example "PayPal" versus "Payment methods").
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
SECTION_RE = re.compile(r"^## (?P<id>[RF]\d+) (?P<title>.+)$", re.M)
STOPWORDS = set("""a an and are as at be by can do does for from has have how i if in is it its
my of on or so that the their them then there these they this to was we what when where which
who will with you your our me am get got any not no yes""".split())


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    text: str
    source: str

    def render(self) -> str:
        return f"[{self.id}] {self.title} ({self.source})\n{self.text}"


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in STOPWORDS]


@lru_cache(maxsize=1)
def load_sections() -> tuple[Section, ...]:
    sections = []
    for name in ("policy.md", "faq.md"):
        doc = (POLICY_DIR / name).read_text()
        matches = list(SECTION_RE.finditer(doc))
        for m, nxt in zip(matches, matches[1:] + [None]):
            body = doc[m.end(): nxt.start() if nxt else len(doc)].strip()
            sections.append(Section(m["id"], m["title"].strip(), body, name))
    return tuple(sections)


def _idf() -> dict[str, float]:
    sections = load_sections()
    df = Counter(t for s in sections for t in set(tokenize(s.title + " " + s.text)))
    return {t: math.log(1 + len(sections) / n) for t, n in df.items()}


def search(query: str, k: int = 3) -> list[Section]:
    idf = _idf()
    q = set(tokenize(query))
    scored = []
    for s in load_sections():
        body, title = Counter(tokenize(s.text)), set(tokenize(s.title))
        score = sum(idf.get(t, 0) * (min(body[t], 3) + 2 * (t in title)) for t in q)
        if score > 0:
            scored.append((score, s))
    return [s for _, s in sorted(scored, key=lambda x: -x[0])[:k]]


def get_section(section_id: str) -> Section | None:
    return next((s for s in load_sections() if s.id == section_id.strip().upper()), None)


def table_of_contents() -> str:
    return "\n".join(f"{s.id}: {s.title}" for s in load_sections())

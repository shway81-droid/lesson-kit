"""차시 본문과 과목으로 성취기준 후보를 랭킹해 돌려준다.

최종 선택은 사람이 한다. 이 모듈은 후보만 좁힌다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "standards-elementary.json"
_TOKEN = re.compile(r"[가-힣]{2,}")
_PAREN = re.compile(r"\(.*?\)")


def load_standards(path: Path = DATA) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_subject(subject: str) -> str:
    """'사회(5~6학년)' -> '사회'. 업스트림 과목명에 학년 표기가 붙어 있다."""
    return _PAREN.sub("", subject).strip()


def tokenize(text: str) -> set[str]:
    return set(_TOKEN.findall(text))


def _score(standard: dict, lesson_tokens: set[str]) -> int:
    """질의 토큰이 성취기준 토큰의 앞부분과 겹치면 맞은 것으로 센다.

    한국어는 조사가 붙는다. 업스트림 keywords 는 정제된 핵심어가 아니라
    본문 앞 5단어를 조사째 자른 것이라('고조선의', '유물을'), 정확히 같은
    표면형만 맞추면 '고조선' 으로 검색했을 때 아무것도 걸리지 않는다.

    한계: 양쪽 다 조사가 붙어 끝 글자가 다르면('고조선을' vs '고조선의')
    이어지지 않는다. 차시 본문 전체를 넣는 정상 경로에서는 겹치는 토큰이
    많아 문제가 되지 않는다.
    """
    terms = tokenize(standard["content"]) | set(standard.get("keywords") or [])
    return sum(
        1
        for token in lesson_tokens
        if any(term.startswith(token) or token.startswith(term) for term in terms)
    )


def find_standards(
    lesson_text: str,
    subject: str,
    grade_group: str | None = None,
    limit: int = 5,
    standards: list[dict] | None = None,
) -> list[dict]:
    rows = standards if standards is not None else load_standards()
    want = normalize_subject(subject)

    pool = [r for r in rows if normalize_subject(r["subject"]) == want]
    if grade_group:
        pool = [r for r in pool if r["grade_group"] == grade_group]

    tokens = tokenize(lesson_text)
    scored = [dict(r, match_score=_score(r, tokens)) for r in pool]
    scored.sort(key=lambda r: (-r["match_score"], r["code"]))
    return scored[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="차시 본문")
    parser.add_argument("--subject", required=True, help="과목명 (예: 사회)")
    parser.add_argument("--grade-group", help="학년군 (초1-2 / 초3-4 / 초5-6)")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    for row in find_standards(args.text, args.subject, args.grade_group, args.limit):
        print(f"{row['code']} (점수 {row['match_score']}) {row['content']}")
        if row.get("explanation"):
            print(f"  해설: {row['explanation']}")
        print()


if __name__ == "__main__":
    main()

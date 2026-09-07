"""NotebookLM 산출물을 원고와 대조한다.

퀴즈 PDF 는 텍스트 레이어가 있어 기계 대조가 끝까지 된다.
슬라이드·인포그래픽은 이미지라 PNG 로 렌더링만 하고 비전으로 읽어야 한다.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz

_WHITESPACE = re.compile(r"\s+")
_BLANK_PAREN = re.compile(r"[（(]\s*[)）]")

# 목록 표식은 반복 적용해 벗긴다. '## 1. 문항' 처럼 겹쳐 붙기 때문이다.
# 번호는 1~2자리만 목록으로 본다. '1392. 조선 건국' 의 연도까지 벗기면
# 연도가 틀려도 대조를 통과해 버린다.
_MARKDOWN = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d{1,2}\.\s+|>\s+)")
# **볼드** 같은 강조 기호. 낱말에 붙은 것만 지운다.
_EMPHASIS = re.compile(r"[*_]{1,3}(?=\S)|(?<=\S)[*_]{1,3}")
_SLIDE_LABEL = re.compile(r"^슬라이드\s*\d+\s*[:：]\s*")

# '항마군 항마군으로' 처럼 같은 낱말이 연달아 찍히는 훼손을 잡는다.
# lookahead 를 두면 뒤 낱말에 조사가 붙은 실제 사례를 놓치고,
# 앞의 lookbehind 가 없으면 '우리나라 나라의' 를 중복으로 오인한다.
_DUPLICATE = re.compile(r"(?<![가-힣A-Za-z0-9])([가-힣A-Za-z0-9]{2,})[\s,.]*\1")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n")
_TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
# '이름: 날짜:', '1번 정답: 단군왕검' 처럼 조판이 붙인 라벨의 앞머리.
# 줄을 통째로 버리면 '단군왕검: 나는 로마 황제였다' 같은 대화체 환각이
# 통째로 빠져나가므로, 앞머리만 벗기고 본문은 검사한다.
_LABEL_PREFIX = re.compile(r"^[^:：]{1,10}[:：]\s*")

# 1글자 줄만 대조에서 뺀다. 임계값을 높이면 '단군왕검'(4자), '8조법'(3자),
# '항마군'(3자) 같은 정답란이 통째로 대조에서 빠져 훼손돼도 통과한다.
MIN_COMPARE_CHARS = 2
# 지어낸 문장 판정 기준. 한국어는 조사가 붙어 '고조선은 이집트다.' 가
# 2낱말이다. 이보다 높이면 가장 흔한 문장 형태를 통째로 놓친다.
MIN_NOVEL_TOKENS = 2
# 문장의 낱말 중 이 비율 이상이 원고에 없으면 지어낸 것으로 본다.
NOVEL_TOKEN_RATIO = 0.5


def normalize(text: str) -> str:
    """공백을 접고 빈칸 괄호를 통일한다.

    PDF 텍스트 추출에서 '(      )' 가 '( )' 로 접히므로 양쪽을 '()' 로 맞춘다.
    """
    text = _BLANK_PAREN.sub("()", text)
    return _WHITESPACE.sub(" ", text).strip()


def find_duplicated_words(text: str) -> list[str]:
    return [match.group(1) for match in _DUPLICATE.finditer(normalize(text))]


def canonical_lines(manuscript: str) -> list[str]:
    """원고에서 대조 대상이 되는 본문 줄만 뽑는다."""
    lines = []
    for raw in manuscript.splitlines():
        # 강조를 먼저 벗겨야 '**1. 문항**' 의 번호가 보인다
        stripped = _EMPHASIS.sub("", raw).strip()
        while True:  # '## 1. 문항' 처럼 표식이 겹쳐 붙는다
            peeled = _MARKDOWN.sub("", stripped)
            if peeled == stripped:
                break
            stripped = peeled
        stripped = _EMPHASIS.sub("", stripped).strip()
        stripped = _SLIDE_LABEL.sub("", stripped).strip()
        if stripped:
            lines.append(stripped)
    return lines


def missing_lines(canonical: str, produced: str) -> list[str]:
    """원고에 있으나 산출물에서 찾을 수 없는 줄을 돌려준다."""
    haystack = normalize(produced)
    return [
        line
        for line in canonical_lines(canonical)
        if len(normalize(line)) >= MIN_COMPARE_CHARS
        and normalize(line) not in haystack
    ]


def extra_sentences(canonical: str, produced: str) -> list[str]:
    """산출물에만 있고 원고에 없는 문장을 돌려준다.

    missing_lines 는 '원고 ⊆ 산출물' 만 본다. NotebookLM 이 원고에 없는
    내용을 지어내도 그 검사는 통과한다. 초등 교재에서 가장 해로운 훼손이라
    반대 방향도 본다.

    NotebookLM 은 원고를 자체 서식으로 재조판하므로 문자열이 그대로
    일치하지 않는다. 라벨 앞머리를 벗긴 뒤 문장 단위로 낱말이 얼마나
    새로운지를 본다.

    한계: 원고에 이미 있는 낱말만 재조합한 거짓 문장은 못 잡는다.
    ('단군왕검이 8조법을 로마에서 만들었다' 처럼 낱말은 다 원고에 있고
    관계만 틀린 경우.) 낱말 통계로는 원리적으로 구분할 수 없다.
    """
    known = set(_TOKEN.findall(canonical))
    found = []
    for chunk in _SENTENCE_SPLIT.split(produced):
        sentence = normalize(chunk)
        while True:  # '이름: 날짜:' 처럼 라벨이 겹칠 수 있다
            peeled = _LABEL_PREFIX.sub("", sentence)
            if peeled == sentence:
                break
            sentence = peeled
        tokens = _TOKEN.findall(sentence)
        if len(tokens) < MIN_NOVEL_TOKENS:
            continue
        novel = [token for token in tokens if token not in known]
        if len(novel) / len(tokens) >= NOVEL_TOKEN_RATIO:
            found.append(sentence)
    return found


def extract_pdf_text(pdf_path: Path) -> str:
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def render_pdf_pages(pdf_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            png = out_dir / f"page_{index:02d}.png"
            page.get_pixmap(dpi=dpi).save(png)
            images.append(png)
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path, help="원고 마크다운")
    parser.add_argument("produced", type=Path, help="산출물 PDF")
    args = parser.parse_args()

    canonical = args.manuscript.read_text(encoding="utf-8")
    produced = extract_pdf_text(args.produced)

    missing = missing_lines(canonical, produced)
    extra = extra_sentences(canonical, produced)
    duplicated = find_duplicated_words(produced)

    print(f"원고 줄 수: {len(canonical_lines(canonical))}")
    print(f"누락: {len(missing)}건")
    for line in missing:
        print(f"  - {line}")
    print(f"원고에 없는 문장: {len(extra)}건")
    for sentence in extra:
        print(f"  + {sentence}")
    print(f"낱말 중복: {len(duplicated)}건")
    for word in duplicated:
        print(f"  - {word}")

    # 훼손을 찾았으면 비영으로 끝낸다. 0 으로 끝내면 러너가 게이트로 쓸 수 없고
    # 사람이 stdout 을 읽어야만 실패를 안다. 조용한 통과가 가장 위험하다.
    if missing or extra or duplicated:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

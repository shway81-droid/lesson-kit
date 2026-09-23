"""교과서 PDF 의 각 장이 교과서 몇 쪽인지, 장 아래에 인쇄된 쪽 번호로 알아낸다.

`--offset` 하나로는 맞지 않는 책이 있다(실측 2026-09-23).

- 천재교과서 5-2: 99쪽 뒤·101쪽 뒤에 쪽 번호 없는 삽입 장(날개)이 있다. offset 1 로
  자르면 2단원 9차시부터 끝까지 19개 차시가 2쪽씩 앞당겨진 채 정상 종료했다.
- 아이스크림 5-2: 두 쪽을 한 장에 붙인 펼침면(가로로 넓은 장)이 섞여 있다. 단원 도입과
  본문 중간에 있어 offset 이 장마다 달라진다. 교과서도 단원별 PDF 3개로 나뉘어 온다.

그래서 쪽 번호를 장마다 읽어 지도를 만든다. 인쇄 번호가 없는 장(전면 사진 등)은 앞뒤에서
채우고, 앞뒤 번호 사이에 들어갈 자리가 없는 무번호 장은 삽입 장으로 본다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz

# 쪽 번호는 지면 맨 아래 10% 안에 찍힌다
FOOTER_RATIO = 0.9
_NUMBER = re.compile(r"\d{1,3}")


def printed_numbers(page: fitz.Page) -> set[int]:
    limit = page.rect.height * FOOTER_RATIO
    return {
        int(word[4])
        for word in page.get_text("words")
        if _NUMBER.fullmatch(word[4]) and word[1] > limit
    }


def page_span(page: fitz.Page) -> int:
    """가로로 넓은 장은 두 쪽을 붙인 펼침면이다."""
    return 2 if page.rect.width > page.rect.height else 1


def _candidates(numbers: set[int], span: int) -> set[int]:
    """이 장의 첫 쪽이 될 수 있는 값. 펼침면은 번호가 왼쪽·오른쪽 어디에 찍혀도 된다."""
    found = set(numbers)
    if span == 2:
        found |= {n - 1 for n in numbers}
    return found


@dataclass
class PageMap:
    pdf_path: Path
    # PDF 장마다 담긴 교과서 쪽. 빈 튜플은 쪽 번호 자리가 없는 삽입 장이다.
    pages: list[tuple[int, ...]]
    inserts: list[int] = field(default_factory=list)   # 0-indexed
    notes: list[str] = field(default_factory=list)

    @property
    def first(self) -> int:
        return min(p for held in self.pages for p in held)

    @property
    def last(self) -> int:
        return max(p for held in self.pages for p in held)

    def covers(self, page_from: int, page_to: int) -> bool:
        held = {p for pages in self.pages for p in pages}
        return page_from in held and page_to in held

    def pdf_range(self, page_from: int, page_to: int) -> tuple[int, int]:
        """교과서 쪽 범위 → 0-indexed PDF 장 범위 (끝 포함).

        시작 쪽 바로 앞의 삽입 장은 그 차시에 붙인다. 날개는 뒤따르는 쪽의 내용을 싣는다
        (실측: 천재 5-2 의 '판소리·탈놀이' 장은 100쪽 '조선 후기 문화' 앞에 있다).
        """
        starts = [i for i, held in enumerate(self.pages) if page_from in held]
        ends = [i for i, held in enumerate(self.pages) if page_to in held]
        if not starts or not ends:
            raise ValueError(
                f"교과서 {page_from}~{page_to}쪽이 {self.pdf_path.name} 에 없다 "
                f"(이 PDF 는 {self.first}~{self.last}쪽)"
            )
        start, end = starts[0], ends[-1]
        while start > 0 and not self.pages[start - 1]:
            start -= 1
        if end < start:
            raise ValueError(f"교과서 {page_from}~{page_to}쪽: 끝 장이 시작 장보다 앞이다")
        return start, end


def build_page_map(pdf_path: Path) -> PageMap:
    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        spans = [page_span(page) for page in doc]
        numbers = [printed_numbers(page) for page in doc]
    count = len(spans)
    cands = [_candidates(n, s) for n, s in zip(numbers, spans)]

    # 기준 장: 다음 장 번호와 이어지는 첫 번호. 본문 속 숫자가 우연히 아래쪽에 걸려도
    # 두 장이 연달아 맞을 일은 드물다.
    anchor = None
    for i in range(count - 1):
        for c in sorted(cands[i]):
            if c + spans[i] in cands[i + 1]:
                anchor = (i, c)
                break
        if anchor:
            break
    if anchor is None:
        raise ValueError(f"{pdf_path.name}: 이어지는 쪽 번호를 찾지 못했다. offset 을 직접 줘야 한다")

    first: list[int | None] = [None] * count
    notes: list[str] = []
    i0, f0 = anchor
    first[i0] = f0

    # 기준 장 앞은 거꾸로 채운다 (단원 도입 펼침면처럼 번호 없는 앞장)
    for i in range(i0 - 1, -1, -1):
        first[i] = first[i + 1] - spans[i]

    # 기준 장 뒤는 앞 장에 이어 붙이며, 인쇄 번호가 기대와 다르면 원인을 가린다
    tentative: list[int] = []      # 번호 없이 기대값으로 채운 장
    for i in range(i0 + 1, count):
        prev = next(j for j in range(i - 1, -1, -1) if first[j] is not None)
        expected = first[prev] + spans[prev]
        if not cands[i] or expected in cands[i]:
            first[i] = expected
            tentative = [] if cands[i] else tentative + [i]
            continue
        closest = min(cands[i], key=lambda c: abs(c - expected))
        behind = expected - closest
        held = sum(spans[j] for j in tentative)
        if 0 < behind <= held:
            # 번호 없는 장 몫으로 쪽을 너무 많이 줬다 → 그 장들 중 뒤쪽이 삽입 장
            while behind > 0 and tentative:
                j = tentative.pop()
                behind -= spans[j]
                first[j] = None
            first[i] = closest
            tentative = []
        elif closest > expected and i + 1 < count and closest + spans[i] in cands[i + 1]:
            notes.append(f"{i + 1}장: {expected}~{closest - 1}쪽이 PDF 에 없다")
            first[i] = closest
            tentative = []
        else:
            # 본문 숫자가 걸린 것. 번호를 믿지 않고 이어 붙인다.
            first[i] = expected
            tentative = []

    pages = [
        () if f is None else tuple(range(f, f + spans[i]))
        for i, f in enumerate(first)
    ]
    inserts = [i for i, held in enumerate(pages) if not held]
    for i in inserts:
        notes.append(f"{i + 1}장: 쪽 번호 자리가 없는 삽입 장")
    return PageMap(pdf_path, pages, inserts, notes)


def locate(maps: list[PageMap], page_from: int, page_to: int) -> tuple[PageMap, int, int]:
    """단원별로 나뉜 PDF 여러 개 중 그 쪽 범위를 담은 것을 찾는다."""
    for page_map in maps:
        if page_map.covers(page_from, page_to):
            start, end = page_map.pdf_range(page_from, page_to)
            return page_map, start, end
    ranges = ", ".join(f"{m.pdf_path.name} {m.first}~{m.last}쪽" for m in maps)
    raise ValueError(f"교과서 {page_from}~{page_to}쪽을 담은 PDF 가 없다 ({ranges})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.pdf:
        page_map = build_page_map(path)
        spreads = sum(1 for held in page_map.pages if len(held) == 2)
        print(f"{path.name}: {len(page_map.pages)}장 = 교과서 {page_map.first}~{page_map.last}쪽"
              f" (펼침면 {spreads}장, 삽입 장 {len(page_map.inserts)}장)")
        for note in page_map.notes:
            print(f"    {note}")


if __name__ == "__main__":
    main()

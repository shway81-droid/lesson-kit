"""교과서 출판사가 주는 나이스 업로드용 진도표(xlsx)에서 차시 목록을 읽는다.

`split_lesson.py --starts` 의 표식 탐지는 추정이다. 출판사마다 조판이 달라 놓치거나
차시가 아닌 쪽을 집어낸다(실측: 천재교과서 5-2 에서 진도표 48차시 대비 표식은 35건).
진도표가 있으면 그것이 정답이다 — 단원·소단원·학습내용·교과서 쪽수가 확정값으로 들어 있다.

진도표에 없는 것: PDF 안에서 그 쪽이 몇 번째 장인지. 앞표지·차례·삽입 장·펼침면 때문에
어긋난다. `--verify` 로 교과서 PDF 를 주면 장마다 인쇄된 쪽 번호로 지도를 만들어 쓴다
(`page_map.py`). 정수 `--offset` 을 주면 그 값을 쓰되 지도와 다른 차시를 경고한다.
어느 쪽이든 찍힌 앞머리를 눈으로 확인한 뒤 쓴다.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

# '22~25', '22 ~ 25', '104~105' 를 받는다. 한 쪽짜리('70')도 허용한다.
_PAGE_RANGE = re.compile(r"(\d+)\s*[~\-–]\s*(\d+)|^(\d+)$")

# 진도표 헤더 이름 → 우리가 쓰는 이름. 출판사가 열 순서를 바꿔도 이름으로 찾는다.
COLUMNS = {
    "단원": "unit",
    "소단원": "topic",
    "학습내용": "title",
    "쪽수": "pages",
    "해당차시": "lesson_no",
    "전체차시": "unit_total",
}


@dataclass
class Lesson:
    unit: str
    topic: str
    title: str
    page_from: int          # 교과서에 인쇄된 쪽 번호
    page_to: int
    lesson_no: int          # 단원 안에서 몇 번째 차시인가
    unit_total: int
    lesson_last: int | None = None   # 한 줄에 '4~5' 처럼 여러 차시를 적은 경우 끝 차시

    @property
    def unit_no(self) -> str:
        """'1. 유적과…'(천재) 도 '1 유적과…'(비상) 도 '1' 로 읽는다."""
        match = re.match(r"\s*(\d+)", self.unit)
        return match.group(1) if match else self.unit.strip()

    @property
    def slug(self) -> str:
        """출력 폴더 이름. 단원 번호와 차시 번호로 정렬 가능하게 만든다."""
        unit_no = self.unit_no
        clean = re.sub(r"[^가-힣A-Za-z0-9]+", "_", self.title).strip("_")
        return f"{unit_no}단원_{self.lesson_no:02d}차시_{clean}"[:80]

    def pdf_range(self, offset: int) -> tuple[int, int]:
        """0-indexed PDF 쪽 범위 (끝 포함). split_lesson.py 에 그대로 넘긴다."""
        return self.page_from - offset, self.page_to - offset


def _parse_pages(value) -> tuple[int, int]:
    text = str(value).strip()
    match = _PAGE_RANGE.search(text)
    if not match:
        raise ValueError(f"쪽수를 읽을 수 없다: {value!r}")
    if match.group(3) is not None:
        single = int(match.group(3))
        return single, single
    return int(match.group(1)), int(match.group(2))


def _parse_lesson_no(value) -> tuple[int, int | None]:
    """'4', 4, '4~5' 를 받는다. 비상교육 진도표는 2차시 수업을 한 줄에 '4~5' 로 적는다."""
    numbers = [int(n) for n in re.findall(r"\d+", str(value))]
    if not numbers:
        raise ValueError(f"차시 번호를 읽을 수 없다: {value!r}")
    return numbers[0], (numbers[-1] if len(numbers) > 1 else None)


def read_lessons(xlsx_path: Path) -> list[Lesson]:
    from openpyxl import load_workbook

    sheet = load_workbook(Path(xlsx_path), data_only=True).worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"빈 진도표다: {xlsx_path}")

    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    index = {}
    for name, key in COLUMNS.items():
        if name not in header:
            # 열이 없으면 조용히 빈 값을 넣지 않는다. 쪽수 하나가 비면
            # 엉뚱한 범위를 잘라 내고도 정상 종료해 버린다.
            raise ValueError(f"진도표에 '{name}' 열이 없다: {header}")
        index[key] = header.index(name)

    lessons: list[Lesson] = []
    for row in rows[1:]:
        if row[index["pages"]] is None:
            continue
        page_from, page_to = _parse_pages(row[index["pages"]])
        lesson_no, lesson_last = _parse_lesson_no(row[index["lesson_no"]])
        lessons.append(
            Lesson(
                unit=str(row[index["unit"]]).strip(),
                topic=str(row[index["topic"]]).strip(),
                title=str(row[index["title"]]).strip(),
                page_from=page_from,
                page_to=page_to,
                lesson_no=lesson_no,
                unit_total=int(row[index["unit_total"]]),
                lesson_last=lesson_last,
            )
        )
    return lessons


def merge_blocks(lessons: list[Lesson]) -> list[Lesson]:
    """쪽수가 같은 연속 차시를 한 덩어리로 합친다.

    진도표는 2차시짜리 수업을 같은 쪽수로 두 줄에 적는다(예: 40~45쪽이 10차시·11차시).
    자료는 그 덩어리에 하나만 만들면 되므로 앞 줄만 남긴다. 합치지 않으면
    같은 범위로 노트북을 두 번 만들어 레이트리밋을 두 배로 쓴다.
    """
    merged: list[Lesson] = []
    for lesson in lessons:
        previous = merged[-1] if merged else None
        same_block = (
            previous is not None
            and previous.unit == lesson.unit
            and (previous.page_from, previous.page_to) == (lesson.page_from, lesson.page_to)
        )
        if not same_block:
            merged.append(lesson)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="나이스 업로드용 진도표")
    parser.add_argument("--unit", help="단원 번호로 거른다 (예: 1)")
    parser.add_argument("--lesson", type=int, help="단원 안 차시 번호로 거른다")
    parser.add_argument("--offset", default="auto",
                        help="교과서 쪽 - PDF 0-indexed 쪽. 기본 auto: --verify PDF 의 인쇄 쪽 번호로 "
                             "장마다 찾는다. PDF 없이 auto 면 1 을 쓴다")
    parser.add_argument("--no-merge", action="store_true",
                        help="쪽수가 같은 연속 차시를 합치지 않는다")
    parser.add_argument("--verify", type=Path, nargs="+",
                        help="교과서 PDF (단원별로 나뉘었으면 모두). 각 차시 첫 쪽의 앞머리를 찍는다")
    args = parser.parse_args()

    lessons = read_lessons(args.xlsx)
    if not args.no_merge:
        lessons = merge_blocks(lessons)
    if args.unit:
        lessons = [l for l in lessons if l.unit_no == str(args.unit)]
    if args.lesson:
        lessons = [l for l in lessons if l.lesson_no == args.lesson]

    auto = args.offset == "auto"
    offset = 1 if auto else int(args.offset)
    maps = []
    if args.verify:
        import fitz
        from page_map import build_page_map, locate
        maps = [build_page_map(path) for path in args.verify]
        for page_map in maps:
            for note in page_map.notes:
                print(f"※ {page_map.pdf_path.name} {note}")
    elif auto:
        print("※ --verify 교과서 PDF 가 없어 offset 1 로 계산했다. 삽입 장·펼침면이 있으면 틀린다")

    mismatched = 0
    for lesson in lessons:
        nos = f"{lesson.lesson_no:2d}" + (f"~{lesson.lesson_last}" if lesson.lesson_last else "")
        print(f"[{lesson.unit_no}단원 {nos}/{lesson.unit_total}차시] {lesson.title}")
        if maps:
            page_map, start, end = locate(maps, lesson.page_from, lesson.page_to)
            if not auto and (start, end) != lesson.pdf_range(offset):
                mismatched += 1
                print(f"    ⚠ offset {offset} 이면 PDF {lesson.pdf_range(offset)} 인데 "
                      f"인쇄 쪽 번호로는 ({start}, {end}) 이다")
                start, end = lesson.pdf_range(offset)
            source = f"  ({page_map.pdf_path.name})" if len(maps) > 1 else ""
        else:
            start, end = lesson.pdf_range(offset)
            source = ""
        print(f"    교과서 {lesson.page_from}~{lesson.page_to}쪽  "
              f"→ PDF --from-page {start} --to-page {end}{source}")
        print(f"    --out output/{lesson.slug}")
        if maps:
            with fitz.open(page_map.pdf_path) as document:
                head = " ".join(document[start].get_text().split())[:70]
            print(f"    확인: {head}")
    print(f"\n{len(lessons)}개 차시")
    if mismatched:
        print(f"⚠ {mismatched}개 차시가 offset {offset} 과 인쇄 쪽 번호가 다르다. "
              f"--offset 을 빼고(auto) 다시 뽑는다")


if __name__ == "__main__":
    main()

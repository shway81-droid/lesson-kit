"""진도표를 따라 학기 교과서 PDF 를 차시별 PDF 로 한 번에 자른다.

`split_lesson.py` 는 차시 하나를 작업 폴더로 잘라내는 도구다. 이것은 학기 전체를
미리 잘라 보관용으로 두는 쪽이다. 차시를 고를 때마다 182쪽을 다시 열지 않아도 되고,
어떤 차시가 있는지 파일 목록으로 바로 보인다.

쪽 범위는 진도표에서 온다. 교과서 쪽이 PDF 몇 번째 장인지는 기본으로 장마다 인쇄된
쪽 번호를 읽어 찾는다(`page_map.py`). 정수 `--offset` 은 삽입 장·펼침면이 없는 책에만 맞다.
단원별로 나뉜 교과서(아이스크림 5-2)는 PDF 를 여러 개 준다.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import fitz

from page_map import PageMap, build_page_map, locate
from read_progress_plan import Lesson, merge_blocks, read_lessons

# 텍스트가 이보다 짧으면 텍스트 레이어가 없는 것으로 본다 (split_lesson 과 같은 기준)
MIN_TEXT_CHARS = 50


@dataclass
class SplitResult:
    lesson: Lesson
    pdf_path: Path
    text_chars: int
    source: Path | None = None
    pdf_from: int = 0        # 0-indexed, 끝 포함
    pdf_to: int = 0

    @property
    def needs_vision(self) -> bool:
        return self.text_chars < MIN_TEXT_CHARS


def _plan_by_offset(textbook_pdf: Path, lessons: list[Lesson], offset: int):
    with fitz.open(textbook_pdf) as probe:
        page_count = probe.page_count
    plan = []
    for lesson in lessons:
        start, end = lesson.pdf_range(offset)
        if start < 0 or end >= page_count:
            raise ValueError(
                f"{lesson.slug}: 교과서 {lesson.page_from}~{lesson.page_to}쪽이 "
                f"PDF 범위를 벗어난다 (PDF {start}~{end}, 전체 {page_count}쪽). "
                f"--offset 이 맞는지 확인하라."
            )
        plan.append((lesson, Path(textbook_pdf), start, end))
    return plan


def _plan_by_page_map(maps: list[PageMap], lessons: list[Lesson]):
    plan = []
    for lesson in lessons:
        try:
            page_map, start, end = locate(maps, lesson.page_from, lesson.page_to)
        except ValueError as error:
            raise ValueError(f"{lesson.slug}: {error}") from error
        plan.append((lesson, page_map.pdf_path, start, end))
    return plan


def split_semester(
    textbook_pdf: Path | list[Path],
    lessons: list[Lesson],
    out_dir: Path,
    offset: int | None = None,
) -> list[SplitResult]:
    """차시마다 PDF 하나를 만든다. 파일명은 Lesson.slug 를 쓴다.

    offset 이 None 이면 인쇄된 쪽 번호로 장을 찾는다. 정수면 그 값만큼 당긴다(PDF 하나일 때).
    """
    pdfs = [Path(p) for p in textbook_pdf] if isinstance(textbook_pdf, (list, tuple)) else [Path(textbook_pdf)]
    out_dir = Path(out_dir)

    # 자르기 전에 전 차시의 범위를 먼저 검사한다. 40번째 차시에서 범위를 벗어나면
    # 앞의 39개는 이미 저장된 뒤라, 어디까지 믿을 수 있는지 알 수 없게 된다.
    if offset is None:
        plan = _plan_by_page_map([build_page_map(p) for p in pdfs], lessons)
    else:
        if len(pdfs) != 1:
            raise ValueError("정수 offset 은 PDF 하나에만 쓴다. 여러 PDF 는 offset 없이(auto) 준다")
        plan = _plan_by_offset(pdfs[0], lessons, offset)

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[SplitResult] = []
    sources = {p: fitz.open(p) for p in pdfs}
    try:
        for lesson, source, start, end in plan:
            out_pdf = out_dir / f"{lesson.slug}.pdf"
            with fitz.open() as target:
                target.insert_pdf(sources[source], from_page=start, to_page=end)
                target.save(out_pdf)
            with fitz.open(out_pdf) as sliced:
                text = "\n".join(page.get_text() for page in sliced).strip()
            results.append(SplitResult(lesson, out_pdf, len(text), source, start, end))
    finally:
        for document in sources.values():
            document.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, nargs="+",
                        help="교과서 PDF. 단원별로 나뉘었으면 모두 준다")
    parser.add_argument("xlsx", type=Path, help="나이스 업로드용 진도표 (맨 뒤)")
    parser.add_argument("--out", type=Path, required=True, help="차시 PDF 를 담을 폴더")
    parser.add_argument("--offset", default="auto",
                        help="교과서 쪽 - PDF 0-indexed 쪽. 기본 auto: 인쇄된 쪽 번호로 찾는다")
    parser.add_argument("--unit", help="단원 번호로 거른다")
    parser.add_argument("--no-merge", action="store_true",
                        help="쪽수가 같은 연속 차시를 합치지 않는다")
    args = parser.parse_args()

    lessons = read_lessons(args.xlsx)
    if not args.no_merge:
        lessons = merge_blocks(lessons)
    if args.unit:
        lessons = [l for l in lessons if l.unit_no == str(args.unit)]

    offset = None if args.offset == "auto" else int(args.offset)
    if offset is None:
        for path in args.pdf:
            for note in build_page_map(path).notes:
                print(f"※ {path.name} {note}")

    results = split_semester(args.pdf, lessons, args.out, offset)

    비전_필요 = [r for r in results if r.needs_vision]
    for result in results:
        표시 = "  [비전 필요]" if result.needs_vision else ""
        print(f"{result.pdf_path.name}  "
              f"교과서 {result.lesson.page_from}~{result.lesson.page_to}쪽 → "
              f"PDF {result.pdf_from + 1}~{result.pdf_to + 1}장  "
              f"{result.text_chars}자{표시}")
    print(f"\n{len(results)}개 차시를 {args.out} 에 저장했다.")
    if 비전_필요:
        print(f"이 중 {len(비전_필요)}개는 텍스트 레이어가 없어 그림으로 읽어야 한다.")


if __name__ == "__main__":
    main()

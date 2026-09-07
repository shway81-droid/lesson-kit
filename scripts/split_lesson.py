"""전체 교과서 PDF 에서 차시 시작을 찾고, 지정한 범위를 잘라낸다.

차시 경계 탐지는 후보 제시용이다. 최종 범위는 사람이 확인한다.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz

# '단원 도입' 은 넣지 않는다. 교과서 본문이 아니라 목차·지도서에 쓰이는
# 편집 용어라 실제 교과서에서 차시가 아닌 쪽을 집어낸다.
#
# 표식은 공백을 모두 지운 텍스트에 맞춘다. 교과서는 제목을 세로쓰기·자간 벌리기로
# 조판하므로 PDF 에서 뽑으면 '생 각 을 열 어 요' 처럼 글자마다 공백이 낀다.
# 낱말 사이에만 `\s*` 를 두면 이런 제목을 통째로 놓친다
# (실측 2026-09-04, 천재교과서 5-2: 옛 패턴 0건 → 공백 제거 후 35건).
LESSON_START_PATTERNS = (
    "학습목표",
    "무엇을배울까요",
    "생각열기",
    "생각을열어요",
)
_PATTERN = re.compile("|".join(LESSON_START_PATTERNS))
_ALL_WHITESPACE = re.compile(r"\s+")

# 이보다 짧으면 텍스트 레이어가 없는 것으로 본다 (벡터/스캔 PDF)
MIN_TEXT_CHARS = 50


@dataclass
class LessonStart:
    page: int  # 0-indexed
    snippet: str


@dataclass
class LessonSlice:
    pdf_path: Path
    text: str
    page_images: list[Path] = field(default_factory=list)
    needs_vision: bool = False


def _page_texts(pdf_path: Path) -> list[str]:
    with fitz.open(pdf_path) as doc:
        return [page.get_text() for page in doc]


def _snippet(text: str, length: int = 60) -> str:
    return " ".join(text.split())[:length]


def find_lesson_starts(pdf_path: Path) -> list[LessonStart]:
    return [
        LessonStart(page=index, snippet=_snippet(text))
        for index, text in enumerate(_page_texts(pdf_path))
        if _PATTERN.search(_ALL_WHITESPACE.sub("", text))
    ]


def split_lesson(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    out_dir: Path,
    dpi: int = 200,
) -> LessonSlice:
    """start_page..end_page (0-indexed, end 포함)를 잘라 out_dir 에 저장한다."""
    # 검증 없이 넘기면 PyMuPDF 가 조용히 받아 준다. from > to 는 역순 PDF 를,
    # 범위 초과는 전권 클램프를 만들고 둘 다 exit 0 으로 끝난다.
    with fitz.open(pdf_path) as probe:
        page_count = probe.page_count
    if start_page < 0:
        raise ValueError(f"시작 쪽이 음수다: {start_page}")
    if end_page < start_page:
        raise ValueError(f"끝 쪽이 시작 쪽보다 앞이다: {start_page} > {end_page}")
    if end_page >= page_count:
        raise ValueError(f"끝 쪽이 원본 범위를 넘는다: {end_page} >= {page_count}쪽")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / "01_차시.pdf"

    with fitz.open(pdf_path) as source, fitz.open() as target:
        target.insert_pdf(source, from_page=start_page, to_page=end_page)
        target.save(out_pdf)

    text = "\n".join(_page_texts(out_pdf)).strip()
    needs_vision = len(text) < MIN_TEXT_CHARS

    images: list[Path] = []
    if needs_vision:
        # 벡터 PDF 는 텍스트 추출이 안 되므로 렌더링해서 비전으로 읽는다
        with fitz.open(out_pdf) as doc:
            for index, page in enumerate(doc, start=1):
                png = out_dir / f"page_{index:02d}.png"
                page.get_pixmap(dpi=dpi).save(png)
                images.append(png)

    return LessonSlice(out_pdf, text, images, needs_vision)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--starts", action="store_true", help="차시 시작 후보만 출력")
    parser.add_argument("--from-page", type=int, help="0-indexed 시작 쪽")
    parser.add_argument("--to-page", type=int, help="0-indexed 끝 쪽 (포함)")
    parser.add_argument("--out", type=Path, default=Path("output/차시"))
    args = parser.parse_args()

    if args.starts or args.from_page is None:
        for start in find_lesson_starts(args.pdf):
            print(f"{start.page:3d}쪽(0-indexed)  {start.snippet}")
        return

    result = split_lesson(args.pdf, args.from_page, args.to_page, args.out)
    print(f"저장: {result.pdf_path}")
    # 사람 확인 지점에서 범위를 대조할 근거. 쪽 수를 찍지 않으면 대조할 것이 없다.
    쪽수 = args.to_page - args.from_page + 1
    print(f"잘라낸 쪽: {args.from_page}~{args.to_page} (0-indexed, {쪽수}쪽)")
    print(f"본문 {len(result.text)}자, 비전 필요: {result.needs_vision}")
    for image in result.page_images:
        print(f"  {image}")


if __name__ == "__main__":
    main()

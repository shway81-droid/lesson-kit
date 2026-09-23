import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from page_map import build_page_map, locate
from read_progress_plan import Lesson
from split_semester import split_semester

A4 = (595, 842)
SPREAD = (1190, 842)


def _book(path, sheets):
    """sheets: (크기, 아래쪽에 찍을 번호들, 본문) 목록. 번호 None 은 무번호 장."""
    doc = fitz.open()
    for size, numbers, body in sheets:
        page = doc.new_page(width=size[0], height=size[1])
        page.insert_text((72, 100), body, fontname="korea-s", fontsize=14)
        for index, number in enumerate(numbers or ()):
            x = 60 if index == 0 else size[0] - 80
            page.insert_text((x, size[1] - 30), str(number), fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_번호가_없는_앞장은_거꾸로_채운다(tmp_path):
    # 표지(무번호) 뒤 1쪽부터 → 천재·비상처럼 offset 이 고정인 책
    pdf = _book(tmp_path / "a.pdf", [(A4, None, "표지")] + [(A4, [n], f"{n}쪽") for n in range(1, 6)])
    page_map = build_page_map(pdf)
    assert page_map.pages[0] == (0,)
    assert page_map.pages[3] == (3,)
    assert page_map.inserts == []


def test_앞뒤_번호_사이에_자리가_없는_무번호_장은_삽입_장이다(tmp_path):
    # 천재 5-2: 99쪽 뒤에 '판소리·탈놀이' 날개가 끼어 있었다. offset 1 로 자르면
    # 그 뒤 차시가 모두 앞당겨진 채 정상 종료했다.
    sheets = [(A4, [n], f"{n}쪽") for n in range(97, 100)]
    sheets += [(A4, None, "판소리 탈놀이")]
    sheets += [(A4, [n], f"{n}쪽") for n in range(100, 104)]
    page_map = build_page_map(_book(tmp_path / "b.pdf", sheets))

    assert page_map.inserts == [3]
    assert page_map.pages[4] == (100,)
    # 삽입 장은 뒤따르는 쪽의 차시에 붙는다
    assert page_map.pdf_range(100, 101) == (3, 5)
    assert page_map.pdf_range(97, 99) == (0, 2)


def test_전면_사진처럼_번호만_빠진_장은_삽입_장이_아니다(tmp_path):
    sheets = [(A4, [10], "10쪽"), (A4, None, "전면 사진"), (A4, [12], "12쪽"), (A4, [13], "13쪽")]
    page_map = build_page_map(_book(tmp_path / "c.pdf", sheets))
    assert page_map.inserts == []
    assert page_map.pages[1] == (11,)


def test_펼침면은_두_쪽으로_센다(tmp_path):
    # 아이스크림 5-2: 단원 도입과 본문 중간에 두 쪽을 붙인 가로 장이 섞여 있다
    sheets = [
        (A4, None, "단원 표지"),          # 6
        (SPREAD, None, "도입 펼침"),      # 7-8
        (SPREAD, [10], "도입 펼침 2"),    # 9-10, 오른쪽 번호만 찍힘
        (A4, [11], "11쪽"),
        (SPREAD, [12, 13], "본문 펼침"),
        (A4, [14], "14쪽"),
    ]
    page_map = build_page_map(_book(tmp_path / "d.pdf", sheets))
    assert page_map.pages == [(6,), (7, 8), (9, 10), (11,), (12, 13), (14,)]
    assert page_map.pdf_range(6, 11) == (0, 3)
    assert page_map.pdf_range(13, 14) == (4, 5)


def test_아래쪽에_걸린_본문_숫자는_무시한다(tmp_path):
    # 아이스크림 1단원 61쪽 아래에 '5' 가 함께 찍혀 있었다
    sheets = [(A4, [60], "60쪽"), (A4, [5, 61], "61쪽"), (A4, [62], "62쪽")]
    page_map = build_page_map(_book(tmp_path / "e.pdf", sheets))
    assert page_map.pages == [(60,), (61,), (62,)]


def test_단원별_pdf_에서_쪽_범위를_찾는다(tmp_path):
    first = build_page_map(_book(tmp_path / "1.pdf", [(A4, [n], f"{n}쪽") for n in range(6, 10)]))
    second = build_page_map(_book(tmp_path / "2.pdf", [(A4, [n], f"{n}쪽") for n in range(10, 14)]))

    page_map, start, end = locate([first, second], 11, 12)
    assert page_map is second
    assert (start, end) == (1, 2)
    with pytest.raises(ValueError, match="담은 PDF 가 없다"):
        locate([first, second], 8, 11)        # 두 파일에 걸치면 자르지 않는다


def test_학기_분할은_기본으로_인쇄_쪽_번호를_쓴다(tmp_path):
    sheets = [(A4, [n], f"{n}쪽 본문이 넉넉히 들어 있는 장입니다") for n in range(97, 100)]
    sheets += [(A4, None, "판소리 탈놀이 날개 장입니다 본문이 넉넉히")]
    sheets += [(A4, [n], f"{n}쪽 본문이 넉넉히 들어 있는 장입니다") for n in range(100, 106)]
    pdf = _book(tmp_path / "교과서.pdf", sheets)
    lessons = [
        Lesson("2. 단원", "소", "조선 후기 문화", 100, 101, 9, 14),
        Lesson("2. 단원", "소", "개항", 102, 103, 10, 14),
    ]

    results = split_semester(pdf, lessons, tmp_path / "차시")

    with fitz.open(results[0].pdf_path) as d:
        assert d.page_count == 3                    # 날개 + 100 + 101
    with fitz.open(results[1].pdf_path) as d:
        assert "102쪽" in d[0].get_text()           # offset 고정이면 101쪽이 잘렸다


def test_학기_분할은_단원별_pdf_여러_개를_받는다(tmp_path):
    body = "쪽 본문이 넉넉히 들어 있는 장입니다 본문 본문"
    one = _book(tmp_path / "1.pdf", [(A4, [n], f"{n}{body}") for n in range(6, 10)])
    two = _book(tmp_path / "2.pdf", [(A4, [n], f"{n}{body}") for n in range(10, 14)])
    lessons = [
        Lesson("1. 가", "소", "앞", 6, 7, 1, 2),
        Lesson("2. 나", "소", "뒤", 12, 13, 1, 2),
    ]

    results = split_semester([one, two], lessons, tmp_path / "차시")

    assert [r.source.name for r in results] == ["1.pdf", "2.pdf"]
    with fitz.open(results[1].pdf_path) as d:
        assert "12쪽" in d[0].get_text()


def test_범위를_못_찾으면_아무것도_저장하지_않는다(tmp_path):
    pdf = _book(tmp_path / "a.pdf", [(A4, [n], f"{n}쪽") for n in range(1, 5)])
    out = tmp_path / "차시"
    lessons = [Lesson("1. 가", "소", "정상", 1, 2, 1, 2), Lesson("1. 가", "소", "없음", 50, 51, 2, 2)]

    with pytest.raises(ValueError, match="없다"):
        split_semester(pdf, lessons, out)
    assert not out.exists() or not list(out.glob("*.pdf"))

import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from read_progress_plan import Lesson
from split_semester import split_semester


@pytest.fixture
def 교과서(tmp_path):
    """10쪽. 각 쪽에 쪽 번호를 적어 어느 쪽이 잘렸는지 확인할 수 있게 한다."""
    path = tmp_path / "교과서.pdf"
    doc = fitz.open()
    for index in range(10):
        page = doc.new_page()
        page.insert_text((72, 100), f"이것은 {index}번째 장입니다. 본문이 넉넉히 들어 있습니다.",
                         fontname="korea-s", fontsize=14)
    doc.save(path)
    doc.close()
    return path


def test_차시마다_pdf_하나를_만든다(교과서, tmp_path):
    lessons = [
        Lesson("1. 단원", "소단원", "구석기", 3, 5, 2, 20),
        Lesson("1. 단원", "소단원", "신석기", 6, 7, 3, 20),
    ]

    results = split_semester(교과서, lessons, tmp_path / "차시", offset=1)

    assert len(results) == 2
    assert all(r.pdf_path.exists() for r in results)
    with fitz.open(results[0].pdf_path) as d:
        assert d.page_count == 3          # 3~5쪽
        assert "2번째 장" in d[0].get_text()   # offset 1 → PDF idx 2
    with fitz.open(results[1].pdf_path) as d:
        assert d.page_count == 2


def test_파일명은_slug_를_쓴다(교과서, tmp_path):
    lessons = [Lesson("1. 단원", "소단원", "구석기 시대", 3, 4, 2, 20)]

    results = split_semester(교과서, lessons, tmp_path / "차시", offset=1)

    assert results[0].pdf_path.name.startswith("1단원_02차시_구석기")
    assert results[0].pdf_path.suffix == ".pdf"


def test_범위를_벗어나면_아무것도_저장하지_않는다(교과서, tmp_path):
    # 뒤쪽 차시에서 터지면 앞의 것들은 이미 저장된 뒤라, 어디까지 믿을지 알 수 없다
    out = tmp_path / "차시"
    lessons = [
        Lesson("1. 단원", "소단원", "정상", 3, 4, 2, 20),
        Lesson("1. 단원", "소단원", "범위초과", 50, 60, 3, 20),
    ]

    with pytest.raises(ValueError, match="offset"):
        split_semester(교과서, lessons, out, offset=1)

    assert not list(out.glob("*.pdf"))


def test_offset_이_틀리면_멈춘다(교과서, tmp_path):
    # offset 을 크게 주면 음수 쪽이 되는데, 조용히 통과하면 엉뚱한 차시가 잘린다
    lessons = [Lesson("1. 단원", "소단원", "구석기", 3, 4, 2, 20)]

    with pytest.raises(ValueError):
        split_semester(교과서, lessons, tmp_path / "차시", offset=10)


def test_텍스트가_없으면_비전_필요로_표시한다(tmp_path):
    path = tmp_path / "그림.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page().draw_rect(fitz.Rect(50, 50, 300, 300), fill=(0.2, 0.4, 0.8))
    doc.save(path)
    doc.close()

    lessons = [Lesson("1. 단원", "소단원", "그림뿐", 2, 3, 1, 20)]
    results = split_semester(path, lessons, tmp_path / "차시", offset=1)

    assert results[0].needs_vision

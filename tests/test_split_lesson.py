import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from split_lesson import find_lesson_starts, split_lesson


def test_학습목표가_있는_쪽을_차시_시작으로_찾는다(교과서_pdf):
    starts = find_lesson_starts(교과서_pdf)
    assert [s.page for s in starts] == [2, 4]


def test_차시_시작_스니펫을_담는다(교과서_pdf):
    starts = find_lesson_starts(교과서_pdf)
    assert "고조선" in starts[0].snippet


def test_지정한_쪽_범위를_잘라낸다(교과서_pdf, tmp_path):
    결과 = split_lesson(교과서_pdf, 2, 3, tmp_path / "out")
    with fitz.open(결과.pdf_path) as doc:
        assert doc.page_count == 2
    assert "고조선" in 결과.text
    assert "삼국" not in 결과.text


def test_텍스트가_있으면_이미지를_만들지_않는다(교과서_pdf, tmp_path):
    결과 = split_lesson(교과서_pdf, 2, 3, tmp_path / "out")
    assert 결과.needs_vision is False
    assert 결과.page_images == []


def test_텍스트가_없으면_png로_렌더링한다(그림만_있는_pdf, tmp_path):
    결과 = split_lesson(그림만_있는_pdf, 0, 1, tmp_path / "out", dpi=72)
    assert 결과.needs_vision is True
    assert len(결과.page_images) == 2
    assert all(p.exists() and p.stat().st_size > 0 for p in 결과.page_images)


def test_시작_쪽이_음수면_거부한다(교과서_pdf, tmp_path):
    with pytest.raises(ValueError):
        split_lesson(교과서_pdf, -1, 3, tmp_path / "out")


def test_끝_쪽이_시작보다_앞이면_거부한다(교과서_pdf, tmp_path):
    # 검증이 없으면 4·3·2 순서의 뒤집힌 PDF 를 만들고 exit 0 으로 끝난다
    with pytest.raises(ValueError):
        split_lesson(교과서_pdf, 4, 2, tmp_path / "out")


def test_끝_쪽이_원본을_넘으면_거부한다(교과서_pdf, tmp_path):
    # 6쪽 문서에 --to-page 99. 검증이 없으면 조용히 전권으로 클램프된다
    with pytest.raises(ValueError):
        split_lesson(교과서_pdf, 2, 99, tmp_path / "out")


def test_마지막_쪽까지는_잘라낸다(교과서_pdf, tmp_path):
    # 6쪽 문서의 끝 쪽 인덱스 5 는 유효하다. 경계를 한 칸 좁히면 안 된다
    결과 = split_lesson(교과서_pdf, 4, 5, tmp_path / "out")
    with fitz.open(결과.pdf_path) as doc:
        assert doc.page_count == 2


def test_main이_잘라낸_쪽_범위를_출력한다(교과서_pdf, tmp_path, capsys, monkeypatch):
    # SKILL.md 의 '사람 확인 지점' 이 범위를 대조하려면 쪽 수가 찍혀야 한다
    import split_lesson as mod

    monkeypatch.setattr(
        sys, "argv",
        ["split_lesson.py", str(교과서_pdf),
         "--from-page", "2", "--to-page", "3", "--out", str(tmp_path / "out")],
    )
    mod.main()

    out = capsys.readouterr().out
    assert "2~3" in out
    assert "2쪽" in out

import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from html_to_pdf import html_to_pdf

HTML = """<!doctype html>
<meta charset="utf-8">
<h1>형성평가</h1>
<p>고조선을 세운 사람은 (      )이다.</p>
<p class="answer">정답: 단군왕검</p>
"""

# NotebookLM 이 다른 클래스명을 쓰면 이렇게 나온다. 숨길 것이 없다.
정답_클래스가_없는_HTML = """<!doctype html>
<meta charset="utf-8">
<h1>형성평가</h1>
<p>고조선을 세운 사람은 (      )이다.</p>
<p class="quiz-solution">정답: 단군왕검</p>
"""


def test_pdf를_만들고_텍스트_레이어가_남는다(tmp_path):
    html = tmp_path / "quiz.html"
    html.write_text(HTML, encoding="utf-8")

    pdf = html_to_pdf(html, tmp_path / "quiz.pdf")

    assert pdf.exists()
    with fitz.open(pdf) as doc:
        text = doc[0].get_text()
    assert "형성평가" in text
    assert "고조선을 세운 사람은" in text


def test_정답을_숨길_수_있다(tmp_path):
    html = tmp_path / "quiz.html"
    html.write_text(HTML, encoding="utf-8")

    학생본 = html_to_pdf(html, tmp_path / "학생.pdf", hide_answers=True)

    with fitz.open(학생본) as doc:
        text = doc[0].get_text()
    assert "고조선을 세운 사람은" in text
    assert "단군왕검" not in text


def test_정답_클래스가_없으면_학생용_PDF를_만들지_않는다(tmp_path):
    # 클래스명이 다르면 --hide-answers 가 조용히 아무 일도 안 하고,
    # 정답이 그대로 인쇄된 종이가 아이들에게 나간다. 종료 코드는 0 이다.
    html = tmp_path / "quiz.html"
    html.write_text(정답_클래스가_없는_HTML, encoding="utf-8")
    out = tmp_path / "학생.pdf"

    with pytest.raises(RuntimeError, match="정답"):
        html_to_pdf(html, out, hide_answers=True)

    assert not out.exists()


def test_정답_클래스가_없어도_정답본은_만든다(tmp_path):
    # 숨기지 않는 쪽은 클래스명과 무관하게 정상 동작해야 한다
    html = tmp_path / "quiz.html"
    html.write_text(정답_클래스가_없는_HTML, encoding="utf-8")

    정답본 = html_to_pdf(html, tmp_path / "정답.pdf")

    with fitz.open(정답본) as doc:
        text = doc[0].get_text()
    assert "단군왕검" in text

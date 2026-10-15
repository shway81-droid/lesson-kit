import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))

from render import concept_html, parse_concept, parse_quiz, quiz_html

원고 = """# 형성평가: 고구려 사람들의 생각과 생활 모습을 알아볼까요

## 문항

1. 옛 사람들이 만든 무덤을 (       )이라고 한다.

2. 무덤 안에 죽은 사람과 함께 묻는 물건을 (       )라고 한다.

## 정답

1. 고분
2. 껴묻거리
"""


def test_문항과_정답을_짝짓는다():
    title, items = parse_quiz(원고)
    assert title == "형성평가: 고구려 사람들의 생각과 생활 모습을 알아볼까요"
    assert items[1] == {"q": "무덤 안에 죽은 사람과 함께 묻는 물건을 (       )라고 한다.", "a": "껴묻거리"}


def test_정답_개수가_다르면_멈춘다():
    with pytest.raises(SystemExit):
        parse_quiz(원고.replace("2. 껴묻거리\n", ""))


def test_빈칸이_없는_문항이면_멈춘다():
    with pytest.raises(SystemExit):
        parse_quiz(원고.replace("(       )이라고", "고분이라고"))


def test_배부본_HTML_에_원고_문장이_그대로_들어간다():
    title, items = parse_quiz(원고)
    h = quiz_html(title, items, {})
    assert "옛 사람들이 만든 무덤을 " in h
    assert "</span>)</span>이라고 한다." in h
    # 정답은 HTML 에 있되 숨겨진다 — 채점용은 body 에 class 만 더한다
    assert 'class="fill"' in h and "고분" in h


def test_개념정리_절을_나누고_마지막_기억해요를_강조한다():
    md = "# 고구려\n\n## 전성기\n5세기경 강력한 국가가 되었다\n\n## 기억해요\n불교를 활용했다\n"
    title, sections = parse_concept(md)
    assert [s["head"] for s in sections] == ["전성기", "기억해요"]
    h = concept_html(title, sections, {}, "")
    assert "remember" in h and "5세기경 강력한 국가가 되었다" in h

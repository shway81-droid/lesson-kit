import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from quiz_to_html import build_html, parse_manuscript, quiz_to_html

원고 = """# 형성평가: 고조선은 어떤 나라일까요

## 문항

1. 고조선을 세운 사람은 (       )이다.

2. 고조선은 (       )개 조항의 법을 만들었다.

## 정답

1. 단군왕검
2. 8
"""


def test_제목과_문항과_정답을_뽑는다():
    title, questions, answers = parse_manuscript(원고)
    assert title == "형성평가: 고조선은 어떤 나라일까요"
    assert questions == ["고조선을 세운 사람은 (       )이다.",
                         "고조선은 (       )개 조항의 법을 만들었다."]
    assert answers == ["단군왕검", "8"]


def test_문항과_정답_개수가_다르면_멈춘다():
    # 어긋난 채로 조판하면 4번 문제에 5번 답이 실린 정답지가 나오는데 종료 코드는 0 이다
    깨진원고 = 원고.replace("2. 8\n", "")
    with pytest.raises(ValueError, match="맞지 않는다"):
        parse_manuscript(깨진원고)


def test_문항_절이_없으면_멈춘다():
    with pytest.raises(ValueError, match="문항"):
        parse_manuscript("# 제목\n\n본문만 있다\n")


def test_정답_절의_번호는_문항으로_세지_않는다():
    # '## 정답' 아래 번호도 _NUMBERED 에 걸린다. 절을 구분하지 않으면 문항이 두 배가 된다
    _, questions, answers = parse_manuscript(원고)
    assert len(questions) == 2
    assert len(answers) == 2


def test_html_에_문항과_정답이_들어간다():
    title, questions, answers = parse_manuscript(원고)
    html = build_html(title, questions, answers)
    assert "고조선을 세운 사람은" in html
    assert "단군왕검" in html
    assert "학년 반" in html and "이름" in html


def test_정답은_answer_요소에_들어간다():
    # html_to_pdf --hide-answers 가 이 클래스를 숨긴다. 밖에 있으면 학생용에 정답이 인쇄된다
    title, questions, answers = parse_manuscript(원고)
    html = build_html(title, questions, answers)
    앞, _, 뒤 = html.partition('<div class="answer">')
    assert "단군왕검" not in 앞
    assert "단군왕검" in 뒤


def test_원고_제목을_그대로_쓴다(tmp_path):
    # NotebookLM 이 붙이던 '인권 퀴즈' 같은 제목이 더는 끼어들지 않는다
    md = tmp_path / "03_형성평가.md"
    md.write_text(원고, encoding="utf-8")

    out = quiz_to_html(md, tmp_path / "인쇄용.html")

    assert "형성평가: 고조선은 어떤 나라일까요" in out.read_text(encoding="utf-8")


def test_꺾쇠는_이스케이프한다():
    html = build_html("제목", ["<b>굵게</b> 라고 쓰면?"], ["답"])
    assert "&lt;b&gt;" in html

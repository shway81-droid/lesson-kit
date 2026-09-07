"""형성평가 원고(마크다운)를 인쇄용 HTML 로 바꾼다.

**NotebookLM 을 거치지 않는다.** 문항과 정답은 이미 `03_형성평가.md` 에 확정되어 있어서
조판만 하면 되고, 거치면 잃는 것만 있다(실측 2026-09-07):

- 빈칸 채우기 문장을 의문문으로 바꿔 놓는다. 배부본과 정답지의 문항 형태가 어긋난다.
- 원고에 없는 4지선다 오답과 해설을 지어낸다. 이 파이프라인은 빈칸형이라 쓰지 않는다.
- 생성 한 번을 레이트리밋에서 더 쓴다.

원고를 그대로 조판하면 정답지가 원고와 어긋날 수가 없다.

정답은 `.answer` 요소에 넣어 `html_to_pdf.py --hide-answers` 가 학생용에서 숨긴다.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

_TITLE = re.compile(r"^#\s+(.*)$")
_SECTION = re.compile(r"^##\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d+)\.\s+(.*)$")

STYLE = """
/* keep-all: 낱말 중간에서 줄이 꺾이면 PDF 텍스트 추출이 '것 을' 로 갈라져 대조에서 누락으로 잡힌다 */
body { font-family: 'Malgun Gothic', sans-serif; line-height: 1.9; font-size: 12pt; word-break: keep-all; }
h1 { font-size: 16pt; margin-bottom: 0.2em; }
.meta { margin-bottom: 1.4em; color: #333; }
.meta span { display: inline-block; margin-right: 2.5em; }
ol.questions { padding-left: 1.4em; }
ol.questions > li { margin-bottom: 1.3em; }
.answer { margin-top: 2.5em; border-top: 1px solid #999; padding-top: 0.8em; }
.answer h2 { font-size: 13pt; }
.answer ol { padding-left: 1.4em; }
"""


def parse_manuscript(text: str) -> tuple[str, list[str], list[str]]:
    """원고에서 제목·문항·정답을 뽑는다.

    문항과 정답 개수가 다르면 멈춘다. 어긋난 채로 조판하면 4번 문제에 5번 답이 실린
    정답지가 나오는데, 종료 코드는 0 이라 아무도 모른다.
    """
    title = "형성평가"
    section: str | None = None
    questions: list[str] = []
    answers: list[str] = []

    for raw in text.splitlines():
        heading = _TITLE.match(raw)
        if heading and not raw.startswith("##"):
            title = heading.group(1).strip()
            continue
        marker = _SECTION.match(raw)
        if marker:
            section = marker.group(1).strip()
            continue
        numbered = _NUMBERED.match(raw)
        if not numbered:
            continue
        if section == "문항":
            questions.append(numbered.group(2).strip())
        elif section == "정답":
            answers.append(numbered.group(2).strip())

    if not questions:
        raise ValueError("원고에서 '## 문항' 절의 번호 붙은 문항을 찾지 못했다")
    if len(questions) != len(answers):
        raise ValueError(
            f"문항 {len(questions)}개와 정답 {len(answers)}개가 맞지 않는다. "
            f"원고의 '## 문항' 과 '## 정답' 절을 확인하라."
        )
    return title, questions, answers


def build_html(title: str, questions: list[str], answers: list[str]) -> str:
    문항 = "\n".join(f"    <li>{html.escape(q)}</li>" for q in questions)
    정답 = "\n".join(f"    <li>{html.escape(a)}</li>" for a in answers)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{STYLE}</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta"><span>학년 반: __________</span><span>이름: __________</span></div>
<ol class="questions">
{문항}
</ol>
<div class="answer">
  <h2>정답</h2>
  <ol>
{정답}
  </ol>
</div>
</body></html>
"""


def quiz_to_html(manuscript_path: Path, html_path: Path) -> Path:
    title, questions, answers = parse_manuscript(
        Path(manuscript_path).read_text(encoding="utf-8"))
    html_path = Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(build_html(title, questions, answers), encoding="utf-8")
    return html_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path, help="형성평가 원고 (03_형성평가.md)")
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    print(f"저장: {quiz_to_html(args.manuscript, args.html)}")


if __name__ == "__main__":
    main()

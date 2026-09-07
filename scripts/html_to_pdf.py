"""NotebookLM 퀴즈 HTML 을 A4 인쇄용 PDF 로 바꾼다.

HTML 경유로 만들면 PDF 에 텍스트 레이어가 남아 기계 대조가 가능하다.
슬라이드·인포그래픽은 이미지라 이 이점이 없다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ANSWER_SELECTOR = ".answer"
HIDE_ANSWERS_CSS = f"{ANSWER_SELECTOR} {{ display: none !important; }}"

PRINT_CSS = """
@page { margin: 18mm 16mm; }
body { font-family: 'Malgun Gothic', sans-serif; line-height: 1.7; }
"""


def html_to_pdf(html_path: Path, pdf_path: Path, hide_answers: bool = False) -> Path:
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.as_uri())
            page.add_style_tag(content=PRINT_CSS)
            if hide_answers:
                # 클래스명이 다르면 숨길 것이 없어 정답이 그대로 인쇄되는데
                # 종료 코드는 0 이다. 아이들에게 나눠 주는 종이라 조용한 실패를
                # 허용하지 않는다. 만들지 말고 멈춘다.
                if page.locator(ANSWER_SELECTOR).count() == 0:
                    raise RuntimeError(
                        f"정답 요소({ANSWER_SELECTOR})를 찾지 못해 학생용 PDF 를 "
                        f"만들지 않았다. 퀴즈 HTML 의 정답 클래스명을 확인하라: {html_path}"
                    )
                page.add_style_tag(content=HIDE_ANSWERS_CSS)
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
        finally:
            # 예외로 빠져나가도 크로미움 프로세스가 남지 않게 한다
            browser.close()

    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--hide-answers", action="store_true")
    args = parser.parse_args()

    out = html_to_pdf(args.html, args.pdf, args.hide_answers)
    print(f"저장: {out}")


if __name__ == "__main__":
    main()

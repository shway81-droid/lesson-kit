import fitz
import pytest


@pytest.fixture
def 교과서_pdf(tmp_path):
    """6쪽 교과서. 2쪽(0-indexed)과 4쪽에 차시 시작 표지가 있다.

    한글은 PyMuPDF 내장 폰트 korea-s 로 넣는다. 다른 폰트는 이 환경에 없다.
    """
    path = tmp_path / "교과서.pdf"
    # 한 줄이 지면 폭을 넘으면 잘려서 추출되지 않는다. 실제 교과서처럼 여러 줄로 넣어
    # 2쪽 슬라이스가 MIN_TEXT_CHARS(50) 를 넉넉히 넘게 한다.
    본문 = [
        ["단원 도입 그림"],
        ["차례"],
        ["학습 목표: 고조선의 생활 모습을 알아봅시다.",
         "청동기 문화를 바탕으로 세워진 우리나라 최초의 나라를",
         "유적과 유물로 살펴봅니다."],
        ["청동기 시대 유물 사진과 설명.",
         "비파형 동검과 미송리식 토기를 보고",
         "당시 사람들의 생활을 추론해 봅니다."],
        ["학습 목표: 삼국의 성립을 알아봅시다.",
         "고구려, 백제, 신라가 세워진 과정을 살펴봅니다."],
        ["고구려 백제 신라"],
    ]
    doc = fitz.open()
    for 줄들 in 본문:
        page = doc.new_page()
        for index, 줄 in enumerate(줄들):
            page.insert_text((72, 100 + index * 24), 줄, fontname="korea-s", fontsize=14)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def 그림만_있는_pdf(tmp_path):
    """텍스트 레이어가 없는 PDF. 벡터/스캔 교과서를 흉내낸다."""
    path = tmp_path / "그림.pdf"
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(50, 50, 300, 300), fill=(0.2, 0.4, 0.8))
    doc.save(path)
    doc.close()
    return path

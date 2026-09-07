import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verify_output

from verify_output import (
    canonical_lines,
    extra_sentences,
    extract_pdf_text,
    find_duplicated_words,
    missing_lines,
    normalize,
    render_pdf_pages,
)


def test_공백을_접는다():
    assert normalize("고조선을   세운  사람") == "고조선을 세운 사람"


def test_빈칸_괄호를_통일한다():
    # PDF 텍스트 추출에서 (      ) 가 ( ) 로 접힌다
    assert normalize("사람은 (      )이다") == normalize("사람은 ()이다")


def test_낱말_중복을_잡는다():
    assert find_duplicated_words("승병인 항마군 항마군 편성") == ["항마군"]


def test_중복이_없으면_빈_목록이다():
    assert find_duplicated_words("고조선을 세운 단군왕검") == []


def test_산출물에_빠진_원고_줄을_찾는다():
    원고 = "고조선은 우리나라 최초의 나라이다.\n단군왕검이 세웠다.\n8조법이 있었다."
    산출 = "고조선은 우리나라 최초의 나라이다. 단군왕검이 세웠다."
    assert missing_lines(원고, 산출) == ["8조법이 있었다."]


def test_모두_들어있으면_빈_목록이다():
    원고 = "고조선은 최초의 나라이다."
    산출 = "제목\n고조선은   최초의 나라이다.\n끝"
    assert missing_lines(원고, 산출) == []


def test_마크다운_표식은_무시한다():
    원고 = "## 슬라이드 1: 고조선\n- 단군왕검이 세웠다"
    산출 = "고조선 단군왕검이 세웠다"
    assert missing_lines(원고, 산출) == []


def _한글_pdf(path, 문장들):
    doc = fitz.open()
    for 문장 in 문장들:
        page = doc.new_page()
        page.insert_text((72, 100), 문장, fontname="korea-s", fontsize=14)
    doc.save(path)
    doc.close()
    return path


def test_pdf에서_텍스트를_뽑는다(tmp_path):
    pdf = _한글_pdf(tmp_path / "a.pdf", ["고조선의 생활", "삼국의 성립"])
    text = extract_pdf_text(pdf)
    assert "고조선의 생활" in text
    assert "삼국의 성립" in text


def test_pdf를_쪽마다_png로_렌더링한다(tmp_path):
    pdf = _한글_pdf(tmp_path / "a.pdf", ["첫 쪽", "둘째 쪽"])
    images = render_pdf_pages(pdf, tmp_path / "png", dpi=72)
    assert len(images) == 2
    assert all(p.exists() and p.stat().st_size > 0 for p in images)

def test_조사가_붙은_실제_훼손도_잡는다():
    # 선례에서 실제로 나온 형태. 원문은 '승병인 항마군으로' 였다.
    # 뒤 낱말에 조사가 붙으므로 정규식에 lookahead 를 두면 놓친다.
    assert find_duplicated_words("승병인 항마군 항마군으로 편성") == ["항마군"]


def test_정상_표현을_중복으로_오인하지_않는다():
    # 낱말 중간에서 매칭하면 '우리나라 나라의' 가 중복으로 잡힌다
    assert find_duplicated_words("우리나라 나라의 이름") == []
    assert find_duplicated_words("지역의 지역사회 활동") == []


def test_숫자와_영문_중복도_잡는다():
    assert find_duplicated_words("8조법 8조법") == ["8조법"]
    assert find_duplicated_words("Silla Silla") == ["Silla"]


def test_연도를_목록_번호로_오인하지_않는다():
    # '1392.' 를 벗기면 연도가 틀려도 대조를 통과해 버린다
    assert canonical_lines("1392. 조선 건국") == ["1392. 조선 건국"]
    assert missing_lines("1392. 조선 건국", "1394. 조선 건국") == ["1392. 조선 건국"]


def test_겹쳐_붙은_표식을_모두_벗긴다():
    assert canonical_lines("## 1. 고조선을 세운 사람은?") == ["고조선을 세운 사람은?"]


def test_볼드_표시를_벗긴다():
    assert canonical_lines("**항마군**은 승병이다") == ["항마군은 승병이다"]


def test_짧은_정답도_반드시_대조한다():
    # 임계값을 올리면 '단군왕검'(4자) '8조법'(3자) '항마군'(3자) 같은
    # 정답란이 통째로 대조에서 빠져 훼손돼도 통과한다. 가장 위험한 실패다.
    원고 = "## 정답\n1. 단군왕검\n2. 8조법\n3. 항마군"
    바뀐_산출 = "형성평가 정답\n1. 온조왕\n2. 화랑도\n3. 승병"
    그대로_산출 = "형성평가 정답\n1. 단군왕검\n2. 8조법\n3. 항마군"
    assert missing_lines(원고, 바뀐_산출) == ["단군왕검", "8조법", "항마군"]
    assert missing_lines(원고, 그대로_산출) == []


def test_원고에_없는_문장을_잡는다():
    # NotebookLM 이 지어낸 내용. missing_lines 만으로는 통과해 버린다
    원고 = "단군왕검이 고조선을 세웠다."
    산출 = "단군왕검이 고조선을 세웠다. 왕검은 로마의 황제였다."
    assert missing_lines(원고, 산출) == []
    assert extra_sentences(원고, 산출) == ["왕검은 로마의 황제였다."]


def test_원고대로면_추가_문장이_없다():
    원고 = "단군왕검이 고조선을 세웠다."
    assert extra_sentences(원고, "단군왕검이 고조선을 세웠다.") == []


def test_재조판된_산출물을_환각으로_오인하지_않는다():
    # NotebookLM 은 원고를 자체 서식으로 다시 짠다. 문항번호·정답라벨을
    # 전부 '지어낸 문장' 으로 신고하면 리포트가 잡음에 묻혀 쓸모가 없어진다.
    원고 = "## 1. 고조선을 세운 사람은 (      )이다.\n\n## 정답\n1. 단군왕검"
    산출 = (
        "이름: 날짜:\n"
        "문제 1) 고조선을 세운 사람은 ( )이다.\n"
        "1번 정답: 단군왕검"
    )
    assert extra_sentences(원고, 산출) == []


def test_두낱말_환각도_잡는다():
    # 한국어는 조사가 붙어 'X는 Y이다' 가 2낱말이다. 가장 흔한 문장 형태라
    # 최소 낱말 수를 높이면 이 형태를 통째로 놓친다.
    원고 = "단군왕검이 고조선을 세웠다."
    assert extra_sentences(원고, 원고 + " 고조선은 이집트다.") == ["고조선은 이집트다."]


def test_명사형과_구어체_환각도_잡는다():
    # 종결어미로 가르면 '~ 출신.' 처럼 명사로 끝나는 거짓 문장을 통째로 놓친다.
    원고 = "단군왕검이 고조선을 세웠다."
    assert extra_sentences(원고, 원고 + " 왕검은 로마의 황제 출신.") == [
        "왕검은 로마의 황제 출신."
    ]
    assert extra_sentences(원고, 원고 + " 왕검은 원래 신라 사람이었잖아") == [
        "왕검은 원래 신라 사람이었잖아"
    ]


def test_대화체_환각도_잡는다():
    # 라벨이 든 줄을 통째로 버리면 지어낸 대사가 빠져나간다
    원고 = "단군왕검이 고조선을 세웠다."
    산출 = 원고 + "\n단군왕검: 나는 로마 황제였다."
    assert extra_sentences(원고, 산출) == ["나는 로마 황제였다."]
def test_볼드가_감싼_번호도_벗긴다():
    assert canonical_lines("**1. 문항**") == ["문항"]


# --- main() 의 종료 코드 게이트 ------------------------------------------------
# 여기가 안전망의 마지막 관문이다. 이 게이트가 없으면 훼손을 stdout 에만 적고
# exit 0 으로 끝나서, 러너도 사람도 실패를 모른 채 지나간다.
# 돌연변이 검증: main() 에서 `raise SystemExit(1)` 을 지우면 아래 두 테스트가
# 실패해야 한다. 게이트 조건에서 duplicated 를 빼면 중복 테스트가 실패해야 한다.


def _main으로_돌린다(monkeypatch, 원고_경로, pdf_경로):
    monkeypatch.setattr(
        sys, "argv", ["verify_output.py", str(원고_경로), str(pdf_경로)]
    )
    verify_output.main()


def test_누락이_있으면_비영으로_끝낸다(tmp_path, monkeypatch):
    원고 = tmp_path / "03_형성평가.md"
    원고.write_text("단군왕검이 고조선을 세웠다.\n8조법이 있었다.", encoding="utf-8")
    pdf = _한글_pdf(tmp_path / "out.pdf", ["단군왕검이 고조선을 세웠다."])

    with pytest.raises(SystemExit) as 잡힘:
        _main으로_돌린다(monkeypatch, 원고, pdf)
    assert 잡힘.value.code == 1


def test_낱말_중복만_있어도_비영으로_끝낸다(tmp_path, monkeypatch):
    # 게이트 조건에서 duplicated 를 빼면 이 테스트가 실패한다.
    # 누락도 없고 지어낸 문장도 없지만 낱말이 두 번 찍힌 경우다.
    원고 = tmp_path / "03_형성평가.md"
    원고.write_text("단군왕검이 고조선을 세웠다.", encoding="utf-8")
    pdf = _한글_pdf(
        tmp_path / "out.pdf",
        ["단군왕검이 고조선을 세웠다.", "고조선을 고조선을 세웠다."],
    )

    산출 = extract_pdf_text(pdf)
    원고_본문 = 원고.read_text(encoding="utf-8")
    assert missing_lines(원고_본문, 산출) == []
    assert extra_sentences(원고_본문, 산출) == []
    assert find_duplicated_words(산출) == ["고조선을"]

    with pytest.raises(SystemExit) as 잡힘:
        _main으로_돌린다(monkeypatch, 원고, pdf)
    assert 잡힘.value.code == 1


def test_지어낸_문장만_있어도_비영으로_끝낸다(tmp_path, monkeypatch):
    # 게이트 조건에서 extra 를 빼면 이 테스트가 실패한다.
    # 누락도 낱말 중복도 없지만 원고에 없는 사실이 새로 등장한 경우다.
    원고 = tmp_path / "03_형성평가.md"
    원고.write_text("단군왕검이 고조선을 세웠다.", encoding="utf-8")
    pdf = _한글_pdf(
        tmp_path / "out.pdf",
        ["단군왕검이 고조선을 세웠다.", "왕검은 로마의 황제였다."],
    )

    산출 = extract_pdf_text(pdf)
    원고_본문 = 원고.read_text(encoding="utf-8")
    assert missing_lines(원고_본문, 산출) == []
    assert find_duplicated_words(산출) == []
    assert extra_sentences(원고_본문, 산출) == ["왕검은 로마의 황제였다."]

    with pytest.raises(SystemExit) as 잡힘:
        _main으로_돌린다(monkeypatch, 원고, pdf)
    assert 잡힘.value.code == 1


def test_훼손이_없으면_조용히_끝난다(tmp_path, monkeypatch, capsys):
    원고 = tmp_path / "03_형성평가.md"
    원고.write_text("단군왕검이 고조선을 세웠다.", encoding="utf-8")
    pdf = _한글_pdf(tmp_path / "out.pdf", ["단군왕검이 고조선을 세웠다."])

    _main으로_돌린다(monkeypatch, 원고, pdf)  # SystemExit 이 나면 실패다

    out = capsys.readouterr().out
    assert "누락: 0건" in out
    assert "낱말 중복: 0건" in out

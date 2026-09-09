import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from answer_overlay import (
    Blank,
    draw_answers,
    find_bracket_pairs,
    find_font,
    pick_one_per_cell,
    render_preview,
)


def _문항이미지(path: Path, 문항들, 크기=(1800, 900), 폰트크기=54):
    """배부본을 흉내낸 이미지. 문항들은 (열, 행, 앞말, 빈칸글자수, 뒷말).

    실제 배부본과 같은 조건(흰 배경, 굵은 한글, 글자 높이 50px 안팎)으로 그려야
    탐지 파라미터가 실제와 같은 의미를 갖는다.
    """
    im = Image.new("RGB", 크기, (255, 255, 255))
    d = ImageDraw.Draw(im)
    f = find_font(폰트크기)
    칸폭 = 크기[0] // 3
    칸높이 = 크기[1] // 2
    for 열, 행, 앞말, 빈칸수, 뒷말 in 문항들:
        x = 열 * 칸폭 + 40
        y = 행 * 칸높이 + 60
        d.text((x, y), f"{앞말}({' ' * 빈칸수}){뒷말}", fill=(0, 0, 0), font=f)
    im.save(path)
    return path


@pytest.fixture
def 배부본(tmp_path):
    """3열 2행에 빈칸이 하나씩 있는 문항 여섯 개."""
    return _문항이미지(
        tmp_path / "배부본.png",
        [
            (0, 0, "1. 가", 8, "이다."),
            (1, 0, "2. 나", 8, "이다."),
            (2, 0, "3. 다", 8, "이다."),
            (0, 1, "4. 라", 8, "이다."),
            (1, 1, "5. 마", 8, "이다."),
            (2, 1, "6. 바", 8, "이다."),
        ],
    )


def test_빈칸_여섯_개를_찾는다(배부본):
    pairs = find_bracket_pairs(배부본)
    assert len(pairs) == 6


def test_찾은_빈칸은_괄호_안쪽이다(배부본):
    """x0 는 여는 괄호의 오른쪽 끝, x1 은 닫는 괄호의 왼쪽 끝이어야 한다.

    괄호 바깥을 돌려주면 정답 글자가 괄호에 겹쳐 찍힌다.
    """
    im = Image.open(배부본).convert("L")
    for b in find_bracket_pairs(배부본):
        assert b.x1 > b.x0
        가운데 = im.crop((b.x0 + 4, b.y - 15, b.x1 - 4, b.y + 15))
        assert min(가운데.getdata()) > 200, "빈칸 안쪽에 글자가 있으면 안 된다"


def test_괄호가_아닌_세로획은_쌍이_되지_않는다(tmp_path):
    """'ㅣ' 처럼 세로로 긴 획만 있고 괄호가 없으면 빈칸으로 잡히면 안 된다."""
    path = _문항이미지(tmp_path / "괄호없음.png", [(0, 0, "가나다 라마바 사아자", 0, "")])
    im = Image.new("RGB", (1800, 900), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((40, 60), "이 문장에는 빈칸이 없다 나비 미리", fill=(0, 0, 0), font=find_font(54))
    im.save(path)
    assert find_bracket_pairs(path) == []


def test_읽기_순서로_돌려준다(배부본):
    """3열 2행이면 왼쪽 위부터 오른쪽으로, 그다음 아랫줄."""
    pairs = find_bracket_pairs(배부본)
    골라낸 = pick_one_per_cell(pairs, rows=2, cols=3, size=Image.open(배부본).size)
    assert len(골라낸) == 6
    윗줄 = 골라낸[:3]
    아랫줄 = 골라낸[3:]
    assert [b.x0 for b in 윗줄] == sorted(b.x0 for b in 윗줄)
    assert max(b.y for b in 윗줄) < min(b.y for b in 아랫줄)


def test_한_칸에_후보가_없으면_None_으로_남긴다(tmp_path):
    """조용히 다섯 개만 돌려주면 4번 자리에 5번 답이 찍힌다."""
    path = _문항이미지(
        tmp_path / "다섯개.png",
        [
            (0, 0, "1. 가", 8, "이다."),
            (1, 0, "2. 나", 8, "이다."),
            (2, 0, "3. 다", 8, "이다."),
            (0, 1, "4. 라", 8, "이다."),
            (1, 1, "5. 마", 8, "이다."),
        ],
    )
    골라낸 = pick_one_per_cell(find_bracket_pairs(path), rows=2, cols=3, size=Image.open(path).size)
    assert len(골라낸) == 6
    assert 골라낸[5] is None


def test_빈칸_수와_정답_수가_다르면_멈춘다(배부본, tmp_path):
    빈칸들 = find_bracket_pairs(배부본)
    with pytest.raises(ValueError, match="정답"):
        draw_answers(배부본, 빈칸들, ["하나", "둘"], tmp_path / "채점용.png")


def test_빈칸을_못_찾은_칸이_있으면_멈춘다(배부본, tmp_path):
    빈칸들 = find_bracket_pairs(배부본)
    빈칸들[2] = None
    with pytest.raises(ValueError, match="3"):
        draw_answers(배부본, 빈칸들, ["1", "2", "3", "4", "5", "6"], tmp_path / "채점용.png")


def test_정답을_실제로_그린다(배부본, tmp_path):
    """그렸다고 주장만 하지 않게, 빈칸 영역의 픽셀이 바뀌었는지 본다."""
    빈칸들 = find_bracket_pairs(배부본)
    out = draw_answers(배부본, 빈칸들, ["가", "나", "다", "라", "마", "바"], tmp_path / "채점용.png")
    전 = Image.open(배부본).convert("RGB")
    후 = Image.open(out).convert("RGB")
    assert 전.size == 후.size
    for b in 빈칸들:
        상자 = (b.x0, b.y - 30, b.x1, b.y + 30)
        assert 전.crop(상자).tobytes() != 후.crop(상자).tobytes()


def test_정답은_빨간색으로_찍힌다(배부본, tmp_path):
    빈칸들 = find_bracket_pairs(배부본)
    out = draw_answers(배부본, 빈칸들, ["가", "나", "다", "라", "마", "바"], tmp_path / "채점용.png")
    후 = Image.open(out).convert("RGB")
    b = 빈칸들[0]
    화소들 = list(후.crop((b.x0, b.y - 30, b.x1, b.y + 30)).getdata())
    assert any(r > 150 and g < 110 and bl < 110 for r, g, bl in 화소들)


def test_좁은_빈칸에서는_글자가_줄어든다(tmp_path):
    """긴 정답이 좁은 칸을 넘어가면 괄호를 뭉개고 옆 글자를 덮는다."""
    넓은칸 = _문항이미지(tmp_path / "넓은.png", [(0, 0, "1. 가", 14, "이다.")])
    좁은칸 = _문항이미지(tmp_path / "좁은.png", [(0, 0, "1. 가", 4, "이다.")])
    for path, 답 in [(넓은칸, "단군왕검"), (좁은칸, "단군왕검")]:
        b = find_bracket_pairs(path)[0]
        out = draw_answers(path, [b], [답], path.with_name(f"채점_{path.stem}.png"))
        im = Image.open(out).convert("L")
        칸 = im.crop((b.x0 - 2, b.y - 40, b.x1 + 2, b.y + 40))
        어두운 = sum(1 for v in 칸.getdata() if v < 200)
        assert 어두운 > 0

    좁은b = find_bracket_pairs(좁은칸)[0]
    넓은b = find_bracket_pairs(넓은칸)[0]
    좁은글자 = draw_answers(좁은칸, [좁은b], ["단군왕검"], tmp_path / "c좁은.png")
    넓은글자 = draw_answers(넓은칸, [넓은b], ["단군왕검"], tmp_path / "c넓은.png")
    # 좁은 칸의 글자는 넓은 칸보다 작으므로 칠해진 화소가 적다
    def _칠해진(out, b):
        im = Image.open(out).convert("L")
        return sum(1 for v in im.crop((b.x0, b.y - 40, b.x1, b.y + 40)).getdata() if v < 200)
    assert _칠해진(좁은글자, 좁은b) < _칠해진(넓은글자, 넓은b)


def test_정답_글자가_괄호를_넘지_않는다(tmp_path):
    좁은칸 = _문항이미지(tmp_path / "좁은2.png", [(0, 0, "1. 가", 4, "이다.")])
    b = find_bracket_pairs(좁은칸)[0]
    out = draw_answers(좁은칸, [b], ["단군왕검"], tmp_path / "채점용.png")
    전 = Image.open(좁은칸).convert("RGB")
    후 = Image.open(out).convert("RGB")
    왼쪽바깥 = (max(0, b.x0 - 30), b.y - 30, b.x0 - 2, b.y + 30)
    오른쪽바깥 = (b.x1 + 2, b.y - 30, b.x1 + 30, b.y + 30)
    assert 전.crop(왼쪽바깥).tobytes() == 후.crop(왼쪽바깥).tobytes()
    assert 전.crop(오른쪽바깥).tobytes() == 후.crop(오른쪽바깥).tobytes()


def test_미리보기는_후보마다_번호를_붙인다(배부본, tmp_path):
    pairs = find_bracket_pairs(배부본)
    out = render_preview(배부본, pairs, tmp_path / "미리보기.png")
    assert out.exists()
    전 = Image.open(배부본).convert("RGB")
    후 = Image.open(out).convert("RGB")
    assert 전.size == 후.size
    assert 전.tobytes() != 후.tobytes()


def test_원본을_건드리지_않는다(배부본, tmp_path):
    원본 = Image.open(배부본).convert("RGB").tobytes()
    빈칸들 = find_bracket_pairs(배부본)
    draw_answers(배부본, 빈칸들, ["가", "나", "다", "라", "마", "바"], tmp_path / "채점용.png")
    render_preview(배부본, 빈칸들, tmp_path / "미리보기.png")
    assert Image.open(배부본).convert("RGB").tobytes() == 원본


def test_Blank_는_좌표를_그대로_들고_있다():
    b = Blank(x0=10, x1=90, y=50)
    assert (b.x0, b.x1, b.y) == (10, 90, 50)

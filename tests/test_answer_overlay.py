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
    render_preview,
    sort_reading_order,
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


def _굵은괄호(d, x, y, 높이=73, 폭=26):
    """실측에서 나온 굵은 괄호를 호로 그린다 (h=73 w=26, 비율 2.8).

    폰트로는 이 비율을 만들기 어렵다. stroke 를 주면 획이 뭉개져 곡률이 사라진다.
    """
    d.arc([x, y, x + 폭 * 2, y + 높이], start=90, end=270, fill=(0, 0, 0), width=8)


def _굵은닫는괄호(d, x, y, 높이=73, 폭=26):
    d.arc([x - 폭, y, x + 폭, y + 높이], start=270, end=90, fill=(0, 0, 0), width=8)


def test_굵게_그린_괄호도_찾는다(tmp_path):
    """배부본 디자인에 따라 괄호가 굵게 그려진다.

    실측 2026-09-09(8차시 백제): 괄호가 h=73 w=26 으로 세로:가로 비율이 2.8 이었다.
    비율 하한이 3.0 이던 동안 여섯 칸을 하나도 못 찾았다. 굵기는 배부본 디자인이
    정하므로, 비율을 빡빡하게 잡으면 이렇게 한 차시를 통째로 놓친다.
    """
    path = tmp_path / "굵은괄호.png"
    im = Image.new("RGB", (1800, 900), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for 열, 행 in [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]:
        x = 열 * 600 + 60
        y = 행 * 450 + 80
        _굵은괄호(d, x, y)
        _굵은닫는괄호(d, x + 240, y)
    im.save(path)

    pairs = find_bracket_pairs(path)
    assert len(pairs) == 6, f"굵은 괄호를 {len(pairs)}개만 찾았다"


def _빈칸그림(path, 자리들, 크기=(2752, 1536)):
    """(x, y) 자리마다 굵은 괄호 한 쌍을 그린다. 배부본 레이아웃을 흉내 낸다."""
    im = Image.new("RGB", 크기, (255, 255, 255))
    d = ImageDraw.Draw(im)
    for x, y in 자리들:
        d.arc([x, y, x + 52, y + 73], start=90, end=270, fill=(0, 0, 0), width=8)
        d.arc([x + 200, y, x + 252, y + 73], start=270, end=90, fill=(0, 0, 0), width=8)
    im.save(path)
    return path


def test_행_간격으로_읽기_순서를_세운다(tmp_path):
    """3열 2행. 왼쪽 위부터 오른쪽으로, 그다음 아랫줄."""
    자리 = [(400, 700), (1400, 760), (2300, 760), (100, 1380), (1150, 1380), (2260, 1380)]
    path = _빈칸그림(tmp_path / "3x2.png", 자리)
    순서 = sort_reading_order(find_bracket_pairs(path))
    assert len(순서) == 6
    assert [b.x0 for b in 순서[:3]] == sorted(b.x0 for b in 순서[:3])
    assert max(b.y for b in 순서[:3]) < min(b.y for b in 순서[3:])


def test_문항이_그림_아래에_있어도_행이_갈린다(tmp_path):
    """실측 2026-09-09(10차시): 문항 텍스트가 그림 아래에 있어 윗줄 y 가 787~849 였다.

    이미지를 위아래로 반 갈라 행을 정하면(경계 768) 여섯 칸이 전부 아랫행으로 몰려
    셀마다 하나만 남고 세 개를 잃는다. 행은 간격으로 갈라야 한다.
    """
    자리 = [(400, 750), (1400, 812), (2300, 812), (100, 1420), (1150, 1420), (2260, 1420)]
    path = _빈칸그림(tmp_path / "아래치우침.png", 자리)
    순서 = sort_reading_order(find_bracket_pairs(path))
    assert len(순서) == 6
    assert len({round(b.y / 300) for b in 순서}) == 2, "두 행으로 갈려야 한다"


def test_2열_3행도_읽기_순서가_맞는다(tmp_path):
    """실측 2026-09-09(8차시): 배부본이 2열 3행으로 나왔다. 열 수를 미리 알 수 없다."""
    자리 = [(300, 200), (1700, 400), (300, 760), (1600, 860), (200, 1330), (1700, 1330)]
    path = _빈칸그림(tmp_path / "2x3.png", 자리)
    순서 = sort_reading_order(find_bracket_pairs(path))
    assert len(순서) == 6
    ys = [b.y for b in 순서]
    assert ys == sorted(ys) or all(ys[i] <= ys[i + 1] + 120 for i in range(5))


def test_한_행만_있어도_왼쪽부터_센다(tmp_path):
    자리 = [(200, 700), (1200, 700), (2200, 700)]
    path = _빈칸그림(tmp_path / "한줄.png", 자리)
    순서 = sort_reading_order(find_bracket_pairs(path))
    assert [b.x0 for b in 순서] == sorted(b.x0 for b in 순서)

"""형성평가 배부본 PNG 의 빈칸에 정답을 얹어 채점용 한 장을 만든다.

배부본은 NotebookLM 인포그래픽이라 텍스트 레이어가 없다. 그래서 괄호를 픽셀로 찾는다.
세로로 길고 좁은 성분 중 **가운데가 한쪽으로 볼록한 것**만 괄호로 본다 — 한글의 세로획은
직선이라 이 조건에서 걸러진다.

왜 NotebookLM 으로 정답 버전을 따로 만들지 않는가 (2026-09-09 검토):
- 정답이 든 소스를 노트북에 올려야 해서 배부본에 정답이 샐 통로가 생긴다.
- 따로 생성하면 레이아웃이 달라져 답안지와 나란히 훑는다는 목적이 사라진다.
- 인포그래픽은 한 획 오타가 잦다. 채점 기준이 되는 종이에 그 위험을 들일 수 없다.
- 인포그래픽 생성이 차시당 2회에서 3회로 늘어 레이트리밋을 더 쓴다.

이 모듈은 다른 scripts/ 모듈을 import 하지 않는다. 정답은 문자열 목록으로 받는다.
원고에서 정답을 뽑는 일은 `quiz_to_html.parse_manuscript()` 가 이미 한다.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

정답색 = (211, 47, 47)
어두움 = 110

# 굵은 한글 폰트를 먼저 찾는다. 가는 폰트는 큰 화면에서 정답이 눈에 덜 띈다.
폰트후보 = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


@dataclass
class Blank:
    """빈칸 하나. x0·x1 은 괄호 **안쪽** 경계, y 는 글자 세로 중앙."""

    x0: int
    x1: int
    y: int


def find_font(size: int) -> ImageFont.FreeTypeFont:
    """한글 폰트를 찾는다. 없으면 멈춘다 — 폰트 없이 그리면 네모가 찍힌다."""
    for 경로 in 폰트후보:
        if Path(경로).exists():
            return ImageFont.truetype(경로, size)
    raise FileNotFoundError(
        "한글 폰트를 찾지 못했다. 다음 중 하나가 있어야 한다:\n  " + "\n  ".join(폰트후보)
    )


def _괄호모양(마스크: np.ndarray) -> str | None:
    """성분 하나가 '(' 인지 ')' 인지 가른다. 괄호가 아니면 None.

    괄호는 위·아래가 한쪽으로 굽고 가운데가 반대쪽으로 볼록하다.
    한글의 'ㅣ' 같은 세로획은 직선이라 이 차이가 나지 않는다.
    """
    h, w = 마스크.shape
    if h < 6 or w < 2:
        return None
    xs = np.tile(np.arange(w), (h, 1))

    def 무게중심(구간):
        칸 = 마스크[구간]
        if 칸.sum() == 0:
            return None
        return float(xs[구간][칸].mean())

    위 = 무게중심(slice(0, max(1, h // 5)))
    가운데 = 무게중심(slice(2 * h // 5, 3 * h // 5))
    아래 = 무게중심(slice(h - max(1, h // 5), h))
    if 위 is None or 가운데 is None or 아래 is None:
        return None

    끝 = (위 + 아래) / 2
    굽이 = 끝 - 가운데
    # 위와 아래가 같은 쪽에 있어야 괄호다. 대각선 획(ㅅ, ㄱ)은 한쪽으로만 흐른다.
    if abs(위 - 아래) > w * 0.55:
        return None
    if abs(굽이) < w * 0.22:
        return None
    return "(" if 굽이 > 0 else ")"


def _성분들(회색: np.ndarray):
    """세로로 길고 좁은 성분을 (모양, x0, x1, y0, y1) 로 돌려준다."""
    label, _ = ndimage.label(회색 < 어두움)
    나온것 = []
    for 조각 in ndimage.find_objects(label):
        ys, xs = 조각
        h = ys.stop - ys.start
        w = xs.stop - xs.start
        if not (30 <= h <= 110 and 3 <= w <= 34 and h >= 3.0 * w):
            continue
        모양 = _괄호모양(회색[ys, xs] < 어두움)
        if 모양:
            나온것.append((모양, xs.start, xs.stop, ys.start, ys.stop))
    return 나온것


def find_bracket_pairs(png_path, 최소폭: int = 55, 최대폭: int = 700) -> list[Blank]:
    """배부본에서 '( )' 쌍을 찾아 빈칸 목록을 돌려준다.

    같은 닫는 괄호를 여러 여는 괄호가 가리키면 **가장 좁은 쌍만** 남긴다.
    넓게 잡으면 앞 문장의 획을 여는 괄호로 오인한 쌍이 살아남는다.
    """
    회색 = np.array(Image.open(png_path).convert("L"))
    성분 = _성분들(회색)
    여는것 = [c for c in 성분 if c[0] == "("]
    닫는것 = [c for c in 성분 if c[0] == ")"]

    # 닫는 괄호를 x 순으로 봐야 여는 괄호에서 가장 가까운 짝이 먼저 걸린다.
    닫는것.sort(key=lambda c: c[1])

    # 키는 (x, y) 다. x 만 쓰면 같은 열의 윗줄과 아랫줄이 서로를 덮어쓴다.
    쌍들: dict[tuple[int, int], tuple[int, int, int]] = {}
    for _, ox0, ox1, oy0, oy1 in 여는것:
        oy = (oy0 + oy1) // 2
        for _, cx0, cx1, cy0, cy1 in 닫는것:
            cy = (cy0 + cy1) // 2
            간격 = cx0 - ox1
            if abs(cy - oy) > 25 or 간격 < 최소폭 or 간격 > 최대폭:
                continue
            키 = (cx0, cy0)
            기존 = 쌍들.get(키)
            if 기존 is None or ox1 > 기존[0]:
                쌍들[키] = (ox1, cx0, (oy + cy) // 2)
            break

    빈칸들 = [Blank(x0=a, x1=b, y=y) for a, b, y in 쌍들.values()]
    빈칸들.sort(key=lambda b: (b.y, b.x0))
    return 빈칸들


def pick_one_per_cell(pairs: list[Blank], rows: int, cols: int, size) -> list[Blank | None]:
    """이미지를 rows x cols 로 나누고 칸마다 빈칸 하나씩 골라 읽기 순서로 돌려준다.

    칸에 후보가 없으면 그 자리를 None 으로 남긴다. 조용히 개수를 줄이면
    4번 자리에 5번 답이 찍힌 채점용이 나오는데 아무도 모른다.
    후보가 여럿이면 가장 좁은 것을 고른다 — 넓은 쪽은 앞 문장까지 삼킨 오탐이다.
    """
    W, H = size
    칸폭 = W / cols
    칸높이 = H / rows
    바구니: dict[tuple[int, int], list[Blank]] = {}
    for b in pairs:
        cx = (b.x0 + b.x1) / 2
        열 = min(cols - 1, int(cx // 칸폭))
        행 = min(rows - 1, int(b.y // 칸높이))
        바구니.setdefault((행, 열), []).append(b)

    골라낸: list[Blank | None] = []
    for 행 in range(rows):
        for 열 in range(cols):
            후보 = 바구니.get((행, 열), [])
            골라낸.append(min(후보, key=lambda b: b.x1 - b.x0) if 후보 else None)
    return 골라낸


def _맞는크기(d: ImageDraw.ImageDraw, 글자: str, 폭: float) -> ImageFont.FreeTypeFont:
    크기 = 58
    while 크기 > 16:
        f = find_font(크기)
        l, _, r, _ = d.textbbox((0, 0), 글자, font=f)
        if r - l <= 폭:
            return f
        크기 -= 2
    return find_font(16)


def draw_answers(png_path, blanks: list[Blank | None], answers: list[str], out_path) -> Path:
    """빈칸 위에 정답을 빨간 글씨로 얹어 새 파일로 저장한다. 원본은 건드리지 않는다."""
    if len(blanks) != len(answers):
        raise ValueError(
            f"빈칸 {len(blanks)}개와 정답 {len(answers)}개가 맞지 않는다. "
            f"미리보기로 빈칸을 확인하거나 --blanks 로 직접 넘겨라."
        )
    빈자리 = [i + 1 for i, b in enumerate(blanks) if b is None]
    if 빈자리:
        raise ValueError(
            f"{', '.join(str(n) for n in 빈자리)}번 문항의 빈칸을 찾지 못했다. "
            f"그림과 겹친 괄호는 탐지가 놓친다. --blanks 로 그 칸의 좌표를 직접 넘겨라."
        )

    im = Image.open(png_path).convert("RGB")
    d = ImageDraw.Draw(im)
    for b, 답 in zip(blanks, answers):
        f = _맞는크기(d, 답, (b.x1 - b.x0) * 0.86)
        l, t, r, bo = d.textbbox((0, 0), 답, font=f)
        x = (b.x0 + b.x1) / 2 - (r - l) / 2 - l
        y = b.y - (bo - t) / 2 - t
        d.text((x, y), 답, fill=정답색, font=f)
    out = Path(out_path)
    im.save(out)
    return out


def render_preview(png_path, pairs: list[Blank], out_path) -> Path:
    """찾은 빈칸마다 테두리와 번호를 그린 미리보기. 사람이 이걸 보고 고른다."""
    im = Image.open(png_path).convert("RGB")
    d = ImageDraw.Draw(im)
    f = find_font(34)
    for i, b in enumerate(pairs, 1):
        if b is None:
            continue
        상자 = (b.x0, b.y - 34, b.x1, b.y + 34)
        d.rectangle(상자, outline=(0, 120, 255), width=4)
        d.text((b.x0 + 4, b.y - 70), f"{i}", fill=(0, 120, 255), font=f)
    out = Path(out_path)
    im.save(out)
    return out


def _좌표읽기(글: str) -> list[Blank]:
    빈칸들 = []
    for 조각 in 글.split(","):
        조각 = 조각.strip()
        if not 조각:
            continue
        부분 = 조각.split(":")
        if len(부분) != 3:
            raise ValueError(f"--blanks 는 'x0:x1:y' 를 쉼표로 잇는다. 잘못된 값: {조각}")
        x0, x1, y = (int(v) for v in 부분)
        빈칸들.append(Blank(x0=x0, x1=x1, y=y))
    return 빈칸들


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("배부본", type=Path, help="04_형성평가.png")
    parser.add_argument("--preview", type=Path, help="후보 미리보기만 만들고 끝낸다")
    parser.add_argument("--out", type=Path, help="채점용 산출 경로")
    parser.add_argument("--answers", help="정답을 쉼표로 이어 준다 (예: 고조선,비파형,8)")
    parser.add_argument("--blanks", help="탐지를 건너뛰고 좌표를 직접 준다 (x0:x1:y,...)")
    parser.add_argument("--rows", type=int, default=2, help="문항 배치 행 수 (기본 2)")
    parser.add_argument("--cols", type=int, default=3, help="문항 배치 열 수 (기본 3)")
    args = parser.parse_args()

    if args.blanks:
        빈칸들 = _좌표읽기(args.blanks)
    else:
        찾은것 = find_bracket_pairs(args.배부본)
        if args.preview:
            경로 = render_preview(args.배부본, 찾은것, args.preview)
            print(f"미리보기: {경로}  후보 {len(찾은것)}개")
            for i, b in enumerate(찾은것, 1):
                print(f"  {i}: {b.x0}:{b.x1}:{b.y}  폭 {b.x1 - b.x0}")
            return
        크기 = Image.open(args.배부본).size
        빈칸들 = pick_one_per_cell(찾은것, args.rows, args.cols, 크기)

    if args.preview:
        경로 = render_preview(args.배부본, [b for b in 빈칸들 if b], args.preview)
        print(f"미리보기: {경로}")
        return

    if not args.answers or not args.out:
        parser.error("--answers 와 --out 이 필요하다 (또는 --preview 만 쓴다)")
    정답들 = [a.strip() for a in args.answers.split(",")]
    경로 = draw_answers(args.배부본, 빈칸들, 정답들, args.out)
    print(f"저장: {경로}")


if __name__ == "__main__":
    main()

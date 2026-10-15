"""lesson-kit 웹 시제품 — 형성평가·개념정리를 원고 그대로 조판한다.

원고(00_원고/*.md)의 글자는 한 자도 바꾸지 않고 HTML 에 옮겨 찍는다. 그림은 images.json 이
자리마다 정한다 — 교과서에서 잘라 낸 그림(캡션은 교과서 캡션 그대로) 또는 글자 없는 AI 삽화.
AI 삽화에는 'AI 삽화' 표지를 붙인다.

    python render.py quiz    03_형성평가.md  images.json out_dir
    python render.py concept 04_개념정리.md  images.json out_dir

quiz 는 배부본(04_형성평가.png)과 채점용(04_형성평가_채점용.png)을 같은 HTML 에서 찍는다.
빈칸 너비를 정답 길이로 정하므로 두 장의 배치가 픽셀 단위로 같다.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATES = HERE / 'templates'
BLANK = re.compile(r'\(\s{2,}\)')
CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'


def parse_quiz(md):
    """`## 문항` 의 번호 문장과 `## 정답` 의 번호 답을 짝짓는다. 개수가 다르면 멈춘다."""
    title = re.search(r'^#\s+(.+)$', md, re.M).group(1).strip()
    q_part, _, a_part = md.partition('## 정답')
    questions = re.findall(r'^\d+\.\s+(.+)$', q_part.split('## 문항', 1)[1], re.M)
    answers = re.findall(r'^\d+\.\s+(.+)$', a_part, re.M)
    if len(questions) != len(answers):
        raise SystemExit(f'문항 {len(questions)}개, 정답 {len(answers)}개 — 개수가 다르다')
    for i, q in enumerate(questions, 1):
        if len(BLANK.findall(q)) != 1:
            raise SystemExit(f'{i}번 문항의 빈칸이 하나가 아니다: {q}')
    return title, [{'q': q.strip(), 'a': a.strip()} for q, a in zip(questions, answers)]


def parse_concept(md):
    title = re.search(r'^#\s+(.+)$', md, re.M).group(1).strip()
    sections = []
    for block in re.split(r'^##\s+', md, flags=re.M)[1:]:
        head, *lines = [l.strip() for l in block.strip().splitlines()]
        sections.append({'head': head, 'lines': [l for l in lines if l]})
    return title, sections


def figure(spec, cls=''):
    if not spec:
        return ''
    src = Path(spec['src']).resolve().as_uri()
    badge = '<span class="ai-badge">AI 삽화</span>' if spec.get('ai') else ''
    fit = ' contain' if spec.get('contain') else ''
    return f'<div class="fig{fit} {cls}"><img src="{src}" alt="">{badge}</div>'


def caption(spec):
    if spec and spec.get('caption'):
        return f'<div class="caption">{html.escape(spec["caption"])}</div>'
    return ''


def page(css, body):
    styles = ''.join((TEMPLATES / f).read_text(encoding='utf-8') for f in ('base.css', css))
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{styles}</style></head><body>{body}</body></html>'


def quiz_html(title, items, images):
    cards = []
    for i, it in enumerate(items, 1):
        width = max(5.5, len(it['a']) * 1.05 + 1.2)
        fill = (f'<span class="blank">(<span class="fill" style="width:{width:.1f}em">'
                f'{html.escape(it["a"])}</span>)</span>')
        before, after = BLANK.split(it['q'])
        q = html.escape(before) + fill + html.escape(after)
        cards.append(f'<div class="card"><div class="num">{i}</div><div class="body">'
                     f'<p class="q">{q}</p>{figure(images.get(f"q{i}"))}</div></div>')
    head = title.replace('형성평가:', '').strip()
    body = (f'<div class="page"><header><h1><span class="tag">형성평가</span>{html.escape(head)}</h1>'
            f'<div class="who">(<i></i>)학년 (<i></i>)반 이름:<i class="name"></i></div></header>'
            f'<div class="grid">{"".join(cards)}</div></div><div class="stamp">채점용</div>')
    return page('quiz.css', body)


def concept_html(title, sections, images, kicker):
    panels = []
    for i, s in enumerate(sections):
        last = i == len(sections) - 1
        lines = s['lines']
        chips = ''
        # 쉼표로 나열만 한 줄(자료 이름 등)은 칩으로 — 글자는 그대로
        if lines and ',' in lines[-1] and not lines[-1].endswith('다'):
            chips = '<div class="chips">' + ''.join(
                f'<span class="chip">{html.escape(c.strip())}</span>' for c in lines[-1].split(',')) + '</div>'
            lines = lines[:-1]
        items = ''.join(f'<li>{html.escape(l)}</li>' for l in lines)
        spec = images.get(s['head'])
        fig = f'<div class="figwrap">{figure(spec)}{caption(spec)}</div>' if spec else ''
        cls = f'panel p{i + 1} c{i % 5}' + (' remember' if last and s['head'] == '기억해요' else '')
        panels.append(f'<section class="{cls}"><h2>{html.escape(s["head"])}</h2><ul>{items}</ul>{chips}{fig}</section>')
    body = (f'<div class="page"><header><div class="kicker">{html.escape(kicker)}</div>'
            f'<h1>{html.escape(title)}</h1></header><div class="grid">{"".join(panels)}</div></div>')
    return page('concept.css', body)


def shoot(html_text, out_png, answers=False, scale=1.5):
    from playwright.sync_api import sync_playwright
    out_png = Path(out_png)
    tmp = out_png.with_suffix('.html')
    if answers:
        html_text = html_text.replace('<body>', '<body class="answers">', 1)
    tmp.write_text(html_text, encoding='utf-8')
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=scale)
        pg.goto(tmp.as_uri())
        pg.evaluate('document.fonts.ready')
        over = pg.evaluate("""[...document.querySelectorAll('.card,.panel')]
            .filter(e => e.scrollHeight > e.clientHeight + 2 || e.scrollWidth > e.clientWidth + 2).length""")
        pg.screenshot(path=str(out_png))
        b.close()
    print(f'{out_png.name}: {"OVERFLOW " + str(over) if over else "OK"}')


def main():
    kind, md_path, img_path, out = sys.argv[1:5]
    md = Path(md_path).read_text(encoding='utf-8')
    images = json.loads(Path(img_path).read_text(encoding='utf-8'))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if kind == 'quiz':
        title, items = parse_quiz(md)
        h = quiz_html(title, items, images)
        shoot(h, out / '04_형성평가.png')
        shoot(h, out / '04_형성평가_채점용.png', answers=True)
    else:
        title, sections = parse_concept(md)
        shoot(concept_html(title, sections, images, images.get('_kicker', '')), out / '05_개념정리.png')


if __name__ == '__main__':
    main()

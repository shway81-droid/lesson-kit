# lesson-kit

**초등 교과서 한 차시를 넣으면 수업에 바로 쓸 자료가 나온다.**

| 자료 | 수업에서 쓰는 자리 |
|---|---|
| 동기유발 영상 | 차시 도입 |
| 수업 슬라이드 | 판서 대체 |
| 형성평가 문제지·정답지 | 차시 마무리 확인 |
| 개념정리 | 정리·게시 |

디자인은 NotebookLM 이 하고, **내용이 교과서와 같은지는 사람과 코드가 확인한다.**
이 저장소의 절반은 그 확인 장치다. `SKILL.md` 가 전체 절차이고, 규칙마다 왜 그런지가
실측 근거와 함께 적혀 있다.

## 설치

Claude Code 스킬로 쓴다. 저장소를 스킬 폴더에 클론한다.

```bash
# 윈도우
git clone https://github.com/shway81-droid/lesson-kit.git "$USERPROFILE/.claude/skills/lesson-kit"
# 맥·리눅스
git clone https://github.com/shway81-droid/lesson-kit.git ~/.claude/skills/lesson-kit
```

의존성을 깐다.

```bash
pip install -r requirements.txt
playwright install chromium
notebooklm login          # 브라우저가 열린다. 구글 계정으로 로그인
notebooklm list           # 노트북 목록이 나오면 인증 성공
```

**윈도우에서는 모든 파이썬 실행에 `PYTHONUTF8=1` 을 붙인다.** 안 붙이면 한글 파일명과
출력이 깨진다.

동작을 확인한다.

```bash
PYTHONUTF8=1 python -m pytest -q
```

## 준비물

### 1. 교과서 PDF 와 진도표

`textbook/<학기>/` 에 학기별로 둔다. 출판사 저작물이라 저장소에 올리지 않는다
(`.gitignore` 가 `textbook/` 을 제외한다). 자세한 규칙은 `textbook/README.md`.

```
textbook/
  5-2/
    초_사회5-2(박기범)_교과서.pdf              학기 전체 한 파일
    초_사회5-2(박기범)_나이스업로드용진도표.xlsx   출판사 제공
```

진도표가 없어도 돌아가지만(표식 탐지로 차시 경계를 추정한다), 있으면 훨씬 정확하다.
출판사 자료실에서 "나이스 업로드용 진도표" 로 받을 수 있다.

### 2. 성취기준 데이터

`data/standards-elementary.json`(2022 개정 초등 611건)이 저장소에 들어 있다.
교육과정이 개정되면 다시 만든다.

```bash
PYTHONUTF8=1 python scripts/build_standards.py
```

## 한 차시 만들기

에이전트에게 차시를 말하면 `SKILL.md` 절차대로 진행한다.

> 사회 5-2 1단원 4차시 수업자료 만들어줘

절차는 5단계이고 **사람이 확인하는 지점이 두 곳**이다 — 차시 범위와 성취기준.

| 단계 | 하는 일 |
|---|---|
| 1 | 진도표에서 차시와 쪽 범위를 뽑아 교과서를 자른다 |
| 2 | 성취기준 후보를 뽑는다 |
| 3 | 원고 4개를 쓰고, 교과서에 없는 내용이 들어갔는지 검사한다 |
| 4 | NotebookLM 이 4종을 만든다 |
| 5 | 전수 대조하고 리포트를 남긴다 |

결과는 `output/<차시>/` 에 쌓인다. 파일 이름 규칙은 `SKILL.md` 의 「산출물 이름 규칙」.

## 먼저 알아 둘 것

**NotebookLM 은 내용을 바꾼다.** 고유명사를 다른 말로 바꾸고, 글자를 빠뜨리고, 없던 문장과
그림을 지어낸다. 그래서 5단계가 있다. **대조를 건너뛰면 이 도구는 쓰면 안 된다.**

**하루에 만들 수 있는 양이 제한된다.** 구글이 종류별로 생성 한도를 건다. 실측으로 슬라이드는
하루 3회쯤, 인포그래픽은 6회쯤에서 막혔고 몇 시간 뒤 풀렸다. 한 차시에 인포그래픽을 두 번
쓰므로 **하루 두세 차시**가 현실적인 한계다.

**교과서 사진은 들어가지 않는다.** NotebookLM 이 소스의 이미지를 읽지도, 생성물에 넣지도
못한다. 자기 삽화로 대체한다. 그림 자체가 학습 자료인 차시는 교과서를 따로 띄운다.

## 다른 과목·학년으로 옮길 때

성취기준 데이터가 초등 전 과목을 담고 있어 과목만 바꾸면 된다.

```bash
PYTHONUTF8=1 python scripts/find_standards.py --text "<차시 본문>" --subject 과학 --grade-group 초5-6
```

새 출판사 교과서를 넣으면 두 가지를 확인한다.

1. **쪽 번호 대응(`--offset`)** — 앞표지 장수가 책마다 다르다. `read_progress_plan.py --verify` 로
   차시 첫 쪽을 찍어 제목과 맞는지 눈으로 본다.
2. **차시 표식** — 진도표가 없을 때만 쓴다. 0건이 나오면 그 교과서의 표식을
   `split_lesson.py` 의 `LESSON_START_PATTERNS` 에 공백 없는 형태로 추가한다.

## 구조

```
SKILL.md                    전체 절차. 규칙마다 실측 근거가 붙어 있다
scripts/
  read_progress_plan.py     진도표(xlsx) → 차시 목록·쪽 범위
  split_semester.py         학기 전체를 차시별 PDF 로 일괄 분할
  split_lesson.py           차시 하나 자르기 / 표식으로 차시 시작 탐지
  find_standards.py         차시 본문 → 성취기준 후보 랭킹
  build_standards.py        성취기준 데이터 구축 (최초 1회)
  nblm_run.py               NotebookLM CLI 명령 조립·실행·재시도
  quiz_to_html.py           형성평가 원고 → 인쇄용 HTML
  html_to_pdf.py            HTML → PDF (정답 숨김 지원)
  verify_output.py          원고 대조 (누락·지어낸 문장·낱말 중복)
  retry_infographic.py      레이트리밋이 풀릴 때까지 기다렸다 생성
tests/                      위 스크립트의 테스트
data/standards-elementary.json
docs/superpowers/           설계 스펙과 구현 계획
```

## 라이선스와 출처

코드는 MIT 라이선스다.

`data/standards-elementary.json` 은 2022 개정 교육과정 성취기준을
[greatsong/k-curriculum-2022](https://github.com/greatsong/k-curriculum-2022) 에서 받아
초등 3개 학년군만 추린 것이다(611건). `scripts/build_standards.py` 로 언제든 다시 만들 수 있다.
원자료는 교육부 고시 문서다.

**교과서 PDF·진도표·생성된 수업자료는 출판사 저작물이다.** 저장소에 올리거나 배포하지 않는다.
`.gitignore` 가 `textbook/` 과 `output/` 을 제외한다. 각자 출판사 자료실에서 받아 쓴다.

## 기여

이 스킬은 실제 수업 준비에 쓰면서 만들었다. 규칙마다 "언제 무엇이 어떻게 실패했는지" 가
`SKILL.md` 에 근거로 붙어 있다. 새 교과서나 과목에서 다르게 동작하면 그 관찰을 이슈로
남겨 주면 좋겠다 — 특히 다음 셋이다.

- 진도표 열 이름이 다른 출판사
- `--offset` 이 1 이 아닌 교과서
- 차시 표식이 0건인 교과서 (`LESSON_START_PATTERNS` 에 추가가 필요하다)

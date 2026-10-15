# prototype — 형성평가·개념정리 직접 조판 시제품

NotebookLM 인포그래픽 대신 원고를 HTML 템플릿에 그대로 찍는다. 화면 글자가 진짜 글자라
오타가 생기지 않고, 배부본과 채점용이 같은 HTML 에서 나와 배치가 픽셀 단위로 같다.

그림 자리는 `images.json` 이 정한다.

- **교과서 그림** — 차시 PDF 에서 잘라 낸 그림. 캡션은 교과서 캡션 그대로 적는다.
- **AI 삽화** — 글자 없는 장면 그림. `"ai": true` 를 주면 오른쪽 아래에 `AI 삽화` 표지가 붙는다.
  형성평가 삽화는 답을 암시하지 않는 장면만 쓴다.

```bash
pip install playwright pymupdf
python render.py quiz    output/<차시>/00_원고/03_형성평가.md  quiz_images.json    out/
python render.py concept output/<차시>/00_원고/04_개념정리.md  concept_images.json out/
```

`quiz_images.json` 은 `{"q1": {"src": "...", "ai": true}, ...}`,
`concept_images.json` 은 절 제목을 키로 `{"영토를 넓히다": {"src": "...", "caption": "...", "contain": true}, "_kicker": "..."}`.

글꼴은 Pretendard 를 시스템에 설치해 두고 쓴다. 렌더 결과 첫 줄이 `OVERFLOW n` 이면 n 개 카드에서
글자가 넘친 것이다 — 원고를 줄이지 말고 템플릿 글자 크기·그림 크기를 고친다.

교과서 그림과 원고, 렌더 결과는 저장소에 올리지 않는다(출판사 저작물).

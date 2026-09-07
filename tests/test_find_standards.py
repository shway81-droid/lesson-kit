import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from find_standards import find_standards, normalize_subject, tokenize


@pytest.fixture
def 성취기준():
    return [
        {
            "code": "[6사04-01]",
            "subject": "사회(5~6학년)",
            "grade_group": "초5-6",
            "area": "영역",
            "content": "선사 시대와 고조선의 유적과 유물을 활용하여 당시 사람들의 생활을 추론한다.",
            "keywords": ["선사", "시대와", "고조선의", "유적과", "유물을"],
            "explanation": "해설",
            "application_notes": "고려사항",
        },
        {
            "code": "[6사01-01]",
            "subject": "사회(5~6학년)",
            "grade_group": "초5-6",
            "area": "영역",
            "content": "우리나라 산지, 하천, 해안 지형의 위치를 확인하고 지형의 분포 특징을 탐구한다.",
            "keywords": ["지형의", "우리나라", "산지", "하천", "해안"],
            "explanation": "해설",
            "application_notes": "고려사항",
        },
        {
            "code": "[4사01-01]",
            "subject": "사회(4학년)",
            "grade_group": "초3-4",
            "area": "영역",
            "content": "주변 여러 장소에서의 경험과 느낌을 다양한 방식으로 표현한다.",
            "keywords": ["주변", "여러", "장소에서의", "경험과", "느낌을"],
            "explanation": "해설",
            "application_notes": "고려사항",
        },
        {
            "code": "[6과01-01]",
            "subject": "과학",
            "grade_group": "초5-6",
            "area": "영역",
            "content": "고조선 시대의 과학 기술을 조사한다.",
            "keywords": ["고조선", "시대의", "과학", "기술을"],
            "explanation": "해설",
            "application_notes": "고려사항",
        },
    ]


def test_괄호가_붙은_과목명을_정규화한다():
    assert normalize_subject("사회(5~6학년)") == "사회"
    assert normalize_subject("실과(초등 5~6학년)") == "실과"
    assert normalize_subject("수학") == "수학"


def test_두글자_이상_한글만_토큰으로_잡는다():
    assert tokenize("고조선의 유물 3개") == {"고조선의", "유물"}


def test_과목이_다르면_제외한다(성취기준):
    결과 = find_standards("고조선", subject="사회", standards=성취기준)
    assert all(r["code"] != "[6과01-01]" for r in 결과)


def test_학년군으로_좁힌다(성취기준):
    결과 = find_standards("장소", subject="사회", grade_group="초3-4", standards=성취기준)
    assert [r["code"] for r in 결과] == ["[4사01-01]"]


def test_본문과_겹치는_성취기준이_먼저_온다(성취기준):
    본문 = "고조선을 세운 단군왕검 이야기와 청동기 유물을 살펴봅시다."
    결과 = find_standards(본문, subject="사회", standards=성취기준)
    assert 결과[0]["code"] == "[6사04-01]"
    assert 결과[0]["match_score"] > 0


def test_limit_만큼만_돌려준다(성취기준):
    assert len(find_standards("고조선", subject="사회", standards=성취기준, limit=2)) == 2


def test_조사가_붙은_성취기준도_찾는다(성취기준):
    # 실제 keywords 는 본문 앞 5단어를 조사째 자른 것이라 '고조선의' 로 들어 있다.
    # 정확한 표면형만 맞추면 '고조선' 으로 아무것도 못 찾고 점수 0 으로 밀린다.
    결과 = find_standards("고조선", subject="사회", standards=성취기준)
    assert 결과[0]["code"] == "[6사04-01]"
    assert 결과[0]["match_score"] > 0


def test_실제_데이터에서_점수가_붙은_후보가_나온다():
    # 후보는 limit 만큼 항상 채워지므로 '비어있지 않음' 만으로는
    # 채점기가 망가져도 통과한다. 1위와 점수를 함께 못박는다.
    본문 = "고조선을 세운 단군왕검과 청동기 시대 유물을 알아봅시다."
    결과 = find_standards(본문, subject="사회", grade_group="초5-6")
    assert 결과[0]["code"] == "[6사04-01]"
    assert 결과[0]["match_score"] > 0
    assert all(r["grade_group"] == "초5-6" for r in 결과)

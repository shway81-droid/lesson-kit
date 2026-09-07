import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_standards import extract_elementary, ELEMENTARY_GRADES


def _record(code, grade_group, school_level="초등학교", subject="사회(5~6학년)"):
    return {
        "code": code,
        "subject": subject,
        "grade_group": grade_group,
        "school_level": school_level,
        "area": "영역",
        "content": "본문",
        "keywords": ["가", "나"],
        "explanation": "해설",
        "application_notes": "고려사항",
        "군더더기필드": "버려져야 함",
    }


def test_초등_학년군만_남긴다():
    records = [
        _record("[6사04-01]", "초5-6"),
        _record("[4사01-01]", "초3-4"),
        _record("[2바01-01]", "초1-2"),
    ]
    assert len(extract_elementary(records)) == 3


def test_school_level이_초등학교여도_고공통은_버린다():
    # 업스트림 오염 레코드 65건이 이 형태다
    records = [
        _record("[10공영1-01-01]", "고공통", school_level="초등학교", subject="공통영어1·2"),
        _record("[6사04-01]", "초5-6"),
    ]
    result = extract_elementary(records)
    assert [r["code"] for r in result] == ["[6사04-01]"]


def test_필요한_필드만_남기고_코드순으로_정렬한다():
    records = [_record("[6사04-01]", "초5-6"), _record("[4사01-01]", "초3-4")]
    result = extract_elementary(records)
    assert [r["code"] for r in result] == ["[4사01-01]", "[6사04-01]"]
    assert set(result[0]) == {
        "code", "subject", "grade_group", "area",
        "content", "keywords", "explanation", "application_notes",
    }


def test_학년군_상수():
    assert ELEMENTARY_GRADES == ("초1-2", "초3-4", "초5-6")

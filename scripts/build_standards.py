"""2022 개정 교육과정 성취기준에서 초등 611건을 추려 data/standards-elementary.json 을 만든다.

출처: https://github.com/greatsong/k-curriculum-2022
      데이터 CC BY 4.0 / 코드 MIT

school_level 이 아니라 grade_group 으로 거른다. 업스트림에는
school_level 이 '초등학교' 인데 고등 과목인 레코드가 65건 섞여 있다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

UPSTREAM = "https://github.com/greatsong/k-curriculum-2022.git"
ELEMENTARY_GRADES = ("초1-2", "초3-4", "초5-6")
KEEP_FIELDS = (
    "code", "subject", "grade_group", "area",
    "content", "keywords", "explanation", "application_notes",
)


def extract_elementary(records: list[dict]) -> list[dict]:
    """초등 학년군 레코드만 남기고 필요한 필드만 추려 코드순으로 정렬한다."""
    out = [
        {key: record.get(key) for key in KEEP_FIELDS}
        for record in records
        if record.get("grade_group") in ELEMENTARY_GRADES
    ]
    out.sort(key=lambda record: record["code"])
    return out


def clone_upstream(dest: Path) -> Path:
    """업스트림을 얕게 복제하고 standards.json 경로를 돌려준다.

    curl 은 이 환경에서 GitHub raw 에 SSL 오류를 내므로 git clone 을 쓴다.
    """
    subprocess.run(
        ["git", "clone", "--depth", "1", "-q", UPSTREAM, str(dest)],
        check=True,
    )
    return dest / "data" / "standards.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="업스트림 standards.json 경로. 생략하면 임시 디렉터리에 복제한다.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "standards-elementary.json",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        source = args.source or clone_upstream(Path(tmp) / "upstream")
        records = json.loads(Path(source).read_text(encoding="utf-8"))

    elementary = extract_elementary(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(elementary, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(elementary)}건 -> {args.out}")


if __name__ == "__main__":
    main()

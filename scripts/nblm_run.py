"""NotebookLM CLI 명령을 조립하고 실행한다.

한 노트북에 교과서 차시 PDF 와 원고 3개가 함께 들어간다. 슬라이드만 교과서를 소스로 쓰고
나머지는 원고를 쓰므로, 생성마다 -s 로 소스를 하나만 지정해야 섞이지 않는다.

형성평가 정답지는 여기를 거치지 않는다. `scripts/quiz_to_html.py` 가 원고를 바로 조판한다.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# 종류 -> 소스 파일명, 생성 고정 옵션, 다운로드 고정 옵션
#
# --length short 는 어디에도 쓰지 않는다. 압축을 유발해 장수가 줄어든다.
#
# **quiz 는 쓰지 않는다.** 형성평가 문항과 정답은 `03_형성평가.md` 에 이미 확정되어 있어서
# 조판만 하면 되고, NotebookLM 을 거치면 잃는 것만 있었다(실측 2026-09-07):
# 빈칸 문장을 의문문으로 바꿨고, 원고에 없는 4지선다 오답과 해설을 지어냈고,
# 레이트리밋을 한 번 더 썼다. 지금은 `scripts/quiz_to_html.py` 가 원고를 바로 조판한다.
#
# supports_format: 다운로드 하위 명령에 `--format` 이 있는지.
#   slide-deck(pdf|pptx) 에만 있다. video/infographic 에 붙이면 거부된다.
#   `--language` 와 `--force` 는 남은 세 종류 모두 지원하므로 조건 없이 붙인다.
ARTIFACTS: dict[str, dict] = {
    "video": {
        "source": "01_동기유발.md",
        "generate_args": ["--format", "brief", "--style", "classic"],
        "download_args": [],
        "supports_format": False,
    },
    "slide-deck": {
        # 교과서 차시 PDF 를 소스로 준다. 원고를 쓰지 않는다.
        "source": "01_차시.pdf",
        "generate_args": ["--format", "detailed"],
        "download_args": [],
        "supports_format": True,
    },
    "infographic": {
        # 형성평가 배부본과 개념정리 두 곳에 쓰인다. 소스는 호출부가 -s 로 지정한다.
        "source": "04_개념정리.md",
        "generate_args": ["--style", "instructional", "--detail", "standard"],
        "download_args": [],
        "supports_format": False,
    },
}


def source_for(kind: str) -> str:
    return ARTIFACTS[kind]["source"]


def build_generate_command(
    kind: str,
    prompt: str,
    notebook_id: str,
    source_id: str,
    language: str = "ko",
    retry: int = 3,
) -> list[str]:
    spec = ARTIFACTS[kind]
    return [
        "notebooklm", "generate", kind, prompt,
        "--notebook", notebook_id,
        "-s", source_id,
        *spec["generate_args"],
        "--language", language,
        "--retry", str(retry),
        "--json",
    ]


def build_download_command(
    kind: str,
    out_path: Path,
    notebook_id: str,
    fmt: str | None = None,
    artifact_id: str | None = None,
    force: bool = False,
) -> list[str]:
    """다운로드 명령을 만든다.

    fmt 를 주면 그 형식으로 받는다(슬라이드를 pptx 로 받는 통로). 안 주면 CLI 기본값이다.

    artifact_id 를 주면 `-a` 로 그 아티팩트만 받는다. 안 주면 CLI 는 **완료된 것 중
    최신**을 받는다 — 재생성 직후에는 새 것이 아직 pending 이라 이전 훼손본을
    조용히 다시 받는다(실측: 슬라이드·인포그래픽 재생성에서 모두 그랬다).
    재생성 흐름에서는 반드시 준다.

    force 는 같은 이름의 파일이 있을 때 덮어쓴다. 안 주면 CLI 가 `이름 (2).pdf` 로
    옆에 저장해서 대조 대상이 갈린다.
    """
    spec = ARTIFACTS[kind]
    if fmt is not None and not spec["supports_format"]:
        raise ValueError(f"{kind} 다운로드에는 --format 옵션이 없다")
    format_args = ["--format", fmt] if fmt is not None else list(spec["download_args"])
    select_args = ["-a", artifact_id] if artifact_id else []
    force_args = ["--force"] if force else []
    return [
        "notebooklm", "download", kind, str(out_path),
        *format_args,
        *select_args,
        *force_args,
        "--notebook", notebook_id,
    ]


# Google 인증서 체인 검증이 간헐적으로 `EE certificate key too weak` 로 실패한다.
# 항상은 아니고 즉시 재시도하면 대부분 통과한다. 다운로드가 여기서 죽으면
# 45분 걸린 생성물을 못 받는다. (실측: 인포그래픽 다운로드 1회차 실패, 2회차 성공)
# `artifact wait` 는 같은 원인으로 "Connection failed calling LIST_ARTIFACTS" 를 낸다.
#
# 예전에는 **재시도할 오류를 문구로 나열**했는데, 그 방식이 두 번 새어 나갔다.
#   ① `RPC LIST_ARTIFACTS failed` 가 사유 없이 빈 줄로 끝나 목록에 안 걸렸다(2026-09-04).
#   ② `--json` 을 붙이면 CLI 가 오류를 **stdout 에 JSON 으로** 내고 stderr 를 비운다.
#      그래서 stderr 검사에 아예 안 걸렸다(2026-09-09: `notebooklm create` 가 재시도 없이 죽었다.
#      실제 출력은 `{"error": true, "code": "ERROR", "message": "[SSL: ...key too weak]"}`).
#      `message` 가 빈 `ERROR` 로만 오는 간헐 실패도 있었다(`source add`).
#
# 그래서 판정을 뒤집었다. **다시 보내도 결과가 같은 것만 즉시 포기하고, 나머지는 재시도한다.**
# 알 수 없는 오류를 만나면 재시도가 기본값이어야 45분짜리 생성물을 잃지 않는다.
#   - 인자 오류: 잘못된 옵션을 세 번 보내도 결과는 같다.
#   - 레이트리밋: 재시도가 한도만 더 태운다. 5~10분 뒤 바깥에서 다시 요청한다.
#     `CREATE_ARTIFACT` 실패는 사유가 안 붙어도 레이트리밋으로 본다 — `-v` 없이는
#     구분이 안 되는데, 아니었을 때 한 번 더 안 보내는 손해보다 한도를 태우는 손해가 크다.
즉시포기 = (
    "Usage:",
    "No such",
    "Error: Invalid",
    "RATE_LIMITED",
    "rate limited",
    "CREATE_ARTIFACT",
)


def run(cmd: list[str], retries: int = 3, wait_seconds: float = 15.0) -> str:
    """명령을 실행하고 stdout 을 돌려준다. 실패하면 예외를 던진다.

    간헐 실패는 wait_seconds 간격으로 retries 번 다시 시도한다.
    인자 오류와 레이트리밋만 바로 던진다 — 다시 보내도 결과가 같다.

    판정에 stdout 과 stderr 를 **함께** 본다. `--json` 모드에서는 오류가 stdout 으로
    나오고 stderr 가 비어 있어서, stderr 만 보면 재시도해야 할 오류를 놓친다.
    """
    for attempt in range(1, retries + 1):
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            return result.stdout
        출력 = (result.stdout or "") + (result.stderr or "")
        if any(marker in 출력 for marker in 즉시포기) or attempt == retries:
            raise RuntimeError(f"{' '.join(cmd)}\n{출력.strip()}")
        time.sleep(wait_seconds)
    raise AssertionError("unreachable")


def artifact_status(artifact_id: str, notebook_id: str) -> str:
    """아티팩트 하나의 현재 상태를 돌려준다.

    응답이 목록 형태가 아니면 'unknown' — 조회가 흔들린 것이지 없는 게 아니다.
    목록은 멀쩡한데 그 안에 없으면 'missing'.

    이 둘을 가르지 않으면 오류 JSON(`{"error": true, ...}`)에 artifacts 키가 없다는
    이유로 'missing' 이 되고, 호출부가 멀쩡히 생성 중인 산출물을 즉시 실패로 버린다
    (실측 2026-09-09).
    """
    응답 = run(["notebooklm", "artifact", "list", "--notebook", notebook_id, "--json"])
    try:
        listing = json.loads(응답)
    except json.JSONDecodeError:
        return "unknown"
    if not isinstance(listing, dict) or "artifacts" not in listing:
        return "unknown"
    for artifact in listing["artifacts"]:
        if artifact["id"] == artifact_id:
            return artifact["status"]
    return "missing"


def wait_for_artifact(
    artifact_id: str,
    notebook_id: str,
    timeout_seconds: float = 3600.0,
    interval_seconds: float = 20.0,
) -> str:
    """완료될 때까지 목록을 폴링한다. 완료 상태를 돌려주고, 못 끝내면 예외를 던진다.

    `notebooklm artifact wait` 를 쓰지 않는 이유: 그 명령은 자기 `--timeout` 에 걸리면
    **stderr 없이 비정상 종료**한다(실측 2026-09-07). 그러면 호출부에서 "아직 안 끝남" 과
    "진짜 실패" 를 구분할 수 없어, 5분이면 끝날 생성을 기다리다 그대로 놓친다.
    목록 폴링은 상태 문자열이 그대로 보여서 그 구분이 된다.
    """
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    안보인횟수 = 0
    while True:
        try:
            status = artifact_status(artifact_id, notebook_id)
            last_error = None
        except RuntimeError as error:
            # 조회 한 번 실패로 포기하지 않는다. CLI 가 오류 문구도 없이 실패하는 일이
            # 잦아서(실측 2026-09-07: artifact list 가 빈 stderr 로 rc=1), 한 번 걸릴 때마다
            # 생성물을 놓치게 된다. 계속 실패하면 deadline 이 잡아 준다.
            last_error = error
            status = "unknown"
        if status == "completed":
            return status
        if status in ("failed", "error"):
            raise RuntimeError(f"아티팩트가 완료되지 못했다: {artifact_id} ({status})")
        # 생성 직후에는 목록에 아직 안 뜬다. 한 번 못 봤다고 포기하면 45분짜리를 버린다.
        if status == "missing":
            안보인횟수 += 1
            if 안보인횟수 >= 3:
                raise RuntimeError(f"아티팩트가 목록에 계속 없다: {artifact_id} (missing)")
        else:
            안보인횟수 = 0
        if time.monotonic() >= deadline:
            꼬리 = f" 마지막 조회 오류: {last_error}" if last_error else ""
            raise RuntimeError(
                f"아티팩트가 {timeout_seconds:.0f}초 안에 끝나지 않았다: "
                f"{artifact_id} ({status}).{꼬리}"
            )
        time.sleep(interval_seconds)


def run_json(cmd: list[str]) -> dict:
    return json.loads(run(cmd))

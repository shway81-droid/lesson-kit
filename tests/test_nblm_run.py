import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from nblm_run import (
    ARTIFACTS,
    build_download_command,
    build_generate_command,
    source_for,
)


def test_세_종류만_다룬다():
    # quiz 는 뺐다. 형성평가는 원고를 quiz_to_html.py 가 바로 조판한다.
    assert set(ARTIFACTS) == {"video", "slide-deck", "infographic"}


def test_quiz는_더_이상_없다():
    # 남아 있으면 누군가 다시 호출해 원고에 없는 4지선다와 해설을 끌어온다
    assert "quiz" not in ARTIFACTS
    with pytest.raises(KeyError):
        build_generate_command("quiz", "p", "nb", "src")


def test_슬라이드의_소스는_교과서_pdf다():
    # 원고가 아니라 교과서를 준다. 원고 경로보다 교과서 문장에 충실했다(실측 2026-09-07).
    assert source_for("slide-deck") == "01_차시.pdf"
    assert source_for("video") == "01_동기유발.md"


@pytest.mark.parametrize("kind", sorted(ARTIFACTS))
def test_모든_생성_명령이_소스를_하나로_묶는다(kind):
    # -s 가 없으면 슬라이드 생성이 형성평가 원고까지 읽어 내용이 섞인다
    cmd = build_generate_command(kind, "프롬프트", "nb123", "src456")
    assert "-s" in cmd
    assert cmd[cmd.index("-s") + 1] == "src456"


@pytest.mark.parametrize("kind", sorted(ARTIFACTS))
def test_모든_생성_명령이_재시도와_json을_지정한다(kind):
    # --retry 와 --json 은 세 종류 모두 지원한다
    cmd = build_generate_command(kind, "프롬프트", "nb123", "src456")
    assert cmd[cmd.index("--retry") + 1] == "3"
    assert "--json" in cmd


@pytest.mark.parametrize("kind", sorted(ARTIFACTS))
def test_모두_한국어를_지정한다(kind):
    # 남은 세 종류는 --language 를 모두 지원한다
    cmd = build_generate_command(kind, "프롬프트", "nb123", "src456")
    assert cmd[cmd.index("--language") + 1] == "ko"


@pytest.mark.parametrize("kind", sorted(ARTIFACTS))
def test_length_short는_절대_쓰지_않는다(kind):
    # --length short 는 압축을 유발해 슬라이드 장수가 줄어든다
    assert "short" not in build_generate_command(kind, "p", "nb", "src")


def test_영상은_brief_형식이다():
    cmd = build_generate_command("video", "p", "nb", "src")
    assert cmd[cmd.index("--format") + 1] == "brief"


def test_슬라이드는_detailed_형식이다():
    cmd = build_generate_command("slide-deck", "p", "nb", "src")
    assert cmd[cmd.index("--format") + 1] == "detailed"


def test_프롬프트가_종류_바로_뒤에_온다():
    cmd = build_generate_command("infographic", "한 장으로 만들어라", "nb", "src")
    assert cmd[:4] == ["notebooklm", "generate", "infographic", "한 장으로 만들어라"]


def test_슬라이드_다운로드는_형식을_지정하지_않으면_pdf다(tmp_path):
    cmd = build_download_command("slide-deck", tmp_path / "s.pdf", "nb123")
    assert "--format" not in cmd
    assert str(tmp_path / "s.pdf") in cmd


def test_슬라이드를_pptx로도_받을_수_있다(tmp_path):
    # download slide-deck --format [pdf|pptx]. 편집 가능한 사본을 받는 통로다.
    cmd = build_download_command("slide-deck", tmp_path / "s.pptx", "nb123", fmt="pptx")
    assert cmd[cmd.index("--format") + 1] == "pptx"
    assert str(tmp_path / "s.pptx") in cmd


@pytest.mark.parametrize("kind", ["video", "infographic"])
def test_형식을_지원하지_않는_종류에_fmt를_주면_거부한다(kind, tmp_path):
    # download video / infographic 에는 --format 옵션이 없다.
    # 조용히 붙여 보내면 실제 CLI 가 rc=2 로 거부한다.
    with pytest.raises(ValueError):
        build_download_command(kind, tmp_path / "out", "nb123", fmt="pdf")


def test_ssl_오류는_재시도하고_다른_오류는_바로_던진다(monkeypatch):
    import nblm_run

    calls = []

    class 결과:
        def __init__(self, rc, err):
            self.returncode, self.stdout, self.stderr = rc, "ok", err

    def 가짜_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return 결과(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate key too weak")
        return 결과(0, "")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda s: None)
    assert nblm_run.run(["notebooklm", "download"]) == "ok"
    assert len(calls) == 2

    calls.clear()
    monkeypatch.setattr(nblm_run.subprocess, "run", lambda cmd, **k: 결과(2, "Error: No such option"))
    with pytest.raises(RuntimeError):
        nblm_run.run(["notebooklm", "download"])
    # 인자 오류는 한 번만 보낸다


def test_다운로드에_아티팩트_id와_덮어쓰기를_붙일_수_있다():
    # id 없이 받으면 완료된 것 중 최신이라, 재생성 직후엔 이전 훼손본을 다시 받는다
    cmd = build_download_command("slide-deck", Path("a.pdf"), "nb", artifact_id="art1", force=True)
    assert cmd[cmd.index("-a") + 1] == "art1"
    assert "--force" in cmd


def test_아티팩트_id를_안_주면_옵션이_붙지_않는다():
    cmd = build_download_command("video", Path("a.mp4"), "nb")
    assert "-a" not in cmd
    assert "--force" not in cmd


def test_wait의_연결_실패도_재시도한다(monkeypatch):
    import nblm_run

    calls = []

    class 결과:
        def __init__(self, rc, err):
            self.returncode, self.stdout, self.stderr = rc, "ok", err

    def 가짜_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return 결과(1, "RPC LIST_ARTIFACTS failed: Connection failed calling LIST_ARTIFACTS")
        return 결과(0, "")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda s: None)
    assert nblm_run.run(["notebooklm", "artifact", "wait", "x"]) == "ok"
    assert len(calls) == 2


def test_빈_사유의_RPC_실패도_재시도한다(monkeypatch):
    # `RPC LIST_ARTIFACTS failed after 0.112s:` 처럼 사유가 안 붙고 끝날 때가 있다.
    # 이걸 못 잡으면 완료를 기다리던 아티팩트를 그대로 놓친다.
    from types import SimpleNamespace
    import nblm_run

    호출 = []

    def 가짜_run(cmd, **kwargs):
        호출.append(cmd)
        if len(호출) == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr="ERROR RPC LIST_ARTIFACTS failed after 0.112s: \n")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    assert nblm_run.run(["notebooklm", "artifact", "wait", "a"]) == "ok"
    assert len(호출) == 2


def test_레이트리밋은_재시도하지_않는다(monkeypatch):
    # CREATE_ARTIFACT 실패는 레이트리밋이다. 재시도하면 한도만 더 태운다.
    from types import SimpleNamespace
    import nblm_run

    호출 = []

    def 가짜_run(cmd, **kwargs):
        호출.append(cmd)
        return SimpleNamespace(returncode=1, stdout="", stderr="ERROR RPC CREATE_ARTIFACT failed after 0.9s\n")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError):
        nblm_run.run(["notebooklm", "generate", "slide-deck"])
    assert len(호출) == 1


def _가짜_목록(status):
    import json as _json
    return _json.dumps({"artifacts": [{"id": "a1", "status": status, "type_id": "slide_deck"}]})


def test_완료될_때까지_폴링한다(monkeypatch):
    import nblm_run

    상태들 = iter(["pending", "pending", "completed"])
    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: _가짜_목록(next(상태들)))
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    assert nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0) == "completed"


def test_실패한_아티팩트는_기다리지_않고_멈춘다(monkeypatch):
    # 계속 기다리면 timeout 까지 붙잡혀 있는다
    import nblm_run

    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: _가짜_목록("failed"))
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="완료되지 못했다"):
        nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0)


def test_목록에_없으면_멈춘다(monkeypatch):
    # id 를 잘못 넘겼는데 조용히 timeout 까지 기다리면 원인을 못 찾는다
    import json as _json
    import nblm_run

    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: _json.dumps({"artifacts": []}))
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="missing"):
        nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0)


def test_시간_초과하면_예외로_끝난다(monkeypatch):
    # 조용히 돌려주면 호출부가 미완성 아티팩트를 받으러 간다
    import nblm_run

    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: _가짜_목록("pending"))
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="끝나지 않았다"):
        nblm_run.wait_for_artifact("a1", "nb", timeout_seconds=0, interval_seconds=0)


def test_조회가_한_번_실패해도_계속_기다린다(monkeypatch):
    # CLI 가 오류 문구도 없이 실패하는 일이 잦다. 한 번 걸릴 때마다 포기하면
    # 5분이면 끝날 생성물을 매번 놓친다.
    import nblm_run

    호출 = {"n": 0}

    def 가짜_run(*a, **k):
        호출["n"] += 1
        if 호출["n"] == 1:
            raise RuntimeError("notebooklm artifact list\n")
        return _가짜_목록("completed")

    monkeypatch.setattr(nblm_run, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    assert nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0) == "completed"
    assert 호출["n"] == 2


def test_계속_실패하면_마지막_오류를_알려_준다(monkeypatch):
    # 'unknown 상태로 시간 초과' 만 나오면 왜 못 봤는지 알 수 없다
    import nblm_run

    def 가짜_run(*a, **k):
        raise RuntimeError("RPC LIST_ARTIFACTS 계속 실패")

    monkeypatch.setattr(nblm_run, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="계속 실패"):
        nblm_run.wait_for_artifact("a1", "nb", timeout_seconds=0, interval_seconds=0)


@pytest.mark.parametrize("kind", sorted(ARTIFACTS))
def test_force와_아티팩트_지정이_함께_붙는다(kind):
    cmd = build_download_command(kind, Path("out"), "nb", artifact_id="a1", force=True)
    assert "--force" in cmd
    assert cmd[cmd.index("-a") + 1] == "a1"


# --json 모드에서 CLI 는 오류를 stdout 에 JSON 으로 낸다. stderr 는 비어 있다.
# 실측 2026-09-09: 이것 때문에 notebooklm create 가 재시도 없이 죽었다.
JSON_SSL_오류 = (
    '{"error": true, "code": "ERROR", '
    '"message": "[SSL: CERTIFICATE_VERIFY_FAILED] certificate key too weak"}'
)
JSON_빈_오류 = '{"error": true, "code": "ERROR", "message": ""}'


class _결과:
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_json_모드의_ssl_오류는_stdout에_있어도_재시도한다(monkeypatch):
    """stderr 만 보면 재시도해야 할 오류를 즉시 실패로 던진다."""
    import nblm_run

    calls = []

    def 가짜_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            return _결과(1, out=JSON_SSL_오류, err="")
        return _결과(0, out="ok")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)
    assert nblm_run.run(["notebooklm", "create", "차시", "--json"]) == "ok"
    assert len(calls) == 2


def test_사유가_빈_오류도_재시도한다(monkeypatch):
    """message 가 빈 'ERROR' 도 간헐 실패였다(실측: source add)."""
    import nblm_run

    calls = []

    def 가짜_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) < 3:
            return _결과(1, out=JSON_빈_오류, err="")
        return _결과(0, out="ok")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)
    assert nblm_run.run(["notebooklm", "source", "add", "a.md", "--json"]) == "ok"
    assert len(calls) == 3


def test_인자_오류는_stdout에_있어도_바로_던진다(monkeypatch):
    """잘못된 인자를 세 번 보내도 결과는 같다. 재시도는 시간만 버린다."""
    import nblm_run

    calls = []

    def 가짜_run(cmd, **kwargs):
        calls.append(cmd)
        return _결과(2, out="Usage: notebooklm download [OPTIONS]", err="")

    monkeypatch.setattr(nblm_run.subprocess, "run", 가짜_run)
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError):
        nblm_run.run(["notebooklm", "download", "--없는옵션"])
    assert len(calls) == 1


def test_오류_메시지에_stdout도_담는다(monkeypatch):
    """stderr 만 담으면 --json 모드 실패는 빈 메시지가 되어 원인을 알 수 없다."""
    import nblm_run

    monkeypatch.setattr(
        nblm_run.subprocess, "run", lambda cmd, **k: _결과(2, out="Usage: 어쩌고", err="")
    )
    with pytest.raises(RuntimeError, match="Usage"):
        nblm_run.run(["notebooklm", "download"], retries=1)


def test_조회가_흔들리면_missing이_아니라_unknown이다(monkeypatch):
    """오류 JSON 에는 artifacts 키가 없다. 그걸 '목록에 없음' 으로 읽으면
    멀쩡히 생성 중인 산출물을 즉시 실패로 버린다."""
    import nblm_run

    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: JSON_SSL_오류)
    assert nblm_run.artifact_status("a1", "nb") == "unknown"


def test_정상_응답에_없으면_missing이다(monkeypatch):
    """응답 형식이 멀쩡한데 목록에 없는 것은 진짜 없는 것이다."""
    import nblm_run

    monkeypatch.setattr(nblm_run, "run", lambda *a, **k: '{"artifacts": [{"id": "다른것", "status": "completed"}]}')
    assert nblm_run.artifact_status("a1", "nb") == "missing"


def test_조회가_한두_번_흔들려도_기다린다(monkeypatch):
    """생성 직후에는 목록에 아직 안 뜬다. 한 번 못 봤다고 포기하면 45분짜리를 버린다."""
    import nblm_run

    상태들 = iter(["unknown", "missing", "pending", "completed"])
    monkeypatch.setattr(nblm_run, "artifact_status", lambda *a: next(상태들))
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)
    assert nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0) == "completed"


def test_계속_목록에_없으면_결국_실패로_본다(monkeypatch):
    """영영 안 나타나는 것을 끝없이 기다리지는 않는다."""
    import nblm_run

    monkeypatch.setattr(nblm_run, "artifact_status", lambda *a: "missing")
    monkeypatch.setattr(nblm_run.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="missing"):
        nblm_run.wait_for_artifact("a1", "nb", interval_seconds=0)

"""인포그래픽 레이트리밋이 풀릴 때까지 기다렸다가 만든다.

여러 차시가 밀려 있으면 한 번에 하나씩, 앞의 것이 끝나야 다음을 요청한다.
동시에 요청하면 풀린 한도를 둘이 나눠 쓰다 둘 다 다시 막힌다.

stdout 한 줄 = 이벤트. 성공·비레이트리밋 오류·최종 포기만 출력한다.
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, "scripts")
from nblm_run import build_generate_command, build_download_command, run, wait_for_artifact

용어_기본 = ""


def attempt(prompt, notebook, source):
    """('ok', id) | ('rate', '') | ('ssl', '') | ('err', 메시지)"""
    cmd = build_generate_command("infographic", prompt, notebook, source, retry=0)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    blob = (r.stdout or "") + (r.stderr or "")
    if "RATE_LIMITED" in blob:
        return "rate", ""
    if "CERTIFICATE_VERIFY_FAILED" in blob or "certificate key too weak" in blob:
        return "ssl", ""
    if r.returncode != 0:
        return "err", blob[-300:]
    return "ok", json.loads(r.stdout)["task_id"]


def make(이름, notebook, source, prompt, out_path, tries=60):
    for i in range(1, tries + 1):
        kind, payload = attempt(prompt, notebook, source)
        if kind == "ok":
            print(f"ACCEPTED {이름} {payload} (시도 {i})", flush=True)
            wait_for_artifact(payload, notebook, timeout_seconds=2700, interval_seconds=20)
            run(build_download_command("infographic", out_path, notebook,
                                       artifact_id=payload, force=True),
                retries=12, wait_seconds=20)
            print(f"SUCCESS {이름} → {out_path}", flush=True)
            return True
        if kind == "err":
            print(f"ERROR {이름}: {payload}", flush=True)
            return False
        time.sleep(15 if kind == "ssl" else 600)
    print(f"GIVEUP {이름}: 레이트리밋이 풀리지 않았다", flush=True)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path,
                        help="작업 목록 JSON. [{이름, notebook, source, prompt, out}] 순서대로 만든다")
    args = parser.parse_args()
    작업들 = json.loads(args.plan.read_text(encoding="utf-8"))
    for 작업 in 작업들:
        make(작업["이름"], 작업["notebook"], 작업["source"], 작업["prompt"], Path(작업["out"]))
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()

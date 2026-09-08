"""배포본과 다른 파일로 돌고 있으면 **스스로 최신본을 받아 재기동**한다.

## 왜 (사용자 결정 2026-09-02)

낡음 판정은 **지문 완전 일치**를 그대로 둔다(사용자 선택). 그 판정은 정확하지만, 러너 파일은
거의 모든 배포에서 바뀌므로 러너와 **무관한 배포 하나가** 접속 중인 모든 러너를 낡음으로
뒤집는다. 그 사실을 조치 요구로 화면에 내보내면 하루에 몇 번씩 「업데이트 필요」가 뜨는데
사용자가 할 일은 없다.

그래서 엄격함은 그대로 두고 **조치를 자동화**한다 — GitHub Actions 셀프호스티드 러너가
러너 애플리케이션을 기본 자동 업데이트하는 것과 같은 형태다. 화면은 이 러너가 자기 갱신을
할 줄 안다고 신고하면 낡음을 조치 요구로 그리지 않는다.

## 규율 — 이 파일이 지키는 것

1. **개발 트리에서는 절대 동작하지 않는다.** 모듈로 실행 중이면(`agent/` 패키지) 자기 자신을
   교체한다는 개념 자체가 성립하지 않는다. 지금 도는 것이 **배포된 단일 파일**임을 지문으로
   확인한 뒤에만 진행한다.
2. **서버가 준 URL 을 쓰지 않는다.** 내려받는 곳은 이 파일의 고정 상수다. 하트비트 응답의
   `download_url` 을 그대로 따르면, 응답을 바꿀 수 있는 누구든 러너가 실행할 파일을 지목할
   수 있게 된다(러너는 그 파일을 **자기 자신으로 교체하고 실행한다** — 최고 권한의 경로다).
3. **받은 것을 검사한 뒤에만 교체한다.** 비어 있거나 파이썬으로 파싱되지 않으면 버린다.
   교체는 같은 디렉토리 임시 파일 → `os.replace` 로 원자적으로 한다(중간에 죽어도 반쪽
   파일이 남지 않는다).
4. **바뀌는 것이 없으면 재기동하지 않는다.** 받은 payload 의 지문이 지금 나와 같으면 그냥
   둔다 — 이 한 줄이 「배포본을 못 따라잡는 러너가 영원히 재기동하는」 고리를 끊는다.
5. **일하는 중에는 갱신하지 않는다.** 진행 중인 답변을 죽여 가며 최신이 될 이유가 없다.
   유휴가 될 때까지 미룬다(다음 하트비트가 다시 알려 준다).
6. **실패가 러너를 죽이지 않는다.** 못 받았거나 못 썼으면 있던 파일로 계속 돈다.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
from contextlib import contextmanager

#: 내려받을 곳. **고정이다** — 서버 응답의 값을 쓰지 않는다(모듈 docstring 규율 2).
SELF_UPDATE_PATH = "/static/agent/bridge_agent.py"

#: 자기 갱신 시도의 최소 간격(초). 배포가 몰리는 날 러너가 재기동을 반복하지 않도록 하는
#: 바닥이다. 규율 4(지문이 같으면 재기동 안 함)가 무한 고리를 이미 막지만, 그것은 «같을 때»의
#: 방어이고 이쪽은 «계속 다를 때»의 방어다 — 둘은 다른 실패를 막는다.
SELF_UPDATE_MIN_INTERVAL_SEC = 120.0

#: 받기 상한(초). 갱신은 급한 일이 아니므로 짧게 끊고 다음 기회를 기다린다.
SELF_UPDATE_FETCH_TIMEOUT_SEC = 30.0

#: 받아 온 파일이 이보다 작으면 러너일 리 없다 — 오류 페이지·잘린 응답을 걸러낸다.
SELF_UPDATE_MIN_BYTES = 20000

# 부모가 새 프로세스의 종료까지 책임지는 경우의 재기동 인계 계약.
SUPERVISED_UPDATE_EXIT = 75


@contextmanager
def agent_install_lock(path: str, timeout: float = 10.0):
    """교체되는 inode가 아닌 고정 sidecar를 잠근다. 락 파일은 삭제하지 않는다."""
    with open(path + ".install.lock", "a+b") as lock:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("runner install lock timeout") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def agent_digest(payload: bytes) -> str:
    """`_self_build()` 와 **같은 방식**의 지문 12자. 두 곳이 다른 방식을 쓰면 대조가 무의미해진다."""
    return hashlib.sha256(payload).hexdigest()[:12]


def running_bundle_path(self_build: str) -> str | None:
    """지금 도는 것이 **배포된 단일 파일**이면 그 경로, 아니면 `None`.

    판정은 경로 모양이 아니라 **지문 일치**로 한다: `sys.argv[0]` 이 가리키는 파일의 지문이
    이 프로세스가 신고하는 지문과 같아야 한다.

    ⚠ 이 검사가 이 모듈에서 가장 중요한 한 줄이다. 개발 트리에서는 `_self_build()` 가
    `agent/events.py` 의 지문을 돌려주므로 배포본과 **영원히** 다르다 — 경로만 보고 진행하면
    러너가 개발자의 소스 파일을 배포본으로 덮어쓴다.
    """
    if not self_build:
        return None
    try:
        path = os.path.realpath(sys.argv[0] or "")
    except Exception:  # noqa: BLE001
        return None
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            if agent_digest(f.read()) != self_build:
                return None
    except Exception:  # noqa: BLE001
        return None
    return path


def fetch_deployed_agent(base: str, ca: str | None,
                   timeout: float = SELF_UPDATE_FETCH_TIMEOUT_SEC) -> bytes | None:
    """배포 중인 러너 파일을 받아 **검사까지 마친** 바이트열. 하나라도 어긋나면 `None`.

    신뢰 앵커는 기동 때 정해진 `base`·`ca` 그대로다 — 이 함수는 그것을 새로 정하지 않는다.
    """
    base = str(base or "").rstrip("/")
    if not base.lower().startswith("https://"):
        # 평문으로는 받지 않는다. 이 파일은 다음 순간 **실행될** 것이다.
        return None
    try:
        import ssl
        import urllib.request

        ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
        req = urllib.request.Request(base + SELF_UPDATE_PATH, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if int(getattr(resp, "status", 0) or 0) != 200:
                return None
            payload = resp.read()
    except Exception:  # noqa: BLE001  (네트워크·TLS·타임아웃 — 못 받으면 그냥 안 바꾼다)
        return None
    if not payload or len(payload) < SELF_UPDATE_MIN_BYTES:
        return None
    try:
        import ast

        ast.parse(payload)
    except (SyntaxError, ValueError):
        # 파이썬이 아니다(로그인 페이지·프록시 오류 본문 등). 이걸 실행하면 러너가 죽는다.
        return None
    return payload


def install_agent_file(path: str, payload: bytes) -> bool:
    """같은 디렉토리 임시 파일에 쓰고 `os.replace` 로 갈아 끼운다. 권한은 원본을 따른다.

    같은 디렉토리를 쓰는 이유: `os.replace` 의 원자성은 **같은 파일시스템** 안에서만 보장된다.
    `/tmp` 에 쓰고 옮기면 파일시스템이 갈릴 수 있고, 그때는 복사 중 죽으면 반쪽 파일이 남는다.
    """
    directory = os.path.dirname(path) or "."
    tmp_path = ""
    try:
        mode = os.stat(path).st_mode & 0o777
    except Exception:  # noqa: BLE001
        mode = 0o600
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".bridge_agent.", suffix=".new", dir=directory)
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, mode)
        with agent_install_lock(path):
            # 형제가 이미 같은 배포본을 설치했어도 호출자는 재기동해야 한다.
            # 재교체만 생략하여 Windows의 실행 파일 읽기와 불필요한 경합을 줄인다.
            try:
                with open(path, "rb") as current:
                    same = current.read() == payload
            except FileNotFoundError:
                same = False
            if same:
                os.unlink(tmp_path)
            else:
                os.replace(tmp_path, path)
        return True
    except Exception:  # noqa: BLE001  (권한·디스크 — 못 쓰면 있던 파일 그대로 돈다)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return False


def reexec_self(path: str) -> None:
    """같은 인자로 자기 자신을 다시 실행한다. 성공하면 **돌아오지 않는다**.

    환경(토큰 `BRIDGE_TOKEN`)과 열린 파일 기술자는 그대로 넘어간다 — 런처가 stderr 를
    로그 파일로 이어 두었다면 새 프로세스도 같은 파일에 이어 쓴다.
    """
    if os.environ.get("DQA_RUNNER_SUPERVISED") == "1":
        raise SystemExit(SUPERVISED_UPDATE_EXIT)
    argv = [sys.executable, path, *sys.argv[1:]]
    if os.name == "nt":
        import subprocess

        # Windows CRT execv는 argv를 직접 인용하지 않는다(공백 설치 경로 포함).
        argv = [subprocess.list2cmdline([arg]) for arg in argv]
    os.execv(sys.executable, argv)

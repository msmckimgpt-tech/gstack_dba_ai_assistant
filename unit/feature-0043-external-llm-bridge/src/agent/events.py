"""사건 코드(안정 계약)·버전 지문·동의 정규화.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request

# ── 사건 코드 (안정 계약) ─────────────────────────────────────────────────────
#
# 조사 스크립트·감사가 의존하는 이름이다. 문장은 자유롭게 고쳐도 되지만 이 값은 계약이므로
# 바꿀 때는 소비처를 함께 본다. 접두사가 곧 계층이다:
#
#   run.*    프로세스 수명        conn.*  서버 연결·인증
#   caps.*   능력 신고            hb.*    하트비트
#   task.*   질문 한 건의 일생     ai.*    로컬 AI CLI 호출
#   api.*    서버 호출 실패        log.*   로그층 자신
_EV_RUN_START = "run.start"
_EV_RUN_READY = "run.ready"
_EV_RUN_STOP = "run.stop"
_EV_RUN_FATAL = "run.fatal"
_EV_CONN_OK = "conn.ok"
_EV_CONN_FAIL = "conn.fail"
_EV_CONN_UNAUTH = "conn.unauthorized"
_EV_CONN_RETRY = "conn.retry"
_EV_HB_FAIL = "hb.fail"
_EV_HB_UNAUTH = "hb.unauthorized"
_EV_HB_STALE = "hb.stale_build"
#: 같은 계정에 최신 러너가 붙어서 이 러너가 물러나는 사건 (TASK-20260901T173000).
_EV_HB_SUPERSEDED = "hb.superseded"
#: 스스로 최신본으로 갈아 끼우고 재기동하는 사건 (TASK-20260902T140000).
#: 세 갈래를 **한 코드**로 남긴다 — 갱신했다 / 못 했다 / 지금은 미룬다(작업 중).
_EV_SELFUPDATE = "run.selfupdate"
_EV_TASK_CLAIM_SKIP = "task.claim.skip"
_EV_TASK_CLAIM_FAIL = "task.claim.fail"
_EV_TASK_DISPATCH = "task.dispatch"
_EV_TASK_UNMET = "task.unmet"
_EV_TASK_CANCEL = "task.cancel"
_EV_TASK_REVIEW = "task.review"
_EV_TASK_SUBMIT_OK = "task.submit.ok"
_EV_TASK_SUBMIT_RETRY = "task.submit.retry"
_EV_TASK_SUBMIT_FAIL = "task.submit.fail"
_EV_TASK_SUBMIT_REJECT = "task.submit.reject"
_EV_AI_FAIL = "ai.fail"
_EV_AI_TIMEOUT = "ai.timeout"
_EV_AI_SPAWN_FAIL = "ai.spawn_fail"
_EV_API_FAIL = "api.fail"


#: 평문이 허용되는 유일한 대상. 이름이 아니라 **호스트**로 판정한다.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


#: 이 러너의 버전. 서버가 콘솔 작업 배급 자격의 **2차 조건**으로 쓴다(1차는 기능 신고).
#:
#: 왜 둘 다인가: 기능 이름만 보면 신고 **형식**이 바뀐 뒤에도 구 러너가 자격을 유지한다.
#: 버전은 그 형식 변경을 표현할 수 있는 유일한 축이다. 서버의 하한은
#: `shared/bridge_tasks.RUNNER_MIN_AGENT_VERSION` — 여기 값이 그보다 낮으면 콘솔 작업이
#: 배급되지 않고, 하트비트 응답의 `runner_update` 가 그 사실을 말한다.
AGENT_VERSION = "2026.09.01"


def _self_build() -> str:
    """이 **파일 자체**의 지문 12자. 못 읽으면 빈 문자열.

    `AGENT_VERSION` 만으로는 부족하다 (사용자 제보 2026-08-31). 날짜 단위라 **같은 날 여러 번
    배포된 러너가 전부 같은 버전**이 된다 — 실제로 그날 러너가 세 번 바뀌었고, 사용자는
    「재설치했는데 목록이 그대로」를 봤다. 서버는 자기가 배포 중인 `static/agent/bridge_agent.py`
    의 지문을 알고 있으므로, 이 값을 비교하면 "정확히 그 파일인가" 를 판정할 수 있다.

    버전(호환성 축)과 지문(동일성 축)은 다른 질문에 답한다 — 그래서 둘 다 싣는다.
    """
    try:
        import hashlib

        with open(__file__, "rb") as _f:
            return hashlib.sha256(_f.read()).hexdigest()[:12]
    except Exception:  # noqa: BLE001  (읽기 실패·경로 부재 — 모르면 빈 값)
        return ""


def _self_os() -> str:
    """이 러너가 도는 **명령 계열**: `"windows"` 또는 `"posix"` (2026-09-01).

    왜 서버가 이걸 알아야 하는가: 연결 화면의 1단계는 붙여넣을 명령을 OS 별로 나눠 보여 주는데,
    종전에는 그 기본 선택을 **브라우저**(`navigator.platform`)로 정했다. 그런데 브라우저가 도는
    OS 와 러너가 도는 OS 는 **같지 않다** — WSL 안에서 러너를 띄우는 사용자는 Windows 브라우저로
    화면을 보므로, 항상 PowerShell 명령이 먼저 뽑혀 매번 탭을 바꿔야 했다(제보 2026-09-01).

    러너가 자기 계열을 신고하면 그 값이 「마지막으로 연결된 OS」가 되고, 화면은 추측 대신
    **실제로 연결됐던 쪽**을 먼저 보여 준다. PowerShell 명령으로 다시 등록하면 그 신고가 곧
    `windows` 라 화면도 따라 바뀐다.

    `sys.platform` 이 아니라 `os.name` 을 보는 이유: 우리가 가르려는 것은 배포판이 아니라
    **어느 명령문이 통하는가** 이고, 그 축에서 WSL 은 리눅스다(`os.name == "posix"`).
    """
    try:
        return "windows" if os.name == "nt" else "posix"
    except Exception:  # noqa: BLE001  (판정 불가 — 모르면 빈 값. 화면은 종전 추측으로 돌아간다)
        return ""


#: 이 러너가 다룰 줄 아는 작업 종류.
#:
#: `console_jobs` — 관리 콘솔 작업(대화가 아닌 프롬프트 한 덩어리). 신고하지 않으면 서버가
#:   배급하지 않는다. 신고 없이 받으면 대화용 프레이밍으로 감싸 산출물이 조용히 망가진다.
#: `batch_jobs` — 배경 배치까지 받겠다는 **별도 동의**. 기본 포함이 아니다: 그 작업은 이
#:   사람이 요청한 적 없고 자기 계정 토큰을 태운다. 이제 동의는 **웹에서 켠다**(하트비트
#:   응답의 `batch_consent`) — `--batch`/`--no-batch` 는 이 머신의 명시 override 로 남는다.
#: `self_review` — 답변 초안을 자기가 5축으로 검증할 줄 안다. **자격이 아니라 관측 축**이라
#:   기본 포함이다: 신고하지 않으면 콘솔이 「검증할 줄 모르는 러너」와 「검증했는데 통과」를
#:   구분하지 못하고, 구분하지 못하면 운영자는 전자를 후자로 읽는다. 실제 수행 여부는
#:   서버 설정(`REDTEAM_ENABLED`)이 정하며 `--no-self-review` 로 이 머신에서 끌 수 있다.
#: `self_update` — 배포본과 다른 파일로 돌고 있으면 **스스로 받아 재기동**할 줄 안다
#:   (TASK-20260902T140000). 이것도 자격이 아니라 **화면이 무엇을 말할지 정하는 축**이다:
#:   신고하면 낡음은 곧 스스로 풀리므로 화면이 조치를 요구하지 않고, 신고가 없으면 종전대로
#:   「업데이트 필요」와 되돌아갈 명령을 보여 준다. `--no-self-update` 로 끄면 신고도 빠진다 —
#:   끈 러너를 「할 줄 안다」로 신고하면 화면이 오지 않을 갱신을 기다리게 된다.
AGENT_FEATURES: tuple[str, ...] = ("console_jobs", "self_review", "self_update")

#: 배경 배치 동의의 기능 이름. 서버 `shared/bridge_consent.BATCH_FEATURE` 와 같은 값이어야 한다.
BATCH_FEATURE = "batch_jobs"


def normalize_consent(value: object) -> bool:
    """서버가 준 동의 값을 bool 로 굳힌다. **모르면 False**(남의 토큰을 태우는 축).

    ⚠ 이 함수는 서버 `shared/bridge_consent.normalize_consent` 의 **거울**이다. 러너는
    사용자 머신에 홀로 놓이는 단일 파일이라 그 모듈을 import 할 수 없다. 이음매 테스트가
    두 구현을 같은 입력표로 돌려 대조한다 — 손으로 맞춰 둔 두 구현은 한쪽만 고쳐지는 날
    조용히 갈리고, 그 갈림은 양쪽을 각각 검사하는 테스트로는 보이지 않는다.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return False
    return text in {"1", "true", "yes", "on", "t", "y"}


def apply_consent(base_features, *, server_consent, local_override=None) -> tuple:
    """신고할 `features` 를 만든다 — `shared/bridge_consent.apply_consent` 의 **거울**.

    `local_override`: `True`=`--batch`(이 머신에서 명시 허용) · `False`=`--no-batch`(이 머신만
    예외) · `None`=지시 없음(서버 값을 따른다). override 가 서버 값을 **양방향으로** 이긴다.
    """
    feats = [str(f) for f in (base_features or []) if str(f) and str(f) != BATCH_FEATURE]
    want = normalize_consent(server_consent) if local_override is None else bool(local_override)
    if want:
        feats.append(BATCH_FEATURE)
    return tuple(feats)


def _batch_override_from_args(args) -> "bool | None":
    """`--batch` / `--no-batch` 를 3-값 override 로 읽는다. 지시가 없으면 `None`.

    둘 다 준 경우는 **끄는 쪽**을 택한다. 모순된 지시에서 남의 계정 사용량을 태우는 방향으로
    기우는 것은 근거가 없다 — argparse 의 상호배타(`add_mutually_exclusive_group`)를 쓰지 않는
    이유는, 옛 온보딩 명령이 `--batch` 를 달고 있는 사람이 새 스크립트를 덧붙였을 때 러너가
    **기동조차 못 하는** 것보다 조용히 안전한 쪽을 고르는 편이 낫기 때문이다.
    """
    if getattr(args, "no_batch", False):
        return False
    if getattr(args, "batch", False):
        return True
    return None


def _transport_is_safe(base: str) -> bool:
    """토큰을 이 주소로 보내도 되는가. https, 또는 진짜 loopback 만 참.

    접두 문자열 비교(`startswith("http://127.0.0.1")`)로는 안 된다 — userinfo 와 서브도메인이
    통과한다: `http://127.0.0.1@evil.example` 의 실제 호스트는 `evil.example` 이고,
    `http://127.0.0.1.evil.example` 도 마찬가지다. 둘 다 토큰을 평문으로 남의 서버에 보낸다.
    URL 을 **파싱해서 hostname 을 본다** — urllib 이 접속할 때 쓰는 것과 같은 값이다.
    """
    try:
        parts = urllib.parse.urlsplit(str(base or ""))
    except Exception:  # noqa: BLE001
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    if parts.scheme == "http":
        return (parts.hostname or "").lower() in _LOOPBACK_HOSTS
    return False

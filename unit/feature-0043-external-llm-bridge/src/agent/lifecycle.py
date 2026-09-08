"""수명주기 — 점유 해제·하트비트·드레인·`main`.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import atexit
import os
import shlex
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .api import Api
from .base import _AI_TIMEOUT_SEC, _CANCEL_TICK_SEC, _DEFAULT_MAX_WORKERS, _DEFAULT_WORKERS, _DEFAULT_WORKER_IDLE_SEC, _MAX_STALLED_ROUNDS, _WAIT_TIMEOUT_SEC
from .cancel import CancelRegistry
from .caps import (_CREATION_SOURCES, baseline_index, confirm_ai_or_report,
                   resolve_caps, sanitize_caps)
from .conf import load_conf, save_conf
from .discovery import _no_ai_message, pick_ai, client_runtime_selection
from .events import AGENT_FEATURES, AGENT_VERSION, BATCH_FEATURE, _EV_AI_FAIL, _EV_CONN_FAIL, _EV_CONN_OK, _EV_CONN_RETRY, _EV_CONN_UNAUTH, _EV_HB_FAIL, _EV_HB_STALE, _EV_HB_SUPERSEDED, _EV_HB_UNAUTH, _EV_RUN_FATAL, _EV_SELFUPDATE, _EV_RUN_READY, _EV_RUN_START, _EV_RUN_STOP, _EV_TASK_CANCEL, _EV_TASK_CLAIM_FAIL, _EV_TASK_CLAIM_SKIP, _EV_TASK_SUBMIT_FAIL, _EV_TASK_SUBMIT_OK, _batch_override_from_args, _self_build, _transport_is_safe, apply_consent
from .handler import handle_one
from .events import RUNNING_BUNDLE_PATH
from .identity import init_runner_instance
from .invoke import _ensure_strict_mcp_supported
from .logs import _RUN_T0, _STATS, _audit_path, _human_log_path, _log, _log_exc, log_event
from .pool import ActiveTasks, WorkerPool
from .runtimes import _RUNTIME_SPECS
from .selfupdate import (SELF_UPDATE_MIN_INTERVAL_SEC, agent_digest,
                         fetch_deployed_agent, install_agent_file, reexec_self)
from .state import ai_health, note_ai_outcome, note_ai_unusable, note_ai_probing, prev_runner_instance, runner_instance
from .timing import _CAPS_BASELINE_WAIT_SEC, _CAPS_RETRY_BACKOFF_SEC, _CAPS_RETRY_CEILING_SEC, _CAPS_RETRY_CEILING_SHOWING_SEC, _DRAINING_RETRY_FLOOR_SEC, _HEARTBEAT_INTERVAL_SEC, _HEARTBEAT_MIN_INTERVAL_SEC, _HEARTBEAT_NUDGE_POLL_SEC, _RECONNECT_BACKOFF_MAX, _RECONNECT_BACKOFF_START, _SHUTDOWN_GRACE_SEC

# ── 메인 ─────────────────────────────────────────────────────────────────────


#: 종료 시 자기 점유를 놓아 줄 대상. 전역인 이유: `atexit`·시그널 핸들러는 인자를 받지 않고,
#: main 의 지역 변수에 닿을 방법이 없다.
_ACTIVE_API: "Api | None" = None


def release_own_claims_on_exit() -> None:
    """이 프로세스가 종료한다 — **붙들고 있던 질문을 대기열로 돌려놓는다**.

    ## 왜 필요한가 (TASK-20260901T140000)

    다음 기동의 사망 신고(`prev_runner_instance()`)만으로도 회수는 된다. 그러나 그것은 **누군가
    러너를 다시 켤 때까지** 기다린다는 뜻이고, 그 사이 질문은 lease(30분)가 끝날 때까지 아무
    러너에게도 보이지 않는다 — 같은 계정에 **다른 머신의 러너가 붙어 있어도** 그렇다.
    종료하는 쪽이 스스로 놓으면 그 창이 사라진다.

    ## 왜 best-effort 인가

    `SIGKILL`·전원 차단·크래시에서는 이 코드가 돌지 않는다. 그것이 바로 다음 기동의 사망
    신고가 필요한 이유다 — 두 경로는 **대체가 아니라 보완**이다. 여기서 실패해도 조용히
    넘어간다: 종료 중에 예외를 올리면 사용자가 보는 것은 회수 실패가 아니라 종료 스택이다.

    타임아웃을 짧게 두는 이유: 서버가 죽어 있으면 종료가 그만큼 늦어지고, 사용자는 Ctrl+C 가
    먹지 않는다고 읽는다. 5초 안에 못 닿으면 다음 기동의 신고에 맡긴다.
    """
    api = _ACTIVE_API
    if api is None or not runner_instance():
        return
    try:
        # `runtimes=None` 으로 부른다 — 종료하면서 능력 목록을 다시 신고할 이유가 없고,
        # `[]` 를 보내면 서버가 "고를 것 없음" 으로 읽어 화면의 모델 목록을 지운다.
        res = api.heartbeat(None, timeout=5.0, released_instances=[runner_instance()])
        n = len(res.get("released_claims") or [])
        if n:
            _log(f"종료 — 처리 중이던 질문 {n}건을 대기열로 돌려놨습니다"
                 f"(러너를 다시 켜면 곧바로 이어서 처리합니다).")
    except Exception:  # noqa: BLE001  (종료 경로 — 무엇이든 조용히 넘어간다)
        pass


#: `run.stop` 을 두 번 찍지 않기 위한 빗장. 종료 경로가 여럿이라(정상 반환·Ctrl+C·SIGTERM →
#: atexit) 각자 찍으면 원장에 종료가 두 번 나오고, 그러면 「러너가 두 번 죽었나」로 읽힌다.
_RUN_STOPPED = threading.Event()

#: **같은 계정**에 더 나중에 연결된 러너가 붙어서, 이 러너가 물러나야 한다는 서버 판정
#: (TASK-20260901T183000, 사용자 결정 2026-09-01 — 「연결된 계정에서 다른 신규 러너에 연결되는
#: 부분이 확인된다면 오래된 러너는 프로세스를 종료 … 계정이 다를 경우는 예외」).
#:
#: 왜 Event 인가: 이 사실을 아는 것은 하트비트 스레드이고, 물러날 수 있는 것은 대기 루프다
#: (진행 중 작업을 마치고 끝내는 절차가 거기 있다). 스레드에서 곧바로 죽이면 처리 중이던
#: 답변이 통째로 사라진다 — 로그아웃 종료가 이미 같은 이유로 `shutdown_after_drain` 을 쓴다.
#:
#: ⚠ **계정이 다르면 이 신호는 오지 않는다.** 서버 판정이 `AccountId` 로 묶여 있어, 한 머신에서
#:   서로 다른 계정으로 러너를 여럿 띄우는 구조는 그대로 허용된다(사용자 결정 2026-09-01).
_SUPERSEDED = threading.Event()

#: 서버가 「이 러너는 배포본과 다른 파일이다」라고 알려 왔다 (TASK-20260902T140000).
#:
#: `_SUPERSEDED` 와 같은 이유로 Event 다 — 아는 것은 하트비트 스레드이고, **자기를 갈아 끼우고
#: 다시 뜰 수 있는 것은 대기 루프**다(진행 중 작업이 없음을 그곳이 안다). 갱신하겠다고 답변
#: 중인 자식 AI 를 죽이면, 사용자는 최신 러너를 얻는 대신 방금 던진 질문을 잃는다.
_SELF_UPDATE = threading.Event()

#: 마지막 자기 갱신 **시도** 시각(monotonic). 배포가 몰리는 날 재기동이 연달아 일어나지
#: 않게 하는 바닥이다. `0.0` = 아직 시도한 적 없음.
_SELF_UPDATE_LAST = [0.0]

#: 능력 협상이 지금 돌고 있는가. 자기갱신이 이 값을 보고 미룬다 (codex R4 P2-9) — 협상은
#: `ActiveTasks` 에 잡히지 않는 배경 스레드이고 자식 CLI 를 최대 240초 붙들기 때문에,
#: 「유휴」로 오판해 `os.execv` 하면 그 질의가 통째로 버려진다.
_CAPS_NEGOTIATING: list = [False]

#: 이 실행이 자기 갱신을 할 수 있는가 — `main()` 이 실제 능력(단일 파일로 도는가)과 사용자
#: 선택(`--no-self-update`)을 함께 판정해 세운다. 신고(`self_update` feature)와 **같은 값**이다:
#: 못 하면서 신고하면 화면이 오지 않을 갱신을 기다린다.
_SELF_UPDATE_OK = [False]
_SELF_UPDATE_BUNDLE = [RUNNING_BUNDLE_PATH]


def _log_run_stop(reason: str = "exit") -> None:
    """이 세션이 **무엇을 했는지** 한 줄로 닫는다. 여러 번 불러도 한 번만 남는다.

    집계는 `log_event` 가 사건 코드별로 모아 둔 것을 그대로 쓴다 — 따로 세지 않으므로
    새 사건이 생겨도 요약에서 빠지지 않는다. 사람 줄에는 핵심 셋(처리·실패·오류)만,
    원장에는 전체 표를 싣는다.
    """
    if _RUN_STOPPED.is_set():
        return
    _RUN_STOPPED.set()
    tally = {k: v for k, v in _STATS.items() if not k.startswith("_")}
    log_event(_EV_RUN_STOP, "브리지 러너 종료", reason=reason,
              uptime_sec=int(time.monotonic() - _RUN_T0),
              submitted=_STATS.get(_EV_TASK_SUBMIT_OK, 0),
              failed=(_STATS.get(_EV_TASK_SUBMIT_FAIL, 0) + _STATS.get(_EV_AI_FAIL, 0)),
              errors=_STATS.get("_errors", 0),
              tally=tally)


def _arm_exit_release(api: Api) -> None:
    """종료 경로 세 갈래(정상 반환·Ctrl+C·SIGTERM)를 모두 자기 해제로 모은다.

    `atexit` 는 정상 종료와 `sys.exit`·전파된 `KeyboardInterrupt` 를 덮지만 **시그널은 덮지
    못한다**. 설치 스크립트가 옛 러너를 정리할 때 쓰는 것이 정확히 그 시그널이므로(재설치가
    이번 결함의 발단이었다), `SIGTERM` 을 `SystemExit` 으로 바꿔 같은 출구로 보낸다.
    """
    global _ACTIVE_API
    _ACTIVE_API = api
    # 종료 요약을 **같은 출구**에 건다 (TASK-20260901T163000). 종전에는 러너가 사라진 뒤
    # 로그의 마지막 줄이 무엇이든 그것이 마지막 사건인지, 그냥 거기서 잘린 것인지 알 수
    # 없었다 — 87분 고아 사고에서 「12:47 종료」를 다른 증거로 짜맞춰야 했던 이유다.
    #
    # ⚠ 등록 순서가 곧 **역순 실행 순서**다: atexit 는 나중에 등록한 것을 먼저 부른다.
    #   그래서 요약을 **먼저** 등록해야 그것이 **마지막에** 실행되어, 자기 점유 해제까지
    #   끝난 뒤의 진짜 마지막 줄이 된다.
    #
    #   라이브 실측(2026-09-01, 배포본 a17b8f5ea7f6)에서 반대로 걸려 있었다 — `--check`
    #   종료 로그가 `run.stop`(seq 4) → `api.fail`(seq 5, 해제 호출의 401) 순으로 남았다.
    #   요약이 마지막 줄이 아니면 그 요약은 **해제 결과를 세지 못하고**, 「여기서 끝났다」의
    #   표지 구실도 못 한다(뒤에 줄이 더 있으니 잘린 것과 구분되지 않는다). 종료 요약의
    #   두 가지 쓸모가 동시에 죽는, 한 줄짜리 순서 결함이었다.
    atexit.register(_log_run_stop)
    atexit.register(release_own_claims_on_exit)
    try:
        import signal as _signal

        def _term(_signum, _frame):  # noqa: ANN001
            raise SystemExit(0)

        _signal.signal(_signal.SIGTERM, _term)
    except Exception:  # noqa: BLE001
        # 시그널을 못 다는 환경(비-메인 스레드·플랫폼 차이)에서도 나머지는 그대로 동작한다.
        pass


def start_heartbeat(api: Api, stop: threading.Event,
                    runtimes: list | None = None,
                    batch_override: "bool | None" = None,
                    baseline_out: dict | None = None,
                    baseline_ready: "threading.Event | None" = None,
                    nudge: "threading.Event | None" = None,
                    on_reported=None) -> threading.Thread:
    """연결 유지 신호를 보내는 데몬 스레드 (TASK-20260828T150000).

    **대기 스레드와 분리한 것이 이 기능의 핵심이다.** 대기(`wait_for_request`)는 빈 워커 자리를
    잡아야 들어가므로, 러너가 바쁠 때 정확히 멈춘다 — 연결 유지 신호가 바쁠 때 멈추면 아무
    소용이 없다(긴 조사 도중에 화면이 '대기 안 함' 이 되고, 토큰 수명도 밀리지 않는다).

    **실패해도 죽지 않는다.** 서버가 배포로 잠깐 사라지는 것과 토큰이 폐기된 것은 다른 사건이고,
    전자로 러너를 끝내면 배포마다 사용자가 다시 띄워야 한다. 401 도 여기서는 **로그만** 남긴다 —
    종료 판정은 메인 루프에 맡긴다(거기에 재발급 안내가 이미 있고, 두 곳에서 죽이면 안내가 두
    벌이 되어 갈린다).

    ⚠ 이 스레드의 `wait` 는 폴링이 아니다 — 서버에서 **아무것도 가져오지 않는다**. 질문 인지는
    여전히 서버 보류(`wait_for_request`)가 하고, 그 즉시성은 이 주기와 무관하다.
    """
    _stale_said = False
    #: 연속 실패 횟수. 리스트로 두는 이유는 `nonlocal` 없이 중첩 함수가 고칠 수 있게 하려는
    #: 것이고, **연속** 을 세는 이유는 한 번의 실패(배포 교대·순단)와 진짜 단절이 로그에서
    #: 같은 모양이면 조사할 때 그 둘을 가릴 수 없기 때문이다.
    _hb_fail_streak = [0]
    #: 직전 프로세스의 사망 신고는 **성공할 때까지** 싣는다 (TASK-20260901T140000).
    #: 첫 신호 한 번만 싣고 말면, 그 한 번이 배포 교대·순단에 걸렸을 때 회수가 통째로
    #: 유실되고 사용자는 종전과 같은 30분 공백을 겪는다. 서버 쪽은 멱등이라(이미 놓은 것은
    #: 0행) 반복해도 비용이 없고, 신고가 받아들여지면 그 다음부터 빠진다.
    _prev = prev_runner_instance()
    _pending_release = [_prev] if _prev else []

    def _loop() -> None:
        nonlocal _stale_said, _pending_release
        interval = _HEARTBEAT_INTERVAL_SEC
        while not stop.is_set():
            # 능력은 **매번** 싣는다. 처음 한 번만 보내면 서버가 재시작하거나 토큰 행이 갈릴 때
            # 화면의 목록이 영영 비고, 그 빈 목록은 "러너가 없다" 와 구분되지 않는다.
            # 서버는 값이 그대로면 쓰지 않으므로(쓰기 증폭 없음) 매번 싣는 비용이 없다.
            reported = [dict(row) for row in (runtimes or [])] if on_reported else runtimes
            outgoing = [{k: v for k, v in row.items() if k != "_client_location"}
                        for row in reported] if on_reported else runtimes
            res = api.heartbeat(outgoing, released_instances=_pending_release)
            code = res.get("_http")
            if code == 401:
                # 복귀 안내는 여기서 하지 않는다 — 대기 루프 한 곳이 정본이다(두 곳에서
                # 안내하면 문구가 갈리고, 한쪽만 고쳐지는 순간 틀린 안내가 남는다).
                log_event(_EV_HB_UNAUTH,
                          "하트비트 401 — 토큰이 무효해졌습니다(로그아웃 또는 만료). "
                          "곧 대기 루프가 재발급 방법을 안내합니다.",
                          level="ERROR", http=401)
            elif code or res.get("_failed"):
                # 순단·배포 교대. 서버의 판정 창이 주기의 3배라 한 번 놓친 것은 흡수된다.
                # WARN 인 이유: 한 번의 실패는 정상 범위다. **연속** 실패를 세어 원장에
                # 남기므로, 조사할 때 `streak` 로 진짜 단절과 순단을 가를 수 있다.
                _hb_fail_streak[0] += 1
                log_event(_EV_HB_FAIL, "하트비트 실패", level="WARN", http=code,
                          streak=_hb_fail_streak[0],
                          detail=str(res.get("error") or "")[:200])
            else:
                if on_reported:
                    on_reported(reported)
                if _hb_fail_streak[0]:
                    # 끊겼다 이어진 사실 자체가 조사 단서다 — 몇 번 만에 돌아왔는지 남긴다.
                    log_event("hb.recovered", "하트비트가 다시 통했다",
                              streak=_hb_fail_streak[0])
                    _hb_fail_streak[0] = 0
                # ── 신고가 닿았다 — **같은 값의 다음 신고는 «캐시» 다** (codex R4 P1-2) ──
                #
                # 능력은 매 하트비트에 실린다. 그런데 출처(`source`)를 그대로 두면 한 번의
                # 확인이 **30초마다 새 확인으로 세어진다**: 서버 `merge_baseline` 이
                # `verified` 신고마다 `verify_streak` 을 1 올리므로, 5회 하트비트(=2.5분)면
                # 상한에 닿아 그 계정의 원장이 러너에게 더 이상 내려가지 않는다(실측 재현).
                # 그러면 R3 S1 이 「몇 달이 지나도 유효한 원장」을 위해 도입한 횟수축이
                # **2.5분 타이머**로 변질되고, 새 머신은 안정된 원장 대신 열린 열거로 떨어져
                # 제보 ②가 그대로 되돌아온다. 게다가 streak 이 매번 달라지므로 저장측
                # 「값이 그대로면 쓰지 않는다」가 항상 거짓이 되어 **쓰기 증폭도 재발**한다.
                #
                # 옳은 표기는 «캐시» 다 — 두 번째 신고부터 이 값의 출처는 라이브 응답이
                # 아니라 **이 프로세스의 메모리**다. 같은 규율이 이미 `config.json` 적재
                # 경로에 있다(`sanitize_caps` 가 `verified` → `cache` 로 강등한다).
                # `cache` 도 신고 가능 출처라 화면의 목록은 그대로 유지된다.
                for _r in (runtimes or []):
                    if _r.get("source") in _CREATION_SOURCES:
                        _r["source"] = "cache"
                # 사망 신고가 서버에 닿았다 — 다음 신호부터는 싣지 않는다.
                if _pending_release:
                    _released = res.get("released_claims") or []
                    if _released:
                        log_event("task.reclaim",
                                  "직전 러너가 붙들고 있던 질문을 되살렸습니다 — 곧 다시 처리합니다",
                                  count=len(_released), prev_run=prev_runner_instance(),
                                  tasks=[str(x) for x in _released[:20]])
                    _pending_release = []
                # 주기는 **서버가 정한다**(P0-J 의 환경 차이 금지와 같은 축). 하한을 두는 것은
                # 서버가 0 을 주는 등의 사고로 신호가 폭주하지 않게 하기 위해서다.
                try:
                    interval = max(_HEARTBEAT_MIN_INTERVAL_SEC,
                                   float(res.get("interval_sec") or interval))
                except (TypeError, ValueError):
                    pass
                # 배포본과 다른 러너로 돌고 있으면 **한 번** 말한다 (2026-08-31).
                #
                # 사용자는 「재설치했는데 목록이 그대로」를 겪었다 — 그날 러너가 세 번 바뀌었고
                # 버전(날짜)은 셋 다 같아서 어디에도 그 사실이 드러나지 않았다. 30초마다
                # 반복하면 소음이라 세션당 한 번만 남긴다(그 뒤로는 화면 쪽 안내가 맡는다).
                # ── 배경 배치 동의를 **웹 토글에서 따라온다** (TASK-20260901T190000) ──────
                #
                # 종전에는 `--batch` 뿐이라 바꾸려면 러너를 다시 띄워야 했다(진행 중 작업이
                # 끊긴다). 이제 서버가 계정별 동의를 하트비트에 실어 주고, 여기서 신고를
                # 갱신한다 — 다음 하트비트에 서버가 그 신고를 저장하면 배급 자격이 바뀐다.
                #
                # ⚠ 키가 **없으면 건드리지 않는다.** 구 서버·기록 실패 응답에는 이 키가 없고,
                # 없는 것을 `False` 로 읽으면 그때마다 동의가 꺼졌다 켜졌다 진동한다.
                # ── 서버 baseline 수신 (TASK-20260902T140200) ────────────────────────
                #
                # 「이 계정의 이 런타임은 마지막으로 무엇을 쓸 수 있었나」. 로컬 캐시가 없는
                # 기동에서 열린 질의 대신 **확인 질의**의 입력으로 쓴다 — 열거는 LLM 답변이라
                # 회차마다 흔들리고, 그것이 「실행할 때마다 목록이 다르다」의 원인이었다.
                #
                # ⚠ 키가 **없으면 건드리지 않는다** (`batch_consent` 와 같은 규율). 구 서버·
                #   기록 실패 응답에는 이 키가 없고, 없는 것을 빈 목록으로 읽으면 방금 받은
                #   baseline 이 다음 30초에 지워진다.
                # ⚠ 제자리 갱신이다 — 협상 스레드가 이 dict 를 그대로 읽는다. `clear()` 후
                #   `update()` 로 쓰지 않는 이유는 `_negotiate_caps` 의 caps 갱신과 같다:
                #   그 틈에 읽으면 빈 목록을 보고 확인할 대상을 잃는다.
                if baseline_out is not None and "caps_baseline" in res:
                    try:
                        _idx = baseline_index(res.get("caps_baseline"))
                        baseline_out.update(_idx)
                        for _gone in [k for k in baseline_out if k not in _idx]:
                            baseline_out.pop(_gone, None)
                    except Exception:  # noqa: BLE001
                        # 원장 수신 실패가 연결 유지 신호를 죽이지 않는다 — 최악이 종전
                        # 동작(baseline 없음)이고, 다음 30초에 다시 온다.
                        pass
                if "batch_consent" in res:
                    _want = apply_consent(api.features,
                                          server_consent=res.get("batch_consent"),
                                          local_override=batch_override)
                    if _want != tuple(api.features):
                        api.features = _want
                        # 남의 계정 사용량을 태우는 축이라 **바뀐 사실을 반드시 말한다** —
                        # 조용히 켜지면 사용자는 자기 AI 가 무엇을 하고 있는지 알 수 없다.
                        log_event(
                            "hb.batch_consent",
                            ("배경 작업(인사이트·클러스터 라벨)을 받도록 켜졌습니다 — "
                             "웹의 '내 AI 연결' 토글에서 끌 수 있습니다."
                             if BATCH_FEATURE in _want else
                             "배경 작업을 더 이상 받지 않습니다."),
                            source=("local" if batch_override is not None else "web"),
                            features=list(_want))
                _u = res.get("runner_update") or {}
                # 같은 계정에 최신 러너가 붙었다 — **이 러너는 물러난다** (사용자 결정
                # 2026-09-01). 남아 있으면 선착순 점유로 사용자 답변을 옛 동작으로 되돌린다.
                # 여기서 죽이지 않고 신호만 세운다: 진행 중 작업을 마치고 끝내는 절차는
                # 대기 루프의 `shutdown_after_drain` 한 곳이 정본이다.
                if _u.get("superseded") and not _SUPERSEDED.is_set():
                    _SUPERSEDED.set()
                    log_event(_EV_HB_SUPERSEDED,
                              "같은 계정에 더 나중에 연결된 러너가 있습니다 — 이 러너는 하던 일을 "
                              "마치고 물러납니다(질문은 그 최신 연결이 처리합니다). "
                              "계정이 다른 러너는 영향받지 않습니다.",
                              level="WARN", local_build=_self_build(),
                              peer_build=str(_u.get("superseded_by_build") or "") or None)
                if _u.get("stale_build"):
                    # 스스로 고칠 수 있으면 **신호만 세우고 조용히 넘어간다** (사용자 결정
                    # 2026-09-02). 러너 파일은 거의 모든 배포에서 바뀌므로, 이 사실을 매번
                    # 경고로 찍으면 로그가 «사용자가 할 일» 로 가득 차는데 정작 할 일은 없다.
                    if _SELF_UPDATE_OK[0]:
                        _SELF_UPDATE.set()
                    elif not _stale_said:
                        # 스스로 못 고친다 — 이때는 사람이 할 일이 실제로 있으므로 말한다.
                        _stale_said = True
                        log_event(_EV_HB_STALE,
                                  "⚠ 실행 중인 러너가 서버 배포본과 다릅니다 — 최신 파일로 다시 받아 "
                                  "실행하세요(웹의 '내 AI 연결하기' → 원클릭 명령). "
                                  "그 전까지는 옛 동작·옛 모델 목록이 그대로 보입니다.",
                                  level="WARN", local_build=_self_build(), ver=AGENT_VERSION,
                                  min_version=str(_u.get("min_version") or "") or None)
            # ── 첫 시도가 **끝났다**는 신호 (TASK-20260902T140200) ────────────────────
            #
            # 협상 스레드가 이 신호를 짧게 기다린다(아래 `main`). 위치가 계약이다:
            # - **분기 체인 뒤** — 성공 분기에서 `baseline_out` 을 채운 뒤에 풀려야 협상이
            #   방금 받은 원장을 보고 확인 질의를 던진다.
            # - **성공·실패 무관** — 성공 분기 안에 두면 서버에 닿지 못한 사용자가 상한
            #   (≈16초)을 통째로 더 기다린다.
            # - 조건에 「원장이 비어 있지 않을 때」를 넣지 않는다 — 첫 연결 계정에서 신호가
            #   영영 오지 않는다.
            if baseline_ready is not None and not baseline_ready.is_set():
                baseline_ready.set()
            # ── 주기 대기, 단 «지금 신고해라» 신호에는 즉시 깨어난다 ────────────────
            #
            # 협상이 플랫폼 하나를 끝낼 때마다 `nudge` 를 세운다(사용자 제보 2026-09-02,
            # 3차). 주기만 기다리면 claude 가 22.7초에 끝나도 그 목록이 최대 30초를 더
            # 기다리고, 사용자에게는 그 합이 「갱신이 안 된다」로 보인다.
            #
            # ⚠ **`stop` 도 함께 봐야 한다.** `nudge` 만 기다리면 종료 신호가 이 대기를
            #   깨우지 못해 최대 한 주기(30초) 늦게 멈춘다 — `try_self_update` 가
            #   `os.execv` 직전에 하트비트를 끊는 경로가 그만큼 밀린다. 그래서 둘 중
            #   먼저 오는 것을 잡되, **`stop` 이 이미 섰으면 기다리지 않는다**.
            if nudge is None:
                stop.wait(interval)
            else:
                _left = interval
                while _left > 0 and not stop.is_set() and not nudge.is_set():
                    _step = min(_HEARTBEAT_NUDGE_POLL_SEC, _left)
                    nudge.wait(_step)
                    _left -= _step
                nudge.clear()

    t = threading.Thread(target=_loop, name="bridge-heartbeat", daemon=True)
    t.start()
    return t


def try_self_update(api: Api, active: ActiveTasks) -> bool:
    """배포본과 다르면 **스스로 갈아 끼우고 다시 뜬다**. 성공하면 돌아오지 않는다.

    반환값은 「이번 회차에 무언가 미뤘는가」가 아니라 **「갱신을 포기했는가」**다 —
    `False` 면 대기 루프는 평소대로 계속 돈다. 성공하면 `os.execv` 라 반환 자체가 없다.

    ## 순서가 곧 안전이다

    1. **유휴일 때만.** 진행 중인 답변이 있으면 이번 회차는 그냥 넘긴다(취소하지 않는다).
       최신이 되자고 사용자가 방금 던진 질문을 죽이는 것은 거래가 성립하지 않는다.
    2. **바닥 간격.** 배포가 몰리는 날 재기동이 연달아 일어나지 않게 한다.
    3. **받아서 검사한 뒤에만 교체.** `fetch_deployed_agent` 가 https·CA·크기·문법을
       모두 통과시킨 것만 돌려준다.
    4. **바뀌는 것이 없으면 재기동하지 않는다.** 받은 것이 지금 나와 같은 파일이면 그대로 둔다 —
       이 한 줄이 「배포본을 못 따라잡는 러너가 영원히 재기동하는」 고리를 끊는다.
    5. **교체 실패는 조용히 넘긴다.** 있던 파일로 계속 도는 것이 언제나 차선이다.

    ⚠ 재기동 직전에 **하트비트를 멈추고 점유를 놓아준다**. `os.execv` 는 `atexit` 를 부르지
    않으므로(프로세스 이미지가 통째로 갈린다), 여기서 하지 않으면 서버는 이 러너를 «살아 있는데
    응답 없음» 으로 30분간 붙들고 있게 된다.
    """
    if not _SELF_UPDATE_OK[0]:
        return False
    if active.count() > 0:
        return False           # 일하는 중 — 다음 하트비트가 다시 알려 준다
    # ⚠ **능력 협상도 «일하는 중»이다** (codex R4 P2-9). 협상은 `ActiveTasks` 에 잡히지
    #   않는 배경 스레드에서 돌고 자식 CLI 를 최대 240초 붙든다. 그 동안 `os.execv` 로
    #   프로세스를 갈아 끼우면 진행 중인 질의와 그 토큰이 통째로 버려지고, 새 프로세스가
    #   처음부터 다시 협상한다 — 사용자에게는 **목록이 더 늦게 뜨는 것**으로 나타난다.
    #   이 cycle 이 줄이려는 것이 정확히 그 지연이므로, 협상이 끝날 때까지 미룬다.
    #   미루는 비용은 없다: `_SELF_UPDATE` 는 그대로 세워져 있고 다음 하트비트가 다시 온다.
    if _CAPS_NEGOTIATING[0]:
        return False
    now = time.monotonic()
    if _SELF_UPDATE_LAST[0] and (now - _SELF_UPDATE_LAST[0]) < SELF_UPDATE_MIN_INTERVAL_SEC:
        return False
    _SELF_UPDATE_LAST[0] = now
    # 신호는 여기서 내린다 — 실패해도 다음 하트비트가 다시 세운다(재시도는 그 주기를 탄다).
    _SELF_UPDATE.clear()
    mine = _self_build()
    path = _SELF_UPDATE_BUNDLE[0]
    if not path:
        # 단일 파일이 아니다(개발 트리) — 여기까지 오면 안 되지만, 판정을 한 번 더 한다.
        return False
    payload = fetch_deployed_agent(api.base, api.ca)
    if payload is None:
        log_event(_EV_SELFUPDATE, "최신 러너 파일을 받지 못했습니다 — 있던 파일로 계속합니다.",
                  level="WARN", phase="fetch", local_build=mine)
        return False
    new_build = agent_digest(payload)
    if new_build == mine:
        # 서버가 낡았다고 했는데 받아 보니 같은 파일이다. 배포 교대 중이거나(엣지가 옛 replica 를
        # 잡음) 판정이 흔들린 것 — 어느 쪽이든 **바꿀 것이 없다**.
        return False
    if not install_agent_file(path, payload):
        log_event(_EV_SELFUPDATE, "최신 러너 파일을 저장하지 못했습니다(권한·디스크) — "
                                  "있던 파일로 계속합니다.",
                  level="WARN", phase="install", local_build=mine, new_build=new_build)
        return False
    log_event(_EV_SELFUPDATE,
              "러너를 최신본으로 갱신했습니다 — 지금 다시 시작합니다(하던 일은 없었습니다).",
              local_build=mine, new_build=new_build, path=path)
    # 재기동 전 정리. 순서: 하트비트를 먼저 멈춰 «살아 있다» 는 신호를 끊고, 그다음 점유를 놓는다.
    try:
        _SELF_UPDATE_STOP[0]()
    except Exception:  # noqa: BLE001
        pass
    release_own_claims_on_exit()
    _log_run_stop(reason="selfupdate")
    try:
        reexec_self(path)
    except Exception:  # noqa: BLE001
        # `execv` 가 실패했다 — 파일은 이미 최신이므로 그냥 끝낸다. 런처가 다시 띄우거나,
        # 사용자가 다음에 실행할 때 최신본이 뜬다. 여기서 계속 돌면 **옛 코드가 새 파일을
        # 들고** 도는 상태가 되어 로그와 실제가 어긋난다.
        log_event(_EV_SELFUPDATE, "재시작에 실패했습니다 — 러너를 종료합니다"
                                  "(다음 실행부터 최신본이 뜹니다).",
                  level="ERROR", phase="reexec", new_build=new_build)
        raise SystemExit(1) from None
    return True


#: 재기동 직전에 하트비트를 멈추는 손잡이. `main()` 이 자기 `heartbeat_stop.set` 을 넣는다 —
#: `try_self_update` 가 그 지역 변수를 볼 수 없기 때문이다(기본값은 아무것도 안 함).
_SELF_UPDATE_STOP = [lambda: None]


def shutdown_after_drain(active: ActiveTasks, cancels: CancelRegistry,
                         grace_sec: float = _SHUTDOWN_GRACE_SEC) -> bool:
    """연결이 명시적으로 해제됐다 — **하던 일을 마치고** 종료한다(사용자 요구 2026-08-28).

    > "웹브라우저 내 로그아웃 + 모든 요청사항이 완료되어 유휴상태가 확인된다면 더 이상
    >  사용되지 않을 브릿지 프로세스도 안전하게 종료될 수 있도록"

    | 상태 | 하는 일 |
    |---|---|
    | 유휴(진행 중 0건) | 즉시 종료 — 더 할 일이 없다 |
    | 진행 중 있음 | 유예 안에서 **끝나기를 기다린다**(죽이는 것은 마지막 수단) |
    | 유예 초과 | 취소로 전환 → 자식 AI 프로세스가 죽는다 → 종료 |

    유예를 두는 이유와 무한정 기다리지 않는 이유가 같다: 이 답변들은 **전달될 곳이 이미
    없다**(로그아웃으로 토큰이 죽어 `submit_answer` 가 401 이다). 그래도 곧 끝날 일을 중간에
    끊지는 않고, 오래 걸리는 것은 붙잡지 않는다 — 붙잡으면 아무도 볼 수 없는 답을 위해
    사용자의 **개인 계정 토큰이 계속 탄다**(P0-T 에서 취소를 만든 것과 같은 이유).

    반환값은 "유휴 상태로 끝났는가" — 호출측 로그가 두 결말을 구분해 말할 수 있게 한다.
    """
    n = active.count()
    if n == 0:
        _log("진행 중인 작업이 없습니다 — 브리지 러너를 종료합니다.")
        return True
    _log(f"진행 중 {n}건이 끝나기를 기다립니다(최대 {grace_sec:.0f}초). "
         "이미 로그아웃되어 답변은 대화에 전달되지 않습니다.")
    if active.wait_idle(grace_sec):
        _log("진행 중이던 작업이 모두 끝났습니다 — 브리지 러너를 종료합니다.")
        return True
    remaining = active.snapshot()
    cancels.add_many(remaining)
    _log(f"유예가 지나 {len(remaining)}건을 중단합니다: {', '.join(remaining)} — 종료합니다.")
    # 취소는 워커가 다음 확인 시점(_CANCEL_TICK_SEC)에 본다. 그 한 tick 만 준다 —
    # 여기서 오래 기다리면 '안전한 종료' 가 다시 '종료되지 않음' 이 된다.
    active.wait_idle(_CANCEL_TICK_SEC * 3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="DQA Connect 상주 러너")
    ap.add_argument("--base", default=os.environ.get("BRIDGE_BASE", ""), help="서비스 베이스 URL")
    ap.add_argument("--token", default=os.environ.get("BRIDGE_TOKEN", ""), help="mat_ 토큰")
    ap.add_argument("--ca", default=os.environ.get("BRIDGE_CA", "") or None, help="사설 CA 인증서 경로")
    ap.add_argument("--ai", default=os.environ.get("BRIDGE_AI", ""),
                    help="claude|codex|gemini, 또는 PATH 상의 다른 AI CLI 이름. "
                         "⚠ 모르는 이름은 능력을 묻기 위해 **실제로 한두 번 실행**한다 — "
                         "AI 가 아닌 프로그램을 지목하지 마라(그 프로그램의 부수효과는 막지 못한다)")
    ap.add_argument("--cmd", default=os.environ.get("BRIDGE_CMD", "") or None,
                    help="직접 지정할 AI 명령. {prompt} 자리에 질문이 들어간다")
    ap.add_argument("--batch", action="store_true",
                    help="배경 배치 작업(인사이트·클러스터 라벨)까지 받는다 — **이 머신에서 "
                         "명시 허용**. 지정하지 않으면 웹의 '내 AI 연결' 토글을 따른다.")
    ap.add_argument("--no-batch", action="store_true",
                    help="웹 토글이 켜져 있어도 **이 머신에서는** 배경 배치를 받지 않는다. "
                         "그 작업은 당신이 요청한 적 없고 당신 계정의 AI 사용량을 쓴다.")
    ap.add_argument("--no-self-review", action="store_true",
                    help="답변을 내보내기 전 **자기 검증**(5축)을 하지 않는다. 기본은 서버 "
                         "설정을 따라 수행 — 검증은 AI 호출을 한 번 더 쓰므로 "
                         "이 머신에서 끄고 싶을 때 사용한다.")
    ap.add_argument("--no-self-update", action="store_true",
                    help="배포본과 달라져도 **스스로 갱신하지 않는다**. 기본은 유휴일 때 최신 "
                         "파일을 받아 조용히 다시 시작 — 이 머신에서 실행 파일을 직접 관리할 때 "
                         "끈다. 끄면 웹 화면이 종전대로 「업데이트 필요」를 보여 준다.")
    ap.add_argument("--once", action="store_true", help="한 건만 처리하고 종료")
    ap.add_argument("--check", action="store_true", help="연결만 확인하고 종료")
    ap.add_argument("--resume", action="store_true",
                    help="지난 설정을 불러온다(주소·CA·AI). 토큰만 새로 주면 된다")
    ap.add_argument("--refresh-caps", action="store_true",
                    help="쓸 수 있는 모델·추론 수준을 AI 에게 **다시 묻는다**"
                         "(기본은 저장된 답을 재사용 — 질의는 네 계정 토큰을 쓴다)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("BRIDGE_WORKERS", 0))
                    or _DEFAULT_WORKERS,
                    help=f"**시작** 동시 처리 수 (기본 {_DEFAULT_WORKERS}). 수요가 오면 늘어난다")
    ap.add_argument("--max-workers", type=int,
                    default=int(os.environ.get("BRIDGE_MAX_WORKERS", 0)) or _DEFAULT_MAX_WORKERS,
                    help=f"확장 상한 (기본 {_DEFAULT_MAX_WORKERS}). 개인 계정 쿼터가 실질 한계다")
    ap.add_argument("--worker-idle-sec", type=float,
                    default=float(os.environ.get("BRIDGE_WORKER_IDLE_SEC", 0))
                    or _DEFAULT_WORKER_IDLE_SEC,
                    help=f"이 시간 넘게 쉰 슬롯을 오래된 것부터 회수 (기본 {int(_DEFAULT_WORKER_IDLE_SEC)}초)")
    # main 이 같은 창에 들인 축 — AI 호출 상한을 진행 신호 기반으로 뒀다(TASK-…140000).
    ap.add_argument("--ai-timeout", type=float,
                    default=_AI_TIMEOUT_SEC,
                    help="AI 호출 상한(초). 기본 0 = 상한 없음 — 진행 중이면 끊지 않는다"
                         "(서버가 진행 신호로 lease 를 갱신하고, 멈추면 회수한다)")
    args = ap.parse_args()
    # 전역을 여기서 확정한다 — 취소 감시 루프가 이 값을 읽는다.
    globals()["_AI_TIMEOUT_SEC"] = max(0.0, float(args.ai_timeout or 0))
    max_workers = max(1, int(args.max_workers or _DEFAULT_MAX_WORKERS))
    # ⚠ 시작값을 상한으로 **clamp** 한다. 종전엔 `max(workers, max_workers)` 였는데, 그러면
    #   `--workers 100 --max-workers 8` 이 상한을 100 으로 밀어올렸다 — 상한이 상한이 아니게
    #   된다(codex 리뷰 P2). 기존 `BRIDGE_WORKERS` 가 큰 머신에서 새 안전장치가 통째로
    #   무력화되는 경로이기도 하다.
    workers = max(1, min(int(args.workers or 1), max_workers))
    if int(args.workers or 1) > max_workers:
        _log(f"--workers {args.workers} 가 상한 {max_workers} 를 넘어 {workers} 로 시작합니다"
             " (상한을 올리려면 --max-workers).")
    idle_sec = max(1.0, float(args.worker_idle_sec or _DEFAULT_WORKER_IDLE_SEC))

    # 재시작 후 복귀 경로 — 명시 인자가 우선이고, 빈 것만 지난 설정으로 채운다.
    if args.resume:
        conf = load_conf()
        args.base = args.base or conf.get("base") or ""
        args.ca = args.ca or conf.get("ca")
        # ⚠ `ai` 는 **상속하지 않는다** (P0-Z5, 라이브 실측 2026-08-28).
        #
        #   P0-Z3 이전에 `ai` 는 "무엇으로 답할까" 하나만 정했고, 그 값은 자동 감지 결과여도
        #   저장해 두는 것이 편의였다. 그런데 P0-Z3 이후 같은 값이 **신고 목록까지 좁힌다** —
        #   의미가 바뀌었는데 저장·상속 규칙은 그대로였다.
        #
        #   결과: `--ai` 를 준 적 없는 사용자도 첫 기동의 자동 감지 결과가 `ai` 로 굳고,
        #   `--resume` 이 그것을 상속해 **다른 런타임이 화면에서 사라진다**. 실제로 라이브
        #   재기동에서 codex 가 설치돼 있는데 claude 만 신고됐다(사용자 요청은 정확히
        #   "claude 뿐만 아니라 codex 등" 이었다).
        #
        #   `ai` 는 그 실행의 제한이지 복원할 설정이 아니다. 제한하려면 매번 명시한다 —
        #   그래야 "지금 무엇이 제한되고 있는가" 가 명령줄에 그대로 보인다.
        #   (`detect_ai()` 가 실행 런타임을 매번 다시 정하므로 잃는 것은 없다.)
        args.cmd = args.cmd or conf.get("cmd")
        if not args.token:
            _log("토큰이 필요합니다 — 웹에서 '연결 정보 만들기' 로 새로 받아 --token 에 주세요.")
            return 2

    # 저장된 능력은 `--resume` 과 무관하게 읽는다 — 그것은 사용자가 준 설정이 아니라
    # 우리가 관측한 결과이고, 매번 다시 묻는 비용을 아끼는 것이 저장의 목적이다.
    # 저장된 값도 **다시 강제한다** — 그러지 않으면 이 파일이 곧 우회 경로가 된다.
    conf_caps = sanitize_caps(load_conf().get("caps"))

    if not args.base or not args.token:
        log_event(_EV_RUN_FATAL, "--base 와 --token 이 필요합니다.", level="FATAL",
                  reason="missing_args")
        return 2
    if not _transport_is_safe(args.base):
        # 토큰이 이 채널로 나간다. loopback 만 예외.
        log_event(_EV_RUN_FATAL, "--base 는 https 여야 합니다(loopback 예외).", level="FATAL",
                  reason="insecure_transport")
        return 2

    api = Api(args.base, args.token, args.ca)
    # 이 프로세스의 신원을 세우고 **직전 프로세스의 id 를 회수**한다 (TASK-20260901T140000).
    # 서버와 첫 말을 트기 전이어야 한다 — 점유(`claim_request`)에 새길 값이 이미 있어야 하고,
    # 직전 id 는 이 호출이 파일을 덮어쓰기 전에만 읽을 수 있다.
    init_runner_instance()
    # ── 세션 머리글 (TASK-20260901T163000) ────────────────────────────────────
    #
    # 사고 조사는 **이 프로세스가 무엇이었는가** 에서 시작한다. 종전 로그로는 그것을 알 수
    # 없어서, 사용자에게 「파이썬 버전이 뭔가요 · 러너를 언제 받으셨나요 · 인자를 어떻게
    # 주셨나요」를 되물어야 했고 그 왕복이 조사 시간의 대부분이었다. 한 줄로 끝낸다.
    #
    # ⚠ 여기 실리는 것에 **비밀은 없다** — 토큰은 물론, `--cmd` 도 사용자가 그 안에 자격증명을
    #   넣었을 수 있어 `_scrub` 를 거친다. 주소는 호스트만 남긴다.
    _host = ""
    try:
        _host = urllib.parse.urlparse(args.base).hostname or ""
    except Exception:  # noqa: BLE001
        _host = ""
    log_event(_EV_RUN_START, "브리지 러너 시작",
              ver=AGENT_VERSION, build=_self_build(),
              run=runner_instance(), prev_run=prev_runner_instance() or None,
              host=_host, ca=bool(args.ca),
              py=".".join(str(x) for x in sys.version_info[:3]),
              platform=sys.platform, pid=os.getpid(),
              workers=workers, max_workers=max_workers,
              ai=(args.ai or "auto"), cmd=(args.cmd or None),
              audit_log=_audit_path(), human_log=(_human_log_path() or "stderr"))
    _arm_exit_release(api)
    # 신고는 **이 실행의 선택**이다(모듈 상수를 바꾸지 않는다). 두 축을 한 번에 조립한다 —
    # 따로 대입하면 나중 대입이 앞의 것을 지운다(`--batch --no-self-review` 조합에서
    # 배치 동의가 사라지던 형태의 결함).
    _feats = list(AGENT_FEATURES)
    # 배치 동의: `--batch`/`--no-batch` 는 **이 머신의 명시 override**, 없으면 웹 토글을 따른다
    # (TASK-20260901T190000). 기동 시점에는 아직 하트비트를 받지 못했으므로 서버 값을 모른다 —
    # 모르면 받지 않는다(fail-closed). 첫 하트비트(≤30초)가 오면 아래 `_loop` 가 갱신한다.
    #
    # 서버는 이 신고를 권한과 함께 확인해야 배급하므로, 동의만으로 남의 조직 작업을
    # 가져가지는 않는다.
    _batch_override = _batch_override_from_args(args)
    _feats = list(apply_consent(_feats, server_consent=False, local_override=_batch_override))
    if getattr(args, "no_self_review", False):
        # 끈 사실을 **신고에서도 지운다** — 신고를 남긴 채 수행만 건너뛰면 콘솔은 이 러너를
        # "검증할 줄 아는데 결과가 없다"(= 통과)로 읽는다. 그 오독이 이 축을 만든 이유다.
        _feats = [f for f in _feats if f != "self_review"]
    # 자기 갱신은 **할 수 있을 때만** 신고한다 (TASK-20260902T140000). 두 조건의 곱이다:
    #   (a) 사용자가 끄지 않았고, (b) 지금 도는 것이 실제로 **배포된 단일 파일**이다.
    # (b) 가 빠지면 개발 트리에서 모듈로 띄운 러너가 「곧 스스로 최신이 됩니다」라고 신고하고,
    # 화면은 그 말을 믿고 조치 요구를 감춘 채 **오지 않을 갱신**을 기다린다. 신고와 실제
    # 능력을 같은 식으로 세워 그 괴리를 구조적으로 없앤다.
    _SELF_UPDATE_OK[0] = (not getattr(args, "no_self_update", False)
                          and bool(_SELF_UPDATE_BUNDLE[0]))
    if not _SELF_UPDATE_OK[0]:
        _feats = [f for f in _feats if f != "self_update"]
    api.features = tuple(_feats)

    # 저장하는 `ai` 는 **사용자가 명시한 것만**이다(위 상속 주석과 같은 이유). 자동 감지
    # 결과를 저장하면 그것이 다음 실행의 제한으로 승격된다.
    save_conf(args.base, args.ca, (args.ai or ""), args.cmd)

    # ⚠ 연결 확인에 `wait_for_request` 를 쓰면 안 된다 (라이브 실측 2026-08-28).
    #
    #   그 도구는 **질문이 없으면 55초를 보류하도록 설계**돼 있다(그것이 '폴링 아님' 의 실체다).
    #   그런데 여기서는 10초 timeout 으로 불렀으므로, **대기 질문이 없는 정상 상태에서 반드시
    #   read timeout** 이 나고 `--check` 가 "연결 실패" 를 출력했다. 온보딩 시점이 정확히 그
    #   상태다 — 지시문이 ③단계로 `--check` 를 권하는데 그것이 **항상 실패**했다.
    #
    #   실측: `list_open_requests` 0.0초/200 (연결 정상) · `wait_for_request` 10초 timeout ·
    #   같은 호출을 90초로 주면 55.3초 뒤 `timed_out: true` 로 정상 반환.
    #
    #   직전 수정이 `_failed` 를 보게 하면서(거짓 "연결 정상" 제거) 이 결함이 드러났다 —
    #   한쪽 오독을 고치니 반대쪽 오독이 보인 형태다. 확인용 호출은 **즉시 답하는 도구**여야
    #   한다. `list_open_requests` 는 같은 인증·같은 경로를 쓰면서 바로 돌아온다.
    probe = api.call("list_open_requests", {"limit": 1}, timeout=20.0)
    if probe.get("_http") == 401:
        log_event(_EV_CONN_UNAUTH,
                  "토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.",
                  level="FATAL", http=401, reason="token_invalid")
        return 3

    # ── AI 는 **연결을 확인한 뒤에** 고른다 ──────────────────────────────────────
    #
    # ⚠ 종전에는 이 선택이 위쪽에 있었고, 실패하면 곧장 FATAL 이었다. 그래서 AI 를 못 찾은
    #   사용자는 연결이 멀쩡해도 설치 스크립트로부터 「연결 확인에 실패했습니다. 토큰이
    #   만료됐다면…」 을 받았다 (사용자 제보 2026-09-01) — 토큰도 CA 도 네트워크도 정상인데
    #   그 세 곳을 뒤지게 만드는 오진이다. 연결과 AI 는 다른 축이므로 판정도 따로 낸다.
    #
    #   순서까지 바꾼 이유(codex 적대 리뷰 P2): 「실패해도 안 끝낸다」만으로는 부족하다.
    #   AI 탐색은 파일시스템을 훑으므로 응답 없는 네트워크 드라이브가 PATH 에 있으면 여기서
    #   오래 멈춘다. 그러면 연결 확인이 그만큼 늦어진다 — 확인이 먼저 끝나야 「연결은 된다」를
    #   빨리 말할 수 있다.
    picked = pick_ai(args.ai, args.cmd)

    if args.check:
        # `_http` 만 보면 **연결 실패(0)를 성공으로 읽는다** — 사설 CA 미지정 상태에서 실제로
        # "연결 정상." 을 출력했다. `--check` 가 거짓 안심을 주면 사용자는 러너가 왜 아무 일도
        # 안 하는지 알 수 없다.
        failed = bool(probe.get("_http")) or bool(probe.get("_failed"))
        if failed:
            log_event(_EV_CONN_FAIL, "연결 실패", level="ERROR",
                      http=probe.get("_http"), detail=str(probe.get("error") or ""))
            if probe.get("_failed"):
                _log("  사설 CA 를 쓰는 서버라면 --ca <rootCA.pem> 을 지정하세요.")
            return 1
        log_event(_EV_CONN_OK, "연결 정상.", host=_host)
        # 연결은 됐다. 그런데 **답할 AI 가 없으면** 이 설치는 아직 쓸 수 없다 — 그 사실을
        # 연결 실패로 뭉치지 않고 따로 낸다(설치 스크립트가 exit 4 로 구분해 안내한다).
        if not picked:
            for line in _no_ai_message():
                _log(line)
            return 4
        _log(f"사용할 AI: {picked[0]}")
        return 0

    # 여기서부터는 상주다 — 답할 AI 가 없으면 **시작하지 않는다**. 질문을 가져가 놓고 답하지
    # 못하면 사용자는 「대기 중」 표시만 보며 기다리게 된다(침묵보다 나쁘다).
    if not picked:
        log_event(_EV_RUN_FATAL, "이 컴퓨터에서 쓸 수 있는 AI 를 찾지 못했습니다.",
                  level="FATAL", reason="no_local_ai")
        for line in _no_ai_message():
            _log(line)
        return 4
    kind, argv = picked
    _log(f"AI = {kind}" + (f" ({args.cmd})" if args.cmd else ""))
    # 구버전 claude 는 `--strict-mcp-config` 를 모른다 — 그러면 **모든 질문이** unknown option
    # 으로 실패한다 (codex P2-2). 기동 시 한 번 확인해서, 없으면 플래그를 빼고 그 사실을 크게
    # 말한다. 조용히 빼면 원 결함(만료 MCP 토큰 경합)이 아무 표시 없이 돌아온다.
    _ensure_strict_mcp_supported(kind)

    # 이 머신이 무엇을 쓸 수 있는가 (P0-Z3). `--cmd` 로 명령을 통째로 준 사용자는 신고하지
    # 않는다 — 그 명령에 모델·등급이 이미 박혀 있고, 웹에서 고른 값은 반영되지 않는다.
    # 반영되지 않을 목록을 화면에 띄우는 것이 P0-T 가 지운 바로 그 상태다.
    # 목록은 **각 AI 가 스스로 답한 것**이다 (P0-Z4). 한 번 물으면 `config.json` 에 남고
    # 다음 기동은 묻지 않는다 — 그 질의는 사용자 계정의 토큰을 쓰고 수십 초가 걸린다.
    # 갱신은 `--refresh-caps` 로 명시할 때만(모델 목록이 바뀌는 일은 드물다).
    caps: dict = {}
    #: 신고 목록. **하트비트 스레드와 워커가 이 같은 객체를 읽는다** — 협상이 끝나면 제자리로
    #: 갱신(`[:]`)해서 다음 하트비트가 저절로 새 목록을 싣게 한다. 새 리스트를 대입하면
    #: 하트비트가 잡아 둔 옛 객체를 계속 보내 목록이 영영 비어 보인다.
    runtimes: list = []
    #: 직전 협상 회차가 **실제로 물어본** 런타임 이름. 재시도 판정의 모수다
    #: (codex 적대리뷰 P2-1, 2026-09-07) — 「신고가 비었는가」만 보면 한 런타임이 성공하는
    #: 순간 나머지의 빈 목록이 영구화된다.
    _caps_asked: list = []

    # ── 협상을 기다릴 것인가 (TASK-20260902T140000) ───────────────────────────
    #
    # ## 무엇이 깨져 있었나 (라이브 실측 2026-09-02)
    #
    # 능력 협상이 하트비트·대기 루프보다 **앞**에 있었고, 협상은 실패해도 데드라인
    # (`_CAPS_PROBE_TIMEOUT_SEC` = 240초)을 전부 소진한다. 그래서 기동 후 4분 동안:
    # 하트비트 0건(웹은 「연결 안 됨」) · 로그 0줄 · 질문 미수령. 그런데 설치 스크립트는
    # `--check` 성공 뒤 2초만 보고 **「완료」** 를 선언한다.
    #
    #   run.start 12:27:53 → (침묵 4분) → run.ready 12:31:53  startup_ms=240896
    #   12:28:12 에 온 질문은 12:31:54 에야 점유됐다.
    #
    # 사용자 제보가 정확히 그 구간이었다 — "연결은 됐다는데 답도 없고 로그도 안 쌓인다".
    #
    # ## 무엇이 협상을 정말로 기다리는가
    #
    # **호출 형태(`argv`)뿐이다.** 표 안 런타임(claude·codex·gemini)은 `_RUNTIME_SPECS` 에
    # argv 가 이미 있으므로 협상 없이도 답할 수 있다 — 협상이 정하는 것은 «화면 선택기에
    # 무엇을 띄울까» 이고, 그것은 나중에 도착해도 된다. 표 **밖** CLI 만 argv 를 협상에서
    # 배우므로 그때만 기다린다.
    _caps_first = (not args.cmd) and (kind not in _RUNTIME_SPECS)

    #: 서버가 준 계정·런타임 baseline. 하트비트 스레드가 **제자리** 갱신하고 협상이 읽는다
    #: (TASK-20260902T140200).
    _caps_baseline: dict = {}
    #: 하트비트가 **첫 성공 응답**을 받았다는 신호. 협상이 이것을 짧게 기다린다 — 기다리지
    #: 않으면 협상이 baseline 보다 먼저 출발해 확인 경로가 **사실상 발화하지 않는다**
    #: (§16.7 G14-e: 존재는 실행이 아니다).
    _baseline_ready = threading.Event()
    #: 「지금 신고해라」 신호. 협상이 플랫폼 하나를 끝낼 때마다 세우고, 하트비트 루프가
    #: 주기 대기 대신 이것을 기다린다 — 주기(30초)를 기다리면 플랫폼별 실시간 갱신이
    #: 그만큼 늦어진다(사용자 제보 2026-09-02, 3차).
    _caps_nudge = threading.Event()

    #: 협상 **회차 번호**와 그 회차의 게시를 직렬화하는 락 (적대리뷰 P2, 2026-09-07).
    #:
    #: 재시도가 생기면서 회차가 겹칠 수 있게 됐다: `resolve_caps` 는 데드라인이 지나면
    #: `t.join(...)` 을 포기하고 반환하는데, 남은 질의 스레드는 계속 살아 있다가 **다음
    #: 회차 중에** `on_settled` 를 부른다. 그러면 앞 회차의 (더 짧은) 부분 목록이 방금
    #: 성공한 목록을 되덮고, 같은 순간 `dict(caps)` 를 읽던 재시도 스레드가
    #: `RuntimeError: dictionary changed size during iteration` 으로 죽는다 — 재시도가
    #: 사라져 원 결함(목록이 영영 안 옴)으로 되돌아간다. 종전엔 협상이 1회뿐이라 이 겹침
    #: 자체가 없었다.
    _caps_round = [0]
    _caps_publish_lock = threading.Lock()

    _negotiate_lock = threading.Lock()

    def _publish_caps_for(round_no: int, targets=None):
        """그 회차 전용 `on_settled`. **낡은 회차의 게시는 버린다.**"""
        def _cb(_got: list, _detail: dict) -> None:
            with _caps_publish_lock:
                if targets is not None and targets != client_runtime_selection():
                    return
                if targets is not None:
                    for name, detail in _detail.items():
                        if isinstance(detail, dict):
                            detail["client_location"] = targets.get(name)
                if round_no != _caps_round[0]:
                    return          # 앞 회차의 지각 스레드 — 지금 목록을 되덮지 않는다
                _publish_caps(_got, _detail)
        return _cb

    def _snapshot_caps() -> dict:
        """`caps` 의 안전한 사본. 게시와 같은 락 아래에서 뜬다."""
        with _caps_publish_lock:
            return dict(caps)

    def _publish_caps(_got: list, _detail: dict) -> None:
        """협상 결과를 **제자리** 갱신하고 하트비트를 깨운다.

        플랫폼 하나가 끝날 때마다도 불린다(`resolve_caps(on_settled=…)`) — 그래서 이 함수는
        **부분 목록으로도 안전**해야 한다:

        - `runtimes[:]` 제자리 대입은 하트비트가 다음 신호에 실을 값이다. 부분 목록이
          앞선 목록을 «지우는» 일은 서버에서 일어나지 않는다 — 계정 원장 병합이 합집합
          누적이고(`shared/bridge_caps.merge_baseline`), 같은 프로세스의 `probed` 는
          누적되므로 이 목록도 협상이 진행될수록 **자라기만** 한다.
        - `caps` 는 워커가 호출법을 읽는 사전이라 **비우지 않는다**(아래 주석).

        ⚠ 이 함수는 질의 스레드 안에서 불린다 — **즉시 끝나는 일만** 한다(제자리 갱신 +
          이벤트 set). 여기서 오래 걸리면 그 플랫폼의 협상이 그만큼 늦게 끝난다.
        """
        runtimes[:] = _got
        # ⚠ `clear()` 후 `update()` 로 쓰지 않는다 — 그 사이에 워커가 읽으면 **빈 caps** 를
        #   보고 호출법을 잃는다. 먼저 덮어쓰고 없어진 키만 지우면, 그 틈에 보이는 것은
        #   기껏해야 «방금 사라진 항목이 남아 있는» 상태다(빈 것보다 훨씬 무해하다).
        caps.update(_detail or {})
        for _gone in [k for k in caps if k not in (_detail or {})]:
            caps.pop(_gone, None)
        # ── 다음 주기를 기다리지 않고 **지금** 신고한다 (사용자 제보 2026-09-02, 3차) ──
        #
        # 하트비트 주기는 30초다. 깨우지 않으면 claude 가 22.7초에 끝나도 그 목록은 최대
        # 30초를 더 기다리고, 사용자에게는 그 합이 「갱신이 안 된다」로 보인다. 여기서
        # 깨우면 플랫폼이 끝난 **직후** 신고가 나가고, 서버 지문이 바뀌어 화면이 받는다.
        _caps_nudge.set()

    _client_jobs = set()
    _client_rows = {}
    _client_status = {}

    def _write_client_status():
        filename = os.environ.get("BRIDGE_RUNTIME_SELECTION")
        if not filename: return
        temp = None
        try:
            fd, temp = tempfile.mkstemp(prefix=".runtime-status-", dir=os.path.dirname(filename))
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"instance": os.environ.get("BRIDGE_RUNTIME_INSTANCE", ""),
                           "pid": os.getpid(), "locations": _client_status}, stream)
            os.replace(temp, os.path.splitext(filename)[0] + ".ready.json")
        except OSError:
            pass
        finally:
            if temp:
                try: os.unlink(temp)
                except OSError: pass

    def _client_reported(rows):
        with _caps_publish_lock:
            targets = client_runtime_selection() or {}
            for row in rows:
                name = row.get("runtime")
                target = row.get("_client_location")
                if target and target == targets.get(name):
                    _client_status[name] = {"target": target, "state": "ready"}
            _write_client_status()

    def _negotiate_client_caps():
        targets = client_runtime_selection() or {}
        with _caps_publish_lock:
            removed = False
            for name in list(_client_rows):
                if (_client_rows[name].get("_client_location") != targets.get(name)):
                    _client_rows.pop(name, None)
                    caps.pop(name, None)
                    removed = True
            if removed:
                rows = list(_client_rows.values())
                if not rows: note_ai_probing("선택한 위치의 모델을 확인하는 중입니다.")
                _publish_caps(rows, {r["runtime"]: caps[r["runtime"]] for r in rows})
            for name, target in targets.items():
                key = (name, json.dumps(target, sort_keys=True))
                if name in _client_rows or key in _client_jobs: continue
                _client_jobs.add(key)
                if name not in _caps_asked: _caps_asked.append(name)
                _client_status[name] = {"target": target, "state": "pending"}
                cached = (caps.get(name) or conf_caps.get(name) or {}) if not args.refresh_caps else {}
                if cached.get("client_location") != target: cached = {}
                _CAPS_NEGOTIATING[0] = True
                def run(name=name, target=target, key=key, cached=cached):
                    failure = None
                    try:
                        got, detail = resolve_caps(name, {name: cached} if cached else None,
                                                   args.refresh_caps,
                                                   baseline=None if args.refresh_caps else dict(_caps_baseline))
                        with _caps_publish_lock:
                            if target != (client_runtime_selection() or {}).get(name): return
                            row = next((r for r in got if r.get("runtime") == name and r.get("models")
                                        and r.get("source") != "baseline"), None)
                            if row:
                                _client_rows[name] = dict(row, _client_location=target)
                                caps[name] = dict(detail[name], client_location=target)
                            else:
                                failure = {"target": target, "state": "failed", "failed_at": time.time_ns(),
                                                        "detail": "모델을 확인하지 못했습니다. 다시 연결해 주세요."}
                            active = client_runtime_selection() or {}
                            rows = [r for n, r in _client_rows.items() if r["_client_location"] == active.get(n)]
                            details = {r["runtime"]: caps[r["runtime"]] for r in rows}
                            _publish_caps(rows, details)
                            if rows: note_ai_outcome(True)
                            elif not any(v.get("state") == "pending" for n, v in _client_status.items() if n != name):
                                note_ai_unusable("연결된 AI의 모델을 확인하지 못했습니다.")
                            if caps: save_conf(args.base, args.ca, "", args.cmd, caps=caps)
                    except Exception:
                        with _caps_publish_lock:
                            if target == (client_runtime_selection() or {}).get(name):
                                failure = {"target": target, "state": "failed", "failed_at": time.time_ns(),
                                                        "detail": "모델 확인에 실패했습니다. 다시 연결해 주세요."}
                        _log_exc("client_caps")
                    finally:
                        with _caps_publish_lock:
                            _client_jobs.discard(key)
                            if failure and target == (client_runtime_selection() or {}).get(name):
                                _client_status[name] = failure
                            _CAPS_NEGOTIATING[0] = bool(_client_jobs)
                            _write_client_status()
                threading.Thread(target=run, name="client-caps-" + name, daemon=True).start()
            _write_client_status()

    def _negotiate_caps(wait_baseline: bool = False) -> None:
        if client_runtime_selection() is not None:
            if wait_baseline and not args.refresh_caps: _baseline_ready.wait(_CAPS_BASELINE_WAIT_SEC)
            _negotiate_client_caps()
            return
        with _negotiate_lock:
            _negotiate_caps_impl(wait_baseline)

    def _negotiate_caps_impl(wait_baseline: bool = False) -> None:
        """능력 협상 1회. 결과는 `runtimes`·`caps` 를 **제자리** 갱신한다."""
        # baseline 은 하트비트 응답으로 온다 — 배경 협상은 그 첫 응답을 짧게 기다린다.
        # 상한을 두는 이유: 서버가 느리거나 응답하지 않아도 협상은 **반드시** 진행돼야 한다
        # (기다림이 곧 웹 선택기의 공백이고, 그것이 이번에 고치는 마찰이다).
        if wait_baseline and not args.refresh_caps:
            _baseline_ready.wait(_CAPS_BASELINE_WAIT_SEC)
        # ⚠ `conf_caps`(기동 시점 파일)가 아니라 **지금까지 얻은 것**을 넘긴다. 재시도가
        #   생기면서 이 차이가 생겼다: 회차마다 파일 스냅샷을 넘기면 앞 회차에 성공한
        #   런타임을 다음 회차가 **다시 묻는다**(그 AI 의 토큰을 이유 없이 태우고, 흔들리는
        #   답이 이미 안정된 목록을 덮을 수도 있다). `caps` 는 성공분만 누적하므로
        #   `resolve_caps` 의 `ask` 계산이 «아직 못 얻은 것» 으로 저절로 좁아진다.
        _round = _caps_round[0] + 1
        _caps_round[0] = _round
        _cached = None if args.refresh_caps else (_snapshot_caps() or conf_caps or None)
        _targets = client_runtime_selection()
        if _targets is not None:
            _cached = {name: value for name, value in (_cached or {}).items()
                       if name in _targets and value.get("client_location") == _targets[name]}
        _base = None if args.refresh_caps else (dict(_caps_baseline) or None)
        # 자기갱신이 이 창을 「유휴」로 오판해 `os.execv` 하지 않도록 표시한다
        # (codex R4 P2-9 — `try_self_update` 의 `_CAPS_NEGOTIATING` 가드).
        # `finally` 로 반드시 내린다: 여기서 새면 그 프로세스는 자기갱신을 **영구히**
        # 못 하고, 낡은 러너가 낡은 동작으로 계속 돈다(고치려던 것보다 나쁜 상태다).
        # 협상에 들어가는 순간부터 **화면은 「확인 중」이어야 한다** (TASK-20260903T200000).
        # 종전에는 이 구간이 「대기 중」(정상)으로 보였고, 그 사이 AI 가 실은 응답 불가여도
        # 사용자는 협상이 끝날 때까지(실측 ~200초) 그 사실을 듣지 못했다.
        note_ai_probing("연결된 AI 가 답할 수 있는지 확인하는 중입니다.")
        _CAPS_NEGOTIATING[0] = True
        try:
            _got, _detail = resolve_caps(args.ai or None, _cached, args.refresh_caps,
                                         baseline=_base,
                                         on_settled=_publish_caps_for(_round, _targets),
                                         asked_out=_caps_asked)
        finally:
            _CAPS_NEGOTIATING[0] = False
        # 최종 게시 — 중간 신고와 같은 경로를 쓴다. 두 경로를 따로 쓰면 한쪽만 고쳐지는 날
        # 「부분은 되는데 최종이 안 되는」(또는 반대) 상태가 되고, 그 차이는 라이브에서만
        # 드러난다.
        _publish_caps_for(_round, _targets)(_got, _detail)
        if _got:
            _log("고를 수 있는 것: " + " · ".join(
                f"{r['label']}({len(r['models'])}종"
                + (f", 추론 {len(r['efforts'])}단계" if r["efforts"] else "")
                + ")" for r in _got))
            # 출처 표기에서 「내장 기본값」을 뺀다 (2026-08-31). 모델 목록 폴백이 없어졌으므로
            # 여기 오른 런타임은 **전부** 그 AI 가 답한 것이다. 없는 출처를
            # 이름으로 남겨 두면 다음 사람이 그 경로가 아직 있다고 읽는다.
            _by_probe = [n for n, c in caps.items() if (c or {}).get("source") == "probe"]
            # 확인 경로(`verified`)는 **따로 센다** (TASK-20260902T140200). 「직전 목록을
            # 대조해 확인받았다」와 「처음부터 열거했다」는 안정성이 다른 사실이고, 둘을
            # 한 이름으로 뭉개면 목록이 왜 안정됐는지(또는 왜 아직 흔들리는지) 조사할 수 없다.
            _by_verify = [n for n, c in caps.items() if (c or {}).get("source") == "verified"]
            _src = []
            if _by_probe:
                _src.append("본인 응답 " + ", ".join(_by_probe))
            if _by_verify:
                _src.append("직전 목록 확인 " + ", ".join(_by_verify))
            _log("  출처: " + (" · ".join(_src) if _src else "실조회")
                 + ("" if args.refresh_caps or not _cached else " (캐시 — 갱신은 --refresh-caps)"))
        else:
            _log("고를 수 있는 AI 를 찾지 못했습니다 — 웹 선택기는 표시되지 않습니다."
                 " (질문 처리는 이 머신의 AI 기본 설정으로 계속 진행됩니다.)")
        # 물어서 얻은 답을 남긴다(다음 기동은 묻지 않는다). 저장 실패는 기동을 막지 않는다 —
        # 그때는 다음에 다시 묻게 될 뿐이다.
        # 표 밖 CLI 는 질의가 **통한 호출 형태**를 알아냈다 — 실제 질문도 그 형태로 보낸다
        # (기본 추정 `-p` 가 아니라). 이것이 없으면 질의는 성공했는데 답변만 실패한다.
        # ⚠ 제자리 갱신이다 — 대기 루프가 이 리스트를 워커에 그대로 넘긴다.
        _learned = (caps.get(kind) or {}).get("argv")
        if _learned and kind not in _RUNTIME_SPECS:
            argv[:] = list(_learned)
        if caps:
            save_conf(args.base, args.ca, (args.ai or ""), args.cmd, caps=caps)
        # ── 「모른다」를 남기지 않는다 (TASK-20260903T200000) ─────────────────────
        #
        # 캐시가 있으면 위 협상은 **아무것도 묻지 않는다**(`ask` 가 빈다). 그러면 여기까지
        # 와도 원장은 `None` 이고, 화면은 「확인 중」에 영구히 머문다 — 거짓은 아니지만
        # 사용자에게 쓸모가 없다. 사용자 라이브가 정확히 이 경로였다: 캐시된 caps +
        # 만료된 claude OAuth → 협상이 돌지 않아 관측 기회가 없었고 화면은 정상이었다.
        #
        # 그래서 짧은 생존 확인 1회로 반드시 `True`/`False` 중 하나로 떨어뜨린다.
        if ai_health()[0] is None:
            confirm_ai_or_report(kind, list(argv))

    def _needs_retry() -> bool:
        """**물어봤는데 실조회로 확인하지 못한 런타임이 남았는가.**

        판정 모수는 신고 목록이 아니라 **직전 회차가 물어본 런타임 집합**(`_caps_asked`)이다.
        신고 목록만 보면 한 런타임이 성공하는 순간 재시도가 멎어, 같은 머신의 **다른**
        런타임이 빈 목록·원장 폴백에 영구히 갇힌다 — claude 는 답하고 codex 는 못 답하는
        조합이 실제로 이 프로젝트의 라이브 형태다 (codex 적대리뷰 P2-1, 2026-09-07).

        런타임 하나가 «아직» 인 조건은 둘이다:

        - 신고에 **아예 없다** — 물어봤는데 아무것도 못 얻었다.
        - 신고에 있는데 출처가 `baseline` 이다 — 원장 폴백은 확인을 통과한 값이 아니라
          화면을 비우지 않으려고 임시로 얹은 것이다. 실조회가 성공하면 그것을 덮는다.

        ⚠ 아직 한 번도 물어보지 못했으면(`_caps_asked` 가 빈 첫 진입) 신고 유무로 본다 —
          모수를 모르는 상태에서 「남은 것 없음」으로 읽으면 재시도가 시작조차 하지 않는다.

        `runtimes` 항목의 `source` 는 서버로 나가는 신고에 실려 있다(`_assemble`).
        """
        confirmed = {str((r or {}).get("runtime") or "") for r in runtimes
                     if str((r or {}).get("source") or "") not in ("", "baseline")}
        if not _caps_asked:
            return not confirmed
        return any(n not in confirmed for n in _caps_asked)

    def _negotiate_caps_until_reported(stop: threading.Event,
                                       immediate: bool = True) -> None:
        """신고할 목록을 **얻을 때까지** 협상을 되풀이한다 (사용자 제보 2026-09-07).

        ## 무엇을 고치는가

        종전에는 이 자리가 `_negotiate_caps(wait_baseline=True)` **1회**였다. 그 1회가
        아무것도 얻지 못하면 그 러너가 사는 동안 웹 선택기는 영영 비어 있는다 — 그런데
        서버가 그 자리에 내보내는 문구는 「연결된 본인 AI 에게 쓸 수 있는 모델을 확인하는
        중입니다」다. **화면은 진행 중이라고 말하는데 실제로는 아무것도 다시 확인하지 않는**
        상태였고, 사용자에게는 「AI 는 연결됐는데 모델 목록이 안 나온다」로 보였다.

        실패 사유는 다시 물으면 풀리는 종류가 흔하다 — 라이브 관측: `OAuth access token has
        expired`(로그인하면 풀린다) · `TimeoutExpired`(그때 그 머신이 느렸다) · 그리고 이
        파일이 이미 기록한 「codex 는 같은 조건에서 성공과 실패를 오간다」.

        ## 멈추는 조건은 둘뿐이다

        - **실조회로 확인된 목록을 얻었다** (`_needs_retry()` 가 거짓). 원장 폴백뿐인 목록은
          여기 해당하지 않는다 — 그 판정은 `_needs_retry` 에 있다.
        - **러너가 내려간다** (`stop` — 종료·로그아웃·자기갱신 재기동). `Event.wait` 로
          기다리므로 대기 중에도 즉시 깨어난다. `time.sleep` 이면 최대 15분을 붙잡는다.

        ⚠ 「몇 번까지」를 두지 않는다. 총 횟수를 정해 멈추면 한 시간 뒤에 CLI 로그인을 고친
          사용자가 목록을 영영 못 받는데, 그것이 이 재시도가 없애려는 상태와 **같은 상태**다.
          비용은 간격 사다리(`_CAPS_RETRY_BACKOFF_SEC`)가 억제한다 — 천장에서 시간당 4회다.

        `immediate=False` 는 **직전에 이미 한 회차를 돌린** 호출부용이다(표 밖 CLI 의 동기
        협상). 그 자리에서 곧바로 같은 협상을 또 돌리면 방금 태운 비용을 즉시 반복한다.
        """
        if immediate:
            _negotiate_caps(wait_baseline=True)
        attempt = 0
        while not stop.is_set() and _needs_retry():
            # 천장은 **화면이 지금 무엇을 보여주는가**로 갈린다 (적대리뷰 P2, 2026-09-07).
            # 원장 폴백이라도 목록이 서 있으면 사용자는 막혀 있지 않다 — 그때까지 15분마다
            # 개인 계정 토큰으로 질의를 태울 이유가 없다. 아무것도 못 보여주는 동안만 빠르다.
            _ceiling = (_CAPS_RETRY_CEILING_SHOWING_SEC if runtimes
                        else _CAPS_RETRY_CEILING_SEC)
            delay = (_CAPS_RETRY_BACKOFF_SEC[attempt] if attempt < len(_CAPS_RETRY_BACKOFF_SEC)
                     else _ceiling)
            attempt += 1
            log_event("caps.retry_scheduled",
                      f"쓸 수 있는 모델을 아직 받지 못했습니다 — {int(delay)}초 뒤 다시 물어봅니다.",
                      level="INFO", attempt=attempt, delay_sec=delay)
            if stop.wait(delay):
                return
            # ⚠ 대기 뒤 **다시 본다**. 대기 중에 다른 경로(사용자의 `--refresh-caps` 재기동은
            #   새 프로세스이므로 해당 없지만, 부분 신고 콜백 `_publish_caps`)가 목록을
            #   채웠을 수 있고, 그때 한 번 더 묻는 것은 순수한 낭비다.
            if not _needs_retry() or stop.is_set():
                return
            # baseline 은 이미 받아 뒀다 — 회차마다 다시 기다리면 그만큼 공백이 길어진다.
            _negotiate_caps()
        if runtimes and attempt and not _needs_retry():
            _log("쓸 수 있는 모델을 받았습니다 — 웹 선택기에 나타납니다.")

    def _watch_client_selection() -> None:
        def revision():
            try:
                stat = os.stat(os.environ["BRIDGE_RUNTIME_SELECTION"])
                return stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns
            except OSError: return None
        previous = None
        while not heartbeat_stop.wait(1):
            current = revision()
            if current != previous:
                previous = current
                try:
                    _negotiate_caps()
                except Exception as exc:
                    _log_exc("caps.selection_refresh_fail", "연결 위치 변경 확인 실패", exc)

    if args.cmd:
        _log("모델·추론등급은 --cmd 의 명령이 정합니다(웹 선택기는 표시되지 않습니다).")
        # `--cmd` 는 협상을 돌지 않으므로 여기서도 원장이 `None` 으로 남는다. 같은 함수로
        # 떨어뜨린다 — 「확인 중이 영구 상태가 되는 경로」를 하나도 남기지 않기 위함이다.
        note_ai_probing("연결된 AI 가 답할 수 있는지 확인하는 중입니다.")
        threading.Thread(
            target=lambda: confirm_ai_or_report("custom", shlex.split(args.cmd)),
            name="bridge-liveness", daemon=True).start()
    elif _caps_first:
        # 이 CLI 는 호출 형태를 협상에서 배운다 — 배우기 전에 질문을 받으면 답하지 못한다.
        _negotiate_caps()

    # 연결 유지 신호를 먼저 띄운다 — 첫 질문이 오기 전(대기만 하는 동안)에도 토큰 수명이
    # 밀려야 하고, 화면의 '대기 중' 표시도 그때부터 참이어야 한다.
    heartbeat_stop = threading.Event()
    start_heartbeat(api, heartbeat_stop, runtimes, batch_override=_batch_override,
                    baseline_out=_caps_baseline, baseline_ready=_baseline_ready,
                    nudge=_caps_nudge,
                    on_reported=_client_reported if client_runtime_selection() is not None else None)
    if os.environ.get("BRIDGE_RUNTIME_SELECTION") and not args.cmd:
        threading.Thread(target=_watch_client_selection, daemon=True).start()
    # 자기 갱신이 재기동 직전에 하트비트를 끊을 수 있게 손잡이를 건넨다 — `os.execv` 는
    # `atexit` 를 부르지 않으므로, 여기서 끊지 않으면 서버는 사라진 프로세스를 계속 «대기 중»
    # 으로 읽는다.
    _SELF_UPDATE_STOP[0] = heartbeat_stop.set

    # ⚠ 문(gate)의 술어도 `_needs_retry()` 다 (적대리뷰 P2, 2026-09-07). `not runtimes` 로
    #   두면 **다른 런타임이 하나라도 신고되면** 표 밖 CLI 가 argv 를 못 배운 채 재질의
    #   기회를 0 으로 잃는다 — `_needs_retry` 를 만든 이유가 바로 그 술어 오류인데 문에는
    #   옛 술어가 남아 있었다(고친 판정과 그 판정을 부르는 자리가 갈린 형태).
    if not args.cmd and (not _caps_first or _needs_retry()):
        # 협상은 **뒤에서** 한다. 끝나면 위 `runtimes` 가 제자리로 갱신되고 다음 하트비트가
        # 새 목록을 싣는다 — 그때까지 웹 선택기만 비어 있고, 질문 처리는 이미 살아 있다.
        #
        # ⚠ **`_caps_first`(표 밖 CLI) 도 아무것도 못 얻었으면 여기로 온다** (2026-09-07).
        #   그쪽은 위에서 이미 한 번 동기 협상을 돌았지만, 실패했을 때 재시도할 자리가
        #   없었다 — 재시도를 «표 안 CLI 전용» 으로 두면 같은 결함이 한 갈래에만 남는다
        #   (§16.7 G8: 정책을 고쳤으면 적용면을 전수로 본다).
        #
        # ⚠ 이 경로가 **웹 화면의 공백 창**을 만든다는 사실이 이번 수정의 출발점이다. 그
        #   공백 자체는 의도된 것이고(질문 처리를 먼저 살린다), 결함이었던 것은 **공백이
        #   끝난 사실을 화면이 모른다**는 쪽이었다 — 서버 `caps_rev` 지문과 프런트
        #   `onCapsChange` 가 그 축을 닫는다.
        # baseline 을 짧게 기다린 뒤 확인 질의로 간다 — 기다림 없이 출발하면 확인 경로가
        # 사실상 발화하지 않고, 그러면 목록 안정화라는 이 cycle 의 절반이 코드로만 존재한다.
        threading.Thread(
            target=lambda: _negotiate_caps_until_reported(heartbeat_stop,
                                                          immediate=not _caps_first),
            name="bridge-caps", daemon=True).start()

    cancels = CancelRegistry()
    #: 동시 처리 슬롯. 수요가 오면 늘고, 안 쓰면 오래된 것부터 준다.
    pool = WorkerPool(workers, max_workers, idle_sec, time.monotonic())
    #: 지금 처리 중인 task. 종료 시 '유휴인가' 를 물을 수 있게 한다(TASK-20260828T150000).
    #: 슬롯(`pool`)과 다른 사실을 센다 — 저쪽은 '자리가 몇 개인가', 이쪽은 '무엇이 돌고 있는가'.
    active = ActiveTasks()
    #: 점유가 반복 실패한 task — 같은 것을 무한히 다시 시도해 서버를 두드리지 않도록 건너뛴다.
    skip: set[str] = set()
    #: 서버에 대기 질문이 있는데 한 건도 처리하지 못한 연속 라운드 수(spin 감지).
    stalled = 0
    done_once = threading.Event()

    #: 연결이 끊겼을 때의 복구 간격(feature-0045). 대기가 아니라 재연결이므로 sleep 이 있다.
    backoff = 0.0

    log_event(_EV_RUN_READY,
              "대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. "
              f"(동시 {workers}건에서 시작 · 수요 시 최대 {max_workers} · "
              f"{int(idle_sec)}초 유휴 시 회수 · Ctrl+C 로 종료)",
              runtime=kind, workers=workers, max_workers=max_workers,
              idle_sec=int(idle_sec),
              startup_ms=int((time.monotonic() - _RUN_T0) * 1000))
    while True:
        # ⚠ **여기서 워커 자리를 잡지 않는다** (codex P1-2, 2026-08-28).
        #
        # 종전에는 `slots.acquire()` 가 이 앞에 있었다(tight loop 차단 목적). 그런데 취소와 새
        # 질문은 **같은 응답**으로 오므로, 자리가 없어 여기서 멈추면 `wait_for_request` 를 아예
        # 부르지 않게 되고 **취소 통보도 함께 끊긴다** — 워커가 다 찬 동안 사용자가 중단을 눌러도
        # 러너는 최대 `_AI_TIMEOUT_SEC`(약 28분) 동안 모른 채 개인 계정 토큰을 계속 태운다.
        # 취소를 즉시 인지시키려던 설계가 정작 가장 필요한 순간에 꺼져 있었다.
        #
        # 그래서 **대기는 항상** 하고, 자리는 디스패치 직전에 **비차단으로** 잡는다.
        # ⚠ 대기 자체에는 여전히 sleep 이 없다 — 대기는 서버가 한다.
        # 같은 계정에 최신 러너가 붙었으면 **여기서 물러난다** (TASK-20260901T173000).
        #
        # 대기 호출 **앞**에 둔다: 뒤에 두면 최대 대기시간(수십 초) 동안 새 질문을 자기 쪽으로
        # 끌어와 놓고 물러나게 되고, 그 사이 사용자는 이미 최신 러너를 띄워 두고도 옛 답을
        # 한 번 더 받는다. 종료 절차는 로그아웃과 **같은 한 곳**(`shutdown_after_drain`)이다 —
        # 하던 일은 마치고 나간다.
        if _SUPERSEDED.is_set():
            heartbeat_stop.set()
            idle = shutdown_after_drain(active, cancels)
            log_event(_EV_HB_SUPERSEDED,
                      "더 나중에 연결된 러너에 자리를 넘기고 종료합니다.",
                      level="WARN", idle=idle, active=active.count())
            _log("  이 러너는 더 이상 필요하지 않습니다 — 같은 계정에 더 나중에 연결된")
            _log("  러너가 이미 질문을 처리하고 있습니다(한 계정에는 러너 하나만 남깁니다).")
            return 0
        # 배포본과 달라졌으면 **여기서** 갈아 끼우고 다시 뜬다 (TASK-20260902T140000).
        #
        # 자리는 `_SUPERSEDED` 바로 뒤, 대기 호출 **앞**이다. 물러남이 갱신보다 먼저인 이유:
        # 이미 자리를 넘기기로 한 러너를 최신으로 만들 이유가 없다(곧 종료된다). 대기보다
        # 앞인 이유는 같다 — 뒤에 두면 수십 초짜리 대기에서 질문 하나를 끌어와 놓고 갱신하러
        # 나가게 되고, 그러면 «옛 코드가 그 질문을 처리» 하거나 «점유만 하고 사라진다».
        # 진행 중 작업이 있으면 `try_self_update` 가 알아서 이번 회차를 넘긴다.
        if _SELF_UPDATE.is_set():
            try_self_update(api, active)
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            # 연결이 **명시적으로** 해제됐다(로그아웃, 또는 러너가 오래 멈춰 있어 만료).
            # 사용자 요구(2026-08-28): 이때 러너도 안전하게 종료된다 — 다만 하던 일을 먼저
            # 마친다. 종료 절차는 `shutdown_after_drain` 한 곳이 정본이다.
            log_event(_EV_CONN_UNAUTH, "토큰이 무효해졌습니다(로그아웃 또는 만료).",
                      level="ERROR", http=401, active=active.count())
            # 죽은 토큰으로 30초마다 계속 두드리지 않는다.
            heartbeat_stop.set()
            shutdown_after_drain(active, cancels)
            # 다시 띄우는 **정확한 명령**을 준다 — 설정은 이미 저장돼 있으므로 토큰만 새로 받으면
            # 된다. (자발적 종료여도 안내는 남긴다: 로그아웃이 의도치 않았을 수 있다.)
            _log("  다시 연결하려면:")
            _log("  1) 웹 대화 화면에서 'AI 연결하기' → [연결 정보 만들기] → 토큰 복사")
            _log(f"  2) python3 {os.path.basename(__file__)} --resume --token <새 토큰>")
            return 3
        # ⚠ `if code:` 로 쓰면 안 된다 — 연결 실패의 `_http` 는 **0** 이고 0 은 falsy 라
        #   바로 이 블록(백오프)을 건너뛴다. 아래 주석이 설명하는 동작이 정작 코드에는 없었다
        #   (라이브 실측 2026-08-28: 사설 CA 미지정 → 매 호출 실패인데 성공 경로로 흘러 빈
        #   응답을 정상 처리하다 spin 가드로 사망). 실패는 `_failed` 로 명시 판정한다.
        if code or res.get("_failed"):
            # feature-0045: 서버가 배포로 교체되는 동안은 **연결 자체가 실패**한다(`_http == 0`).
            # 종전에는 곧바로 `continue` 였는데, 그러면 서버가 없는 몇 초 동안 초당 수천 번을
            # 재시도해 사용자 머신의 CPU 를 태운다(대기에 sleep 이 없다는 설계가, 실패 경로에서는
            # 정확히 반대로 작용했다). **대기에는 여전히 sleep 이 없다** — 여기서 쉬는 것은 대기가
            # 아니라 **연결 복구**다. 두 가지는 다른 일이고, 다르게 다뤄야 한다.
            backoff = min(_RECONNECT_BACKOFF_MAX, (backoff * 2) or _RECONNECT_BACKOFF_START)
            log_event(_EV_CONN_RETRY, "대기 실패 — 잠시 뒤 다시 연결합니다", level="WARN",
                      http=code, backoff_sec=round(backoff, 1),
                      detail=str(res.get("error") or "")[:200])
            time.sleep(backoff)
            continue
        backoff = 0.0
        if res.get("draining"):
            # feature-0045: 배포 교대다. **오류가 아니므로 백오프하지 않는다** — 곧바로 다시
            # 부르면 남은 인스턴스가 받는다. 다만 이 응답은 **즉시** 오고, 엣지가 그 인스턴스를
            # 후보에서 빼기까지 짧은 창(health_interval 2s)이 있다. 그 창에서 sleep 0 으로
            # 재호출하면 초당 수십~수백 회가 되어 계정 시간당 호출 상한을 태우고 429 락아웃을
            # 만든다 — 실패 경로에서 없앤 hot loop 를 성공 경로에 다시 만드는 셈이다.
            # 인지 지연이 무시할 만큼 짧은 하한만 둔다(백오프가 아니다 — 자라지 않는다).
            log_event("conn.draining", "서버 인스턴스 교대 중 — 곧바로 다시 대기합니다.",
                      level="DEBUG")
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 취소는 **새 질문과 같은 응답**으로 온다(별도 채널이 아니다 — P0-J 의 즉시 인지가
        # 취소에도 그대로 적용된다). 진행 중인 워커가 다음 확인 시점에 이것을 보고 하차한다.
        fresh = cancels.add_many(res.get("canceled_task_ids") or [])
        if fresh:
            log_event(_EV_TASK_CANCEL, "취소 통보 — 진행 중이면 중단합니다", level="WARN",
                      at="notified", count=len(fresh), tasks=list(fresh))

        # ── 유휴 슬롯 회수 ─────────────────────────────────────────────────
        # 여기가 **tick 이다.** 서버가 대기를 최대 55초 보류하므로 이 루프는 적어도 그 간격으로
        # 돈다 — 시간을 재려고 타이머 스레드를 띄우거나 서버를 두드릴 필요가 없다(폴링 금지와
        # 정합). 조용한 시간대에는 타임아웃 라운드가 곧 회수 라운드가 된다.
        # ⚠ 대기 질문이 있으면 회수하지 않는다. 곧 쓸 자리를 버리면 바로 다시 늘려야 하고,
        #   그 사이 `available=0` 인 창이 생겨 진행이 멈출 수 있다(codex 리뷰 P1 후단).
        if not (res.get("task_ids") or []):
            reaped = pool.reap(time.monotonic())
            if reaped:
                _log(f"유휴 슬롯 {reaped}개 회수 — 동시 처리 {pool.capacity}건")

        # skip 은 영구 블랙리스트가 아니다 — **대기가 실제로 비어서 타임아웃했을 때만** 비운다.
        #
        # 왜 비워야 하나: 다른 러너가 집어 간 작업을 skip 에 넣었는데 그쪽이 죽어 lease 가
        # 만료되면 그 작업은 대기열로 돌아온다. 그때도 계속 건너뛰면 **러너가 돌고 있는데도
        # 사용자는 답을 못 받는다.**
        #
        # 왜 하필 타임아웃 시점인가: "남은 것이 전부 skip" 일 때 비우면, 실패가 반복될 경우
        # 비움 → 재시도 → 실패 → 다시 전부 skip → 비움 … 이 간격 없이 돌아 tight loop 가 된다.
        # 타임아웃은 서버가 55초를 붙들었다는 뜻이라 그 자체가 자연스러운 재시도 간격이다.
        if res.get("timed_out"):
            skip.clear()
            stalled = 0

        pending = [str(t) for t in (res.get("task_ids") or []) if str(t) not in skip]
        if not pending:
            # 서버는 대기 질문이 **있다**고 했는데(즉시 반환) 우리가 전부 건너뛰는 중이다.
            # 이 상태로 `continue` 하면 `wait_for_request` 가 또 즉시 돌아와 **간격 없이 서버를
            # 두드린다** — 우리가 없애려던 바로 그 폴링이, 그것도 최악의 형태로 생긴다.
            #
            # **서버가 open task 를 실제로 보고했을 때만** 집계한다(2026-08-28 라이브 실측):
            # `timed_out` 은 취소 통보로도 False 가 되고 그때 `task_ids` 는 비어 있다 —
            # 처리할 것이 없는데 "처리 못 했다" 고 세면 안 된다.
            #
            # ⚠ 여기서 **러너를 죽이지 않는다** (codex P1-4, 2026-08-28). 종전에는 20라운드 뒤
            #   `exit 4` 였는데, 그러면 **진행 중이던 다른 워커의 답변까지 함께 사라진다**.
            #   한 task 의 점유 실패(권한 재검증·원장 장애 등)로 러너 전체를 끄는 것은 blast
            #   radius 가 과하다. 대신 **경고하고 계속 산다** — 그 사이 다른 워커는 답을 제출하고,
            #   문제의 task 는 lease 만료나 서버측 종결로 자연히 빠진다.
            if res.get("task_ids"):
                stalled += 1
                if stalled == _MAX_STALLED_ROUNDS:
                    log_event("task.stalled",
                              "대기 질문을 연속으로 처리하지 못했습니다(점유 실패 반복). "
                              "서버 상태와 토큰 권한을 확인하세요 — 러너는 계속 대기합니다.",
                              level="ERROR", pending=len(res.get("task_ids") or []),
                              rounds=stalled)
                # 쉬는 것은 대기가 아니라 **재시도 간격**이다(hot loop 차단, 상한 있음).
                time.sleep(min(_RECONNECT_BACKOFF_MAX, _DRAINING_RETRY_FLOOR_SEC * stalled))
            continue
        stalled = 0

        # ── 수요 기반 확장 ─────────────────────────────────────────────────
        # 목표는 **진행 중 + 대기**다(상한까지). 대기 수만 보면 실행 중인 작업이 쓰는 자리를
        # 빼고 세어 과소 확장한다(codex 리뷰 P1). 관측된 수요에만 반응한다 — 예측이 빗나가면
        # 그 비용이 사용자 계정 쿼터로 나간다.
        added = pool.grow_for(len(pending))
        if added:
            _log(f"동시 요청 {len(pending)}건(진행 중 {pool.in_use}) — "
                 f"슬롯 {added}개 확장, 동시 처리 {pool.capacity}건")

        # 자리를 **비차단으로** 잡는다 — 없으면 이번 라운드는 디스패치를 건너뛴다.
        # 그 task 는 서버에 그대로 남아 다음 대기에서 다시 제안되고, 그동안에도 우리는
        # `wait_for_request` 를 계속 부르므로 **취소 통보가 끊기지 않는다**(P1-2 의 요지).
        #
        # ⚠ 여기서 `Condition` 으로 블로킹하지 않는 이유가 그것이다. 자리가 날 때까지 막으면
        #   더 정확해 보이지만, 막힌 동안 서버를 읽지 못해 **취소 인지가 자리 반납에 묶인다**.
        #   짧은 간격으로 되돌아오는 편이 취소를 더 빨리 본다.
        sid = pool.try_acquire()
        if sid is None:
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 점유는 **여기서** 한다(값싸고 즉시 끝난다). 점유하는 순간 그 task 는 다음
        # `wait_for_request` 결과에서 빠지므로, 워커가 다 찼을 때 같은 것을 다시 받지 않는다.
        task_id = pending[0]
        # `runner_instance` — 이 점유를 **어느 프로세스**가 들고 있는지 서버에 새긴다
        # (TASK-20260901T140000). 이 값이 있어야 다음 기동의 사망 신고가 정확히 이 점유만
        # 놓아준다. 없으면 종전 동작(lease 30분 대기)으로 자연 degrade 한다.
        claimed = api.call("claim_request",
                           {"task_id": task_id, "runner_instance": runner_instance()})
        if claimed.get("_http") == 409:
            log_event(_EV_TASK_CLAIM_SKIP, "이미 다른 세션이 가져갔다 — 건너뜀",
                      level="DEBUG", task=task_id, http=409)
            skip.add(task_id)
            pool.release(sid)
            continue
        if claimed.get("_http") or claimed.get("_failed"):
            # ⚠ `_failed`(연결 실패, `_http == 0`)를 함께 본다 (codex P2-2, 2026-08-28).
            #   앞선 수정은 대기 루프만 고쳤고 여기는 그대로였다 — claim 도중 TCP/TLS 가 끊기면
            #   **빈 응답을 정상 점유로 읽고** AI 를 돌려, 아무도 기다리지 않는 답을 만든다.
            log_event(_EV_TASK_CLAIM_FAIL, "점유 실패", level="WARN", task=task_id,
                      http=claimed.get("_http"),
                      detail=str(claimed.get("error") or "")[:200])
            # 일시 장애(연결 실패·5xx·429)는 **영구 skip 하지 않는다** — 그 task 는 정상이고
            # 잠시 뒤면 집을 수 있다. 영구 skip 은 "이미 남이 가져갔다"(409) 처럼 재시도해도
            # 달라지지 않는 경우에만 쓴다(codex P1-4 의 blast radius 축소와 같은 취지).
            _code = int(claimed.get("_http") or 0)
            if _code and _code < 500 and _code != 429:
                skip.add(task_id)
            pool.release(sid)
            continue

        # 진행 중 원장 등록은 **스레드를 띄우기 전**에 한다. 스레드 안에서 하면 그 사이에
        # 종료 절차가 유휴로 오판하고(카운트 0) 방금 점유한 작업을 두고 나간다.
        active.enter(task_id)

        def _work(tid: str = task_id, payload: dict = claimed, slot: int = sid) -> None:
            try:
                handle_one(api, tid, payload, kind, argv, args.cmd, cancels, runtimes, caps,
                           self_review=not getattr(args, "no_self_review", False))
            finally:
                cancels.forget(tid)
                active.leave(tid)
                # 반납 시각이 곧 그 슬롯의 `last_used` 다 — 회수 순서가 여기서 정해진다.
                pool.release(slot)
                done_once.set()

        try:
            threading.Thread(target=_work, daemon=True).start()
        except (RuntimeError, OSError) as e:  # 스레드 한도·메모리 부족
            # 여기서 그냥 터지면 **슬롯과 서버 점유가 함께 샌다** — 슬롯은 busy 인 채로,
            # task 는 lease 만료까지 남의 눈에 안 보인 채로 묶인다(codex 리뷰 P2).
            _log_exc("task.worker.spawn_fail",
                     "워커 스레드를 시작하지 못했습니다 — 자리를 반납하고 건너뜁니다.",
                     e, task=task_id, in_use=pool.in_use)
            pool.release(sid)
            continue
        if args.once:
            # 그 한 건이 **끝날 때까지** 기다린다. 바로 반환하면 daemon 스레드가 죽어
            # 답이 제출되지 않는다(`--once` 가 아무것도 안 하는 것과 같아진다).
            done_once.wait()
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log_run_stop("keyboard_interrupt")
        sys.exit(0)

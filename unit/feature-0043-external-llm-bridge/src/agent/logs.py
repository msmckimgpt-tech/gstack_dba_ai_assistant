"""로그 — 사람이 읽는 줄 + 기계가 감사하는 원장.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time

from .base import _CONF_DIR
from .state import runner_instance

# ── 로그 — 사람이 읽는 줄 + 기계가 감사하는 원장 (TASK-20260901T163000) ─────────
#
# ## 왜 구조가 필요한가 (실측 근거)
#
# 종전 로그는 `[bridge <시각>] <한국어 문장>` 한 형태뿐이었다. 사람이 읽기엔 좋았지만
# **사고를 조사하는 데 필요한 축이 문장 안에 녹아 있어** 꺼낼 수 없었다:
#
#   - 「이 줄이 무슨 사건인가」를 한국어 문장 매칭으로만 판별했다. 문장을 한 글자만 고쳐도
#     그동안 쓰던 조사 방법이 조용히 깨진다.
#   - 심각도가 없다. 「참고」와 「제출 실패」가 같은 모양이라 `grep` 로 오류만 볼 수 없었다.
#   - `task_id` 는 있는 줄과 없는 줄이 섞여 있고, **어느 프로세스가 쓴 줄인지**(러너 인스턴스)
#     는 어디에도 없다. 재기동이 잦은 러너에서 이건 치명적이다 — 실제 87분 고아 사고(§
#     `init_runner_instance` 주석)의 시간축을 파일 mtime·DB 하트비트로 복원해야 했다.
#   - 소요 시간이 없다. 「전달」과 「제출 완료」 사이가 몇 초였는지 두 줄의 시각을 빼서 구해야
#     하는데, 동시 처리(`--workers`)면 두 줄이 인터리브되어 그 뺄셈조차 틀린다.
#   - 예외는 `except Exception as e: _log(f"…: {e}")` 형태라 **예외 형(type)과 스택이 통째로
#     버려진다**. `e` 문자열만으로는 같은 문장을 내는 다른 원인을 가를 수 없다.
#   - Windows 는 로그 자체가 없었다. 설치 스크립트가 `Start-Process -WindowStyle Hidden` 으로
#     띄우면서 stderr 를 어디에도 잇지 않아, 그 머신의 사고는 **증거가 0** 이었다.
#
# ## 무엇을 하는가
#
# 한 번의 `_log`/`log_event` 호출이 **두 곳**에 간다:
#
#   1. **사람 sink** — stderr(그리고 필요하면 `bridge.log`). 종전 형식을 잃지 않되 심각도와
#      사건 코드·핵심 필드를 앞에 세운다:
#        `[bridge 2026-09-01 16:30:11+0900] ERROR task.submit.fail task=ab12 http=500 | 제출 실패 …`
#   2. **감사 sink** — `bridge.events.jsonl` 한 줄 JSON. 사람이 읽는 줄이 버리는 것(예외 형,
#      스택, 자식 stderr 전문, 밀리초 단위 소요)을 여기 남긴다. 기계가 읽으므로 문장을 고쳐도
#      조사 방법이 깨지지 않는다 — 안정 계약은 **문장이 아니라 `ev` 코드와 필드 이름**이다.
#
# ## 하지 않는 것
#
#   - `logging` 모듈을 쓰지 않는다. 이 파일은 남의 머신에서 남의 파이썬으로 도는 단일 파일이고,
#     전역 로거 설정은 그 환경의 다른 설정과 싸운다. 필요한 것은 두 sink 와 잠금뿐이다.
#   - 서버로 로그를 보내지 않는다. 이 파일의 보안 계약(`나가는 곳`)을 넓히지 않는다 —
#     서버와의 대조는 `task_id`·`run`(러너 인스턴스) 키로 사후에 한다.

#: 심각도. 사람 sink 와 감사 sink 가 각각 다른 하한을 가질 수 있다 — 화면은 조용하되 원장은
#: 상세해야 하기 때문이다(그 반대는 쓸모가 없다).
_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "FATAL": 50}


def _level_from_env(name: str, default: str) -> int:
    raw = (os.environ.get(name) or "").strip().upper()
    return _LOG_LEVELS.get(raw, _LOG_LEVELS[default])


#: 사람이 보는 줄의 하한. 기본 INFO — DEBUG 는 조사할 때만 켠다.
_LOG_LEVEL_MIN = _level_from_env("BRIDGE_LOG_LEVEL", "INFO")
#: 감사 원장의 하한. 기본 DEBUG — **원장은 빠짐없는 것이 목적**이라 화면보다 낮게 둔다.
_AUDIT_LEVEL_MIN = _level_from_env("BRIDGE_AUDIT_LEVEL", "DEBUG")

def _int_from_env(name: str, default: int, minimum: int) -> int:
    """환경변수 정수. **깨진 값으로 러너가 죽지 않게** 한다.

    로그 설정 오타(`BRIDGE_LOG_KEEP=three`)로 상주 러너가 기동조차 못 하면, 관측을 좋게
    하려던 축이 가용성을 깎는다. 못 읽으면 기본값을 쓰고 그 사실만 남긴다.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


#: 원장 파일이 이 크기를 넘으면 회전한다. 상주 프로세스가 몇 달을 도는 것이 정상이므로
#: 상한이 없으면 디스크를 조용히 먹는다(그리고 그 조용함이 정확히 이 파일이 고치려는 병이다).
_LOG_MAX_BYTES = _int_from_env("BRIDGE_LOG_MAX_BYTES", 8 * 1024 * 1024, 64 * 1024)
#: 보관 세대 수. 사고 조사는 보통 직전 며칠이면 되고, 무한 보관은 위 상한을 무의미하게 만든다.
_LOG_KEEP = _int_from_env("BRIDGE_LOG_KEEP", 3, 1)

#: 두 sink 와 순번을 함께 지키는 잠금. 워커 스레드·하트비트 스레드가 동시에 쓴다.
_LOG_LOCK = threading.RLock()
#: 이 프로세스 안에서의 사건 순번. 같은 초에 여러 줄이 나도 **순서**를 잃지 않게 한다
#: (동시 처리에서 시각만으로는 인터리브 순서를 복원할 수 없다).
_LOG_SEQ = 0

#: 사건 코드별 발생 횟수. 종료 요약(`run.stop`)이 이 표를 그대로 싣는다 — 「이번 세션에서
#: 질문 몇 건을 처리했고 몇 번 실패했나」를 로그 전체를 훑지 않고 마지막 한 줄로 알 수 있다.
_STATS: dict[str, int] = {}
#: 프로세스 시작 시각(단조). 종료 요약의 `uptime_sec`.
_RUN_T0 = time.monotonic()

#: 로그에서 마스킹할 비밀 문자열(토큰 등). 값을 **아는 채로** 지우는 것이 패턴 추측보다 확실하다.
_LOG_SECRETS: set[str] = set()
#: 값을 모를 때를 위한 패턴 방어. 위 등록이 누락돼도 형태로 잡는다.
_SECRET_PATTERNS = (
    re.compile(r"\bmat_[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(BRIDGE_TOKEN|token)\s*[=:]\s*[\"']?[A-Za-z0-9._\-]{8,}"),
)


def register_secret(value: str | None) -> None:
    """이 값이 로그에 나타나면 지운다. 토큰을 손에 쥔 **직후** 부른다.

    패턴만으로 막지 않는 이유: 토큰 형식은 바뀔 수 있고, 바뀐 그날의 로그가 새는 것을
    나중에 알아채는 방법이 없다. 값을 알고 있을 때 등록해 두는 편이 확실하다.
    """
    v = (value or "").strip()
    if len(v) >= 8:
        _LOG_SECRETS.add(v)


def _scrub(text: str) -> str:
    """비밀을 지운 문자열. 두 sink 모두 이 함수를 거친 것만 쓴다.

    ⚠ 집합을 **스냅샷으로** 돈다: 다른 스레드가 `register_secret` 하는 순간 집합을 순회 중이면
    `RuntimeError: Set changed size during iteration` 이 나고, 그 예외가 하필 **로그를 쓰는
    도중** 터진다(= 그 사건이 통째로 사라진다).
    """
    out = str(text)
    for s in tuple(_LOG_SECRETS):
        if s and s in out:
            out = out.replace(s, "***")
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: m.group(0)[:6] + "***", out)
    return out


def _log_dir() -> str:
    """로그가 사는 곳. 기본은 설정과 같은 폴더 — 사고 조사에서 둘을 함께 본다.

    `BRIDGE_LOG_DIR` 로 옮길 수 있게 두되 **설정 경로(`_CONF_DIR`)는 건드리지 않는다**:
    그쪽을 움직이면 이미 저장된 설정이 보이지 않게 되어, 로그를 좋게 하려다 연결을 깬다.
    """
    return (os.environ.get("BRIDGE_LOG_DIR") or "").strip() or _CONF_DIR


def _audit_path() -> str:
    return os.path.join(_log_dir(), "bridge.events.jsonl")


#: `_human_log_path` 의 1회 판정 결과. `Event` 를 쓰는 이유는 「아직 안 정했다」와
#: 「정했는데 None(=쓰지 않는다)」을 구분해야 하기 때문이다.
_HUMAN_LOG_RESOLVED = threading.Event()
_HUMAN_LOG_PATH: str | None = None


def _human_log_path() -> str | None:
    """사람 줄을 **파일로도** 적어야 하는가. 적어야 하면 그 경로, 아니면 `None`.

    ## 왜 자동 판정인가

    POSIX 설치 스크립트는 러너의 stderr 를 `bridge.log` 로 잇는다. 그 상태에서 이 함수가
    같은 파일을 또 열면 **모든 줄이 두 번** 남는다. 반대로 Windows 설치본은 stderr 를 아무
    데도 잇지 않아 **한 줄도 남지 않았다** — 그 머신의 사고는 증거가 없었다.

    두 경우를 사용자가 설정으로 구분하게 만들면 대부분 틀린 쪽을 고른다(그리고 틀린 것을
    알아채는 시점은 사고 조사 중이다). 그래서 **stderr 가 이미 그 파일인지**를 직접 본다 —
    같은 파일이면 우리가 또 쓰지 않고, 아니면 우리가 쓴다.

    `BRIDGE_LOG_FILE` 로 명시할 수 있다(`-` 는 파일 기록 끔).

    판정은 **한 번만** 한다: 프로세스가 도는 동안 stderr 가 갈아끼워지는 일은 없고, 줄마다
    `stat` 을 두 번 부르면 로그가 곧 비용이 된다(DEBUG 를 켜면 서버 왕복마다 한 줄이다).
    """
    global _HUMAN_LOG_PATH
    if _HUMAN_LOG_RESOLVED.is_set():
        return _HUMAN_LOG_PATH
    override = (os.environ.get("BRIDGE_LOG_FILE") or "").strip()
    path: str | None = override or os.path.join(_log_dir(), "bridge.log")
    if override == "-":
        path = None
    else:
        try:
            st_err = os.fstat(sys.stderr.fileno())
            st_log = os.stat(path)
            # 같은 파일이면 stderr 쪽이 이미 적고 있다. `st_ino` 는 Windows(NTFS)에서도 유효하다.
            if (st_err.st_ino and st_err.st_ino == st_log.st_ino
                    and st_err.st_dev == st_log.st_dev):
                path = None
        except Exception:  # noqa: BLE001  (콘솔·파이프·파일 부재 — 그때는 우리가 적는다)
            pass
    _HUMAN_LOG_PATH = path
    _HUMAN_LOG_RESOLVED.set()
    return path


def _rotate_if_needed(path: str) -> None:
    """상한을 넘으면 `.1` 로 밀어내고 세대를 정리한다. 실패해도 로그는 계속 쓴다."""
    try:
        if os.path.getsize(path) < _LOG_MAX_BYTES:
            return
    except OSError:
        return
    try:
        oldest = f"{path}.{_LOG_KEEP}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for n in range(_LOG_KEEP - 1, 0, -1):
            src, dst = f"{path}.{n}", f"{path}.{n + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        os.replace(path, f"{path}.1")
    except Exception:  # noqa: BLE001  (회전 실패로 기록을 멈추지는 않는다)
        pass


def _append_line(path: str, line: str) -> None:
    """한 줄 append. 디렉토리·권한을 함께 챙긴다(원장에는 대화 조각이 실릴 수 있다)."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _rotate_if_needed(path)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
        if new:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    except Exception:  # noqa: BLE001  (기록 실패가 러너를 멈추게 하지 않는다)
        pass


#: 사람 줄에서 **앞에 세울** 필드와 순서. 나머지는 이 뒤에 이름순으로 붙는다.
#: 조사할 때 가장 먼저 찾는 순서다 — 어느 질문(task)의, 어느 AI(runtime)로, 얼마나 걸렸고,
#: 서버가 뭐라 했나(http).
_FIELD_ORDER = ("task", "conv", "runtime", "model", "effort", "dur_ms", "http", "exit", "attempt")
#: 사람 줄에 붙이는 필드 값의 길이 상한. 원장에는 전문이 남으므로 여기서는 읽기 쉬움이 우선이다.
_FIELD_VALUE_MAX = 80


def _render_fields(fields: dict) -> str:
    def _key(item):
        k = item[0]
        return (_FIELD_ORDER.index(k) if k in _FIELD_ORDER else len(_FIELD_ORDER), k)

    parts = []
    for k, v in sorted(fields.items(), key=_key):
        if v is None or isinstance(v, (dict, list, tuple)):
            continue          # 구조값은 원장에만 — 사람 줄에서는 소음이다
        s = _scrub(str(v)).replace("\n", " ")
        if len(s) > _FIELD_VALUE_MAX:
            s = s[:_FIELD_VALUE_MAX] + "…"
        parts.append(f"{k}={s}")
    return " ".join(parts)


def log_event(event: str, msg: str = "", *, level: str = "INFO",
              exc: BaseException | None = None, **fields) -> None:
    """사건 하나를 두 sink 에 남긴다.

    `event` 는 **안정 계약**이다 — 문장(`msg`)은 자유롭게 고쳐도 되지만 이 코드는 조사
    스크립트가 의존하므로 바꿀 때는 그 사실을 알고 바꾼다. 코드 목록은 `_EV_*` 상수.

    `exc` 를 주면 예외 형·표현·스택이 **원장에만** 실린다. 사람 줄에는 요약 한 조각만 —
    스택이 화면을 덮으면 정작 읽어야 할 다음 줄이 밀려난다.
    """
    global _LOG_SEQ
    lvl = level.upper() if level.upper() in _LOG_LEVELS else "INFO"
    sev = _LOG_LEVELS[lvl]
    if exc is not None:
        fields = {**fields,
                  "err_type": type(exc).__name__,
                  "err": _scrub(str(exc))[:400]}
    now = time.time()
    with _LOG_LOCK:
        _LOG_SEQ += 1
        seq = _LOG_SEQ
        # 집계를 **여기 한 자리**에서 한다. 호출부마다 세면 새 경로가 생길 때 빠지고, 빠진
        # 그 경로가 하필 조사하려는 것이다. 종료 시 이 표가 「이번 세션이 무엇을 했나」가 된다.
        # ⚠ 잠금 **안**이어야 한다 — `d[k] = d.get(k,0)+1` 은 원자적이지 않아, 워커 스레드가
        #   여럿이면 집계가 조용히 적게 세어진다(그리고 그 오차는 아무도 눈치채지 못한다).
        _STATS[event] = _STATS.get(event, 0) + 1
        if sev >= _LOG_LEVELS["ERROR"]:
            _STATS["_errors"] = _STATS.get("_errors", 0) + 1
        # ── 사람 sink ────────────────────────────────────────────────────────
        if sev >= _LOG_LEVEL_MIN:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S") + _tz_suffix()
            rendered = _render_fields(fields)
            head = f"[bridge {stamp}] {lvl:<5} {event}"
            line = head + (f" {rendered}" if rendered else "") + \
                (f" | {_scrub(msg)}" if msg else "") + "\n"
            try:
                sys.stderr.write(line)
                sys.stderr.flush()
            except Exception:  # noqa: BLE001  (닫힌 stderr — 파일 sink 는 계속 간다)
                pass
            human = _human_log_path()
            if human:
                _append_line(human, line)
        # ── 감사 sink ────────────────────────────────────────────────────────
        if sev >= _AUDIT_LEVEL_MIN:
            rec = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
                      + f".{int((now % 1) * 1000):03d}" + _tz_suffix(),
                "lvl": lvl,
                "ev": event,
                "seq": seq,
                "run": runner_instance() or None,
                "pid": os.getpid(),
            }
            for k, v in fields.items():
                if v is None:
                    continue
                rec[k] = _scrub(v) if isinstance(v, str) else v
            if msg:
                rec["msg"] = _scrub(msg)
            if exc is not None:
                rec["tb"] = _scrub(_short_traceback(exc))
            try:
                _append_line(_audit_path(),
                             json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            except Exception:  # noqa: BLE001
                pass


def _tz_suffix() -> str:
    """`+0900` 같은 오프셋. 지역시각만 적으면 다른 표준시의 서버 로그와 대조할 수 없다.

    사람이 자기 시계와 대조하기 위해 지역시각을 쓰되(사용자 요청 2026-08-31), 기계가 UTC 로
    환산할 수 있게 오프셋을 함께 적는다 — 「웹은 15:35 인데 로그는 06:35」 는 오프셋이 있으면
    같은 사건임이 계산으로 나온다.
    """
    off = -(time.altzone if time.daylight and time.localtime().tm_isdst else time.timezone)
    sign = "+" if off >= 0 else "-"
    off = abs(int(off))
    return f"{sign}{off // 3600:02d}{(off % 3600) // 60:02d}"


def _short_traceback(exc: BaseException, frames: int = 12) -> str:
    """스택 **마지막 N 프레임**. 전문을 남기면 원장 한 줄이 화면 하나만큼 커진다.

    마지막을 남기는 이유: 터진 자리가 거기다. 위쪽 프레임(진입점·루프)은 매번 같아서
    구분에 기여하지 않는다.
    """
    try:
        import traceback

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # [0] 은 "Traceback (most recent call last):" 머리, 마지막은 예외 문장이다.
        body = tb[1:-1][-frames:] if len(tb) > 2 else tb[1:]
        return "".join([tb[0]] + body + tb[-1:])[-4000:]
    except Exception:  # noqa: BLE001
        return ""


def _log(msg: str, *, event: str = "log", level: str = "INFO", **fields) -> None:
    """종전 그대로 쓸 수 있는 한 줄 기록 (`_log("…")`).

    호출부 80여 곳을 한꺼번에 고치지 않기 위해 **위치인자 하나**의 계약을 유지한다. 새로
    쓰는 자리는 `event=`·필드를 함께 주는 편이 좋고, 그러면 그 줄만 조사 가능해진다.
    """
    log_event(event, msg, level=level, **fields)


def _log_exc(event: str, msg: str, exc: BaseException, **fields) -> None:
    """예외를 **버리지 않고** 남긴다 — 형·표현은 두 sink, 스택은 원장."""
    log_event(event, msg, level="ERROR", exc=exc, **fields)

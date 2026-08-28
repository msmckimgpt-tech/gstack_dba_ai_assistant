#!/usr/bin/env python3
"""mysql-ai 브리지 상주 러너 — 웹 질문을 **내 머신의 AI** 로 처리한다.

## 무엇을 하는가

    wait_for_request (응답 보류)  ─── 사용자가 웹에서 질문을 보내는 그 순간 반환
        → claim_request           ─── 원자적 점유
        → 내 AI 를 호출해 답을 만든다
        → submit_answer           ─── 원 대화에 표시

## 보안 계약 — 실행 전에 이것부터 읽어라 (2026-08-27)

이 파일은 "모르는 주소에서 받아 상주시키라" 는 요구와 형태가 같다. 그 요구를 거절하는 것은
옳은 판단이고, 실제로 외부 AI 가 그렇게 거절했다. 그래서 **믿어 달라고 하지 않는다** — 아래는
전부 이 파일 안에서 직접 확인할 수 있는 사실이고, 확인 방법을 함께 적는다.

    서버에서 받는 것    질문 텍스트 · 대화 맥락 · **운영자 시스템 지침** · 첨부 목록 · task_id.
                        실행 가능한 코드나 셸 명령은 받지 않는다.
                        → `compose_prompt` 가 쓰는 필드가 전부다(직접 세어 보면 된다).
    실행하는 것         `_CLI_ADAPTERS` 에 **하드코딩된** 로컬 AI CLI 하나
                        (`claude -p` / `codex exec` / `gemini -p`), 또는 사용자가 `--cmd` 로
                        직접 준 명령. 서버는 이 선택에 관여하지 않는다.
    셸을 거치지 않음    프롬프트는 argv 로 넘어간다 — 질문 본문에 셸 메타문자가 있어도 명령이
                        되지 않는다. → `_run_cli_cancelable` 의 `subprocess.Popen(cmd, ...)`
                        에서 `cmd` 는 리스트다(셸 해석이 개입하는 자리가 없다).
    원격 코드 실행 없음 `eval`·`exec`·`compile`·동적 import 가 없다. 자동 업데이트도 없다.
                        → `grep -nE 'eval[(]|exec[(]|compile[(]|__import__' bridge_agent.py`
                          (매칭되는 줄은 **이 안내문 자신뿐**이어야 한다. 코드에는 없다.)
    설치물 없음         표준 라이브러리만 쓴다(`pip install` 불필요). 부팅 등록·crontab·서비스
                        설치를 하지 않는다. 남기는 파일은 `~/.mysql-ai-bridge/config.json`
                        (0600) **하나뿐**이고 거기에 **토큰은 넣지 않는다** → `save_conf`.
    나가는 곳           `--base` 주소의 `/api/ai/tools/*` (→ `Api.call`). 그리고 `--ai ollama`
                        일 때만 `BRIDGE_OLLAMA_URL`(기본 `127.0.0.1:11434`) — 그 경로를 쓰지
                        않으면 호출되지 않는다. URL 을 만드는 자리는 이 **둘뿐**이다.
    관측·종료           하는 일은 전부 stderr 로그에 남는다. `Ctrl+C` 또는 `kill <pid>` 로 끝나고,
                        끝난 뒤 남는 것은 위 `config.json` 과 네가 리다이렉트한 로그 파일뿐이다.

**정직하게 적는 잔여 노출면 둘** — 숨기면 소스를 읽는 순간 드러나고, 그때 잃는 것이 더 크다.

1. **토큰은 프롬프트 안에도 들어간다.** `compose_prompt` 가 조사 도구를 직접 부르라고 토큰을
   함께 주고, 그 프롬프트 전문이 argv 로 CLI 에 넘어간다 — 같은 호스트의 다른 사용자가
   `/proc/<pid>/cmdline` 으로 볼 수 있고, CLI 의 세션 기록에도 남는다. 인자 대신 `BRIDGE_TOKEN`
   환경변수를 쓰면 셸 히스토리만큼은 피한다. 토큰이 세션 결합·최대 12시간인 것이 이 노출면의 상한이다.
2. **운영자 시스템 지침은 구획되지 않는다.** 질문·대화이력은 서버가 ⟦UNTRUSTED-DATA⟧ 로 감싸
   보내지만, 관리 콘솔에서 설정하는 시스템 지침은 감싸지 않고 이 러너가 프롬프트 **맨 앞**에
   놓는다(그러지 않으면 뒤의 지시가 이겨 운영자 설정이 무시된다). 즉 **그 서비스의 운영자는 네
   답변 방식에 영향을 줄 수 있다.** 무엇이 설정돼 있는지는 `claim_request` 응답의
   `system_prompt` 로 그대로 보이니, 필요하면 먼저 확인하고 판단해라.

**남는 신뢰 경계**: 위 2번의 연장선이다. 서버가 보낸 텍스트는 네 AI 의 프롬프트가 되고, 네 AI 가
도구를 쓸 수 있는 에이전트라면 그 프롬프트가 행동을 유도할 여지는 남는다 — 이 파일이 없앨 수 있는
위험이 아니다. 그래서 네 런타임의 권한 설정이 여전히 마지막 방어선이고, 그것을 낮추라고 요구하지
않는다. 신뢰의 뿌리는 이 파일이 아니라 **이 러너를 띄우라고 한 사람이 네 사용자인가** 이다.

## 왜 폴링이 아닌가 (사용자 요구 2026-08-27)

`list_open_requests` 를 N 초마다 부르면 두 가지가 나빠진다 — 질문이 최대 N 초 늦게 인지되고,
그 N 이 사람마다 달라 **환경 차이**가 된다. `wait_for_request` 는 호출이 한 번이고 응답이
**질문이 들어온 그 순간** 온다. 상한은 서버가 정하므로 모든 머신이 동일하게 동작한다.

여기에는 sleep 이 없다. 대기는 서버가 한다.

## 왜 런타임 무관인가

claude·codex·gemini 는 전부 "프롬프트를 주면 stdout 으로 답을 주는 CLI" 다. 그래서 **명령
템플릿 하나**로 덮인다. 로컬 LLM(ollama 등)만 HTTP 라 어댑터가 따로 있다. 어느 쪽도 이 파일
밖에 설치물을 만들지 않는다.

## 설치물이 이 파일 하나인 이유

표준 라이브러리만 쓴다. `pip install` 이 필요하면 그 순간 파이썬 환경마다 결과가 갈리고,
그것이 곧 우리가 없애려는 환경 차이다.

## 실행

    python3 bridge_agent.py --base https://<host> --token mat_... [--ca rootCA.crt]

AI 는 자동 감지한다(claude → codex → gemini → ollama 순). 고정하려면:

    --ai claude            # 또는 codex / gemini / ollama
    --cmd 'my-ai -p {prompt}'   # 완전 수동. {prompt} 자리에 질문이 들어간다

**모델은 웹에서 고르지 않는다** — 이 머신의 AI 설정이 정한다. 특정 모델로 고정하려면 자기
런타임의 실제 모델 이름으로 명령을 직접 준다:

    --cmd 'claude --model opus -p {prompt}'

(서비스가 아는 모델 이름과 각 CLI 가 아는 모델 이름은 다르다. 그 이름을 아는 것은 사용자다.)

한 번만 처리하고 끝내려면 `--once`. 연결만 확인하려면 `--check`.

## 동시 처리 — 수요에 맞춰 늘고, 안 쓰면 줄어든다 (사용자 결정 2026-08-28)

**1개로 시작해서 필요한 만큼만 늘린다.** 직렬이면 5분짜리 조사 하나가 뒤따르는 10초짜리
질문을 통째로 막는데(서버는 애초에 병렬이다 — `claim_request` 는 원자적 점유이고
`wait_for_request` 는 여러 건을 한 번에 돌려준다), 그렇다고 처음부터 여러 개를 띄우면
질문이 하나뿐인 대부분의 시간에 쓰지도 않을 용량을 들고 있게 된다.

    확장   `wait_for_request` 가 돌려준 대기 질문 수가 현재 슬롯 수를 넘으면 그만큼 늘린다
           (상한 `--max-workers`, 기본 8). **수요가 관측된 순간에만** 늘어난다
    축소   `--worker-idle-sec`(기본 300초) 넘게 쉰 슬롯을 **오래된 것부터** 회수한다.
           최소 1개는 남긴다 — 0이 되면 다음 질문을 받을 창구가 사라진다

여기에 타이머 스레드도, 추가 sleep 도 없다. 서버가 대기를 최대 55초 보류하므로 **그 반환이
곧 tick** 이다(폴링 금지 원칙과 정합 — 우리는 시간을 재려고 서버를 두드리지 않는다).

슬롯을 꺼낼 때 **가장 최근에 쓴 것부터** 쓴다(LIFO). 그래야 안 쓰이는 슬롯이 계속 안 쓰인 채로
남아 회수 대상이 된다 — 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어 아무것도 회수되지 않는다.

`--workers N` 은 **시작 개수**다(기본 1). 상한은 `--max-workers` 가 정한다 — 실질 한계는
**개인 계정의 쿼터**와 AI 런타임의 동시성인데 그건 우리가 알 수 없어 사용자에게 남긴다.

## 취소 (2026-08-28)

웹에서 중단을 누르거나 새 질문으로 갈아타면 서버가 그 작업을 취소한다. 러너는 그것을
`wait_for_request` 응답의 `canceled_task_ids` 로 **즉시** 알고(별도 채널이 아니다),
진행 중이던 AI 프로세스를 **죽인다** — 죽이지 않으면 아무도 볼 수 없는 답을 위해 개인 계정
토큰이 계속 탄다. 제출도 하지 않는다(해도 서버가 409 로 거절한다).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_UA = "mysql-ai-bridge-agent/1"

#: 답변 끝에서 대화 제목을 실어 오는 한 줄 규약. CLI 런타임은 stdout 하나뿐이라 별도 채널이
#: 없다 — 제출 전에 이 줄을 떼어내므로 사용자 화면에는 남지 않는다.
_TITLE_MARK = "#TITLE:"

#: 서버가 최대 55초 보류한다. 그보다 넉넉히 잡아야 **정상 대기**를 타임아웃으로 오인하지 않는다.
_WAIT_TIMEOUT_SEC = 90.0
#: 조사·응답 생성 상한. **0 = 상한 없음(기본)** — 사용자 요구 2026-08-28:
#:
#:   "기본적으로 time_out 은 진행되어선 안되며, 각 단계에 대한 갱신을 수신받는 부분을
#:    기준으로. 연결은 살아있는 상태입니다."
#:
#: 고정 상한은 **일하고 있는 AI 를 끊는다**. 실제로 900초일 때 27단계짜리 조사가 그 벽에
#: 걸려 "AI 호출이 900초를 넘겨 중단했습니다" 로 끝났다(PB-0008 검증 중 관측) — 개인 AI 는
#: 답을 만들고 있었고, 서버도 기다릴 수 있었는데 중간에서 러너가 끊은 것이다.
#:
#: 그럼 멈춘 것과 일하는 것을 무엇으로 가르나 — **진행 신호**다. 도구를 부를 때마다 서버가
#: 점유 lease 를 밀어 주므로(`_renew_claim_lease`), 조사가 이어지는 한 lease 는 만료되지
#: 않고, 정말 멈추면 마지막 호출로부터 30분 뒤 서버가 회수한다. 회수되면 이 러너의 제출은
#: 409 로 거절되어 스스로 하차한다 — 상한은 **서버가 관측한 사실**로 집행되지, 러너의 시계로
#: 집행되지 않는다.
#:
#: 취소는 여전히 즉시 듣는다(`_CANCEL_TICK_SEC` 마다 확인 → 프로세스 kill). "무제한" 이
#: "사용자가 멈출 수 없다" 를 뜻하지 않는다.
#:
#: 값을 주면 그 초만큼만 기다린다(`--ai-timeout` · `BRIDGE_AI_TIMEOUT_SEC`) — 개인 계정
#: 쿼터를 스스로 제한하고 싶은 사용자를 위한 opt-in 이다.
_AI_TIMEOUT_SEC = float(os.environ.get("BRIDGE_AI_TIMEOUT_SEC", "0") or 0)
#: 진행 중인 AI 프로세스의 **취소 확인 간격**.
#:
#: ⚠ 이건 폴링이 아니다 — 서버를 두드리지 않는다. 자식 프로세스가 끝나기를 `Thread.join(timeout)`
#: 으로 기다리면서 그 틈에 취소 여부를 보는 것이고, 대기 자체는 여전히 블로킹이다(sleep 없음).
_CANCEL_TICK_SEC = 1.0
#: **시작** 동시 처리 수. 수요가 관측되면 늘어난다(`WorkerPool`).
_DEFAULT_WORKERS = 1
#: 확장 상한. 개인 계정 쿼터와 런타임 동시성이 실질 한계라 무제한은 위험하다 — 요청이 몰리면
#: 개인 머신에 수십 개 프로세스가 뜨고 쿼터가 한 번에 소진된다(사용자 결정 2026-08-28: 8).
_DEFAULT_MAX_WORKERS = 8
#: 이 시간 넘게 쉰 슬롯은 회수한다(사용자 결정 2026-08-28: 5분).
#: 너무 짧으면 질문이 드문드문 이어질 때 확장·축소를 반복하고, 너무 길면 유휴 슬롯이 오래 남는다.
_DEFAULT_WORKER_IDLE_SEC = 300.0
#: 대기 질문이 있는데 한 건도 처리하지 못한 채 반복되는 라운드의 상한.
#: 넘으면 조용히 도는 대신 **크게 실패**한다 — 간격 없는 재시도는 서버를 두드리는 폴링이다.
_MAX_STALLED_ROUNDS = 20


#: 재시작 대비 설정 파일. **토큰은 넣지 않는다** — 비밀이고, 어차피 세션과 함께 죽는다.
#: 저장하는 것은 다시 물어보기 번거로운 것들(주소·CA 경로·AI 선택)뿐이다.
_CONF_DIR = os.path.join(os.path.expanduser("~"), ".mysql-ai-bridge")
_CONF_PATH = os.path.join(_CONF_DIR, "config.json")


def save_conf(base: str, ca: str | None, ai: str, cmd: str | None) -> None:
    """다음 실행이 `--resume` 한 줄로 끝나게 한다.

    머신을 재시작하면 이 프로세스는 사라진다(사용자 지적 2026-08-27). 그때 사용자가 다시
    챙겨야 하는 것이 많을수록 **아무도 다시 띄우지 않는다.** 토큰만 새로 받으면 되게 한다.
    """
    try:
        os.makedirs(_CONF_DIR, exist_ok=True)
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump({"base": base, "ca": ca, "ai": ai, "cmd": cmd}, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        _log(f"설정 저장 실패(무시): {e}")


def load_conf() -> dict:
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

#: 연결이 **끊겼을 때만** 쓰는 복구 간격(feature-0045). 서버가 배포로 교체되는 몇 초 동안
#: 연결이 실패하는데, 그때 쉬지 않고 재시도하면 초당 수천 번을 두드려 사용자 머신의 CPU 를
#: 태운다. 대기(`wait_for_request`)에는 여전히 sleep 이 없다 — 이건 대기가 아니라 재연결이다.
#: 상한을 15초로 둔 이유: 롤링 배포 한 replica 의 교체가 보통 그 안에 끝나므로, 복구가
#: 지연되어 질문 인지가 늦어지는 일이 없다.
_RECONNECT_BACKOFF_START = 1.0
_RECONNECT_BACKOFF_MAX = 15.0

#: 서버가 "배포 교대 중" 이라고 답했을 때의 **하한**. 백오프가 아니라 고정값이다 — 자라지
#: 않으므로 인지가 늦어지지 않고, 엣지가 그 인스턴스를 후보에서 빼는 짧은 창(2s)에 호출이
#: 폭주해 계정 호출 상한을 태우는 것만 막는다.
_DRAINING_RETRY_FLOOR_SEC = 0.5


def _log(msg: str) -> None:
    sys.stderr.write(f"[bridge] {msg}\n")
    sys.stderr.flush()


#: 평문이 허용되는 유일한 대상. 이름이 아니라 **호스트**로 판정한다.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


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


# ── 서버 호출 ────────────────────────────────────────────────────────────────


class Api:
    def __init__(self, base: str, token: str, ca: str | None):
        self.base = base.rstrip("/")
        self.token = token
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None

    def call(self, tool: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}/api/ai/tools/{tool}", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as resp:
                return json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 상태코드를 뭉개지 않는다 — 401(재발급 필요)·409(남이 점유)·429(상한)는
            # 호출측이 서로 다르게 대응해야 하는 신호다.
            return {"_http": e.code, "error": detail}
        except Exception as e:  # noqa: BLE001
            # ⚠ `_http: 0` = **연결 자체가 안 됐다**(TLS·DNS·거부). 0 은 falsy 라
            #   `if not r.get("_http")` / `if code:` 같은 진위 검사에서 **성공으로 읽힌다** —
            #   실제로 `--check` 가 사설 CA 미지정 상태에서 "연결 정상" 을 출력했다(라이브 실측
            #   2026-08-28). 호출측이 실수하지 않도록 명시 플래그를 함께 싣는다.
            return {"_http": 0, "_failed": True, "error": str(e)[:300]}


# ── 취소 원장 ────────────────────────────────────────────────────────────────


class CancelRegistry:
    """서버가 알려준 **취소된 task** 를 워커에게 전달하는 통로.

    대기 스레드(`wait_for_request`)와 워커 스레드가 함께 읽고 쓰므로 락으로 감싼다.
    락 없이 `set` 을 공유해도 CPython 에서는 대개 동작하지만, "대개" 로 두면 취소가 가끔
    안 먹는 버그가 되고 그건 재현이 거의 불가능하다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids: set[str] = set()

    def add_many(self, task_ids) -> list[str]:
        """새로 취소된 것만 골라 기록하고 그 목록을 돌려준다(로그용)."""
        fresh: list[str] = []
        with self._lock:
            for raw in task_ids or []:
                tid = str(raw or "")
                if tid and tid not in self._ids:
                    self._ids.add(tid)
                    fresh.append(tid)
        return fresh

    def is_canceled(self, task_id: str) -> bool:
        with self._lock:
            return str(task_id) in self._ids

    def forget(self, task_id: str) -> None:
        """처리를 마친 task 는 원장에서 뺀다 — 무한히 자라지 않게."""
        with self._lock:
            self._ids.discard(str(task_id))


# ── 동시 처리 슬롯 ───────────────────────────────────────────────────────────


class WorkerPool:
    """동시 처리 슬롯을 **수요에 맞춰 늘리고, 쉬는 것부터 회수한다**(사용자 결정 2026-08-28).

    왜 `Semaphore` 가 아닌가: 세마포어는 크기를 바꿀 수 없다. 종전에는 고정 N 이었고, 그래서
    질문이 하나뿐인 대부분의 시간에도 N 개를 들고 있었다.

    ## 슬롯을 목록으로 두는 이유

    카운터 하나로도 개수는 셀 수 있다. 그런데 "**오래된** 슬롯부터 회수" 는 개수만으로는
    표현되지 않는다 — 어느 것이 얼마나 쉬었는지 알아야 한다. 그래서 슬롯마다 `last_used` 를
    들고, 회수는 그 순서로 한다.

    ## 왜 LIFO 로 꺼내는가

    유휴 슬롯 중 **가장 최근에 쓴 것**을 준다. 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어
    idle 임계를 넘는 슬롯이 영영 생기지 않고, 그러면 축소가 작동하지 않는다. 한쪽만 계속 쓰면
    나머지는 자연히 오래되어 회수 대상이 된다.

    ## 시간

    `time.monotonic()` 을 쓴다(벽시계는 NTP 보정·서머타임에 뒤로 갈 수 있다). 슬롯은 생성
    시각으로 초기화한다 — 0 같은 센티넬로 두면 "프로세스 시작 직후" 가 곧 "아주 오래 쉼" 이
    되어 첫 라운드에 회수된다.
    """

    def __init__(self, start: int, maximum: int, idle_sec: float, now: float,
                 clock=time.monotonic) -> None:
        # `clock` 은 **테스트 훅**이다. 시각을 락 안에서 만들어야 정렬 불변식이 지켜지는데
        # (아래 `release` 참조), 그러면 호출측이 시각을 주입할 수 없어 회수 순서를 결정적으로
        # 검증할 방법이 사라진다. 시계 자체를 갈아끼우면 둘 다 만족한다.
        self._clock = clock
        self._cv = threading.Condition()
        self._max = max(1, int(maximum))
        self._idle = float(idle_sec)
        self._next_id = 1
        #: 유휴 슬롯 `(last_used, id)` — **last_used 오름차순**(앞이 가장 오래 쉰 것).
        self._free: list[tuple[float, int]] = []
        #: 사용 중 슬롯 id.
        self._busy: set[int] = set()
        for _ in range(max(1, min(int(start), self._max))):
            self._free.append((now, self._next_id))
            self._next_id += 1

    # ── 조회 ────────────────────────────────────────────────────────────────

    @property
    def capacity(self) -> int:
        with self._cv:
            return len(self._free) + len(self._busy)

    @property
    def in_use(self) -> int:
        with self._cv:
            return len(self._busy)

    # ── 사용 ────────────────────────────────────────────────────────────────

    def try_acquire(self) -> int | None:
        """유휴 슬롯 하나를 잡는다. 없으면 `None`(블로킹하지 않는다)."""
        with self._cv:
            if not self._free:
                return None
            _, sid = self._free.pop()      # 가장 최근에 쓴 것 — 위 'LIFO' 참조
            self._busy.add(sid)
            return sid

    def release(self, sid: int) -> None:
        """슬롯을 돌려준다. 그 사이 축소로 사라진 슬롯이면 조용히 버린다.

        ⚠ **반납 시각을 락 안에서 만든다.** 호출측이 `time.monotonic()` 을 먼저 계산해 넘기면,
        먼저 시간을 얻은 스레드가 늦게 락을 잡는 순간 `_free` 가 시각 역순으로 쌓인다. 그러면
        `reap` 이 맨 앞만 보고 "아직 임계 전" 이라 판단해 **뒤에 갇힌 오래된 슬롯을 영영 회수하지
        못한다**(codex 리뷰 P2). 정렬 불변식은 이 한 줄에 걸려 있다.

        모르는 슬롯을 버리는 이유: 반납이 조용히 용량을 부풀리는 버그는 재현이 어렵다.
        """
        with self._cv:
            if sid not in self._busy:
                return
            self._busy.discard(sid)
            self._free.append((self._clock(), sid))     # 락 안 — 단조 증가가 보장된다
            self._cv.notify_all()

    # ── 확장·축소 ───────────────────────────────────────────────────────────

    def grow_for(self, pending: int) -> int:
        """대기 질문 `pending` 건을 **지금 진행 중인 것과 함께** 소화할 만큼 늘린다(상한까지).

        ⚠ 목표는 `in_use + pending` 이다. 대기 수만 보면 **진행 중인 작업이 쓰는 자리를 빼고**
        세어 과소 확장한다 — capacity 4 · busy 3 · pending 3 이면 총수요가 6인데 `grow_to(3)` 은
        아무것도 늘리지 않고, 결국 한 건만 시작된다(codex 리뷰 P1).

        **관측된 수요에만** 반응한다 — 예측해서 미리 늘리지 않는다. 예측이 빗나가면 그 비용은
        사용자 계정의 쿼터로 나간다.
        """
        added = 0
        with self._cv:
            now = self._clock()                      # 락 안에서 — `release` 와 같은 이유
            target = min(len(self._busy) + int(pending), self._max)
            while len(self._free) + len(self._busy) < target:
                self._free.append((now, self._next_id))
                self._next_id += 1
                added += 1
            if added:
                self._cv.notify_all()
        return added

    def reap(self, now: float) -> int:
        """`idle_sec` 넘게 쉰 유휴 슬롯을 **오래된 것부터** 회수한다. 회수 개수를 돌려준다.

        **최소 1개는 남긴다.** 0이 되면 다음 질문을 받을 창구가 사라지고, 그 상태는 스스로
        풀리지 않는다(확장은 수요를 봐야 하는데 수요를 보려면 슬롯이 있어야 한다).

        사용 중인 슬롯은 건드리지 않는다 — 오래 걸리는 조사가 회수되면 그 답변이 사라진다.
        """
        removed = 0
        with self._cv:
            while self._free and (len(self._free) + len(self._busy)) > 1:
                last_used, sid = self._free[0]
                if now - last_used <= self._idle:
                    break                    # 정렬돼 있으므로 뒤는 볼 필요 없다
                self._free.pop(0)
                removed += 1
        return removed


# ── 내 AI 호출 ───────────────────────────────────────────────────────────────

#: 자동 감지 순서와 호출 방법. 전부 "프롬프트 → stdout" 계약이라 한 틀로 덮인다.
_CLI_ADAPTERS: list[tuple[str, list[str]]] = [
    ("claude", ["claude", "-p", "{prompt}"]),
    ("codex", ["codex", "exec", "--skip-git-repo-check", "{prompt}"]),
    ("gemini", ["gemini", "-p", "{prompt}"]),
]


#: 모델·추론 강도는 **웹에서 지정하지 않는다** (P0-T, 사용자 결정 2026-08-28 · 형제 cycle).
#:
#: 종전에는 웹 컴포저에서 고른 값을 `--model` 인자로 넘겼다. 그런데 그 값은 서비스 내부의
#: litellm alias(`claude-haiku-4` 등)라 어느 CLI 도 알지 못했고 — 기본값이 haiku 이므로 사실상
#: **모든** 요청이 모델 지정 실패 → 기본 모델 재시도 경로를 탔다. 요청은 반영되지 않으면서
#: "못 맞췄다" 는 고지만 매번 붙는, 있으나 마나 한 왕복이었다.
#:
#: 이제 어떤 모델로 답할지는 **이 머신의 AI 설정**이 정한다 — 고정하고 싶으면
#: `--cmd 'claude --model opus -p {prompt}'` 처럼 자기 런타임의 실제 모델 이름으로 지정한다
#: (그 이름을 아는 것은 서버가 아니라 사용자다).


def _which(name: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def detect_ai() -> tuple[str, list[str]] | None:
    for name, argv in _CLI_ADAPTERS:
        if _which(name):
            return name, argv
    if _which("ollama"):
        return "ollama", []
    return None


#: `ask_local_ai` 가 "사용자가 취소했다" 를 알리는 신호.
#:
#: 실패 문자열로 섞지 않는 이유: 실패는 **답을 제출해서 알려야 하고**(침묵보다 낫다), 취소는
#: **제출하면 안 된다**(사용자가 안 보겠다고 한 것이다). 두 결과를 같은 값으로 돌려주면
#: 호출측이 그것을 구분하지 못해 둘 중 하나가 반드시 틀린 동작을 한다.
CANCELED = "__canceled__"


def _run_cli_cancelable(cmd: list[str], cancel_check) -> tuple[bool, str]:
    """CLI 를 돌리되 **취소되면 죽인다**. (성공여부, 본문 | CANCELED)

    왜 `subprocess.run` 이 아닌가: `run` 은 끝날 때까지 블로킹이라 그동안 도착한 취소를 볼 수
    없다. 그러면 사용자가 중단을 눌러도 개인 계정 토큰이 그 조사가 끝날 때까지 계속 탄다 —
    취소의 실질 목적이 바로 그 낭비를 막는 것이다.

    ⚠ 여기에도 sleep 은 없다. 자식이 끝나기를 `Thread.join(timeout)` 으로 **블로킹 대기**하고,
    그 반환 틈에 취소를 확인할 뿐이다. 서버를 두드리지 않으므로 폴링이 아니다.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:  # noqa: BLE001
        return False, f"AI 실행 실패: {e}"

    # 파이프를 비우는 일은 별도 스레드에 맡긴다. 여기서 직접 읽으면 자식이 큰 출력을 낼 때
    # 파이프 버퍼가 차서 서로 기다리는 교착이 된다(고전적인 Popen 함정).
    box: dict[str, str] = {}

    def _drain() -> None:
        out, err = proc.communicate()
        box["out"] = out or ""
        box["err"] = err or ""

    pump = threading.Thread(target=_drain, daemon=True)
    pump.start()

    waited = 0.0
    while pump.is_alive():
        pump.join(_CANCEL_TICK_SEC)
        waited += _CANCEL_TICK_SEC
        if cancel_check():
            _kill(proc)
            pump.join(5.0)
            return False, CANCELED
        if _AI_TIMEOUT_SEC and waited >= _AI_TIMEOUT_SEC:
            _kill(proc)
            pump.join(5.0)
            return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."

    if proc.returncode != 0:
        return False, f"AI 가 오류로 끝났습니다(exit {proc.returncode}): {box.get('err', '')[:400]}"
    return True, (box.get("out") or "").strip()


def _kill(proc) -> None:
    """자식을 확실히 끝낸다. 이미 죽었으면 조용히 지나간다."""
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 cancel_check=None) -> tuple[bool, str]:
    """내 AI 에게 물어 답 문자열을 얻는다. (성공여부, 본문)

    모델은 이 머신의 AI 설정이 정한다 — 서버는 모델을 요구하지 않는다(위 상수 자리 주석).

    `cancel_check` 는 "지금 취소됐는가" 를 묻는 함수다. 취소되면 본문 자리에 `CANCELED` 를
    돌려준다 — 실패와 구분해야 호출측이 "제출하지 않는다" 를 선택할 수 있다.
    """
    _canceled = cancel_check or (lambda: False)
    if custom:
        argv = shlex.split(custom)
        kind = "custom"
    if kind == "ollama":
        model = os.environ.get("BRIDGE_OLLAMA_MODEL", "llama3")
        # 이미 취소됐다면 호출 자체를 하지 않는다(HTTP 는 중간에 끊어도 서버 쪽 생성이 계속될
        # 수 있어, 시작하지 않는 것이 유일하게 확실한 절약이다).
        if _canceled():
            return False, CANCELED
        req = urllib.request.Request(
            os.environ.get("BRIDGE_OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=(_AI_TIMEOUT_SEC or None)) as r:
                return True, str(json.loads(r.read().decode("utf-8", "replace")).get("response") or "")
        except Exception as e:  # noqa: BLE001
            return False, f"로컬 LLM 호출 실패: {e}"

    # 프롬프트는 **인자로** 넘긴다(셸을 거치지 않는다) — 질문 본문에 셸 메타문자가 섞여도
    # 그대로 전달되고, 명령 주입 경로가 생기지 않는다.
    cmd = [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv]
    if _canceled():
        return False, CANCELED
    return _run_cli_cancelable(cmd, _canceled)


# ── 프롬프트 ─────────────────────────────────────────────────────────────────


def compose_prompt(api: Api, task: dict) -> str:
    """내 AI 에게 줄 프롬프트. **조사 도구 사용법을 함께 준다** — 그래야 DB 를 실제로 본다."""
    q = str(task.get("question") or "")
    ctxt = str(task.get("conversation_context") or "")
    sysp = str(task.get("system_prompt") or "")
    scope = task.get("scope") or {}
    atts = task.get("attachments") or []
    parts: list[str] = []
    if sysp:
        # 운영자가 설정한 5단계 지침(전역·제품·역할·계정·개인). **맨 앞**에 둔다 — 뒤에 두면
        # 앞의 지시가 이기고, 그러면 운영자 설정이 사실상 무시된다.
        parts += ["── 아래 지침을 시스템 프롬프트로 삼아 답하라 ──", sysp,
                  "── 지침 끝 ──", ""]
    if scope.get("product_name") or scope.get("datasources"):
        # 어떤 제품·어떤 DB 를 보고 있는지 모르면 엉뚱한 스키마를 찾아 헤맨다.
        who = scope.get("product_name") or ""
        key = scope.get("product_key") or ""
        ds = ", ".join(str(d) for d in (scope.get("datasources") or []))
        parts += [f"대상 제품: {who}" + (f" ({key})" if key else "")
                  + (f" · 데이터소스: {ds}" if ds else ""), ""]
    parts += [
        "너는 사내 DB 질의 어시스턴트다. 아래 사용자 질문에 답하라.",
        "",
        # ⚠ 본문 형태를 **정확히** 준다. 종전 예시는 `task_id` 가 없고 인자를 `arguments` 로
        #   감싸지 않아, 그대로 따르면 400("task_id 가 필요합니다") 또는 "schema_name과
        #   table_name은 필수" 만 돌아왔다 — 러너 경로의 조사가 통째로 실패하는 형태였다
        #   (codex REV-20260828T040000 P1).
        "필요하면 이 도구들을 HTTP 로 직접 호출해 실제 DB 를 조사하라"
        " (POST · JSON 본문 · 헤더에 Authorization: Bearer <아래 토큰>).",
        f"  공통 본문 = {{\"task_id\":\"{task.get('task_id')}\","
        " \"reason\":\"지금 이걸 왜 조사하는지 한 문장\", \"arguments\":{...}}",
        f"  {api.base}/api/ai/tools/list_schemas      arguments: {{}}",
        f"  {api.base}/api/ai/tools/describe_schema   arguments: {{\"schema_name\":\"...\"}}",
        f"  {api.base}/api/ai/tools/describe_table    arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/search_tables     arguments: {{\"keyword\":\"...\"}}",
        f"  {api.base}/api/ai/tools/get_table_indexes arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/get_foreign_keys  arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/execute_sql       arguments: {{\"sql\":\"SELECT ...\"}}",
        f"  토큰: {api.token}",
        "",
        # 조사 내역은 사용자 화면의 「실행 단계」에 그대로 그려진다. 사유가 없으면 서버가
        # 도구의 일반적 목적으로 채우는데, 그건 *이 질문에서의* 이유가 아니다.
        "`reason` 은 매 호출에 넣어라 — 사용자 화면의 실행 단계에 「어떤 이유로 → 어떤 작업」"
        " 으로 표시된다.",
        "",
        "추측하지 말고 조사한 사실만 쓰라. 확인하지 못한 것은 '미확인' 이라고 밝혀라.",
        "답변만 출력하라(머리말·맺음말 없이).",
        # 제목 축: 러너는 CLI 의 stdout 만 받으므로 별도 채널이 없다. 마지막 한 줄을 규약으로
        # 삼고 제출 전에 떼어낸다 — 마커가 없으면 답변은 그대로다(파싱 실패가 답을 망치지 않음).
        f"답변의 **맨 마지막 줄**에 `{_TITLE_MARK} <이 대화를 요약한 30자 안팎의 제목>` 을"
        " 한 줄 덧붙여라. 이 줄은 사용자에게 보이지 않고 대화 제목으로만 쓰인다.",
    ]
    if ctxt:
        parts += ["", "── 이전 대화 ──", ctxt]
    if atts:
        names = ", ".join(f"{a.get('filename')}(id={a.get('attachment_id')})" for a in atts)
        parts += ["", f"첨부 {len(atts)}건: {names}",
                  f"  본문 읽기: POST {api.base}/api/ai/tools/read_task_attachment "
                  f"{{\"task_id\":\"{task.get('task_id')}\",\"attachment_id\":<id>}}",
                  "  첨부가 있는 질문은 반드시 본문을 읽고 답하라."]
    parts += ["", "── 질문 ──", q]
    return "\n".join(parts)


def split_title(answer: str) -> tuple[str, str]:
    """답변에서 `#TITLE:` 마지막 줄을 떼어 `(본문, 제목)` 으로 가른다.

    마커가 없으면 본문은 **손대지 않는다** — 규약을 지키지 않는 런타임이 있어도 답변이
    상하지 않아야 한다(제목이 없을 뿐이다). 마지막 줄만 본다: 중간에 같은 문자열이 있으면
    그건 답변 내용이지 제목이 아니다.
    """
    body = str(answer or "")
    lines = body.rstrip().split("\n")
    if not lines:
        return body, ""
    tail = lines[-1].strip()
    # `#` 를 요구한다 — `lstrip("#")` 로 느슨하게 받으면 답변의 정상적인 마지막 줄
    # `Title: 실제 데이터 열` 까지 제목으로 오인해 **본문에서 지운다**(codex P2).
    if not tail.upper().startswith(_TITLE_MARK.upper()):
        return body, ""
    rest = "\n".join(lines[:-1]).rstrip()
    if not rest:
        # 제목 줄이 전부라면 떼어낼 수 없다 — 떼면 빈 답변이 되어 제출이 400 으로 거절되고
        # 사용자 화면에는 대기 말풍선만 남는다. 제목을 포기하고 본문을 지킨다.
        return body, ""
    title = tail[len(_TITLE_MARK):].strip().strip("\"'`").strip()
    return rest, title[:120]


# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, claimed: dict, kind: str, argv: list[str],
               custom: str | None, cancels: "CancelRegistry | None" = None) -> bool:
    """이미 **점유된** task 하나를 처리한다.

    점유(`claim_request`)를 여기서 하지 않고 호출측(대기 루프)이 하는 이유: 점유가 늦으면 그
    task 가 `wait_for_request` 결과에 계속 남아, 워커가 다 찼을 때 같은 것을 반복해서 받게 된다
    (그리고 그 반복이 곧 서버를 두드리는 tight loop 다). 점유는 값싸고 즉시 끝나므로 대기
    루프에서 처리하고, 오래 걸리는 AI 호출만 워커로 넘긴다.
    """
    _canceled = (lambda: cancels.is_canceled(task_id)) if cancels else (lambda: False)

    prompt = compose_prompt(api, {**claimed, "task_id": task_id})
    _log(f"{task_id}: 내 AI({kind})에게 전달")
    ok, answer = ask_local_ai(kind, argv, prompt, custom, _canceled)
    if answer == CANCELED:
        # 사용자가 취소했다. **제출하지 않는다** — 서버도 409 로 거절하지만, 여기서 멈추는 것이
        # 토큰과 왕복을 아끼는 지점이다.
        _log(f"{task_id}: 사용자가 취소했다 — 중단(제출 안 함)")
        return False
    if not ok or not answer.strip():
        # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
        # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
        answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
            "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

    # 답을 만드는 동안 취소됐을 수 있다 — 제출 **직전**에 한 번 더 본다.
    # 제목 분리보다 **앞**에 둔다: 어차피 버릴 답이면 가공할 이유가 없다.
    if _canceled():
        _log(f"{task_id}: 답변 완료 직전에 취소됨 — 제출하지 않는다")
        return False

    # 제목 줄은 답변에서 떼어 별도 필드로 보낸다 — 본문에 남기면 사용자가 규약 문자열을 본다.
    answer, title = split_title(answer)
    payload = {"task_id": task_id, "answer": answer, "source_tasks": [task_id]}
    if title:
        payload["title"] = title
    res = api.call("submit_answer", payload, timeout=120.0)
    if res.get("_http") == 409:
        # 취소 신호를 못 본 채 여기까지 왔다(서버가 마지막 관문). 정상 흐름이다.
        _log(f"{task_id}: 서버가 제출을 거절했다(취소된 요청) — 버린다")
        return False
    if res.get("_failed"):
        # ⚠ 연결 실패는 `_http == 0` 이라 아래 진위 검사에 걸리지 않는다 (codex P2-2).
        #   그대로 두면 **저장 여부를 모르는데 "제출 완료" 라고 기록**한다. 답변은 이미 만들어
        #   놓았으므로 한 번 더 시도할 값어치가 있다 — 서버의 `SubmittedAt IS NULL` 가드가
        #   중복 제출을 409 로 막으므로 재시도는 안전하다(멱등).
        _log(f"{task_id}: 제출 중 연결 실패 — 한 번 더 시도합니다: {res.get('error')}")
        time.sleep(_RECONNECT_BACKOFF_START)
        res = api.call("submit_answer", payload, timeout=120.0)
        if res.get("_failed") or res.get("_http"):
            _log(f"{task_id}: 제출 실패(재시도 후) {res.get('_http')} {res.get('error')} — "
                 "이 답변은 전달되지 않았다. lease 만료 뒤 다시 제안된다.")
            return False
    if res.get("_http"):
        _log(f"{task_id}: 제출 실패 {res.get('_http')} {res.get('error')}")
        return False
    _log(f"{task_id}: 제출 완료 (대화 반영={res.get('delivered_to_conversation')})")
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="mysql-ai 브리지 상주 러너")
    ap.add_argument("--base", default=os.environ.get("BRIDGE_BASE", ""), help="서비스 베이스 URL")
    ap.add_argument("--token", default=os.environ.get("BRIDGE_TOKEN", ""), help="mat_ 토큰")
    ap.add_argument("--ca", default=os.environ.get("BRIDGE_CA", "") or None, help="사설 CA 인증서 경로")
    ap.add_argument("--ai", default=os.environ.get("BRIDGE_AI", ""), help="claude|codex|gemini|ollama")
    ap.add_argument("--cmd", default=os.environ.get("BRIDGE_CMD", "") or None,
                    help="직접 지정할 AI 명령. {prompt} 자리에 질문이 들어간다")
    ap.add_argument("--once", action="store_true", help="한 건만 처리하고 종료")
    ap.add_argument("--check", action="store_true", help="연결만 확인하고 종료")
    ap.add_argument("--resume", action="store_true",
                    help="지난 설정을 불러온다(주소·CA·AI). 토큰만 새로 주면 된다")
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
        args.ai = args.ai or conf.get("ai") or ""
        args.cmd = args.cmd or conf.get("cmd")
        if not args.token:
            _log("토큰이 필요합니다 — 웹에서 '연결 정보 만들기' 로 새로 받아 --token 에 주세요.")
            return 2

    if not args.base or not args.token:
        _log("FATAL: --base 와 --token 이 필요합니다.")
        return 2
    if not _transport_is_safe(args.base):
        # 토큰이 이 채널로 나간다. loopback 만 예외.
        _log("FATAL: --base 는 https 여야 합니다(loopback 예외).")
        return 2

    api = Api(args.base, args.token, args.ca)

    if args.cmd:
        kind, argv = "custom", []
    else:
        picked = (args.ai, dict(_CLI_ADAPTERS).get(args.ai, [])) if args.ai else None
        if picked and args.ai == "ollama":
            picked = ("ollama", [])
        if not picked or (args.ai and args.ai not in dict(_CLI_ADAPTERS) and args.ai != "ollama"):
            picked = detect_ai()
        if not picked:
            _log("FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.")
            return 2
        kind, argv = picked
    _log(f"AI = {kind}" + (f" ({args.cmd})" if args.cmd else ""))
    save_conf(args.base, args.ca, kind, args.cmd)

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
        _log("FATAL: 토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.")
        return 3
    if args.check:
        # `_http` 만 보면 **연결 실패(0)를 성공으로 읽는다** — 사설 CA 미지정 상태에서 실제로
        # "연결 정상." 을 출력했다. `--check` 가 거짓 안심을 주면 사용자는 러너가 왜 아무 일도
        # 안 하는지 알 수 없다.
        failed = bool(probe.get("_http")) or bool(probe.get("_failed"))
        if failed:
            _log(f"연결 실패: {probe.get('error')}")
            if probe.get("_failed"):
                _log("  사설 CA 를 쓰는 서버라면 --ca <rootCA.pem> 을 지정하세요.")
            return 1
        _log("연결 정상.")
        return 0

    cancels = CancelRegistry()
    #: 동시 처리 슬롯. 수요가 오면 늘고, 안 쓰면 오래된 것부터 준다.
    pool = WorkerPool(workers, max_workers, idle_sec, time.monotonic())
    #: 점유가 반복 실패한 task — 같은 것을 무한히 다시 시도해 서버를 두드리지 않도록 건너뛴다.
    skip: set[str] = set()
    #: 서버에 대기 질문이 있는데 한 건도 처리하지 못한 연속 라운드 수(spin 감지).
    stalled = 0
    done_once = threading.Event()

    #: 연결이 끊겼을 때의 복구 간격(feature-0045). 대기가 아니라 재연결이므로 sleep 이 있다.
    backoff = 0.0

    _log(f"대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. "
         f"(동시 {workers}건에서 시작 · 수요 시 최대 {max_workers} · "
         f"{int(idle_sec)}초 유휴 시 회수 · Ctrl+C 로 종료)")
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
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            # 여기서 조용히 죽으면 사용자는 "왜 답이 안 오지" 만 남는다. 다시 띄우는 **정확한
            # 명령**을 준다 — 설정은 이미 저장돼 있으므로 토큰만 새로 받으면 된다.
            _log("토큰이 무효해졌습니다(로그아웃 또는 만료).")
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
            _log(f"대기 실패 {code}: {res.get('error')} — {backoff:.0f}초 뒤 다시 연결합니다.")
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
            _log("서버 인스턴스 교대 중 — 곧바로 다시 대기합니다.")
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 취소는 **새 질문과 같은 응답**으로 온다(별도 채널이 아니다 — P0-J 의 즉시 인지가
        # 취소에도 그대로 적용된다). 진행 중인 워커가 다음 확인 시점에 이것을 보고 하차한다.
        fresh = cancels.add_many(res.get("canceled_task_ids") or [])
        if fresh:
            _log(f"취소 통보: {', '.join(fresh)} — 진행 중이면 중단합니다.")

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
                    _log(f"WARN: 대기 질문 {len(res.get('task_ids') or [])}건을 {stalled}회 연속 "
                         "처리하지 못했습니다(점유 실패 반복). 서버 상태와 토큰 권한을 "
                         "확인하세요 — 러너는 계속 대기합니다.")
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
        claimed = api.call("claim_request", {"task_id": task_id})
        if claimed.get("_http") == 409:
            _log(f"{task_id}: 이미 다른 세션이 가져갔다 — 건너뜀")
            skip.add(task_id)
            pool.release(sid)
            continue
        if claimed.get("_http") or claimed.get("_failed"):
            # ⚠ `_failed`(연결 실패, `_http == 0`)를 함께 본다 (codex P2-2, 2026-08-28).
            #   앞선 수정은 대기 루프만 고쳤고 여기는 그대로였다 — claim 도중 TCP/TLS 가 끊기면
            #   **빈 응답을 정상 점유로 읽고** AI 를 돌려, 아무도 기다리지 않는 답을 만든다.
            _log(f"{task_id}: 점유 실패 {claimed.get('_http')} {claimed.get('error')}")
            # 일시 장애(연결 실패·5xx·429)는 **영구 skip 하지 않는다** — 그 task 는 정상이고
            # 잠시 뒤면 집을 수 있다. 영구 skip 은 "이미 남이 가져갔다"(409) 처럼 재시도해도
            # 달라지지 않는 경우에만 쓴다(codex P1-4 의 blast radius 축소와 같은 취지).
            _code = int(claimed.get("_http") or 0)
            if _code and _code < 500 and _code != 429:
                skip.add(task_id)
            pool.release(sid)
            continue

        def _work(tid: str = task_id, payload: dict = claimed, slot: int = sid) -> None:
            try:
                handle_one(api, tid, payload, kind, argv, args.cmd, cancels)
            finally:
                cancels.forget(tid)
                # 반납 시각이 곧 그 슬롯의 `last_used` 다 — 회수 순서가 여기서 정해진다.
                pool.release(slot)
                done_once.set()

        try:
            threading.Thread(target=_work, daemon=True).start()
        except (RuntimeError, OSError) as e:  # 스레드 한도·메모리 부족
            # 여기서 그냥 터지면 **슬롯과 서버 점유가 함께 샌다** — 슬롯은 busy 인 채로,
            # task 는 lease 만료까지 남의 눈에 안 보인 채로 묶인다(codex 리뷰 P2).
            _log(f"{task_id}: 워커 스레드를 시작하지 못했습니다({e}) — 자리를 반납하고 건너뜁니다.")
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
        _log("종료합니다.")
        sys.exit(0)

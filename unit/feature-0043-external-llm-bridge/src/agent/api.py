"""서버 호출 (`Api`).

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import _UA
from .events import AGENT_FEATURES, AGENT_VERSION, _EV_API_FAIL, _self_build, _self_os
from .logs import log_event, register_secret
from .timing import _HEARTBEAT_TIMEOUT_SEC

# ── 서버 호출 ────────────────────────────────────────────────────────────────


class Api:
    #: 이 인스턴스가 신고할 기능. `--batch` 로 배치 동의를 더한다 —
    #: 전역 상수를 바꾸지 않는 이유: 같은 프로세스에서 두 Api 를 만들 수 있고, 동의는
    #: **그 실행의 선택**이지 모듈의 성질이 아니다.
    features: tuple[str, ...] = AGENT_FEATURES

    def __init__(self, base: str, token: str, ca: str | None):
        self.base = base.rstrip("/")
        self.token = token
        # 경로도 들고 있는다 — 자기 갱신(TASK-20260902T140000)이 **같은 신뢰 앵커**로 파일을
        # 받아야 하는데, `ctx` 만 남기면 그 사실을 다시 인자로 실어 날라야 하고 그러면 두 곳이
        # 갈릴 준비를 마친다(한쪽만 CA 를 바꾸면 갱신이 조용히 OS 신뢰 저장소로 떨어진다).
        self.ca = ca or None
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None
        # 로그에 이 값이 실릴 자리를 미리 막는다 — 서버 오류 본문·자식 CLI stderr·`--cmd`
        # 문자열 어디에도 토큰이 섞여 나올 수 있고, 그 로그는 사용자가 우리에게 붙여 보낸다.
        register_secret(token)

    def call(self, tool: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        return self._post(f"/api/ai/tools/{tool}", payload, timeout)

    def heartbeat(self, runtimes: list | None = None,
                  timeout: float = _HEARTBEAT_TIMEOUT_SEC,
                  released_instances: "list[str] | None" = None) -> dict:
        """"살아 있다" + **"이런 걸 쓸 수 있다"**. 도구가 아니라 연결 유지 경로다.

        도구 목록에 넣지 않는 이유는 그것이 조사 도구의 목록이기 때문이다 — 거기 끼면 AI 에게
        "이걸 호출해 조사하라" 는 잘못된 신호를 준다. 인증은 도구와 **같은 토큰**을 쓴다.

        능력(`runtimes`)을 별도 채널이 아니라 여기에 싣는 이유 (P0-Z3): 살아 있음과 능력은
        **같은 사실의 두 면**이다. 따로 보내면 "살아 있다고 하는데 능력은 모르는" 또는 그
        반대의 상태가 생기고, 화면은 그 둘 중 어느 쪽을 믿을지 정해야 한다. 한 왕복으로
        묶으면 그 질문 자체가 생기지 않는다 — 러너가 죽으면 둘 다 함께 낡는다.
        """
        # ⚠ `if runtimes` 로 쓰면 **빈 목록이 미신고로 뭉개진다**(codex REV-20260828T170000 P1-3).
        # 그러면 `--cmd` 로 갈아탄 러너가 "고를 것 없음" 을 말하지 못하고, 서버에 남아 있던 과거
        # 목록이 계속 신선한 것으로 노출된다 — 사용자는 고를 수 있는데 반영되지 않는 화면을 본다.
        # `None`(신고할 처지가 아님)과 `[]`(신고했고 고를 것이 없음)은 여기서도 다른 값이다.
        body: dict = {} if runtimes is None else {"runtimes": runtimes}
        # 기능·버전 신고 (TASK-20260831T100000). **항상** 싣는다 — 능력(`runtimes`)과 달리
        # 이것은 "무엇을 다룰 줄 아는가" 라 `--cmd` 사용자에게도 참이다. 서버는 이 값으로
        # 콘솔 작업 배급 자격을 정하고, 낡은 버전이면 응답으로 갱신 경로를 알려 준다.
        body["features"] = list(self.features)
        body["agent_version"] = AGENT_VERSION
        # 죽은 인스턴스의 **사망 신고** (TASK-20260901T140000). 기동 첫 신호에는 직전
        # 프로세스를, 종료 시에는 자기 자신을 싣는다. 서버는 그 id 로 점유된 미제출 작업만
        # 놓아준다 — 다른 러너(다른 머신)의 작업은 id 를 알 수 없어 애초에 걸리지 않는다.
        if released_instances:
            body["released_instances"] = [str(x) for x in released_instances if x]
        # 지문은 **동일성** 축이다 (2026-08-31). 날짜 버전이 같아도 파일이 다르면 서버가
        # 「배포본과 다른 러너가 돌고 있다」를 알 수 있고, 그 사실을 화면이 말해 줄 수 있다.
        body["agent_build"] = _self_build()
        # 명령 계열 신고 (2026-09-01). 연결 화면의 1단계가 **마지막으로 연결된 쪽**을 먼저
        # 보여 주게 하는 유일한 사실 — 브라우저가 도는 OS 는 러너가 도는 OS 가 아니다(WSL).
        body["agent_os"] = _self_os()
        return self._post("/api/ai/bridge_heartbeat", body, timeout)

    def _post(self, path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": _UA})
        # 서버 왕복은 **여기 한 자리**에서 계측한다 (TASK-20260901T163000). 호출측마다 재는
        # 것은 빠지는 곳이 생기고, 빠진 곳이 하필 느려지는 곳이다. `dur_ms` 가 원장에 있으면
        # 「러너가 느린가 · 서버가 느린가 · AI 가 느린가」를 로그만으로 가를 수 있다.
        _t0 = time.monotonic()

        def _ms() -> int:
            return int((time.monotonic() - _t0) * 1000)

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as resp:
                out = json.loads(resp.read().decode("utf-8", "replace") or "{}")
                log_event("api.ok", level="DEBUG", path=path, dur_ms=_ms())
                return out
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 상태코드를 뭉개지 않는다 — 401(재발급 필요)·409(남이 점유)·429(상한)는
            # 호출측이 서로 다르게 대응해야 하는 신호다.
            #
            # ⚠ 여기서 기록만 하고 **판정하지 않는다**. 409 는 정상 흐름(취소·경합)이고 401 은
            #   사고다 — 그 구분은 호출측이 문맥과 함께 한다. 심각도는 그래서 WARN 이 상한이다.
            log_event(_EV_API_FAIL, "서버가 오류로 답했다", level="WARN",
                      path=path, http=e.code, dur_ms=_ms(), detail=detail)
            return {"_http": e.code, "error": detail}
        except Exception as e:  # noqa: BLE001
            # ⚠ `_http: 0` = **연결 자체가 안 됐다**(TLS·DNS·거부). 0 은 falsy 라
            #   `if not r.get("_http")` / `if code:` 같은 진위 검사에서 **성공으로 읽힌다** —
            #   실제로 `--check` 가 사설 CA 미지정 상태에서 "연결 정상" 을 출력했다(라이브 실측
            #   2026-08-28). 호출측이 실수하지 않도록 명시 플래그를 함께 싣는다.
            #
            # 연결 실패는 **예외 형이 곧 원인**이다 — `SSLCertVerificationError`(사설 CA 미지정)
            # 와 `URLError`(DNS·거부)와 `timeout`(서버 지연)은 사용자가 할 일이 전혀 다른데,
            # `str(e)` 만 남기면 그 셋이 비슷하게 보인다. 형과 스택을 원장에 남긴다.
            log_event(_EV_API_FAIL, "서버에 닿지 못했다", level="WARN", exc=e,
                      path=path, http=0, dur_ms=_ms())
            return {"_http": 0, "_failed": True, "error": str(e)[:300]}

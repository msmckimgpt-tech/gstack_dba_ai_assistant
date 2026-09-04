"""서비스 페이지가 **이 컴퓨터의 능력**을 부르는 로컬 브리지.

## 왜 이 파일이 있는가 (사용자 결정 2026-09-04)

「Slack 같은 웹 기반 클라이언트」 요구에서 출발했지만, 결정한 구조는 **화면을 클라이언트에
넣는 것이 아니다.** 화면은 서비스에 하나만 두고, 클라이언트는 브라우저가 못 하는 일만 한다.

그 근거는 이 프로젝트가 **러너에 대해 이미 내린 판단과 같다** (`build_client.py`):

> 러너 자체는 동봉하지 않는다 — 동봉하면 서버 배포와 클라이언트 배포가 갈려
> 「고쳤는데 그대로」가 재발한다.

UI 를 클라이언트에 넣으면 그 기각한 구조를 화면에 대해 채택하는 것이 된다. 실제로 이번
주기에 **낡은 설치본이 조용히 실패**해 반나절을 썼다(해시 대조로만 갈라졌다). 화면을 고칠
때마다 그 함정이 돌아온다.

## 이 파일이 여는 위험 — 설계의 중심

로컬 HTTP 서버가 **서비스 origin 에 열린다.** 그 origin 의 어떤 페이지든 이 브리지를 부를 수
있고, **서비스에 XSS 가 생기면 사용자 머신의 프로세스 실행으로 이어진다.** tkinter 껍데기에는
없던 표면이다. 그래서 방어를 네 겹으로 둔다:

1. **127.0.0.1 바인딩 + 임의 포트.** 외부 인터페이스에 뜨지 않는다.
2. **실행마다 새 nonce.** 딥링크로만 전달되고 모든 요청의 헤더에 있어야 한다.
3. **origin 고정.** 허용 origin 은 `ConnectPlan.base` 하나뿐이다(TOFU 로 고정된 그 서버).
   `Origin` 헤더가 그것이 아니면 거절한다.
4. **위험 동작은 사람 확인**(사용자 결정 2026-09-04). 조회·상태는 웹이 바로 부르지만,
   **프로세스를 띄우는 동작**(로그인 대행·러너 상주)은 브리지가 네이티브 확인 창을 띄워
   사람의 예/아니오를 받는다. XSS 가 생겨도 **사람 없이는 진행되지 않는다.**

⚠ 3번만으로 부족한 이유를 명시한다: nonce 는 같은 페이지에서 읽히므로 XSS 는 그것도 가져간다.
사람 확인이 그 시나리오에서 유일하게 남는 방어선이다.
"""

from __future__ import annotations

import http.server
import json
import secrets
import socketserver
import threading
import time
import urllib.parse
from typing import Callable

from . import core

#: 브라우저가 «사설망 접근」 preflight 에서 요구하는 헤더. 없으면 최신 Chrome/Edge 가
#: https 페이지의 127.0.0.1 요청을 차단한다(실측 2026-09-04: 이 헤더로 통과).
_PNA_HEADER = "Access-Control-Allow-Private-Network"

#: **프로세스를 띄우는** 동작. 이것만 사람 확인을 받는다 — 조회까지 물으면 사람이 확인창을
#: 습관적으로 넘기게 되고, 그러면 정작 위험한 순간의 확인도 같이 넘어간다.
DANGEROUS: frozenset[str] = frozenset({"login", "connect"})


class Bridge:
    """로컬 브리지. **상태를 갖지 않는다** — 매 요청이 nonce·origin 을 다시 통과해야 한다."""

    def __init__(self, plan: core.ConnectPlan,
                 confirm: Callable[[str], bool],
                 host: str = "127.0.0.1"):
        self.plan = plan
        #: 위험 동작에서 사람에게 묻는 함수. **주입받는다** — tkinter 는 주 스레드만 쓸 수
        #: 있어서 여기서 직접 부르면 안 되고, 껍데기가 그 규약을 아는 쪽이다.
        self._confirm = confirm
        #: 실행마다 새로 만든다. 재시작하면 옛 링크는 죽는다.
        self.nonce = secrets.token_urlsafe(24)
        self.origin = _origin_of(plan.base)
        #: 마지막으로 패널이 말을 걸어온 시각. **수명 판정의 근거**다 — 아래 설명 참조.
        self.last_seen = time.monotonic()
        self._states: list[core.RuntimeState] = []
        self._runner_proc = None
        #: 껍데기가 **알림 영역 아이콘을 실제로 띄웠는가**. 패널의 안내 문구가 이 값을 본다.
        #: 껍데기가 세워 주기 전까지는 거짓이다 — 모르면 「유지된다」고 말하지 않는다.
        self.resident = False
        self._log: list[str] = []
        handler = _make_handler(self)
        self._srv = socketserver.ThreadingTCPServer((host, 0), handler)
        self._srv.daemon_threads = True
        self.port = self._srv.server_address[1]
        self._thread: threading.Thread | None = None

    # ── 수명 ──────────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """항상 안전하게 끝난다 — **기동하지 않은 브리지에도** 부를 수 있다.

        ⚠ `shutdown()` 은 `serve_forever()` 루프가 도는 것을 전제로, 그 루프가 멈출 때까지
        **블록한다**. 루프가 시작된 적 없으면 영원히 기다린다. 실측 2026-09-04: 기동 없이
        `stop()` 을 부른 테스트가 그대로 멎었다. 기동에 실패한 앱이 종료되지 않는 것과
        같은 결함이라 여기서 닫는다.
        """
        try:
            if self._thread is not None:
                self._srv.shutdown()
                self._thread.join(timeout=5)
                self._thread = None
        finally:
            self._srv.server_close()

    @property
    def idle_seconds(self) -> float:
        """패널이 말을 걸어온 지 얼마나 됐는가.

        ## 왜 이것이 수명 신호인가 (실측 2026-09-04)

        처음에는 **띄운 브라우저 프로세스**가 살아 있는 동안 브리지를 유지했다. 틀렸다 —
        Chrome 이 **이미 떠 있으면** 새 창을 기존 인스턴스에 위임하고 런처 프로세스는
        **즉시 종료한다**(실측: exit=0, 5초 내). 그래서 브리지가 곧바로 닫혔고 앱 창의
        패널은 「연결 프로그램에 닿지 못했습니다」만 봤다.

        프로세스 계보는 브라우저마다·상황마다 다르다. 대신 **패널이 실제로 말을 걸어오는가**
        를 본다 — 그것이 「이 창이 아직 살아 있다」의 직접 증거다.
        """
        return time.monotonic() - self.last_seen

    # ── 검문 ──────────────────────────────────────────────────────────────────
    def authorize(self, origin: str, nonce: str, site: str) -> str | None:
        """통과시키지 못하는 이유를 돌려준다. `None` 이면 통과.

        ⚠ **세 가지를 모두** 본다. 하나라도 빠지면 그 하나가 방어선 전체가 된다.
        """
        if not secrets.compare_digest(str(nonce or ""), self.nonce):
            return "nonce"
        if str(origin or "") != self.origin:
            return "origin"
        # `Sec-Fetch-Site` 는 브라우저가 붙이고 스크립트가 위조하지 못한다. 없으면(비-브라우저
        # 클라이언트) 통과시키지 않는다 — 이 브리지의 상대는 브라우저 하나뿐이다.
        if str(site or "") not in ("cross-site", "same-site", "same-origin"):
            return "fetch-site"
        return None

    # ── 동작 ──────────────────────────────────────────────────────────────────
    def act(self, action: str, body: dict) -> dict:
        self.last_seen = time.monotonic()
        fn = getattr(self, f"_do_{action}", None)
        if fn is None:
            return {"ok": False, "error": "unknown_action"}
        if action in DANGEROUS and not self._confirm(_confirm_text(action, body)):
            return {"ok": False, "error": "declined",
                    "detail": "사용자가 이 컴퓨터에서의 실행을 승인하지 않았습니다."}
        return fn(body)

    def _do_ping(self, _body: dict) -> dict:
        """패널이 살아 있음을 알린다. `act()` 가 이미 `last_seen` 을 갱신했다."""
        return {"ok": True}

    @property
    def connected(self) -> bool:
        """러너가 지금 살아 있는가. 껍데기(트레이·패널)가 상태를 읽는 **공개 창구**다.

        ⚠ `_runner_proc` 를 호출부가 직접 들여다보게 두지 않는다 — 그러면 수명 판정이 여러
        곳에 흩어지고, 그 중 하나만 고쳐지는 드리프트가 난다(이 저장소가 창 숨김 가드에서
        이미 겪은 형태).
        """
        return bool(self._runner_proc and self._runner_proc.poll() is None)

    def disconnect(self) -> bool:
        """러너를 내린다. 끊을 것이 있었으면 `True`.

        트레이의 [연결 끊기] 가 부른다. **브리지 자체는 계속 산다** — 패널을 다시 열어
        재연결할 수 있어야 하기 때문이다(그것이 상주의 의미다).
        """
        if not self.connected:
            return False
        try:
            self._runner_proc.terminate()
        except Exception:  # noqa: BLE001 — 이미 죽었으면 그것으로 족하다
            pass
        self._say("연결을 끊었습니다.")
        return True

    def _do_status(self, _body: dict) -> dict:
        return {"ok": True, "base": self.plan.base, "log": self._log[-40:],
                "runtimes": [_state_json(s) for s in self._states],
                # ⚠ 패널이 「창을 닫아도 유지됩니다」를 말해도 되는지는 **트레이가 실제로 떠
                #   있는가**에 달렸다. 껍데기가 이 값을 세우고 패널은 그것만 본다 — 프런트가
                #   스스로 추정하면 트레이 없는 머신에서 거짓을 말하게 된다(§P0-R).
                "resident": bool(self.resident),
                "connected": self.connected}

    def _do_discover(self, _body: dict) -> dict:
        found: list[core.RuntimeState] = []
        for name in core.RUNTIMES:
            for loc in core.discover_runtime(name):
                found.append(core.probe_runtime(name, where=loc.where, path=loc.path))
        for st in found:
            if st.logged_in:
                core.verify_answers(st)
        self._states = found
        self._say(f"AI {len(found)}개를 찾았습니다.")
        return {"ok": True, "runtimes": [_state_json(s) for s in found]}

    def _do_login(self, body: dict) -> dict:
        st = self._pick(body.get("id"))
        if st is None:
            return {"ok": False, "error": "unknown_runtime"}
        ok, msg = core.login(st)
        self._say(msg)
        return {"ok": ok, "detail": msg}

    def _do_connect(self, body: dict) -> dict:
        st = self._pick(body.get("id"))
        self._say("사내 CA 를 받는 중…")
        ca = core.install_ca(self.plan)
        self._say("러너를 받는 중…")
        runner = core.install_runner(self.plan, ca)
        rc, out = core.check_connection(self.plan, runner, ca, st)
        if rc == 4:
            self._say("서버 연결은 정상인데 쓸 수 있는 AI 를 찾지 못했습니다.")
            return {"ok": False, "error": "no_ai"}
        if rc != 0:
            self._say(out[:200])
            return {"ok": False, "error": "check_failed", "detail": out[:400]}
        core.pin_server(self.plan.home, self.plan.base)
        self._runner_proc = core.spawn_runner(self.plan, runner, ca, st)
        self._say("연결됐습니다.")
        return {"ok": True}

    def _pick(self, ident: str | None) -> core.RuntimeState | None:
        for st in self._states:
            if st.label == ident:
                return st
        return None

    def _say(self, line: str) -> None:
        self._log.append(line)


def _origin_of(base: str) -> str:
    """`https://h:443/x` → `https://h:443`. 비교 대상은 **origin** 이지 URL 이 아니다."""
    parts = urllib.parse.urlsplit(str(base or ""))
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _state_json(st: core.RuntimeState) -> dict:
    return {"id": st.label, "name": st.name, "where": st.where, "path": st.path,
            "logged_in": st.logged_in, "answers": st.answers, "usable": st.usable,
            "detail": st.detail, "can_login_here": st.can_login_here}


def _confirm_text(action: str, body: dict) -> str:
    who = str(body.get("id") or "")
    if action == "login":
        return (f"웹 화면이 이 컴퓨터에서 «{who}» 로그인 명령을 실행하려고 합니다.\n\n"
                "직접 요청한 것이 아니라면 [아니요] 를 누르세요.")
    return (f"웹 화면이 이 컴퓨터에서 «{who}» 로 연결을 시작하려고 합니다.\n"
            "러너를 내려받아 상주시킵니다.\n\n"
            "직접 요청한 것이 아니라면 [아니요] 를 누르세요.")


def _make_handler(bridge: "Bridge"):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # ── 응답 도구 ────────────────────────────────────────────────────────
        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", bridge.origin)
            self.send_header("Access-Control-Allow-Headers", "content-type,x-dqa-nonce")
            self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
            self.send_header(_PNA_HEADER, "true")
            self.send_header("Vary", "Origin")

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ── 경로 ─────────────────────────────────────────────────────────────
        def do_OPTIONS(self):  # noqa: N802
            # ⚠ preflight 에는 아직 nonce 가 실리지 않는다(브라우저가 커스텀 헤더를 안 보낸다).
            #   그래서 여기서는 **origin 만** 본다. 실제 검문은 POST 에서 한다.
            if self.headers.get("Origin") != bridge.origin:
                self._json(403, {"ok": False, "error": "origin"})
                return
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):  # noqa: N802
            # 조회조차 GET 으로 열지 않는다 — GET 은 `<img>`·`<script>` 로도 발사되어
            # preflight 없이 나간다. 모든 동작은 POST + 커스텀 헤더를 거친다.
            self._json(405, {"ok": False, "error": "use_post"})

        def do_POST(self):  # noqa: N802
            why = bridge.authorize(self.headers.get("Origin", ""),
                                   self.headers.get("X-DQA-Nonce", ""),
                                   self.headers.get("Sec-Fetch-Site", ""))
            if why:
                self._json(403, {"ok": False, "error": why})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            except Exception:  # noqa: BLE001
                self._json(400, {"ok": False, "error": "bad_json"})
                return
            action = self.path.strip("/").split("/")[-1]
            try:
                self._json(200, bridge.act(action, body if isinstance(body, dict) else {}))
            except core.IntegrityError as exc:
                self._json(200, {"ok": False, "error": "integrity", "detail": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._json(200, {"ok": False, "error": "failed", "detail": str(exc)[:400]})

        def log_message(self, *_a):  # 조용히 — 토큰이 로그에 남지 않게
            return

    return Handler

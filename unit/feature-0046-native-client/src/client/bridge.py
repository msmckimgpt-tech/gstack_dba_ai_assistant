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
from dataclasses import replace
from typing import Callable

from . import core, updater, version

#: 브라우저가 «사설망 접근」 preflight 에서 요구하는 헤더. 없으면 최신 Chrome/Edge 가
#: https 페이지의 127.0.0.1 요청을 차단한다(실측 2026-09-04: 이 헤더로 통과).
_PNA_HEADER = "Access-Control-Allow-Private-Network"

#: **프로세스를 띄우는** 동작. 이것만 사람 확인을 받는다 — 조회까지 물으면 사람이 확인창을
#: 습관적으로 넘기게 되고, 그러면 정작 위험한 순간의 확인도 같이 넘어간다.
#:
#: ⚠ `update_apply` 가 여기 있는 것은 **가장 강한 형태**이기 때문이다 — 러너 한 장을 받는
#: 것이 아니라 이 프로그램 전체를 갈아 끼우는 **설치기**를 돌린다. 배포본이 서명되지 않았으므로
#: 「알 수 없는 게시자」 실행을 사람 없이 하지 않는다(사용자 결정 2026-09-07).
DANGEROUS: frozenset[str] = frozenset({"login", "connect", "update_apply"})


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
        #: 껍데기가 **알림 영역 아이콘이 지금 살아 있는가**를 답하는 함수. 패널의 안내 문구가
        #: 이 판정을 본다. 껍데기가 세워 주기 전까지는 `None` 이고, 그때 `resident` 는
        #: 거짓이다 — 모르면 「유지된다」고 말하지 않는다.
        self.resident_probe: Callable[[], bool] | None = None
        #: 껍데기가 **이 프로그램을 끝내는** 함수. 업데이트 설치는 실행 중인 exe 를 갈아
        #: 끼우므로 우리가 비켜 줘야 한다 — 껍데기마다 끝내는 방법이 달라서 주입받는다
        #: (내장 창은 `shell.quit`, 브라우저 셸은 `_SHELL_QUIT.set`).
        self.on_quit: Callable[[], None] | None = None
        #: 마지막 확인에서 발견한 새 버전. 트레이·패널·확인 문구가 **같은 값**을 본다 —
        #: 각자 다시 조회하면 확인창이 말한 버전과 실제로 받는 버전이 갈릴 수 있다.
        self.pending_update: "updater.Update | None" = None
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

    @property
    def resident(self) -> bool:
        """**지금** 창을 닫아도 이 프로그램이 남는가 — 패널 안내 문구의 유일한 근거.

        ⚠ 읽기 전용이다. 종전에는 껍데기가 `br.resident = tray is not None` 으로 **기동
        시점의 bool** 을 대입했는데, 아이콘은 뜬 뒤에도 사라지므로(탐색기 재시작 후 재등록
        실패) 그 값은 곧 거짓말이 된다 — 패널은 계속 「닫아도 유지됩니다」를 말하고, 실제로는
        닫는 순간 프로그램이 끝난다(§P0-R). 대입 자리를 없애 그 형태를 **구조적으로 불가능**
        하게 만들었다(§16.7 G10 — 재발 클래스의 구조 가드 승격).

        ⚠ probe 가 던지면 **거짓**이다. 판정 불가를 「유지된다」로 읽으면 그 실패가 그대로
        거짓 안내가 된다.
        """
        probe = self.resident_probe
        if probe is None:
            return False
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001 — 모르면 「유지된다」고 말하지 않는다
            return False

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
        if action not in DANGEROUS:
            return fn(body)
        # ⚠ **확인 대상을 «묻기 전에» 고정한다.** 이 서버는 스레드당 요청을 처리하므로,
        #   확인창이 떠 있는 사이 다른 요청(`update_check`)이 `pending_update` 를 갈아 끼울
        #   수 있다. 종전에는 확인이 끝난 뒤 핸들러가 그 필드를 다시 읽어서, 확인창이 말한
        #   버전과 실제로 설치되는 버전이 **갈렸다** — 이 cycle 의 테스트가 그것을 잡았다.
        #   확인창이 방어선인 시스템에서 그 확인이 무엇에 대한 동의인지가 정의되어야 한다.
        target = self.pending_update if action == "update_apply" else None
        if not self._confirm(_confirm_text(action, body, bridge=self, pending=target)):
            return {"ok": False, "error": "declined",
                    "detail": "사용자가 이 컴퓨터에서의 실행을 승인하지 않았습니다."}
        if action == "update_apply":
            return self._do_update_apply(body, target=target)
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

    # ── 업데이트 (feature-0046 client-update-channel, 2026-09-07) ──────────────
    def _do_update_check(self, _body: dict) -> dict:
        """더 새 버전이 있는가. **조회뿐이라 확인창이 없다**(`DANGEROUS` 밖).

        찾은 것은 `pending_update` 에 남긴다 — 이어지는 확인창·트레이·패널이 **같은 값**을
        보게 하기 위해서다. 각자 다시 조회하면 확인창이 말한 버전과 실제로 받는 버전이
        갈릴 수 있고, 그 어긋남은 사용자에게 보이지 않는다.
        """
        found, why = updater.check_detail(self.plan.home)
        self.pending_update = found
        # ⚠ 「최신이다」와 「확인하지 못했다」를 같은 필드로 접지 않는다 — 접으면 CA 만료로
        #   조용히 실패하는 머신이 최신인 머신과 구분되지 않는다(적대 리뷰 §3-3).
        updater.mark_checked(self.plan.home, error=why or None)
        if why:
            updater.log(self.plan.home, f"check FAILED — {why}")
        if found is None:
            return {"ok": True, "current": version.CLIENT_VERSION, "available": None,
                    "error": why or None}
        self._say(f"새 버전이 있습니다 — {found.version}")
        return {"ok": True, "current": version.CLIENT_VERSION,
                "available": {"version": found.version, "notes": found.notes,
                              "size": found.size}}

    def _do_update_apply(self, _body: dict,
                         target: "updater.Update | None" = None) -> dict:
        """확인을 받은 뒤 설치기를 받아 실행한다. `act()` 가 이미 물었다(`DANGEROUS`).

        ⚠ **확인할 것이 없으면 진행하지 않는다.** `pending_update` 가 없으면 `act()` 가
        띄운 확인 문구는 「받을 버전을 아직 확인하지 못했습니다 — 확인을 먼저 눌러 주세요」
        이고 **[아니요] 를 누르라고 지시한다**. 그런데도 [예] 로 진행하면, 사용자가 승인한
        대상과 실제로 실행되는 대상이 갈린다 — 확인창이 방어선인 시스템에서 그 확인이
        무엇에 대한 동의인지가 정의되지 않는다(적대 리뷰 F3, 런타임 probe 로 확인).
        그래서 여기서 거절해 그 문구를 **실제 집행**으로 만든다.

        ⚠ 확인 시점의 `Update` 를 **지역으로 고정해** 넘긴다. 이 서버는 스레드당 요청을
        처리하므로, 확인창이 떠 있는 사이 다른 요청(`update_check`)이 `pending_update` 를
        갈아 끼울 수 있다 — 그러면 확인창이 말한 버전과 설치되는 버전이 달라진다(§3-7).
        """
        # ⚠ **폴백을 두지 않는다** (적대 리뷰 P1-B, probe 로 재현). `or self.pending_update`
        #   가 있으면 `act()` 가 `target=None` 으로 고정해 넘겼는데도 그 고정이 무효화된다 —
        #   확인창이 「받을 버전을 아직 확인하지 못했습니다」라고 말한 그 갈래에서, 확인 중에
        #   주기 감시가 세운 구체 버전이 설치됐다. 게다가 그 문구는 「no pending」 전용이라
        #   F5 의 주소 불일치 경고가 **아예 표시되지 않는다** — 완화가 통째로 비켜 간다.
        if target is None:
            return {"ok": False, "error": "no_pending",
                    "detail": "받을 버전을 먼저 확인해 주세요."}
        return self.update_now(confirmed=True, target=target)

    def update_now(self, confirmed: bool = False,
                   target: "updater.Update | None" = None,
                   require_idle: bool = False) -> dict:
        """확인 → 내려받기 → 검사 → 설치기 실행 → 이 프로그램 종료.

        트레이 메뉴와 웹 패널이 **같은 함수**를 부른다. 입구가 둘인데 코드패스가 갈리면
        한쪽만 고쳐지는 드리프트가 난다(§P0-AC.1 이 트레이 「다시 연결」을 두지 않은 근거와
        같은 축).

        ⚠ `confirmed` 는 **호출부가 이미 사람에게 물었을 때만** 참이다. 기본값이 거짓인
        이유는, 이 인자를 잊은 새 호출부가 «묻지 않고 설치하는» 경로가 되지 않게 하기
        위해서다 — 실패는 안전한 쪽으로 기운다.

        ⚠ `require_idle` 은 **사람이 없는 경로**(자동 적용)가 준다. 확인창이 뜨는 경로에서는
        「지금 연결 중이라 답변이 죽는다」를 문구가 말하고 결정은 사람이 하지만, 자동 경로에는
        그 결정을 대신할 사람이 없다 — 그래서 연결이 살아 있으면 미룬다(적대 리뷰 F4,
        이식 원본 `try_self_update` 의 `if active.count() > 0: return False` 와 같은 자리).
        """
        found = target or self.pending_update or updater.check(self.plan.home)
        if found is None:
            return {"ok": False, "error": "up_to_date",
                    "detail": f"이미 최신입니다 ({version.CLIENT_VERSION})."}
        self.pending_update = found
        # ⚠ **순서의 정본은 `updater.run_flow` 하나다** (적대 리뷰 C-2). 브리지(웹 패널·
        #   트레이)와 tkinter 껍데기가 같은 순서를 밟아야 하고, 그 순서 안에 무결성 판정과
        #   단일 실행 게이트가 들어 있다 — 두 곳에 복제하면 그 중 하나만 고쳐진다.
        return updater.run_flow(
            self.plan.home, target=found,
            confirm=None if confirmed else self._confirm,
            say=self._say,
            is_connected=lambda: self.connected,
            require_idle=require_idle,
            on_started=self._quit_soon)

    def _quit_soon(self, delay: float = 1.5) -> None:
        """**응답을 보낸 뒤** 프로그램을 끝낸다.

        ⚠ 여기서 곧바로 끝내면 이 요청의 HTTP 응답이 나가지 못하고, 패널은 「연결 프로그램에
        닿지 못했습니다」를 본다 — 실제로는 성공했는데 화면이 실패를 말하는 형태다(§P0-R).
        """
        quit_fn = self.on_quit
        if quit_fn is None:
            return
        threading.Timer(delay, lambda: self._safe_quit(quit_fn)).start()

    @staticmethod
    def _safe_quit(quit_fn: Callable[[], None]) -> None:
        try:
            quit_fn()
        except Exception:  # noqa: BLE001 — 못 끝내도 설치기는 이미 떴다
            pass

    def _do_status(self, _body: dict) -> dict:
        pending = self.pending_update
        return {"ok": True, "base": self.plan.base, "log": self._log[-40:],
                "runtimes": [_state_json(s) for s in self._states],
                # 화면이 「업데이트 있음」을 그릴 근거. **서버가 아니라 이 프로그램이** 판정한다
                # — 판정을 프런트가 조립하면 같은 사실을 두 곳이 다르게 말한다.
                "version": version.CLIENT_VERSION,
                "update": ({"version": pending.version, "notes": pending.notes}
                           if pending else None),
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

    def _plan_for(self, body: dict) -> "tuple[core.ConnectPlan | None, str]":
        """이번 연결에 쓸 값. `(plan, 문제)` — `plan` 이 `None` 이면 `문제` 를 읽는다.

        ## 왜 패널이 값을 주는가 (2026-09-04)

        종전에는 **딥링크로 받은 값만** 썼다. 그래서 인자 없이 켠 앱 창(시작 메뉴·바탕화면)은
        토큰이 없어 연결을 걸 수 없었다 — 프로그램이 웹의 부속물로 남던 이유다.

        토큰을 발급하는 주체는 원래부터 **로그인 세션**이고, 앱 창은 그 세션을 갖고 있다.
        그러니 값을 주는 쪽은 패널이 자연스럽다. 딥링크가 실어 온 값은 이제 **폴백**이다
        (그 값은 창을 여는 사이 만료됐을 수도 있다).

        ⚠ 봉투는 딥링크와 **같은 문자열**을 그대로 쓴다(`launch.protocol`). 웹이 이미 만들어
        두는 값이고, 여기서 필드를 새로 정하면 같은 뜻의 봉투가 둘이 되어 한쪽만 고쳐진다.

        ⚠ **`base` 는 우리가 아는 그 서버여야 한다.** 패널이 다른 주소를 실어 보내면 거절한다 —
        그 값으로 CA·러너를 내려받게 되므로, 서버가 자기 자신 아닌 곳을 가리키는 순간
        고정(TOFU)이 무력해진다.
        """
        sent = core.parse_scheme_url(str(body.get("launch") or ""))
        if sent:
            if str(sent.get("base", self.plan.base)).rstrip("/") != self.plan.base:
                return None, "base"
            if not sent.get("token"):
                return None, "token"
            # ⚠ 봉투가 지문을 **생략했다고 기존 값을 지우지 않는다** (codex 적대 리뷰
            #   2026-09-04). `install_ca`·`install_runner` 는 기대값이 비면 대조를 **건너뛴다** —
            #   빈 값으로 덮으면 무결성 검사가 조용히 꺼진다. 서버가 값을 못 낸 회차에
            #   대조가 사라지는 것이 정확히 그 형태다.
            return replace(self.plan, token=sent["token"],
                           ca_sha256=sent.get("ca_sha256") or self.plan.ca_sha256,
                           agent_sha256=sent.get("agent_sha256")
                           or self.plan.agent_sha256), ""
        return (self.plan, "") if self.plan.token else (None, "token")

    def _do_connect(self, body: dict) -> dict:
        plan, why = self._plan_for(body)
        if plan is None:
            detail = ("연결 정보를 받지 못했습니다. 이 창에서 로그인한 뒤 다시 눌러 주세요."
                      if why == "token" else
                      "웹 화면이 다른 서버를 가리켰습니다. 연결하지 않았습니다.")
            self._say(detail)
            return {"ok": False, "error": "no_" + why, "detail": detail}
        st = self._pick(body.get("id"))
        self._say("사내 CA 를 받는 중…")
        ca = core.install_ca(plan)
        self._say("러너를 받는 중…")
        runner = core.install_runner(plan, ca)
        rc, out = core.check_connection(plan, runner, ca, st)
        if rc == 4:
            self._say("서버 연결은 정상인데 쓸 수 있는 AI 를 찾지 못했습니다.")
            return {"ok": False, "error": "no_ai"}
        if rc != 0:
            self._say(out[:200])
            return {"ok": False, "error": "check_failed", "detail": out[:400]}
        core.pin_server(plan.home, plan.base)
        self._runner_proc = core.spawn_runner(plan, runner, ca, st)
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


def _confirm_text(action: str, body: dict, bridge: "Bridge | None" = None,
                  pending: "updater.Update | None" = None) -> str:
    who = str(body.get("id") or "")
    if action == "update_apply":
        # ⚠ **버전을 말한다.** 「업데이트할까요?」만 물으면 사용자는 무엇이 설치되는지도,
        #   연결이 끊긴다는 것도 모른다. 문구의 정본은 `updater.confirm_text` 하나이고
        #   트레이 경로도 같은 것을 쓴다.
        # ⚠ 호출부가 고정해 준 대상이 있으면 **그것**을 말한다. 여기서 필드를 다시 읽으면
        #   문구와 설치 대상이 서로 다른 시점의 값을 보게 된다(`act()` 의 ⚠ 참조).
        pending = pending or getattr(bridge, "pending_update", None)
        connected = bool(getattr(bridge, "connected", False))
        if pending is None:
            return ("웹 화면이 이 컴퓨터에서 업데이트 설치를 실행하려고 합니다.\n"
                    "받을 버전을 아직 확인하지 못했습니다 — 확인을 먼저 눌러 주세요.\n\n"
                    "직접 요청한 것이 아니라면 [아니요] 를 누르세요.")
        home = getattr(getattr(bridge, "plan", None), "home", None)
        return updater.confirm_text(pending, connected, home=home)
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

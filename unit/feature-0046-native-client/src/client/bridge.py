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
from .discovery import DiscoveryCache, state_json

#: 브라우저가 «사설망 접근」 preflight 에서 요구하는 헤더. 없으면 최신 Chrome/Edge 가
#: https 페이지의 127.0.0.1 요청을 차단한다(실측 2026-09-04: 이 헤더로 통과).
_PNA_HEADER = "Access-Control-Allow-Private-Network"

#: **프로세스를 띄우는** 동작. 끝난 뒤 알림 영역으로 **알린다**.
#:
#: ## 왜 「묻기」에서 「알리기」로 바꿨나 (사용자 결정 2026-09-07)
#:
#: 종전에는 이 동작들 앞에 네이티브 확인 창을 띄웠다. 사용자 제보:
#:
#:   > 연결을 되묻는것은 사용자에게 위협으로 다가올 수 있습니다.
#:   > 별도의 확인 창 없이 수행되도록 구성해주세요.
#:
#: 실제로 그 창은 **사용자가 방금 패널에서 [이 서비스에 연결] 을 누른 직후** 떴다 — 자기가
#: 시킨 일을 다시 묻는 모양이고, 문구가 「웹 화면이 이 컴퓨터에서 …」로 시작해 경고처럼 읽힌다.
#:
#: ⚠ **잃는 것을 분명히 적는다.** 이 확인은 서비스에 XSS 가 생겼을 때 「사람 없이 사용자
#: 머신에서 프로세스가 뜨는 것」을 막던 **마지막 겹**이었다(origin·nonce 는 XSS 가 그대로
#: 통과한다 — 같은 페이지에서 읽히기 때문이다). 그 겹은 이제 없다.
#:
#: 대신 **끝난 뒤 알린다.** 막지는 못하지만 **모르게 일어나지는 않는다** — 사용자가 알림을
#: 보고 이상하면 트레이에서 [연결 끊기]·[종료] 를 할 수 있다. 사용자 결정 2026-09-07.
NOTIFIED: frozenset[str] = frozenset({"login", "connect"})

#: **확인 창을 유지하는 동작.** 위 `NOTIFIED` 와 **다른 판정축**이다.
#:
#: ## 왜 업데이트만 여전히 묻는가 (두 사용자 결정이 공존한다)
#:
#: 같은 날(2026-09-07) 두 결정이 났고 **대상이 다르다**:
#:
#: - 연결·로그인 → 「되묻지 말고 알려라」. 근거는 사용자가 **방금 패널에서 [연결] 을 누른
#:   직후** 그 창이 떴다는 것이다 — 자기가 시킨 일을 다시 묻는 모양이었다.
#: - 업데이트 → 「확인 후 적용」. 사용자가 누른 것은 [업데이트 **확인**] 이고, 그 다음에
#:   일어나는 일(어느 버전이 설치되는가 · AI 연결이 끊긴다 · 어디서 받는가)은 **아직 말한
#:   적이 없다**. 이 확인창이 그것을 처음 말하는 자리다.
#:
#: ⚠ 그리고 잃는 것의 크기가 다르다. 연결은 러너 한 장을 상주시키지만 이것은 **서명되지 않은
#: 설치기가 프로그램 전체를 갈아 끼운다** — 위 `NOTIFIED` 주석이 「마지막 겹이 없어졌다」고
#: 적은 그 겹을, 대가가 가장 큰 동작에서는 유지한다.
CONFIRMED: frozenset[str] = frozenset({"update_apply"})


class Bridge:
    """로컬 브리지. **상태를 갖지 않는다** — 매 요청이 nonce·origin 을 다시 통과해야 한다."""

    def __init__(self, plan: core.ConnectPlan,
                 notify: "Callable[[str, str], None] | None" = None,
                 confirm: "Callable[[str], bool] | None" = None,
                 host: str = "127.0.0.1"):
        self.plan = plan
        #: `CONFIRMED` 동작 앞에서 사람에게 **묻는** 함수. **주입받는다** — tkinter 는 주
        #: 스레드만 쓸 수 있어서 여기서 직접 부르면 안 되고, 껍데기가 그 규약을 아는 쪽이다.
        #:
        #: ⚠ **주지 않으면 «아니요» 다.** 묻지 못하는 환경에서 「예」로 떨어지면 물어보려던
        #: 이유가 통째로 무력화된다 — 확인은 **받아야** 성립하지 못 받으면 성립하지 않는다
        #: (`gui.confirm` 이 창을 못 띄울 때 거짓을 내는 것과 같은 규율).
        self._confirm = confirm or (lambda _message: False)
        #: 프로세스를 띄운 **뒤** 사용자에게 알리는 함수(제목, 본문). **주입받는다** —
        #: 알림 영역 아이콘은 껍데기가 세우고, 못 세운 머신도 있다(그때는 알리지 못한다).
        #: ⚠ 알림이 실패해도 동작은 계속된다 — 알림은 통지이지 관문이 아니다.
        self._notify = notify or (lambda title, body: None)
        #: 실행마다 새로 만든다. 재시작하면 옛 링크는 죽는다.
        self.nonce = secrets.token_urlsafe(24)
        self.origin = _origin_of(plan.base)
        #: 마지막으로 패널이 말을 걸어온 시각. **수명 판정의 근거**다 — 아래 설명 참조.
        self.last_seen = time.monotonic()
        self._states: list[core.RuntimeState] = []
        self._runner_proc = None
        self._runner_lock = threading.Lock()
        self._runner_generation = 0
        self._stopping = False
        self.discovery = DiscoveryCache(plan.home)
        self._selected: dict[str, core.RuntimeState] = {}
        self._retry_after: dict[str, int] = {}
        self._selection_ids: dict[str, str] = {}
        self._connect_lock = threading.RLock()
        self._connection_session = ""
        self._runner_ca = None
        #: 껍데기가 **알림 영역 아이콘이 지금 살아 있는가**를 답하는 함수. 패널의 안내 문구가
        #: 이 판정을 본다. 껍데기가 세워 주기 전까지는 `None` 이고, 그때 `resident` 는
        #: 거짓이다 — 모르면 「유지된다」고 말하지 않는다.
        self.resident_probe: Callable[[], bool] | None = None
        #: Explicit application shutdown belongs to the shell.
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
        self._stopping = True
        self.disconnect()
        proc = self._runner_proc
        try:
            if proc is not None and hasattr(proc, "wait"):
                proc.wait(timeout=10)
        finally:
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
        # ⚠ **확인 대상을 «묻기 전에» 고정한다.** 이 서버는 스레드당 요청을 처리하므로,
        #   확인창이 떠 있는 사이 다른 요청(`update_check`)이 `pending_update` 를 갈아 끼울
        #   수 있다. 확인이 끝난 뒤 핸들러가 그 필드를 다시 읽으면, 확인창이 말한 버전과
        #   실제로 설치되는 버전이 **갈린다** — 적대 리뷰가 probe 로 재현한 결함이다.
        if action in CONFIRMED:
            target = self.pending_update if action == "update_apply" else None
            if not self._confirm(_confirm_text(action, body, bridge=self,
                                               pending=target)):
                return {"ok": False, "error": "declined",
                        "detail": "사용자가 이 컴퓨터에서의 실행을 승인하지 않았습니다."}
            if action == "update_apply":
                return self._do_update_apply(body, target=target)

        result = fn(body)
        # ⚠ **끝난 뒤에** 알린다. 앞에서 알리면 실패한 시도까지 「실행했다」고 말하게 되고,
        #   그 알림은 사용자가 확인할 방법이 없는 소음이 된다.
        if action in NOTIFIED and isinstance(result, dict) and result.get("ok") and not result.get("already_connected") and not result.get("pending"):
            try:
                self._notify(*_notice(action, body))
            except Exception:  # noqa: BLE001 — 알림 실패가 동작을 되돌리지 않는다
                pass
        return result

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
        proc = self._runner_proc
        return bool(proc and getattr(proc, "running", proc.poll() is None))

    def disconnect(self) -> bool:
        """러너를 내린다. 끊을 것이 있었으면 `True`.

        트레이의 [연결 끊기] 가 부른다. **브리지 자체는 계속 산다** — 패널을 다시 열어
        재연결할 수 있어야 하기 때문이다(그것이 상주의 의미다).
        """
        with self._runner_lock:
            self._runner_generation += 1
            self._selected.clear()
            proc = self._runner_proc
            if proc is None or proc.poll() is not None:
                return False
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
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
            prepared = updater.installation.prepared_version()
            return {"ok": True, "current": version.CLIENT_VERSION, "available": None,
                    "prepared_version": prepared,
                    "detail": updater.prepared_text(prepared) if prepared and not why else "",
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
        """Install without interrupting the app or its runner. Confirmation remains required."""
        found = target or self.pending_update or updater.check(self.plan.home)
        if found is None:
            return {"ok": False, "error": "up_to_date",
                    "detail": f"이미 최신입니다 ({version.CLIENT_VERSION})."}
        self.pending_update = found
        # ⚠ **순서의 정본은 `updater.run_flow` 하나다** (적대 리뷰 C-2). 브리지(웹 패널·
        #   트레이)와 tkinter 껍데기가 같은 순서를 밟아야 하고, 그 순서 안에 무결성 판정과
        #   단일 실행 게이트가 들어 있다 — 두 곳에 복제하면 그 중 하나만 고쳐진다.
        result = updater.run_flow(
            self.plan.home, target=found,
            confirm=None if confirmed else self._confirm,
            say=self._say,
            is_connected=lambda: self.connected,
            require_idle=require_idle)
        if result.get("prepared"):
            self.pending_update = None
            try:
                self._notify("업데이트 설치 완료", result["detail"])
            except Exception:
                pass
        return result


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
                "installation": updater.installation_status(self.plan.home),
                "update": ({"version": pending.version, "notes": pending.notes}
                           if pending else None),
                # ⚠ 패널이 「창을 닫아도 유지됩니다」를 말해도 되는지는 **트레이가 실제로 떠
                #   있는가**에 달렸다. 껍데기가 이 값을 세우고 패널은 그것만 본다 — 프런트가
                #   스스로 추정하면 트레이 없는 머신에서 거짓을 말하게 된다(§P0-R).
                "resident": bool(self.resident),
                "connected": self.connected,
                "connections": [state_json(st) for st in list(self._selected.values())
                                if self._connection_state(st).get("state") == "ready"] if self.connected else [],
                "connection_session": getattr(self, "_connection_session", ""),
                "client_features": ["platform_connections", "discovery_cache", "wsl_accounts"]}

    def _do_discover(self, _body: dict) -> dict:
        result = self.discovery.discover(force=_body.get("force") is True,
                                         background=_body.get("background") is True)
        self._states = list(self.discovery.states)
        return result

    def _do_discovery_status(self, _body: dict) -> dict:
        result = self.discovery.snapshot()
        self._states = list(self.discovery.states)
        return result

    def _do_login(self, body: dict) -> dict:
        st = self._pick(body.get("id"))
        if st is None:
            return {"ok": False, "error": "unknown_runtime"}
        ok, msg = core.login(st)
        self.discovery.invalidate(st.label)
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
        ident = body.get("id")
        st = self._pick(ident)
        if ident and (st is None or not st.usable):
            return {"ok": False, "error": "unknown_runtime",
                    "detail": "이 위치를 다시 확인해 주세요."}
        with self._runner_lock:
            generation = self._runner_generation
        with self._connect_lock:
            if self._stopping or generation != self._runner_generation:
                return {"ok": False, "error": "cancelled"}
            return self._connect_one(body, st, generation)

    def _runner_event(self, state: str, message: str) -> None:
        self._say(message)
        if state == "disconnected":
            self._notify("연결이 끊겼습니다", message)

    def _connect_one(self, body: dict, st: core.RuntimeState | None, generation: int) -> dict:
        plan, why = self._plan_for(body)
        if plan is None:
            detail = ("연결 정보를 받지 못했습니다. 이 창에서 로그인한 뒤 다시 눌러 주세요."
                      if why == "token" else
                      "웹 화면이 다른 서버를 가리켰습니다. 연결하지 않았습니다.")
            self._say(detail)
            return {"ok": False, "error": "no_" + why, "detail": detail}
        session = str(body.get("connection_session") or "")[:128]
        ca = None
        if session:
            try:
                ca = self._runner_ca if self._runner_active() and self._runner_ca else core.install_ca(plan)
                verified = core.connection_identity(plan, ca)
                if verified != session:
                    raise ValueError("session mismatch")
            except Exception:
                return {"ok": False, "error": "session_invalid",
                        "detail": "로그인 세션을 확인하지 못했습니다. 다시 로그인해 주세요."}
        same_session = ((session and session == self._connection_session)
                        or (not session and plan.token == self.plan.token))
        if session and same_session and self._runner_active() and plan.token != self.plan.token:
            try:
                same_session = core.connection_identity(self.plan, ca) == session
            except Exception:
                same_session = False
        with self._runner_lock:
            if self._stopping or generation != self._runner_generation:
                return {"ok": False, "error": "cancelled"}
            if st and self._runner_active() and same_session:
                previous = self._selected.get(st.name)
                if previous and all(getattr(previous, k) == getattr(st, k)
                                    for k in ("name", "where", "path", "distro", "user")):
                    state = self._connection_state(st).get("state")
                    if state == "failed":
                        self._retry_after[st.name] = time.time_ns()
                        self._write_selection(self._selected, changed_name=st.name)
                    return {"ok": True, "already_connected": state == "ready",
                            "pending": state != "ready", "id": st.label}
                self._write_selection({**self._selected, st.name: st}, changed_name=st.name)
                self._selected[st.name] = st
                return {"ok": True, "pending": True, "id": st.label}
        self._say("연결을 준비하는 중…")
        plan = replace(plan, selection_file="")
        ca = ca or core.install_ca(plan)
        runner = core.install_runner(plan, ca)
        # 새 로그인은 기존 연결로 표시하지 않는다. 새 토큰 검증을 끝낸 뒤에만 교체한다.
        rc, out = core.check_connection(plan, runner, ca, st)
        if rc == 4:
            self._say("서버 연결은 정상인데 쓸 수 있는 AI 를 찾지 못했습니다.")
            return {"ok": False, "error": "no_ai"}
        if rc != 0:
            self._say(out[:200])
            return {"ok": False, "error": "check_failed", "detail": out[:400]}
        core.pin_server(plan.home, plan.base)
        with self._runner_lock:
            if self._stopping or generation != self._runner_generation:
                return {"ok": False, "error": "cancelled"}
            previous = self._runner_proc
            if previous is not None and previous.poll() is None:
                previous.terminate()
        if previous is not None and hasattr(previous, "wait"):
            previous.wait(timeout=10)
        with self._runner_lock:
            if self._stopping or generation != self._runner_generation:
                return {"ok": False, "error": "cancelled"}
            if st:
                self._write_selection({st.name: st}, changed_name=st.name)
                plan = replace(plan, selection_file=str(plan.home / "runtime-selection.json"),
                               selection_instance=secrets.token_hex(16))
            proc = core.spawn_runner(plan, runner, ca, st, on_event=self._runner_event)
            if proc is not None and proc.poll() is not None:
                return {"ok": False, "error": "runner_exited",
                        "detail": "AI 연결이 종료됐습니다. 다시 연결해 주세요."}
            self._runner_proc = proc
            self._runner_ca = ca
            self.plan = plan
            self._connection_session = session
            if st:
                self._selected = {st.name: st}
        self._say("모델을 확인하는 중…" if st else "연결됐습니다.")
        return {"ok": True, "pending": bool(st), "id": st.label if st else ""}

    def _runner_active(self):
        return self._runner_proc is not None and self._runner_proc.poll() is None

    def _connection_state(self, st):
        if not self.connected:
            if self._runner_proc is not None and self._runner_proc.poll() is None:
                return {"state": "pending"}
            return {"state": "failed", "detail": "AI 연결이 종료됐습니다. 다시 연결해 주세요."}
        try:
            path = self.plan.home / "runtime-selection.ready.json"
            if path.stat().st_size > 262144: return {"state": "pending"}
            doc = json.loads(path.read_text(encoding="utf-8"))
            row = doc.get("locations", {}).get(st.name, {})
            target = {k: getattr(st, k) for k in ("path", "where", "distro", "user")}
            if st.name in self._selection_ids:
                target["selection_id"] = self._selection_ids[st.name]
            if (doc.get("instance") == self.plan.selection_instance and row.get("target") == target
                    and doc.get("pid") == getattr(self._runner_proc, "pid", None)):
                if row.get("state") == "failed" and row.get("failed_at", 0) < self._retry_after.get(st.name, 0):
                    return {"state": "pending"}
                if row.get("state") == "ready" and self.discovery.preferences.get(st.name) != st.label:
                    self.discovery.remember(st)
                return row
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {"state": "pending"}

    def _do_connection_status(self, body):
        st = self._selected.get(str(body.get("name") or ""))
        if st is None or st.label != body.get("id"):
            return {"ok": False, "state": "failed", "detail": "연결할 위치를 다시 선택해 주세요."}
        return {"ok": True, **self._connection_state(st)}

    def _write_selection(self, selected, *, changed_name=None):
        # 러너 하나에 위치를 원자적으로 전달한다. 새 플랫폼을 추가해도 기존 질문을 끊지 않는다.
        import os
        import tempfile
        self.plan.home.mkdir(parents=True, exist_ok=True)
        ids = {name: (secrets.token_hex(16) if name == changed_name or name not in self._selection_ids
                      else self._selection_ids[name]) for name in selected}
        fd, temp = tempfile.mkstemp(prefix=".runtime-selection-", dir=self.plan.home)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({name: {k: getattr(st, k) for k in ("path", "where", "distro", "user")}
                           | {"selection_id": ids[name]} for name, st in selected.items()}, stream, ensure_ascii=False)
            os.replace(temp, self.plan.home / "runtime-selection.json")
            self._selection_ids = ids
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

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
    return state_json(st)


def _notice(action: str, body: dict) -> "tuple[str, str]":
    """끝난 뒤 알림 영역에 띄울 (제목, 본문) — `NOTIFIED` 동작용.

    ⚠ 경고가 아니라 **보고**다. 사용자가 방금 시킨 일이므로 「직접 요청한 것이 아니라면」
    같은 문구를 쓰지 않는다 — 그 어투가 확인 창을 위협으로 읽히게 만든 원인이다.
    """
    who = str(body.get("id") or "")
    if action == "login":
        return (core.DISPLAY_NAME, f"{who} 로그인 명령을 실행했습니다.")
    return (core.DISPLAY_NAME, f"{who} 로 연결했습니다. 이제 질문에 답할 수 있습니다.")


def _confirm_text(action: str, body: dict, bridge: "Bridge | None" = None,
                  pending: "updater.Update | None" = None) -> str:
    """`CONFIRMED` 동작의 **사전** 확인 문구 — 현재는 업데이트 설치 하나다.

    ⚠ `_notice` 와 대칭이 아니다. 저쪽은 「방금 시킨 일을 보고」하고 이쪽은 「아직 말한 적
    없는 일을 미리」 말한다 — 사용자가 누른 것은 [업데이트 **확인**] 이고, 어느 버전이
    설치되는지·AI 연결이 끊기는지·어디서 받는지는 이 창이 처음 말하는 자리다.
    """
    if action == "update_apply":
        # ⚠ **버전을 말한다.** 「업데이트할까요?」만 물으면 사용자는 무엇이 설치되는지도,
        #   연결이 끊긴다는 것도 모른다. 문구의 정본은 `updater.confirm_text` 하나이고
        #   트레이 경로도 같은 것을 쓴다.
        # ⚠ 호출부가 고정해 준 대상이 있으면 **그것**을 말한다. 여기서 필드를 다시 읽으면
        #   문구와 설치 대상이 서로 다른 시점의 값을 보게 된다(`act()` 의 ⚠ 참조).
        pending = pending or getattr(bridge, "pending_update", None)
        connected = bool(getattr(bridge, "connected", False))
        if pending is None:
            return ("업데이트를 설치하려고 합니다.\n"
                    "받을 버전을 아직 확인하지 못했습니다 — 확인을 먼저 눌러 주세요.\n\n"
                    "직접 요청한 것이 아니라면 [아니요] 를 누르세요.")
        home = getattr(getattr(bridge, "plan", None), "home", None)
        return updater.confirm_text(pending, connected, home=home)
    # ⚠ 도달하지 않는 갈래를 **조용히 참으로 만들지 않는다.** `CONFIRMED` 에 새 동작을
    #   더하고 문구를 잊으면, 사용자는 무엇을 승인하는지 모르는 창을 보게 된다.
    return (f"이 컴퓨터에서 «{action}» 을 실행하려고 합니다.\n\n"
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

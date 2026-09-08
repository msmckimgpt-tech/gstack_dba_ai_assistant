// REQ-20260514-0001: 대화 공유 페이지 (anonymous accessible) 의 vanilla JS.
// /share/{token} 페이지에서 로드되어 /api/public/share/{token} 을 호출하고
// 메시지·SQL·결과셋을 read-only 렌더링한다.
//
// share-client-entry (사용자 결정 2026-09-08): **열람과 참가의 경로가 갈린다.**
//   · 열람 — 평범한 웹브라우저로 끝난다(익명 포함). 종전 그대로다.
//   · 참여(join)·fork — **DQA 앱**에서 한다. 브라우저에서는 앱으로 건너가는 버튼만 보이고,
//     직접 실행 버튼(참여·fork)은 **앱 창 안에서만** 나타난다.
// 판정 신호는 브리지 좌표 하나뿐이다(`window.__dqaClientBridge` ← share-client-context.js).
//
// ⚠ 이 분기는 **표시이지 집행이 아니다.** 참여·fork 의 자격은 서버가 로그인 세션과 공유
//   토큰으로 정한다(`routers/share.py` 의 join·fork 게이트). 여기서 버튼을 감추는 것은
//   경로를 하나로 모으는 UX 결정이지 권한 통제가 아니며, 그렇게 설계했다 — 우회로 얻는
//   것은 권한이 아니라 «어느 화면에서 눌렀는가» 뿐이다.
//
// ⚠ **어디까지 우회되는지 적어 둔다** (적대 리뷰 2026-09-08 2R-§3). 전달받은 링크에
//   `?client_port=…` 하나를 붙이면 아래 `inClientApp()` 의 2차 신호가 참이 되어 앱 유도를
//   건너뛰고 직접 실행 버튼이 뜬다. 이것은 **결함이 아니라 이 설계의 알려진 성질**이다 —
//   서버 게이트가 자격을 집행하므로 권한은 변하지 않는다. 다만 이 사실이 기록돼 있지 않으면
//   다음 사람이 이 유도를 «통제» 로 오인하고 그 위에 무언가를 얹는다(프런트 게이트를 분기
//   판정에 쓰면 한쪽 갈래가 영구히 죽는, 이 저장소가 이미 겪은 형태).

(function () {
  "use strict";

  // 메인 UI(app.js)와 동일한 SQL 가독성 줄바꿈 키워드 — formatSqlForDisplay 가 사용.
  const SQL_FORMAT_KEYWORDS = [
    "LEFT OUTER JOIN",
    "RIGHT OUTER JOIN",
    "FULL OUTER JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "INNER JOIN",
    "OUTER JOIN",
    "FULL JOIN",
    "CROSS JOIN",
    "UNION ALL",
    "GROUP BY",
    "ORDER BY",
    "INSERT INTO",
    "DELETE FROM",
    "SELECT",
    "FROM",
    "WHERE",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "UNION",
    "UPDATE",
    "SET",
    "VALUES",
  ];

  // share-sender-nickname: 발신자 각인이 없는 메시지(1:1 대화·legacy)의 화자 라벨 폴백 기준.
  // render() 가 payload 의 conversation.{owner_username,is_group} 으로 갱신한다(senderLabel 참조).
  // `_shareIsGroup` 은 **그룹으로 확인됐을 때만** false 가 아니게 되며, 미상(구 payload)이면
  // true 로 둬 소유자명 폴백을 막는다(fail-closed — 오귀속보다 익명 토큰이 정직하다).
  let _shareOwnerUsername = "";
  let _shareIsGroup = true;

  const path = window.location.pathname.split("/").filter(Boolean);
  const token = path.length > 0 ? decodeURIComponent(path[path.length - 1]) : "";

  if (!token) {
    showError("공유 토큰이 URL 에 없습니다.");
    return;
  }

  setupCopyLink();
  watchFooterSpacing();

  fetchShare(token)
    .then((data) => {
      render(data, token);
      // 진입 시 대화의 최신(맨 아래) 메시지부터 보이도록 문서 스크롤을 맨 아래로 둔다.
      engageInitialBottomPin();
    })
    .catch((err) => showError(err && err.message ? err.message : "공유 데이터를 불러오지 못했습니다."));

  // 수신자가 현재 공유 링크를 손쉽게 재전달할 수 있도록 "링크 복사" 버튼을 연결한다.
  function setupCopyLink() {
    const btn = document.getElementById("shareCopyLinkBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const url = window.location.href;
      const original = btn.textContent;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(url);
        } else {
          const ta = document.createElement("textarea");
          ta.value = url;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
        }
        btn.textContent = "복사됨 ✓";
        btn.classList.add("is-copied");
      } catch (e) {
        btn.textContent = "복사 실패";
      }
      window.setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove("is-copied");
      }, 1600);
    });
  }

  async function fetchShare(tok, branchView) {
    // feature-0019 shared-readonly-paging: branchView 가 주어지면 그 버전의 브랜치를 읽기전용으로
    // 요청한다(서버는 공유 window 내 검증 후에만 반영·active_leaf 불변). 범위 밖이면 서버가 무시.
    let _url = `/api/public/share/${encodeURIComponent(tok)}`;
    if (branchView != null) _url += `?branch_view=${encodeURIComponent(String(branchView))}`;
    const res = await fetch(_url, {
      credentials: "same-origin",
    });
    if (res.status === 404) throw new Error("공유 링크를 찾을 수 없습니다.");
    if (res.status === 410) {
      // TASK-20260619T012028-share-link-expiry: 서버 메시지로 만료/취소 구분.
      const body = await res.json().catch(() => ({}));
      throw new Error(body && body.error ? body.error : "이 공유 링크는 더 이상 사용할 수 없습니다.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body && body.error ? body.error : `서버 오류 (${res.status})`);
    }
    return res.json();
  }

  function render(data, tok) {
    const conv = (data && data.conversation) || {};
    const share = (data && data.share) || {};
    const viewer = (data && data.viewer) || {};
    const messages = Array.isArray(data && data.messages) ? data.messages : [];

    const topicEl = document.getElementById("shareTopic");
    if (topicEl) topicEl.textContent = conv.topic || "공유된 대화";

    const ownerEl = document.getElementById("shareOwner");
    if (ownerEl) ownerEl.textContent = conv.owner_username ? `소유자 ${conv.owner_username}` : "";
    // share-sender-nickname: 각인 없는 메시지의 화자 폴백 기준을 이번 payload 로 갱신.
    // 메시지 렌더(renderMessage)·rail 라벨보다 **먼저** 세팅돼야 한다.
    _shareOwnerUsername = typeof conv.owner_username === "string" ? conv.owner_username.trim() : "";
    // 소유자명 폴백은 1:1 로 **확인된** 대화에서만 허용한다(그룹 legacy 행 오귀속 차단).
    // 서버가 신호를 안 주면(구 payload) 그룹으로 간주 — fail-closed.
    _shareIsGroup = conv.is_group !== false;

    const scopeEl = document.getElementById("shareScope");
    if (scopeEl) {
      if (share.scope_mode === "anchored" && share.anchor_message_id != null) {
        scopeEl.textContent = `범위: 여기까지 공유 (메시지 #${share.anchor_message_id})`;
      } else {
        scopeEl.textContent = "범위: 대화 전체";
      }
    }

    const productEl = document.getElementById("shareProduct");
    if (productEl) {
      const productLabel = conv.product_name || conv.product_key || "";
      productEl.textContent = productLabel ? `제품 ${productLabel}` : "";
    }

    // TASK-20260619T012028-share-link-expiry: 만료일 표시 (무기한이면 숨김).
    const expiryEl = document.getElementById("shareExpiry");
    if (expiryEl) {
      expiryEl.textContent = share.expires_at ? `만료 ${formatDateTime(share.expires_at)}` : "";
    }

    const viewCountEl = document.getElementById("shareViewCount");
    if (viewCountEl) viewCountEl.textContent = `조회 ${share.view_count || 0}회`;

    const messagesEl = document.getElementById("shareMessages");
    if (messagesEl) {
      messagesEl.innerHTML = "";
      if (messages.length === 0) {
        const empty = document.createElement("div");
        empty.className = "share-empty";
        empty.textContent = "공유된 메시지가 없습니다.";
        messagesEl.appendChild(empty);
      } else {
        messages.forEach((msg, idx) => messagesEl.appendChild(renderMessage(msg, idx, tok)));
      }
    }

    // 공유 대화도 우측 스크롤바 가이드 뱃지(point rail)를 구성한다 — 메인 UI(app.js
    // renderMessagePointRail)와 동형. 공유 페이지는 window(document) 스크롤이라 rail 은
    // position:fixed 미니맵으로 구현된다(메인은 #messageLog 내부 스크롤).
    setupSharePointRail(messages);

    const joinBtn = document.getElementById("shareJoinBtn");
    const forkBtn = document.getElementById("shareForkBtn");
    const appBtn = document.getElementById("shareAppEntryBtn");
    const appGet = document.getElementById("shareAppGetLink");
    const loginLink = document.getElementById("shareLoginLink");
    // share-join-btn-visibility (2026-08-04 사용자 요청): 참여 버튼은 **링크가 참여
    // 허용(joinable) + 로그인** 이면 노출한다. 종전엔 can_join(= 로그인 && joinable &&
    // !already_member) 만 봤기 때문에, 대화 소유자·기존 멤버가 자기 공유 링크를 열면
    // 참여 버튼이 아무 설명 없이 사라져 "그룹 대화 참여 버튼 누락" 으로 인지되는 마찰이
    // 실측됐다(share Id=81, viewer=owner).
    // (권한 게이트 자체는 서버 can_join/joinable 계산 그대로 — 프론트 표시만 넓힌다.)
    //
    // ⚠ 이미 멤버인 viewer 는 **join 을 호출하지 않는다**(openJoinedConversation). 서버 join 은
    // 이미 멤버여도 windowed 링크면 `stamp_member_visibility(is_new_member=False)` 로 가시
    // 범위를 교집합 축소하며(owner·full 멤버는 skip 되지만 기존 windowed 멤버는 좁아지고
    // 복구 경로가 없다), 표시를 넓힌 대가로 그 mutation 을 사용자에게 노출할 수는 없다.
    // 핸들러는 1 회만 부착되므로(wireShareAction) 첫 render 의 viewer 를 클로저에 가두면
    // 재렌더 후 stale 판정이 된다 — 최신 viewer 를 모듈 스코프에 두고 클릭 시점에 읽는다.
    _latestViewer = viewer;
    _latestClient = (data && data.client) || {};

    // share-client-entry: 직접 실행은 **앱 창 안에서만**. 밖에서는 앱으로 건너간다.
    //
    // ⚠ 단 **결정의 전제가 갖춰졌을 때만** 그렇게 한다. 사용자 결정은 「앱 전용 + 받기 안내」
    //   였다(2026-09-08). 그러므로 다음 두 회차에는 종전 웹 경로로 **열화**한다:
    //     ① 서버가 앱 링크를 내지 못했다 — 우리 쪽 장애다.
    //     ② 받을 곳이 없다(`download_url` 부재) — 「받기 안내」가 성립하지 않는 배포다.
    //   ②를 빼고 앱 전용만 집행하면 결정의 절반만 적용되어, 앱이 없는 수신자는 설치할 방법도
    //   돌아갈 길도 없는 화면을 본다. 리눅스 도커 파이프라인은 설치기를 만들지 못하므로
    //   (`oauth_as._client_download_url` 참조) 그 회차는 예외가 아니라 흔한 상태다.
    //   결정이 전제한 조건이 갖춰졌을 때만 결정을 적용하는 편이 결정에 더 충실하다
    //   (P0-Q — 되돌아갈 길을 가리키면서 그 길을 닫아 두면 막다른 길이다).
    const appEntryReady = Boolean(
      _latestClient.app_link && _latestClient.download_url && appPlatformSupported());
    const directActions = inClientApp() || !appEntryReady;

    // ⚠ **이미 멤버인 사람의 클릭은 «이동» 이지 «참여» 가 아니다.** 그 갈래는 `join` 을
    //   호출하지 않고 `/?conversation=` 로 갈 뿐이라(openJoinedConversation) 앱의 능력을
    //   전혀 쓰지 않는다. 이 cycle 이 앱 뒤로 옮기기로 한 것은 join 과 fork 두 가지이므로,
    //   그 둘이 아닌 이동까지 데스크톱 설치 뒤로 보내면 결정 범위 밖의 기능이 함께 끌려간다
    //   (자기 공유 링크를 확인하는 소유자, 앱 없는 자리에서 링크를 받은 기존 멤버).
    const canReturnToConversation = Boolean(viewer.already_member && viewer.conversation_id);
    const showJoin = shouldShowJoin(viewer) && (directActions || canReturnToConversation);
    wireShareAction(joinBtn, showJoin, () => {
      const v = _latestViewer || {};
      if (v.already_member) openJoinedConversation(v.conversation_id);
      else doJoin(tok, joinBtn);
    });
    if (joinBtn && showJoin) {
      // ⚠ 앱 밖에서 보이는 유일한 경우가 «이미 멤버» 갈래이므로, 그때는 **라벨 자체**를
      //   바꾼다. 「대화에 참여」라고 적힌 버튼이 참여가 아니라 이동을 하면, 그 사람은
      //   자기가 무엇을 누르는지 모른 채 누른다(툴팁은 터치 기기에 도달하지 않는다).
      const moveOnly = Boolean(viewer.already_member);
      joinBtn.textContent = moveOnly ? "대화로 이동" : "대화에 참여";
      joinBtn.title = moveOnly
        ? "이미 참여 중인 대화입니다 — 그 대화로 이동합니다"
        : "이 공유 링크로 그룹 대화에 참여합니다";
    }
    wireShareAction(
      forkBtn,
      directActions && Boolean(viewer.is_authenticated && viewer.can_fork),
      () => doFork(tok, forkBtn),
    );

    // 평범한 브라우저 — 앱 진입 하나로 모은다.
    const showAppEntry = !directActions && appEntryIsUseful(viewer);
    wireShareAction(appBtn, showAppEntry, () => enterViaApp());
    if (appBtn && !appBtn.dataset.shareEntryBusy) {
      // 이미 멤버에게 남은 앱 동작은 fork 뿐이다 — 라벨이 그 사실을 말한다.
      //
      // ⚠ **busy 중에는 건드리지 않는다** (적대 리뷰 3R C1). 클릭이 라벨을 「앱을 여는 중...」
      //   으로 바꾸고 `disabled` 를 거는데, 그 2.5초 사이에 재렌더가 일어나면 여기서 라벨만
      //   되돌아가 **「정상 라벨 + 죽은 버튼」** 이 된다 — 사용자에게는 「누를 수 있게 생긴
      //   버튼이 안 눌린다」로 보이고, 그것은 이 조치가 고치려던 「눌렀는데 아무 일도 없다」와
      //   구분되지 않는다. 라벨·`disabled`·busy 마커는 **한 주인**(클릭 타이머)이 갖는다.
      appBtn.textContent = viewer.already_member
        ? "DQA 앱에서 fork" : "DQA 앱에서 참여 · fork";
    }
    if (appBtn && showAppEntry) {
      // ⚠ 단정하지 않는다. 서버는 미로그인 viewer 의 `can_fork`·`can_join` 을 알려 주지
      //   않으므로(로그인 전에는 false 로 온다), 「할 수 있습니다」는 화면이 확인하지 않은
      //   능력을 약속하는 문장이 된다.
      appBtn.title = viewer.is_authenticated
        ? "이 대화를 DQA 앱에서 엽니다 — 참여·fork 는 앱에서 진행합니다"
        : "DQA 앱에서 로그인한 뒤 참여·fork 를 진행합니다";
    }
    // ⚠ **상시 설명 한 줄** — 이 화면의 독자는 이 제품을 처음 보는 사람일 수 있다(익명
    //   접근을 허용하는 유일한 화면이다). 툴팁에만 둔 설명은 터치 기기에 존재하지 않으므로,
    //   무엇을 누르면 무슨 일이 일어나는지 화면에 남긴다. 클릭하면 상태 문구로 교체된다.
    const hintEl = document.getElementById("shareAppHint");
    if (hintEl) {
      // ⚠ **켜기만 하고 끄지 않으면** 재렌더로 앱 진입이 사라진 뒤에도 「참여·fork 는 앱에서
      //   합니다」가 남아, 되살아난 종전 웹 버튼 바로 옆에서 서로를 반증한다(적대 리뷰 3R C2 —
      //   상시 설명이 눈앞에서 틀리면 그 문장 전체의 신뢰가 떨어진다). `wireShareAction` 과
      //   같은 규약으로 **토글**한다. 단 클릭 후 상태 문구가 떠 있는 동안에는 유지한다.
      const keepFired = Boolean(hintEl.dataset.shareHintFired);
      if (showAppEntry && !keepFired) {
        setHintText(viewer.already_member
          ? "fork 는 DQA 앱에서 합니다 (Windows)."
          : "참여·fork 는 DQA 앱에서 합니다 (Windows).");
      }
      hintEl.classList.toggle("hidden", !showAppEntry && !keepFired);
    }
    syncFooterSpacing();
    // ⚠ 받기 안내는 **실물이 있을 때만**(서버가 존재를 확인해 URL 을 낸 경우). 없는
    //   다운로드를 안내하면 사용자는 안내받은 대로 갔다가 막힌다.
    const canGet = showAppEntry && Boolean(_latestClient.download_url);
    if (appGet && canGet) appGet.href = String(_latestClient.download_url);
    wireShareAction(appGet, canGet, null);

    // ⚠ **열화 분기의 미로그인 수신자에게는 로그인 진입이 있어야 한다** (3R H2).
    //   열화(`directActions`)는 「종전 웹 경로를 살려 둔다」는 뜻인데, 그 경로에서 join·fork 를
    //   가르는 조건은 플랫폼이 아니라 `is_authenticated` 다 — 로그인하면 바로 그 버튼에 닿는다.
    //   이 링크가 없으면 앱 창 안·받을 곳 없음·비-Windows 세 갈래 모두에서 그 사람의 화면에
    //   남는 것은 [링크 복사] 하나뿐이다(실측).
    //   ⚠ **앱 전용 분기에서는 감춘다** — 거기서는 로그인해도 누를 버튼이 없어 링크 자체가
    //   막다른 길이 된다(그것이 2026-09-08 에 이 링크를 지운 원래 이유다).
    wireShareAction(loginLink, directActions && !viewer.is_authenticated, null);
    compactFooterForNarrow();
  }

  // 하단 고정 바가 본문을 덮지 않게 여백을 **실제 높이에 맞춘다**.
  //
  // ⚠ 종전에는 `.share-container { padding-bottom: 80px }`(모바일 96px)라는 **상수**가
  //   그 역할을 했다. 바가 「안내문 한 줄 + 버튼 한 줄」로 고정이던 동안에는 성립했지만,
  //   이번 변경이 안내 행을 하나 더 얹으면서 그 예산이 깨졌다 — 실측(2026-09-08,
  //   chromium): 데스크톱 hover 82.5px > 80px, 375px 뷰포트 180.1px > 96px,
  //   320px 뷰포트 198.1px > 96px. 초과분은 `position: fixed` 바에 **영구히 가려진 대화
  //   말미**가 되고, 하필 이 화면은 진입 시 맨 아래로 pin 되므로 사용자가 처음 보는 자리가
  //   그 가려진 구간이다.
  //
  // ⚠ 상수를 키우는 대신 **재서 맞춘다** — 문구·언어·폭·글꼴이 바뀌면 상수는 또 어긋난다.
  //   CSS 상수는 스크립트가 죽었을 때의 폴백으로 남긴다.
  // ⚠ 값을 **줄이지 않는다**(관측 최댓값 유지). hover 로 바가 커질 때마다 여백이 늘었다
  //   줄면 본문이 위아래로 흔들린다. 폭이 바뀌면 그때만 리셋하고 다시 잰다.
  let _footerPadFor = -1;
  function syncFooterSpacing() {
    try {
      const footer = document.querySelector(".share-footer");
      const container = document.querySelector(".share-container");
      if (!footer || !container) return;
      // ⚠ 인쇄 매체에서는 바가 없다 — 그 자리를 비워 두면 빈 페이지가 한 장 더 난다.
      //   CSS 쪽 `@media print` 가 `!important` 로 막지만, 값을 애초에 얹지 않는 편이 정직하다.
      try {
        if (window.matchMedia && window.matchMedia("print").matches) return;
      } catch (_) { /* matchMedia 부재 환경 — CSS 쪽 방어에 맡긴다 */ }
      if (_footerPadFor !== window.innerWidth) {
        _footerPadFor = window.innerWidth;
        container.style.paddingBottom = "";
      }
      const need = Math.ceil(footer.getBoundingClientRect().height) + 12;
      const cur = parseFloat(getComputedStyle(container).paddingBottom) || 0;
      if (need > cur) container.style.paddingBottom = need + "px";
    } catch (_) { /* 여백 계산 실패가 화면을 깨지 않는다 */ }
  }

  // 안내 문구를 쓴다. **문단이 아니라 자식 span 에** 쓴다 — 좁은 폭에서 [DQA 앱 받기] 가
  // 이 문단 안으로 접혀 들어오므로(`compactFooterForNarrow`), 문단에 `textContent` 를 대입하면
  // 그 링크가 함께 지워진다(실측으로 사라졌다). 그러면 안내는 없는 버튼을 가리키게 된다.
  function setHintText(text) {
    const slot = document.getElementById("shareAppHintText");
    if (slot) slot.textContent = text;
    else {
      const hint = document.getElementById("shareAppHint");
      if (hint) hint.textContent = text;   // 구조가 바뀐 경우의 폴백
    }
  }

  //: 이 폭 아래에서는 받기 링크를 **안내문 안**으로 접는다. 값의 근거는 실측이다 —
  //: 320px 에서 버튼 3개가 두 줄로 접히며 액션 그룹만 67px 를 먹는다.
  const _NARROW_FOOTER_PX = 420;

  // 좁은 화면에서 하단 고정 바의 **행 수**를 줄인다.
  //
  // ⚠ 여백 동기화(`syncFooterSpacing`)는 「가려지지 않는다」를 보장할 뿐 «바가 화면의 얼마를
  //   가져가는가» 는 보장하지 않는다 — 실측(2026-09-08): 320×568 에서 바가 174px 로
  //   **화면의 31%** 였다. 게다가 그 높이의 대부분은 Windows 전용 경로(스킴 버튼·`.exe`
  //   받기·Windows 안내)인데, 그 경로가 실행되지 않는 기기(휴대폰)에서 가장 크게 문다.
  //   읽기 위한 화면에서 고정 바가 1/3 을 영구 점유하면 그것은 기능이 아니라 방해다
  //   (적대 리뷰 2026-09-08 ux-2R-F4).
  //
  // ⚠ 정보를 **버리지 않는다** — 받기 링크는 사라지는 것이 아니라 안내문 줄 끝으로 옮겨간다.
  function compactFooterForNarrow() {
    try {
      const get = document.getElementById("shareAppGetLink");
      const hint = document.getElementById("shareAppHint");
      const actions = document.querySelector(".share-actions");
      if (!get || !hint || !actions) return;
      const narrow = window.innerWidth <= _NARROW_FOOTER_PX;
      const wanted = narrow ? hint : actions;
      if (get.parentElement !== wanted) wanted.appendChild(get);
      get.classList.toggle("share-app-get--inline", narrow);
    } catch (_) { /* 배치 실패가 화면을 깨지 않는다 */ }
  }

  function watchFooterSpacing() {
    const footer = document.querySelector(".share-footer");
    if (!footer) return;
    compactFooterForNarrow();
    syncFooterSpacing();
    try {
      new ResizeObserver(syncFooterSpacing).observe(footer);
    } catch (_) {
      // ResizeObserver 미지원 — hover 로 커지는 순간만이라도 따라간다.
      footer.addEventListener("mouseenter", syncFooterSpacing);
      footer.addEventListener("focusin", syncFooterSpacing);
    }
    window.addEventListener("resize", () => {
      compactFooterForNarrow();
      syncFooterSpacing();
    });
  }

  // 이 기기에 DQA 앱이 **존재할 수 있는가**.
  //
  // ⚠ 앱은 Windows 전용이고(feature-0046 FUNCTION §4 — macOS 는 서명·공증 없이는 Gatekeeper
  //   가 차단해 범위 밖), 받기 링크가 가리키는 것도 `.exe` 다. 그런데 공유 링크는 이 제품이
  //   바깥을 향해 여는 유일한 표면이라 **macOS·Linux·모바일 수신자가 흔하다.** 그 사람에게
  //   앱 전용을 강제하면 누를 수 있는 유일한 버튼이 그 기기에서 동작하지 않는 스킴이 되고,
  //   그 옆 받기는 `.exe` 다 — 참여·fork 로 가는 길이 **하나도 없다**.
  //
  //   이것은 사용자 결정(앱 전용)의 예외가 아니라, 이미 채택한 열화 규칙(「결정이 전제한
  //   조건이 갖춰졌을 때만 결정을 적용한다」)의 같은 적용이다. 받을 곳이 없는 배포에서
  //   열화하는 것과 **받을 수 없는 기기에서 열화하는 것**은 같은 사유다.
  //
  // ⚠ UA 판정은 위조 가능하지만 여기서는 문제가 아니다 — 이 분기는 **표시**이고, 위조해서
  //   얻는 것은 「앱 전용 화면을 본다」뿐이다(그리고 그 사람은 앱이 있을 것이다).
  function appPlatformSupported() {
    try {
      const nav = window.navigator || {};
      const hint = String(nav.userAgentData && nav.userAgentData.platform ? nav.userAgentData.platform
        : (nav.platform || nav.userAgent || ""));
      return /win/i.test(hint);
    } catch (_) {
      // 판정할 수 없으면 **앱 전용을 강제하지 않는다** — 모르는 채 길을 닫는 쪽이 더 나쁘다.
      return false;
    }
  }

  // 지금 이 화면이 **DQA 앱 창 안**인가. 신호는 브리지 좌표 하나뿐이다 —
  // `share-client-context.js` 가 정본 모듈(`app/client-bridge.js`)에서 받아 얹어 둔다.
  // ⚠ 그 모듈이 아직 안 돌았으면 `undefined` 이고, 그것은 「앱 밖」과 같게 다룬다 —
  //   모르면 앱 밖으로 본다(잘못 「앱 안」으로 보면 앱에서만 되는 버튼을 브라우저에
  //   띄우고, 눌러도 아무 일이 없다).
  function inClientApp() {
    try {
      if (window.__dqaClientBridge) return true;
      // ⚠ **2차 신호.** 어댑터 모듈(`share-client-context.js` → `app/client-bridge.js`)이
      //   적재에 실패하면 전역은 비고, 그 상태에서 앱 창은 **자기를 앱 밖으로 판정**해
      //   지금 보고 있는 이 페이지를 향해 딥링크를 다시 쏜다 — 사용자가 빠져나올 수 없는
      //   왕복이 된다. 모듈이 안 돌았다면 좌표는 주소에서 지워지지 않고 남아 있으므로,
      //   그것을 두 번째 근거로 쓴다(값을 쓰지는 않는다 — 판정에만 쓴다).
      return new URLSearchParams(window.location.search).has("client_port");
    } catch (_) {
      return false;
    }
  }

  // 앱으로 건너갈 값어치가 있는가. **할 수 없는 일을 권하지 않는다** — 참여도 fork 도
  // 불가능한 링크에서 앱을 띄우면 사용자는 앱을 열고 나서야 그것을 안다.
  // ⚠ 미로그인은 «가능/불가» 를 아직 알 수 없다(서버가 can_* 를 false 로 준다). 그 사람에게
  //   앱은 로그인 자리이기도 하므로 보여 준다 — 이 화면에서 로그인할 길은 이제 없다.
  function appEntryIsUseful(viewer) {
    const v = viewer || {};
    if (!v.is_authenticated) return true;
    // ⚠ **이미 멤버면 «참여» 는 이미 끝난 일이다** — 그 사람에게 남은 것은 fork 뿐이다.
    //   `joinable` 만 보고 버튼을 남기면 한 줄에 「대화로 이동」(웹에서 바로 들어감)과
    //   「DQA 앱에서 참여 · fork」(앱을 받으라)와 「참여·fork 는 앱에서 합니다」가 나란히
    //   서서 서로를 반증한다 — 상시 설명이 눈앞에서 틀리면 그 문장 전체의 신뢰가 떨어지고,
    //   정작 fork 하려는 사람도 안내를 믿지 않는다(적대 리뷰 2026-09-08 ux-2R-F3).
    if (v.already_member) return Boolean(v.can_fork);
    return Boolean(v.joinable || v.can_join || v.can_fork);
  }

  // 앱을 띄운다. 스킴 URL 로 여는 것이 유일한 수단이다 — 브라우저는 샌드박스라 프로세스를
  // 직접 띄우지 못한다(connect-modal 의 `_fireScheme` 과 같은 형태).
  //
  // ⚠ **성공을 확인할 방법이 없다.** 브라우저는 스킴 핸들러 부재를 알려 주지 않으므로,
  //   앱이 없는 사람에게는 «아무 일도 일어나지 않는» 것으로 보인다. 그래서 누른 직후
  //   안내를 띄운다 — 무엇이 일어나야 하는지와, 일어나지 않았을 때 무엇을 할지.
  function enterViaApp() {
    const link = String((_latestClient && _latestClient.app_link) || "");
    if (!link) return;
    // ⚠ **버튼 자체가 눌렸다고 말한다.** 상시 설명이 생기면서 클릭의 피드백이 「없던 줄이
    //   생긴다」(출현)에서 「같은 자리·같은 크기·같은 색의 텍스트가 바뀐다」(교체)로 격하됐다 —
    //   인지적으로 가장 눈에 안 띄는 변화다. 같은 바의 다른 세 액션은 전부 버튼 안에서
    //   말한다(`복사됨 ✓` · `참여 중...` · `fork 중...`). 앱 진입만 그 관례에서 빠지면
    //   「눌렀는데 아무 일도 없다」와 구분되지 않는다(적대 리뷰 2026-09-08 ux-2R-F2).
    // ⚠ 되돌리는 것은 **성공했기 때문이 아니다** — 스킴 발사는 성공을 확인할 수 없다.
    //   이 앱은 새 창으로 뜨므로 이 탭은 살아 있고, 사용자가 다시 누를 수 있어야 한다.
    const btn = document.getElementById("shareAppEntryBtn");
    if (btn && !btn.dataset.shareEntryBusy) {
      btn.dataset.shareEntryBusy = "1";
      const label = btn.textContent;
      btn.textContent = "앱을 여는 중...";
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = label;
        btn.disabled = false;
        delete btn.dataset.shareEntryBusy;
      }, 2500);
    }
    const hint = document.getElementById("shareAppHint");
    if (hint) {
      // ⚠ **표시로 먼저 전환하고, 그다음 태스크에서 텍스트를 넣는다.** `display:none` 인
      //   live region 의 내용 변경은 스크린리더에 통지되지 않는다 — 이 안내는 스킴 발사의
      //   **유일한** 피드백이라, 통지되지 않으면 그 사용자에게는 「눌러도 아무 반응 없음」과
      //   구분되지 않는다.
      hint.dataset.shareHintFired = "1";
      setHintText("");
      hint.classList.remove("hidden");
      const message = _latestClient.download_url
        ? "DQA 앱을 여는 중입니다. 창이 안 보이면 다른 창·알림 영역을 확인해 주세요. 앱이 없으면 [DQA 앱 받기]."
        : "DQA 앱을 여는 중입니다. 창이 안 보이면 다른 창·알림 영역을 확인해 주세요. (Windows 전용)";
      setTimeout(() => { setHintText(message); syncFooterSpacing(); }, 0);
    }
    try {
      window.location.href = link;
    } catch (_) {
      /* 스킴 발사 실패도 화면을 깨지 않는다 — 위 안내가 다음 행동을 이미 말했다. */
    }
  }

  // render() 가 갱신하는 최신 viewer 스냅샷 — 1 회 부착된 클릭 핸들러가 클릭 시점에 읽는다.
  let _latestViewer = {};
  // 같은 이유로 앱 진입 정보(`app_link`·`download_url`)도 모듈 스코프에 둔다 — 버전 페이징
  // 재렌더로 값이 바뀌어도 클릭은 **그 시점의** 값을 읽어야 한다.
  let _latestClient = {};

  // 이미 멤버/소유자인 viewer 의 '대화에 참여' 클릭 — **join 을 호출하지 않고** 그 대화로 이동한다.
  // 이유: 서버 join 은 이미 멤버여도 windowed 링크면 가시 범위를 교집합으로 축소한다
  // (`stamp_member_visibility(is_new_member=False)`, 복구 경로 없음). 표시를 넓힌 것이
  // 데이터 축소로 이어지면 안 된다. cid 는 서버가 already_member 일 때만 준다.
  function openJoinedConversation(cid) {
    window.location.href = cid ? `/?conversation=${encodeURIComponent(String(cid))}` : "/";
  }

  // 참여(join) 버튼 노출 여부 — 로그인 + 링크가 참여 허용(joinable) 이면 노출한다.
  // already_member 는 **관여하지 않는다**: 소유자·기존 멤버에게 버튼이 사라지던 것이
  // 이번 수정의 대상이다(위 render 주석 참조). viewer.joinable 이 없는 구버전 응답에서는
  // can_join 만 보아 종전 동작으로 폴백한다.
  function shouldShowJoin(viewer) {
    const v = viewer || {};
    return Boolean(v.is_authenticated && (v.can_join || v.joinable));
  }

  // 공유 뷰 액션(참여·fork·로그인)의 표시 토글 + 클릭 배선. render() 는 버전 페이징
  // (pageBranchShare) 으로 재호출되므로 ① 조건이 거짓이 된 경우 다시 숨기고(종전엔
  // remove 만 해서 상태가 눌어붙었다) ② 리스너는 dataset 마커로 1 회만 부착한다
  // (종전엔 재렌더마다 중복 부착되어 클릭 1회에 doJoin/doFork 가 여러 번 발사됐다).
  function wireShareAction(el, visible, onClick) {
    if (!el) return;
    el.classList.toggle("hidden", !visible);
    if (!visible || !onClick || el.dataset.shareWired === "1") return;
    el.dataset.shareWired = "1";
    el.addEventListener("click", onClick);
  }

  // feature-0019 shared-readonly-paging: 공유 뷰에서도 편집된 user 메시지의 버전을 < n/m > 로
  // 읽기전용 열람. 서버가 sibling_ids/version_number/version_count 를 공유 window 내로 scoped 부착
  // (범위 밖 버전은 카운트·존재 비노출). active_leaf 미변경 — 조회만.
  function buildShareBranchPager(msg, tok) {
    const pager = document.createElement("div");
    pager.className = "share-branch-pager";
    const cur = Number(msg.version_number || 1);
    const total = Number(msg.version_count || 1);
    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "share-branch-pager-btn";
    prev.textContent = "‹";
    prev.disabled = cur <= 1;
    prev.setAttribute("aria-label", "이전 버전");
    prev.addEventListener("click", (ev) => { ev.stopPropagation(); pageBranchShare(tok, msg, -1); });
    const label = document.createElement("span");
    label.className = "share-branch-pager-label";
    label.textContent = `${cur} / ${total}`;
    const next = document.createElement("button");
    next.type = "button";
    next.className = "share-branch-pager-btn";
    next.textContent = "›";
    next.disabled = cur >= total;
    next.setAttribute("aria-label", "다음 버전");
    next.addEventListener("click", (ev) => { ev.stopPropagation(); pageBranchShare(tok, msg, 1); });
    pager.append(prev, label, next);
    return pager;
  }

  function pageBranchShare(tok, msg, direction) {
    const sibs = Array.isArray(msg.sibling_ids) ? msg.sibling_ids : [];
    const cur = Number(msg.version_number || 1);
    const nextIdx = (cur - 1) + direction;
    if (nextIdx < 0 || nextIdx >= sibs.length) return;
    // feature-0019 paging-scroll-preserve: 공유 뷰(문서 스크롤)도 페이징 재렌더 시 위치를 보존한다.
    // render() 가 #shareMessages 를 통째로 교체하므로 그대로 두면 스크롤이 튄다. 저장 후 rAF 로 복원.
    // 진입 bottom-pin 이 아직 활성이면(진입 직후 페이징) 여기의 위치 보존이 우선하도록 해제한다.
    releaseShareBottomPin();
    const savedY = window.scrollY || window.pageYOffset || 0;
    fetchShare(tok, sibs[nextIdx])
      .then((data) => {
        render(data, tok);
        requestAnimationFrame(() => {
          const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
          window.scrollTo(0, Math.min(savedY, maxY));
        });
      })
      .catch((err) => showError(err && err.message ? err.message : "버전 전환에 실패했습니다."));
  }

  function renderMessage(msg, idx, tok) {
    const row = document.createElement("article");
    const role = msg && msg.role === "user" ? "user" : "assistant";
    row.className = `share-message share-message-${role}`;
    // point rail 점프용 안정 anchor — 렌더 순서 index 기반(공유 메시지 id 유무와 무관).
    if (idx != null) {
      row.id = `share-msg-${idx}`;
      row.dataset.idx = String(idx);
    }

    const meta = document.createElement("div");
    meta.className = "share-message-meta";
    const badge = document.createElement("span");
    badge.className = `share-role-badge share-role-${role}`;
    // share-sender-nickname: user 는 메시지별 발신자명(닉네임), assistant 는 종전 역할 라벨.
    // textContent 라 사용자명이 마크업으로 해석되지 않는다(XSS 차단).
    badge.textContent = senderLabel(msg);
    // 긴 사용자명은 배지 폭을 CSS 로 제한(ellipsis)하므로 **실제로 잘렸을 때만** 전체 값을
    // title 로 보존한다. 무조건 걸면 화면 텍스트와 똑같은 툴팁이 전 말풍선에서 점멸하고
    // AT 에도 같은 문자열이 두 번(이름+설명) 전달된다(§18.8 적대 패널 F-2 반영).
    // 레이아웃 확정 후 판정해야 scrollWidth/clientWidth 가 유효하다.
    _deferOverflowTitle(badge);
    const time = document.createElement("span");
    time.className = "share-message-time";
    time.textContent = formatDateTime(msg.created_at);
    meta.append(badge, time);
    row.appendChild(meta);

    const content = document.createElement("div");
    content.className = "share-message-content";
    renderMarkdownContent(content, msg.content || "");
    row.appendChild(content);

    if (msg.role === "assistant" && msg.meta) {
      const details = renderAssistantDetails(msg.meta);
      if (details) row.appendChild(details);
    }

    // 편집된 user 메시지 버전 페이저(읽기전용).
    if (role === "user" && Number(msg.version_count || 0) > 1) {
      row.appendChild(buildShareBranchPager(msg, tok));
    }

    return row;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 공유 대화 우측 스크롤바 가이드 뱃지(point rail) — 메인 UI(app.js
  // renderMessagePointRail)와 동형 미니맵. 공유 페이지는 window(document) 스크롤이라
  // rail 은 position:fixed 로 뷰포트 우측 전체 높이를 덮고, 각 dot 의 top% 는 "문서 전체
  // 높이 대비 메시지 중심 위치" 비율로 배치한다(미니맵 의미). 클릭 시 EaseOutExpo 로 대상
  // 메시지를 뷰포트 중앙으로 짧게 스크롤한다(REQ-20260629-point-scroll).
  // ─────────────────────────────────────────────────────────────────────────
  let _sharePointRailWired = false;
  let _sharePointRailRaf = 0;

  function setupSharePointRail(messages) {
    const list = Array.isArray(messages) ? messages : [];
    renderSharePointRail(list);
    if (_sharePointRailWired) return; // scroll/resize 리스너는 1 회만 부착.
    _sharePointRailWired = true;
    // dot 의 top% 는 "문서 좌표" 기반이라 스크롤만으로는 불변 → 스크롤 시엔 활성 표시만
    // 갱신하고, 레이아웃 reflow 가 발생하는 resize 에서만 재배치한다. rAF 로 합쳐 과다 호출 방지.
    const onScroll = () => {
      if (_sharePointRailRaf) return;
      _sharePointRailRaf = requestAnimationFrame(() => {
        _sharePointRailRaf = 0;
        highlightSharePoint();
      });
    };
    const onResize = () => {
      layoutSharePointRail();
      highlightSharePoint();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    // 비동기 콘텐츠(markdown 표·mermaid 다이어그램·이미지)가 늦게 렌더되며 메시지 높이가
    // 바뀌면 dot 위치(문서 좌표 비율)도 재계산해야 한다. ResizeObserver 로 추적, 미지원
    // 환경은 알려진 지연 시점 재배치로 폴백한다.
    const messagesEl = document.getElementById("shareMessages");
    if (messagesEl && typeof ResizeObserver !== "undefined") {
      try { new ResizeObserver(() => onResize()).observe(messagesEl); }
      catch (_) { [300, 1000, 2500].forEach((ms) => window.setTimeout(onResize, ms)); }
    } else {
      [300, 1000, 2500].forEach((ms) => window.setTimeout(onResize, ms));
    }
    window.addEventListener("load", onResize);
  }

  function renderSharePointRail(messages) {
    const rail = document.getElementById("sharePointRail");
    if (!rail) return;
    rail.innerHTML = "";
    const list = Array.isArray(messages) ? messages : [];
    // 1 개 이하면 rail 숨김(메인 UI 와 동일 임계).
    if (list.length <= 1) { rail.classList.add("hidden"); return; }
    rail.classList.remove("hidden");
    list.forEach((msg, idx) => {
      const role = msg && msg.role === "user" ? "user" : "assistant";
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = `share-point-dot is-${role}`;
      dot.dataset.idx = String(idx);
      const when = (msg && msg.created_at) ? formatDateTime(msg.created_at) : "";
      // share-sender-nickname: rail 툴팁/aria 도 말풍선 배지와 같은 화자 라벨을 쓴다
      // (한 화면에서 같은 메시지의 화자가 두 이름으로 보이지 않게 — 표기 단일 출처).
      const who = senderLabel(msg);
      const topic = String((msg && msg.content) || "").trim().slice(0, 60).replace(/\s+/g, " ");
      dot.title = [when, who].filter(Boolean).join(" · ") + (topic ? ` · ${topic}` : "");
      dot.setAttribute("aria-label", dot.title);
      dot.addEventListener("click", (ev) => {
        ev.preventDefault();
        const target = document.getElementById(`share-msg-${idx}`);
        if (!target) return;
        // share-point-rail-bars: 막대 내 클릭 y 위치(0=상단~1=하단)를 메시지 [top,bottom] 에
        // 매핑해 그 지점으로 스크롤(메인 뷰 scrollMessagePointToRatio 와 동형). 기존엔 항상 중앙.
        const dotRect = dot.getBoundingClientRect();
        const ratio = dotRect.height > 0
          ? Math.max(0, Math.min(1, (ev.clientY - dotRect.top) / dotRect.height))
          : 0.5;
        scrollShareMessageToRatio(target, ratio);
      });
      rail.appendChild(dot);
    });
    layoutSharePointRail();
    highlightSharePoint();
  }

  function layoutSharePointRail() {
    const rail = document.getElementById("sharePointRail");
    if (!rail) return;
    const dots = rail.querySelectorAll(".share-point-dot");
    if (!dots.length) return;
    const totalHeight = Math.max(1, document.documentElement.scrollHeight);
    const scrollY = window.scrollY || window.pageYOffset || 0;
    dots.forEach((dot) => {
      const el = document.getElementById(`share-msg-${dot.dataset.idx}`);
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const topInDoc = rect.top + scrollY;       // 뷰포트 좌표 → 문서 좌표.
      // share-point-rail-bars: 메인 뷰와 동일하게 각 뱃지를 메시지 실 스크롤 범위 비례 세로
      // 막대로 배치(기존 중심점 top%-only → top%+height%). 긴 메시지=긴 막대라 rail 이 대화
      // 세로 미니맵이 된다(공유 페이지는 window/문서 좌표 기준).
      const topPct = Math.max(0, Math.min(100, (topInDoc / totalHeight) * 100));
      const heightPct = Math.max(0, Math.min(100 - topPct, (rect.height / totalHeight) * 100));
      dot.style.top = `${topPct}%`;
      dot.style.height = `${heightPct}%`;
    });
  }

  function highlightSharePoint() {
    const rail = document.getElementById("sharePointRail");
    if (!rail) return;
    const midpoint = window.innerHeight / 2;       // 뷰포트 중앙(좌표계: 뷰포트).
    let closestIdx = null;
    let closestDist = Infinity;
    rail.querySelectorAll(".share-point-dot").forEach((dot) => {
      const el = document.getElementById(`share-msg-${dot.dataset.idx}`);
      if (!el) return;
      const r = el.getBoundingClientRect();
      const center = r.top + r.height / 2;
      const dist = Math.abs(center - midpoint);
      if (dist < closestDist) { closestDist = dist; closestIdx = dot.dataset.idx; }
    });
    rail.querySelectorAll(".share-point-dot").forEach((dot) => {
      dot.classList.toggle("is-active", String(dot.dataset.idx) === String(closestIdx));
    });
  }

  // EaseOutExpo 윈도우 스크롤 — 대상 메시지를 뷰포트 중앙으로 짧게 이동.
  // native scrollIntoView(behavior:smooth, 브라우저 임의 duration) 대비 단축 + 명시 easing.
  const SHARE_POINT_SCROLL_DURATION_MS = 280;
  function shareEaseOutExpo(t) {
    return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }
  function sharePrefersReducedMotion() {
    try { return Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
    catch (_) { return false; }
  }
  function scrollShareMessageIntoCenter(target) {
    if (!target) return;
    // rail 점프는 사용자가 명시적으로 특정 메시지로 이동하려는 조작이므로 진입 pin 해제.
    releaseShareBottomPin();
    const rect = target.getBoundingClientRect();
    const currentY = window.scrollY || window.pageYOffset || 0;
    const topInDoc = rect.top + currentY;
    const dest = topInDoc - (window.innerHeight - rect.height) / 2;
    const maxY = Math.max(0, (document.documentElement.scrollHeight || 0) - window.innerHeight);
    const to = Math.max(0, Math.min(maxY, dest));
    const delta = to - currentY;
    if (delta === 0) return;
    if (sharePrefersReducedMotion()) { window.scrollTo(0, to); return; }
    const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : null;
    if (t0 == null) { window.scrollTo(0, to); return; } // performance.now 부재 폴백.
    function step(now) {
      const p = Math.min(1, (now - t0) / SHARE_POINT_SCROLL_DURATION_MS);
      window.scrollTo(0, currentY + delta * shareEaseOutExpo(p));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // share-point-rail-bars: 대상 메시지의 세로 범위 내 ratio(0=상단~1=하단) 지점을 뷰포트
  // 중앙으로 EaseOutExpo 스크롤한다. rail 막대 클릭 위치 비례 이동에 쓰인다
  // (scrollShareMessageIntoCenter 는 항상 메시지 중앙 — 다른 진입 재사용 대비 유지).
  function scrollShareMessageToRatio(target, ratio) {
    if (!target) return;
    releaseShareBottomPin();
    const r = Math.max(0, Math.min(1, Number(ratio)));
    const rect = target.getBoundingClientRect();
    const currentY = window.scrollY || window.pageYOffset || 0;
    const topInDoc = rect.top + currentY;
    const pointInDoc = topInDoc + rect.height * r;
    const dest = pointInDoc - window.innerHeight / 2;
    const maxY = Math.max(0, (document.documentElement.scrollHeight || 0) - window.innerHeight);
    const to = Math.max(0, Math.min(maxY, dest));
    const delta = to - currentY;
    if (delta === 0) return;
    if (sharePrefersReducedMotion()) { window.scrollTo(0, to); return; }
    const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : null;
    if (t0 == null) { window.scrollTo(0, to); return; } // performance.now 부재 폴백.
    function step(now) {
      const p = Math.min(1, (now - t0) / SHARE_POINT_SCROLL_DURATION_MS);
      window.scrollTo(0, currentY + delta * shareEaseOutExpo(p));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 진입 시 초기 스크롤 위치 — 대화의 최신(맨 아래) 메시지가 보이도록 문서 스크롤을
  // 맨 아래로 둔다(메신저·채팅 UI 관례: 진입 시 마지막 대화부터 보기). 마크다운 표·
  // mermaid 다이어그램·외부 이미지·point rail 은 비동기로 늦게 렌더되며 문서 높이가
  // 커지므로, 사용자가 아직 조작하지 않았다면 콘텐츠 안정 시점마다 다시 맨 아래로
  // 고정한다(setupSharePointRail 의 지연 재배치와 동형). "안정"은 고정 시간이 아니라
  // 성장 신호(ResizeObserver·img load)마다 리셋되는 settle 타이머로 판정하고, 절대
  // 상한(ceiling)으로 무한 pin 을 막는다 — 느린 mermaid/이미지가 상한 안에 끝나면
  // 무거운 대화도 확실히 맨 아래로 안착한다. 사용자가 스크롤(휠/터치/스크롤-의도 키)
  // 하거나 컨트롤에 focus(Tab/클릭) 하거나 버전 페이징·rail 점프 등 명시적 조작을 하면
  // 즉시 pin 을 해제해 자동 스크롤이 사용자 조작과 싸우지 않게 한다. pageBranchShare
  // (스크롤 위치 보존)와 scrollShareMessageIntoCenter(rail 점프)는 진입 pin 을 명시
  // 해제한다.
  // ─────────────────────────────────────────────────────────────────────────
  const SHARE_BOTTOM_PIN_SETTLE_MS = 600;   // 성장이 멈춘 뒤 이만큼 지나면 해제.
  const SHARE_BOTTOM_PIN_CEILING_MS = 8000; // 성장이 안 멈춰도 이 상한에서 강제 해제.
  let _shareBottomPinActive = false;
  let _shareBottomPinObserver = null;
  let _shareBottomPinImgHandler = null;
  let _shareBottomPinSettleTimer = 0;
  let _shareBottomPinCeilingTimer = 0;

  function scrollShareToBottom() {
    const maxY = Math.max(0, (document.documentElement.scrollHeight || 0) - window.innerHeight);
    window.scrollTo(0, maxY);
  }

  // 스크롤 의도 키에서만 해제(Tab·수식키 과다 트리거 방지 — focus 는 focusin 이 담당).
  function onShareBottomPinKeydown(ev) {
    switch (ev && ev.key) {
      case "ArrowUp": case "ArrowDown": case "PageUp": case "PageDown":
      case "Home": case "End": case " ": case "Spacebar":
        releaseShareBottomPin();
    }
  }

  function releaseShareBottomPin() {
    if (!_shareBottomPinActive) return;
    _shareBottomPinActive = false;
    window.removeEventListener("wheel", releaseShareBottomPin);
    window.removeEventListener("touchstart", releaseShareBottomPin);
    window.removeEventListener("keydown", onShareBottomPinKeydown);
    window.removeEventListener("focusin", releaseShareBottomPin);
    if (_shareBottomPinObserver) {
      try { _shareBottomPinObserver.disconnect(); } catch (_) {}
      _shareBottomPinObserver = null;
    }
    if (_shareBottomPinImgHandler) {
      const el = document.getElementById("shareMessages");
      if (el) el.removeEventListener("load", _shareBottomPinImgHandler, true);
      _shareBottomPinImgHandler = null;
    }
    if (_shareBottomPinSettleTimer) { clearTimeout(_shareBottomPinSettleTimer); _shareBottomPinSettleTimer = 0; }
    if (_shareBottomPinCeilingTimer) { clearTimeout(_shareBottomPinCeilingTimer); _shareBottomPinCeilingTimer = 0; }
  }

  function engageInitialBottomPin() {
    _shareBottomPinActive = true;
    scrollShareToBottom();

    // 사용자 조작 시 즉시 pin 해제: 스크롤 제스처(휠/터치)·스크롤 의도 키·컨트롤 focus.
    window.addEventListener("wheel", releaseShareBottomPin, { passive: true });
    window.addEventListener("touchstart", releaseShareBottomPin, { passive: true });
    window.addEventListener("keydown", onShareBottomPinKeydown);
    window.addEventListener("focusin", releaseShareBottomPin);

    // 성장이 멈춘 뒤 settle_ms 지나면 해제. 성장 신호마다 리셋한다.
    const armSettle = () => {
      if (!_shareBottomPinActive) return;
      if (_shareBottomPinSettleTimer) clearTimeout(_shareBottomPinSettleTimer);
      _shareBottomPinSettleTimer = window.setTimeout(releaseShareBottomPin, SHARE_BOTTOM_PIN_SETTLE_MS);
    };
    // 늦게 렌더되는 콘텐츠(표·mermaid·이미지)로 문서 높이가 커지는 동안, 아직 사용자가
    // 조작하지 않았다면 다시 맨 아래로 고정하고 settle 타이머를 리셋한다.
    const repin = () => {
      if (!_shareBottomPinActive) return;
      scrollShareToBottom();
      armSettle();
    };
    const messagesEl = document.getElementById("shareMessages");
    if (messagesEl && typeof ResizeObserver !== "undefined") {
      try {
        _shareBottomPinObserver = new ResizeObserver(repin);
        _shareBottomPinObserver.observe(messagesEl); // observe 즉시 1회 콜백 → 초기 arm.
      } catch (_) {
        [150, 400, 1000, 2500].forEach((ms) => window.setTimeout(repin, ms));
      }
    } else {
      // ResizeObserver 미지원 환경: 알려진 지연 시점 재고정(point rail 과 동일 임계).
      [150, 400, 1000, 2500].forEach((ms) => window.setTimeout(repin, ms));
    }
    // 외부 이미지는 intrinsic size 가 없어 늦게 로드되며 문서를 늘린다 — 로드 시 재고정
    // (load 는 버블하지 않으므로 capture 로 컨테이너에서 포착).
    if (messagesEl) {
      _shareBottomPinImgHandler = (ev) => {
        const t = ev && ev.target;
        if (t && t.tagName === "IMG") repin();
      };
      messagesEl.addEventListener("load", _shareBottomPinImgHandler, true);
    }

    // settle 최초 arm + 절대 상한(성장이 안 멈춰도 무한 pin 방지).
    armSettle();
    _shareBottomPinCeilingTimer = window.setTimeout(releaseShareBottomPin, SHARE_BOTTOM_PIN_CEILING_MS);
  }

  // 메시지 본문을 markdown → HTML 로 렌더한다. 메인 UI(app.js markdownToHtml)와
  // 동일 파이프라인(marked.parse → DOMPurify.sanitize)을 사용해 표·코드블록·리스트·
  // 제목·강조·링크가 그대로 가시화되도록 한다. 라이브러리 부재 시 평문으로 폴백.
  //
  // 본문 내 ```sql 코드블록은 메인 UI 와 동일하게 항상 펼쳐 표시한다.
  // (이전의 "쿼리 보기/닫기" 열고닫기 토글은 의도된 기능이 아니었음 — 실행된
  //  쿼리 사이의 전환은 renderAssistantDetails 의 SQL navigator 가 담당한다.)
  // TASK-0256: ```diff 코드 블록을 라인별 +/- span 으로 재구성 (app.js 와 동일 파이프라인).
  function diffLineClass(line) {
    // +++/--- 는 뒤에 공백+경로(git 파일 헤더)일 때만 meta — 내용이 "---" 인
    // 삭제 라인 회색 오분류 방지(REV-0256 MINOR).
    if (/^(diff |index |new file|deleted file|rename )/.test(line)) return "diff-meta";
    if (/^(\+\+\+|---)\s/.test(line)) return "diff-meta";
    if (line.startsWith("@@")) return "diff-hunk";
    if (line.startsWith("+")) return "diff-add";
    if (line.startsWith("-")) return "diff-del";
    return "diff-ctx";
  }

  // @@ -a,b +c,d @@ 헌크 헤더에서 old/new 시작 줄번호 추출. 없으면 null.
  function parseDiffHunkHeader(line) {
    const m = /^@@\s*-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s*@@/.exec(line);
    return m ? { oldStart: parseInt(m[1], 10), newStart: parseInt(m[2], 10) } : null;
  }

  // 맨 앞 마커(+/-/공백) 1글자 + 뒤따르는 공백 1개 제거 — 복사 시 순수 코드만 남김.
  function stripDiffMarker(line) {
    let s = line;
    if (s[0] === "+" || s[0] === "-" || s[0] === " ") s = s.slice(1);
    if (s[0] === " ") s = s.slice(1);
    return s;
  }

  // 각 줄을 {cls, mark, code, oldNo, newNo} 로 분해 — GitHub 식 양쪽 줄번호.
  function buildDiffRows(lines) {
    let oldNo = 1;
    let newNo = 1;
    return lines.map((line) => {
      const cls = diffLineClass(line);
      if (cls === "diff-hunk") {
        const h = parseDiffHunkHeader(line);
        if (h) { oldNo = h.oldStart; newNo = h.newStart; }
        return { cls, mark: "", code: line, oldNo: "", newNo: "" };
      }
      if (cls === "diff-meta") {
        return { cls, mark: "", code: line, oldNo: "", newNo: "" };
      }
      if (cls === "diff-add") {
        return { cls, mark: "+", code: stripDiffMarker(line), oldNo: "", newNo: newNo++ };
      }
      if (cls === "diff-del") {
        return { cls, mark: "-", code: stripDiffMarker(line), oldNo: oldNo++, newNo: "" };
      }
      // context — 모델이 첨부 줄번호 prefix(`<N>→`)를 ```diff context 줄로 흘려보낸 경우를
      // 정규화한다(app.js buildDiffRows 와 동일 로직 — 공유 대화 뷰도 같은 누출을 본다). prefix
      // 를 떼어 순수 코드만 남기고, 떼어낸 실제 소스 줄번호로 gutter 를 동기화. clean diff 는
      // 미매칭 → 무변경(회귀 0).
      const leakedNo = /^\s*(\d+)→/.exec(line);
      if (leakedNo) {
        oldNo = newNo = parseInt(leakedNo[1], 10);
        return { cls, mark: " ", code: line.slice(leakedNo[0].length), oldNo: oldNo++, newNo: newNo++ };
      }
      return { cls, mark: " ", code: stripDiffMarker(line), oldNo: oldNo++, newNo: newNo++ };
    });
  }

  function enhanceDiffBlocks(html) {
    // 줄번호 + +/- 마커는 data-gutter → CSS ::before content 로만 렌더(의사요소라 복사 비포함).
    // 코드는 마커 제거 후 textContent 로만 넣어 복사 시 순수 코드만 잡힘(XSS 무첨가, DOMPurify 최종).
    if (typeof document === "undefined") return html;
    try {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      const blocks = tpl.content.querySelectorAll("pre > code.language-diff");
      if (!blocks.length) return html;
      const NB = "\u00a0"; // NBSP — gutter 정렬용
      blocks.forEach((codeEl) => {
        const raw = (codeEl.textContent || "").replace(/\n$/, "");
        const rows = buildDiffRows(raw.split("\n"));
        let maxNo = 1;
        rows.forEach((r) => {
          if (r.oldNo) maxNo = Math.max(maxNo, r.oldNo);
          if (r.newNo) maxNo = Math.max(maxNo, r.newNo);
        });
        const w = String(maxNo).length;
        const padNo = (v) => {
          const s = v === "" || v == null ? "" : String(v);
          return NB.repeat(Math.max(0, w - s.length)) + s;
        };
        const sqlMode = looksLikeSql(raw); // SQL diff 만 라인 코드 토큰 하이라이트(비-SQL diff 는 평문 유지)
        codeEl.textContent = "";
        rows.forEach((r) => {
          const span = document.createElement("span");
          span.className = "diff-line " + r.cls;
          span.setAttribute(
            "data-gutter",
            padNo(r.oldNo) + NB + padNo(r.newNo) + NB + (r.mark || NB)
          );
          // 내용 라인(add/del/ctx)만 토큰화 — hunk(@@)·meta 라인 고유색 유지(§18.8 리뷰 MINOR).
          const tokenize = sqlMode && r.code.length &&
            (r.cls === "diff-add" || r.cls === "diff-del" || r.cls === "diff-ctx");
          if (tokenize) {
            span.appendChild(sqlTokenizeToFragment(r.code)); // 토큰 span textContent-only(XSS 무첨가)
          } else {
            span.textContent = r.code.length ? r.code : " ";
          }
          codeEl.appendChild(span);
        });
        const pre = codeEl.closest("pre");
        if (pre) {
          pre.classList.add("diff-block");
          if (sqlMode) pre.classList.add("diff-sql");
          pre.style.setProperty("--diff-gutter-ch", String(2 * w + 3));
        }
      });
      return tpl.innerHTML;
    } catch (_) {
      return html;
    }
  }

  function enhanceAttachmentEditBlocks(html) {
    // ★ TASK-0286: ```attachment-edit 코드 블록(전체 수정본 본문)을 "📎 수정된 첨부 파일" 안내로
    // 치환 — 공유 화면에서도 전체 본문 텍스트를 노출하지 않는다(app.js 와 동형 안전망).
    if (typeof document === "undefined") return html;
    if (!html || html.indexOf("language-attachment-edit") === -1) return html;
    try {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      const blocks = tpl.content.querySelectorAll("pre > code.language-attachment-edit");
      if (!blocks.length) return html;
      blocks.forEach((codeEl) => {
        const raw = codeEl.textContent || "";
        let fname = "";
        const firstLine = (raw.split("\n", 1)[0] || "").trim();
        try { fname = String((JSON.parse(firstLine) || {}).filename || ""); } catch (_) {}
        const note = document.createElement("div");
        note.className = "attachment-edit-note";
        note.textContent = "📎 수정된 첨부 파일" + (fname ? ` (${fname})` : "");
        const pre = codeEl.closest("pre");
        (pre || codeEl).replaceWith(note);
      });
      return tpl.innerHTML;
    } catch (_) {
      return html;
    }
  }

  // ```sql 코드블록 구문 하이라이트 — app.js enhanceSqlBlocks 의 로컬 복제(share 번들 단독 로드,
  // diff/attachment 헬퍼와 동일 패턴). 외부 하이라이터 없이 경량 토크나이저 → <span class="sql-tok-*">.
  // 토큰 텍스트는 textContent 로만 넣어 XSS 무첨가(이후 DOMPurify 가 span+class 만 통과).
  const SQL_HL_LANGS = new Set([
    "sql", "mysql", "mariadb", "postgresql", "postgres", "pgsql", "plpgsql",
    "plsql", "tsql", "sqlite", "oracle", "mssql",
  ]);
  const SQL_HL_KEYWORDS = new Set([
    "SELECT","FROM","WHERE","AND","OR","NOT","NULL","IS","IN","LIKE","ILIKE",
    "RLIKE","REGEXP","BETWEEN","EXISTS","ANY","SOME","JOIN","INNER","LEFT",
    "RIGHT","FULL","OUTER","CROSS","NATURAL","ON","USING","GROUP","BY","ORDER",
    "HAVING","LIMIT","OFFSET","UNION","INTERSECT","EXCEPT","MINUS","ALL",
    "DISTINCT","AS","INSERT","INTO","VALUES","UPDATE","SET","DELETE","CREATE",
    "ALTER","DROP","TRUNCATE","TABLE","VIEW","MATERIALIZED","INDEX","SEQUENCE",
    "TRIGGER","DATABASE","SCHEMA","WITH","RECURSIVE","CASE","WHEN","THEN","ELSE",
    "END","ASC","DESC","NULLS","FIRST","LAST","PRIMARY","KEY","FOREIGN",
    "REFERENCES","CONSTRAINT","UNIQUE","CHECK","DEFAULT","AUTO_INCREMENT",
    "IDENTITY","ENGINE","PROCEDURE","FUNCTION","RETURNS","RETURN","DECLARE",
    "BEGIN","IF","ELSEIF","WHILE","LOOP","FOR","CALL","EXEC","EXECUTE","GRANT",
    "REVOKE","COMMIT","ROLLBACK","SAVEPOINT","TRANSACTION","START","EXPLAIN",
    "ANALYZE","DESCRIBE","SHOW","USE","ADD","COLUMN","MODIFY","CHANGE","RENAME",
    "TO","CASCADE","RESTRICT","TEMPORARY","TEMP","REPLACE","IGNORE","PARTITION",
    "OVER","WINDOW","ROWS","RANGE","UNBOUNDED","PRECEDING","FOLLOWING","CURRENT",
    "ROW","TOP","FETCH","NEXT","ONLY","LATERAL","PIVOT","UNPIVOT","MERGE",
    "MATCHED","OUTPUT","GO","ESCAPE","COLLATE","INTERVAL","TRUE","FALSE",
    "UNKNOWN","PRINT","INTO","SEPARATOR","STRAIGHT_JOIN","FORCE","LOCK","UNLOCK",
  ]);
  const SQL_HL_TYPES = new Set([
    "INT","INTEGER","BIGINT","SMALLINT","TINYINT","MEDIUMINT","DECIMAL","NUMERIC",
    "FLOAT","DOUBLE","REAL","BIT","BOOLEAN","BOOL","CHAR","VARCHAR","NCHAR",
    "NVARCHAR","VARCHAR2","TEXT","TINYTEXT","MEDIUMTEXT","LONGTEXT","NTEXT",
    "DATE","DATETIME","DATETIME2","SMALLDATETIME","TIMESTAMP","TIME","YEAR",
    "BLOB","TINYBLOB","MEDIUMBLOB","LONGBLOB","BINARY","VARBINARY","JSON","JSONB",
    "UUID","SERIAL","BIGSERIAL","MONEY","ENUM","GEOMETRY","XML","CLOB","NUMBER",
    "UNSIGNED","ZEROFILL",
  ]);

  function sqlTokenizeToFragment(text) {
    const RE = /(\/\*[\s\S]*?\*\/|--[^\n]*)|('[^']*(?:''[^']*)*'|"[^"]*(?:""[^"]*)*")|(`[^`]*(?:``[^`]*)*`)|(@{0,2}[A-Za-z_][A-Za-z0-9_$]*)|(0[xX][0-9A-Fa-f]+|\d+\.?\d*(?:[eE][+-]?\d+)?)|(\s+)|([\s\S])/g;
    const frag = document.createDocumentFragment();
    let pending = "";
    const flush = () => { if (pending) { frag.appendChild(document.createTextNode(pending)); pending = ""; } };
    const span = (cls, s) => {
      flush();
      const el = document.createElement("span");
      el.className = cls;
      el.textContent = s;
      frag.appendChild(el);
    };
    let m;
    while ((m = RE.exec(text)) !== null) {
      if (m[1]) span("sql-tok-comment", m[1]);
      else if (m[2]) span("sql-tok-string", m[2]);
      else if (m[3]) pending += m[3];
      else if (m[4]) {
        const w = m[4];
        if (w[0] === "@") span("sql-tok-var", w);
        else {
          const W = w.toUpperCase();
          if (SQL_HL_KEYWORDS.has(W)) span("sql-tok-keyword", w);
          else if (SQL_HL_TYPES.has(W)) span("sql-tok-type", w);
          else if (/^\s*\(/.test(text.slice(RE.lastIndex))) span("sql-tok-func", w);
          else pending += w;
        }
      }
      else if (m[5]) span("sql-tok-number", m[5]);
      else pending += m[0];
    }
    flush();
    return frag;
  }

  function highlightSqlInto(codeEl, raw) {
    const text = String(raw || "").replace(/\n$/, "");
    codeEl.textContent = "";
    codeEl.appendChild(sqlTokenizeToFragment(text));
  }

  // diff 내용이 SQL 로 보이는지 판정 — app.js looksLikeSql 과 동일(실제 SQL statement 모양 앵커,
  // import…from·.create()/.delete() 코드 관용구 오탐 방지, <select> 태그 lookbehind 배제).
  function looksLikeSql(text) {
    return /(?<![<\/])\bSELECT\b[\s\S]{0,3000}?\bFROM\b/i.test(text)
        || /\bINSERT\s+INTO\b/i.test(text)
        || /\bUPDATE\s+[`"\[\w.]+[\s\S]{0,2000}?\bSET\b/i.test(text)
        || /\bDELETE\s+FROM\b/i.test(text)
        || /\b(CREATE|ALTER|DROP)\s+(OR\s+REPLACE\s+)?(TEMP(ORARY)?\s+)?(TABLE|VIEW|INDEX|DATABASE|SCHEMA|PROCEDURE|FUNCTION|TRIGGER|SEQUENCE|MATERIALIZED)\b/i.test(text)
        || /\bTRUNCATE\s+(TABLE\s+)?[`"\[\w.]/i.test(text)
        || /\bMERGE\s+INTO\b/i.test(text)
        || /\b(GRANT|REVOKE)\b[\s\S]{0,200}?\bON\b/i.test(text)
        || /\bWITH\s+[`"\w]+\s+AS\s*\(/i.test(text);
  }

  function enhanceSqlBlocks(html) {
    if (typeof document === "undefined") return html;
    if (!html || html.indexOf("language-") === -1) return html;
    try {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      let touched = false;
      tpl.content.querySelectorAll("pre > code[class*='language-']").forEach((codeEl) => {
        const mlang = /(?:^|\s)language-([A-Za-z0-9_+-]+)/.exec(codeEl.className || "");
        if (!mlang || !SQL_HL_LANGS.has(mlang[1].toLowerCase())) return;
        const raw = codeEl.textContent || "";
        if (!raw.trim()) return;
        highlightSqlInto(codeEl, raw);
        const pre = codeEl.closest("pre");
        if (pre) pre.classList.add("sql-block");
        touched = true;
      });
      return touched ? tpl.innerHTML : html;
    } catch (_) {
      return html;
    }
  }

  function csvDownloadFilename() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    const ts = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(
      d.getHours()
    )}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    return `result_${ts}.csv`;
  }

  // conv-audit (csv-inline-no-download): 공유 대화 뷰도 메인 UI 와 동일하게 인라인 ```csv 블록에
  // 다운로드 버튼을 붙인다. 공유 뷰에서 CSV 텍스트는 이미 본문에 가시화되어 있으므로(복사 가능),
  // 화면에 보이는 그 텍스트를 클라이언트 Blob 으로 저장하는 것은 새로운 데이터 노출이 아니다.
  // (서버 파일 /api/file 및 step csv_paths 는 공유 redaction 대상 — 여기선 손대지 않는다.)
  function enhanceCsvBlockDownloads(target) {
    if (typeof document === "undefined" || !target) return;
    const blocks = target.querySelectorAll("pre > code.language-csv");
    blocks.forEach((codeEl) => {
      const pre = codeEl.closest("pre");
      if (!pre || pre.dataset.csvDownloadReady === "1") return;
      const csvText = (codeEl.textContent || "").replace(/\s+$/, "");
      if (!csvText.trim()) return;
      // 백엔드 _collapse_large_csv_blocks 가 대형 블록을 미리보기로 접고 전체 파일 /api/file
      // 링크를 바로 뒤에 주입한 경우, 절단된 미리보기에 다운로드 버튼을 붙이면 일부 행만
      // 받는 오해를 준다 → 버튼 skip(app.js enhanceCsvBlockDownloads 와 동일 가드).
      const nextEl = pre.nextElementSibling;
      if (nextEl && nextEl.querySelector && nextEl.querySelector('a[href*="/api/file?"]')) {
        pre.dataset.csvDownloadReady = "1";
        return;
      }
      pre.dataset.csvDownloadReady = "1";
      // 기존 구조화 결과 다운로드 버튼(.share-csv-download-btn)과 동일 스타일 재사용.
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "share-csv-download-btn";
      btn.textContent = "📥 CSV 다운로드";
      btn.title = "위 CSV 데이터를 파일로 저장합니다";
      btn.addEventListener("click", () => {
        try {
          const blob = new Blob(["\uFEFF" + csvText + "\n"], {
            type: "text/csv;charset=utf-8;",
          });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = csvDownloadFilename();
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1500);
        } catch (_) {
          /* best-effort */
        }
      });
      pre.parentNode.insertBefore(btn, pre.nextSibling);
    });
  }

  function renderMarkdownContent(target, text) {
    const source = String(text || "").trim();
    if (!source) {
      target.textContent = "";
      return;
    }
    if (window.marked && window.DOMPurify) {
      // feature-0013 후속: 공유 대화도 메인 UI 와 동일하게 ```mermaid 를 다이어그램으로 렌더.
      // mermaid-render.js(공용) 의 enhanceMermaidBlocks 로 sanitize 이전 텍스트 치환 → DOMPurify →
      // innerHTML 이후 라이브 DOM 에서 strict-mode SVG 렌더. mermaid-render.js 미로드 시 안전 폴백(원문 유지).
      const enhanceMmd =
        typeof window.enhanceMermaidBlocks === "function" ? window.enhanceMermaidBlocks : (h) => h;
      target.innerHTML = window.DOMPurify.sanitize(
        enhanceMmd(enhanceAttachmentEditBlocks(enhanceSqlBlocks(enhanceDiffBlocks(window.marked.parse(source)))))
      );
      markExternalLinks(target);
      enhanceCsvBlockDownloads(target);
      if (typeof window.renderMermaidDiagrams === "function") window.renderMermaidDiagrams(target);
    } else {
      // 폴백: 라이브러리 로드 실패 시 줄바꿈 보존 평문 (share.css .share-content-plain).
      target.classList.add("share-content-plain");
      target.textContent = source;
    }
  }

  // 본문 내 외부 링크는 새 탭 + noopener 로 — 익명 공유 페이지의 안전한 이동.
  function markExternalLinks(target) {
    target.querySelectorAll("a[href]").forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer nofollow");
    });
  }

  function renderAssistantDetails(meta) {
    if (!meta || typeof meta !== "object") return null;
    const container = document.createElement("div");
    container.className = "share-message-details";

    // 1순위: meta.steps 의 execute_sql 단계 — 메인 UI 와 동일하게 "실행된 쿼리"
    // 단위로 묶어 표시한다. 한 답변에 여러 쿼리가 실행됐다면 결과셋에 따라 쿼리를
    // 전환하는 navigator(◀ ▶)로 보여준다 (열고닫기 토글이 아님 — 사용자 의도).
    const steps = Array.isArray(meta.steps) ? meta.steps : [];
    const sqlSteps = steps.filter(
      (s) => s && String(s.tool || "") === "execute_sql" && s.sql,
    );
    if (sqlSteps.length > 0) {
      if (sqlSteps.length === 1) {
        container.appendChild(buildSqlStepPanel(sqlSteps[0]));
      } else {
        container.appendChild(buildSqlNavigator(sqlSteps));
      }
      return container;
    }

    // 폴백: steps 가 없는 구형 메시지 — 기존 final_sql / result_rows 단일 필드.
    let hasAny = false;

    const finalSql = meta.final_sql || meta.sql || "";
    if (finalSql) {
      const pre = document.createElement("pre");
      pre.className = "share-sql";
      pre.textContent = String(finalSql);
      container.appendChild(pre);
      hasAny = true;
    }

    const rows = Array.isArray(meta.result_rows) ? meta.result_rows : null;
    if (rows && rows.length > 0) {
      const table = renderResultTable(rows);
      if (table) {
        container.appendChild(table);
        const dlBtn = document.createElement("button");
        dlBtn.type = "button";
        dlBtn.className = "share-csv-download-btn";
        dlBtn.textContent = "CSV 다운로드";
        dlBtn.addEventListener("click", () => downloadRowsAsCsv(rows, "result.csv"));
        container.appendChild(dlBtn);
        hasAny = true;
      }
    }

    return hasAny ? container : null;
  }

  // 단일 execute_sql 단계를 SQL 블록 + (있으면) 결과 미리보기 표로 렌더.
  // 메인 UI(app.js buildSqlStepPanel)의 share 전용 read-only 이식판이다.
  function buildSqlStepPanel(step) {
    const panel = document.createElement("div");
    panel.className = "share-sql-group";

    // 근거 — 메인 UI 와 일관되게 쿼리 위에 수행 이유를 명시(있을 때만).
    const reason = String((step && step.reason) || "").trim();
    if (reason) {
      const reasonEl = document.createElement("div");
      reasonEl.className = "share-step-reason";
      const reasonLabel = document.createElement("span");
      reasonLabel.className = "share-step-reason-label";
      reasonLabel.textContent = "근거";
      const reasonText = document.createElement("span");
      reasonText.className = "share-step-reason-text";
      reasonText.textContent = reason;
      reasonEl.append(reasonLabel, reasonText);
      panel.appendChild(reasonEl);
    }

    // SQL 문 — 항상 펼쳐 표시.
    if (step.sql) {
      const pre = document.createElement("pre");
      pre.className = "share-sql";
      pre.textContent = formatSqlForDisplay(step.sql);
      panel.appendChild(pre);
    }

    // 결과 미리보기 표 — result_summary.preview_table 가 있을 때만.
    const rs = step.result_summary;
    if (rs && typeof rs === "object") {
      const pt = rs.preview_table;
      if (pt && Array.isArray(pt.columns) && pt.columns.length) {
        const table = buildPreviewTable(pt);
        if (table) panel.appendChild(table);
      }
    }

    return panel;
  }

  // 여러 execute_sql 단계를 ◀ ▶ 로 전환하는 navigator. 결과셋(쿼리)별 패널을
  // 모두 만들어 두고 활성 인덱스만 노출한다 (메인 UI buildSqlNavigator 이식).
  function buildSqlNavigator(sqlSteps) {
    const root = document.createElement("div");
    root.className = "share-sql-navigator";
    root.setAttribute("tabindex", "0");
    root.setAttribute("role", "group");
    root.setAttribute("aria-label", "SQL 쿼리 결과 탐색");

    const header = document.createElement("div");
    header.className = "share-sql-nav-header";

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "share-sql-nav-btn";
    prevBtn.innerHTML = "&#9664;";
    prevBtn.setAttribute("aria-label", "이전 쿼리");
    prevBtn.title = "이전 쿼리 (←)";

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "share-sql-nav-btn";
    nextBtn.innerHTML = "&#9654;";
    nextBtn.setAttribute("aria-label", "다음 쿼리");
    nextBtn.title = "다음 쿼리 (→)";

    const indicator = document.createElement("span");
    indicator.className = "share-sql-nav-indicator";
    indicator.setAttribute("aria-live", "polite");

    const context = document.createElement("span");
    context.className = "share-sql-nav-context";

    header.append(prevBtn, indicator, nextBtn, context);
    root.appendChild(header);

    const panels = document.createElement("div");
    panels.className = "share-sql-nav-panels";
    root.appendChild(panels);

    const panelEls = sqlSteps.map((step) => {
      const p = buildSqlStepPanel(step);
      p.className += " share-sql-nav-panel";
      panels.appendChild(p);
      return p;
    });

    let activeIdx = 0;
    // 결과셋마다 높이가 달라 ◀▶ 전환 시 panels 컨테이너가 줄었다 늘었다 하며
    // 아래 콘텐츠가 점프한다. 지금까지 본 최대 패널 높이를 floor 로 박아
    // 짧은 결과셋으로 전환해도 컨테이너가 줄지 않게 한다(확장 높이 보존).
    let maxPanelHeight = 0;
    function preserveHeight() {
      const h = panels.scrollHeight;
      if (h > maxPanelHeight) {
        maxPanelHeight = h;
        panels.style.minHeight = maxPanelHeight + "px";
      }
    }
    function update() {
      // 전환 직전, 현재 보이는(나가는) 패널 높이를 먼저 기록한다.
      // 초기 update() 는 아직 DOM 에 붙기 전이라 scrollHeight=0 → floor 무변(무해).
      preserveHeight();
      panelEls.forEach((el, i) => {
        el.classList.toggle("is-active", i === activeIdx);
      });
      indicator.textContent = `쿼리 ${activeIdx + 1}/${sqlSteps.length}`;
      const step = sqlSteps[activeIdx] || {};
      const ref = extractFirstTableRef(step.sql);
      context.textContent = ref ? `대상: ${ref}` : "";
      prevBtn.disabled = activeIdx <= 0;
      nextBtn.disabled = activeIdx >= sqlSteps.length - 1;
      // 들어오는 패널이 더 크면 floor 를 키운다(축소만 방지, 확장은 허용).
      preserveHeight();
    }
    function go(delta) {
      const next = Math.min(Math.max(activeIdx + delta, 0), sqlSteps.length - 1);
      if (next !== activeIdx) {
        activeIdx = next;
        update();
      }
    }
    function goTo(idx) {
      const next = Math.min(Math.max(idx, 0), sqlSteps.length - 1);
      if (next !== activeIdx) {
        activeIdx = next;
        update();
      }
    }

    prevBtn.addEventListener("click", (evt) => {
      evt.preventDefault();
      go(-1);
      root.focus();
    });
    nextBtn.addEventListener("click", (evt) => {
      evt.preventDefault();
      go(1);
      root.focus();
    });
    root.addEventListener("keydown", (evt) => {
      const target = evt.target;
      if (target && target !== root && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
        return;
      }
      if (evt.key === "ArrowLeft") {
        evt.preventDefault();
        go(-1);
      } else if (evt.key === "ArrowRight") {
        evt.preventDefault();
        go(1);
      } else if (evt.key === "Home") {
        evt.preventDefault();
        goTo(0);
      } else if (evt.key === "End") {
        evt.preventDefault();
        goTo(sqlSteps.length - 1);
      }
    });

    update();
    return root;
  }

  // result_summary.preview_table({columns, rows[][], truncated}) → read-only 표.
  // 메인 UI buildResultTable 과 동일한 컬럼/행 모델(배열의 배열)을 받는다.
  function buildPreviewTable(previewTable) {
    const columns = Array.isArray(previewTable.columns) ? previewTable.columns : [];
    const rows = Array.isArray(previewTable.rows) ? previewTable.rows : [];
    const truncated = Boolean(previewTable.truncated);
    if (!columns.length) return null;

    const wrap = document.createElement("div");
    wrap.className = "share-result-table-wrap";

    const table = document.createElement("table");
    table.className = "share-result-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = String(col);
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((_, ci) => {
        const td = document.createElement("td");
        const val = Array.isArray(row) ? row[ci] : undefined;
        td.textContent = val == null ? "" : String(val);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);

    const meta = document.createElement("div");
    meta.className = "share-result-table-meta";
    const shown = rows.length;
    meta.textContent = truncated
      ? `${shown}행 표시 중 (더 있음) · ${columns.length}열`
      : `${shown}행 · ${columns.length}열`;
    wrap.appendChild(meta);

    return wrap;
  }

  // 한 줄 SQL 을 주요 키워드 앞에서 줄바꿈해 가독성을 높인다(메인 UI 이식).
  // 문자열/식별자 리터럴 내부는 보존한다.
  function formatSqlForDisplay(raw) {
    const src = String(raw || "").trim();
    if (!src) return "";
    if (/\n/.test(src)) return src;

    const literals = [];
    const literalRe = /('([^'\\]|\\.|'')*'|"([^"\\]|\\.|"")*"|`[^`]*`)/g;
    const masked = src.replace(literalRe, (m) => {
      literals.push(m);
      return `${literals.length - 1}`;
    });

    const keywordAlt = SQL_FORMAT_KEYWORDS.map((k) => k.replace(/ /g, "\\s+")).join("|");
    const pattern = new RegExp(`\\s+(?=\\b(?:${keywordAlt})\\b)`, "gi");
    let formatted = masked.replace(pattern, "\n");

    formatted = formatted.replace(/(\d+)/g, (_, i) => literals[Number(i)]);
    return formatted;
  }

  // 첫 테이블 참조(schema.table)를 추출해 navigator context 라벨에 쓴다.
  function extractFirstTableRef(sql) {
    const match = String(sql || "").match(
      /(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?/i,
    );
    return match ? `${match[1]}.${match[2]}` : "";
  }

  function renderResultTable(rows) {
    if (!rows.length) return null;
    const first = rows[0];
    if (!first || typeof first !== "object") return null;
    const headers = Object.keys(first);
    if (headers.length === 0) return null;

    const table = document.createElement("table");
    table.className = "share-result-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headers.forEach((h) => {
      const th = document.createElement("th");
      th.textContent = h;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      headers.forEach((h) => {
        const td = document.createElement("td");
        const val = row[h];
        td.textContent = val == null ? "" : String(val);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    return table;
  }

  function downloadRowsAsCsv(rows, filename) {
    if (!rows || !rows.length) return;
    const headers = Object.keys(rows[0] || {});
    const escape = (v) => {
      const s = v == null ? "" : String(v);
      return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [headers.map(escape).join(",")];
    rows.forEach((row) => lines.push(headers.map((h) => escape(row[h])).join(",")));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "result.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function doJoin(tok, btn) {
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.textContent = "참여 중...";
    try {
      const res = await fetch(`/api/share/${encodeURIComponent(tok)}/join`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const errMsg = body && body.error ? body.error : `참여 실패 (${res.status})`;
        window.alert(errMsg);
        btn.disabled = false;
        btn.textContent = originalLabel;
        return;
      }
      const body = await res.json();
      const cid = body && body.conversation_id ? body.conversation_id : "";
      window.location.href = cid ? `/?conversation=${encodeURIComponent(cid)}` : "/";
    } catch (e) {
      window.alert(`참여 실패: ${e && e.message ? e.message : e}`);
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  }

  async function doFork(tok, btn) {
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.textContent = "fork 중...";
    try {
      const res = await fetch(`/api/public/share/${encodeURIComponent(tok)}/fork`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const errMsg = body && body.error ? body.error : `fork 실패 (${res.status})`;
        window.alert(errMsg);
        btn.disabled = false;
        btn.textContent = originalLabel;
        return;
      }
      const body = await res.json();
      window.alert(`내 계정에 fork 됐습니다. (${body.copied}개 메시지 복제) 메인 페이지로 이동합니다.`);
      window.location.href = "/";
    } catch (e) {
      window.alert(`fork 실패: ${e && e.message ? e.message : e}`);
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  }

  function roleLabel(role) {
    if (role === "user") return "사용자";
    if (role === "assistant") return "어시스턴트";
    return role || "메시지";
  }

  // share-sender-nickname: 공유 뷰의 user 말풍선 화자 라벨을 **메시지별 발신자**로 해석한다.
  // 종전엔 role 만 보고 전원 "사용자" 로 고정돼, 여러 참여자가 발화한 그룹 대화를 공유하면
  // 누가 무엇을 말했는지 링크 수신자가 구분할 수 없었다(사용자 보고).
  //
  // **지배 규칙: 발화 시점에 각인된 사실일 때만 사람 이름을 쓴다.** 공유 링크는 전달되는
  // 증거물이고 익명 뷰어는 오귀속을 교정할 맥락이 전혀 없으므로, 확신이 없으면 이름 대신
  // 익명 토큰을 쓴다(§18.8 적대 패널 F-1/F-2 반영).
  //   0) meta.attribution_inferred === true → **이름 사용 금지**. fork/제품전환 보정이
  //      사후에 채운 추론값이다(`_conv_copy_messages` 가 미각인 행에 원본 대화 owner 를
  //      기입하며 이 플래그를 남긴다). 그 행의 실제 발신자는 다른 멤버였을 수 있다.
  //      각인 없는 행과 동일하게 아래 3)~4) 로 내려보낸다.
  //   1) meta.sender_username  — 발화 시점 각인된 실제 발신자명.
  //   2) `사용자 <id>`          — id 만 각인된 경우(표시명 조회 실패분). 이름을 모를 뿐
  //                              발신자가 소유자와 다르다는 것은 알고 있으므로 소유자명으로
  //                              폴백하지 않는다(확정적 오귀속 차단 — app.js 와 동일 근거).
  //   3) 대화 소유자명           — 각인이 전혀 없는 메시지 중 **1:1 대화로 확인된 경우만**.
  //                              1:1 은 발신자 = 소유자이고 소유자명은 이미 헤더에
  //                              "소유자 X" 로 노출돼 있어 새 식별자를 더하지 않는다.
  //                              **그룹(또는 판별 불가)이면 쓰지 않는다** — 각인 도입
  //                              (feature-0009 gc-ask-sender-attrib) 이전 legacy 그룹 행은
  //                              발신자가 owner 가 아닐 수 있어 소유자명이 오귀속이 된다.
  //   4) "사용자"               — 위 어디에도 해당 없을 때의 최종 폴백(종전 동작).
  // 익명 열람자에게도 동일 적용(사용자 결정 2026-08-06). 값 자체는 이전부터
  // /api/public/share/{token} 응답의 meta 에 실려 나가고 있었고, 본 변경은 그 값을
  // 화면에 쓰는 표시 계층 수정이다(노출 경계는 SECURITY.md §21.7).
  // share-sender-nickname: 배지가 CSS ellipsis 로 **실제 잘렸을 때만** title 을 건다.
  // 렌더 직후엔 아직 레이아웃이 없어 scrollWidth/clientWidth 가 0 이므로 rAF 로 미룬다
  // (rAF 미지원·비가시 환경이면 조용히 skip — title 은 보조 수단이라 없어도 기능 손실 없음).
  function _deferOverflowTitle(el) {
    if (!el) return;
    const apply = () => {
      try {
        if (el.scrollWidth > el.clientWidth + 1) el.title = el.textContent || "";
        else el.removeAttribute("title");
      } catch (e) { /* 레이아웃 접근 실패는 무시 */ }
    };
    if (typeof window.requestAnimationFrame === "function") window.requestAnimationFrame(apply);
    else setTimeout(apply, 0);
  }

  function senderLabel(msg) {
    if (!msg || msg.role !== "user") return roleLabel(msg && msg.role);
    const meta = (msg && msg.meta) || {};
    // 0) 사후 추론 각인은 사실이 아니다 — 이름·id 둘 다 쓰지 않는다.
    if (meta.attribution_inferred !== true) {
      const uname = typeof meta.sender_username === "string" ? meta.sender_username.trim() : "";
      if (uname) return uname;
      const sid = Number(meta.sender_account_id || 0);
      if (Number.isFinite(sid) && sid > 0) return `사용자 ${sid}`;
    }
    if (!_shareIsGroup && _shareOwnerUsername) return _shareOwnerUsername;
    return roleLabel("user");
  }

  function formatDateTime(ts) {
    if (!ts) return "";
    try {
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return String(ts);
      return d.toLocaleString("ko-KR");
    } catch (e) {
      return String(ts);
    }
  }

  function showError(msg) {
    const main = document.getElementById("shareMessages");
    if (main) {
      main.innerHTML = "";
      const div = document.createElement("div");
      div.className = "share-error";
      div.textContent = msg;
      main.appendChild(div);
    }
  }
})();

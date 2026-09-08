---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: security,ux,qa
timestamp: 2026-09-08T15:00:00+09:00
trigger: 3R 수렴 확인 — 랜딩 차단급 결함이 남아 있는가
verdict: BLOCK (3라운드) → 조치 완료
round: 3
---

# 3라운드 — 수렴 확인

「지금 랜딩해도 되는가」만 물었다. 답은 **아니오** 였고, HIGH 2건이 **둘 다 2R 조치가 만든
회귀**였다. 세 스위트(jsdom 81 · headless 16 · native 전건)를 전부 재현해 **초록임을 확인한
상태에서** 실행으로 재현됐다는 점이 이 라운드의 요지다 — 초록은 커버리지의 증거가 아니다.

## 1. Blocking issues

### H1 [HIGH] allow-list 가 앱 창의 좌표를 «첫 이동» 에서 영구히 잃게 만든다

- Evidence: 정본 `client-bridge.js` 를 jsdom 실엔진에 두 번 적재해 같은 탭을 흉내낸 재현 —
  ① `/share/tok?client_port=41234&client_nonce=<32자 실규격>` → `bridge` 는 잡히지만
  `sessionStorage=null`, 좌표는 `replaceState` 로 주소에서 삭제. ② 같은 탭이
  `/?conversation=77` 로 이동 → `bridge=null` → **앱 창이 자기를 «평범한 브라우저» 로 판정**.
  대조군(앱이 `/` 로 열리는 종전 경로)은 ②에서도 좌표가 살아 있다.
  이동은 가정이 아니라 **이 cycle 이 만든 유일한 출구**다: `doJoin` 성공 → `/?conversation=…`,
  `doFork` 성공 → `/`, `openJoinedConversation` → `/?conversation=…`.
- Location: `static/app/client-bridge.js`(`_PERSIST_SURFACES`) ↔ `static/share.js`(세 출구)
- Reason: allow-list 는 「좌표를 심을 수 있는 표면」을 올바르게 좁혔지만 **앱이 스스로 연
  목적지에서 좌표를 다음 화면으로 운반하는 축을 설계하지 않았다.** 좌표는 앱 창의 유일한
  자격이라, 잃는 순간 `connect-modal` 의 네 가드가 전부 반대로 넘어간다 — 앱 창 안에서
  「DQA 앱 받기」가 그려지고, 결정적으로 `_fireScheme` 의 `if (clientBridge) return false` 가
  무력화되어 **앱 창이 자기 자신에게 딥링크를 쏜다**. 그 함수의 docstring 이 기술한
  2026-09-07 사용자 제보 결함(「이 사이트에서 DQAConnect.exe 를 열려고 합니다」 승인창)이
  그대로 재현되는 조건이며, 발동 조건은 **한 번이라도 러너를 연결한 사용자 전원**이다.
  세션 내 복구 수단도 없다(트레이 [창 열기]는 `request_show(home,"/")` 뿐).
- Action: 좌표 운반 축을 **명시적으로** 설계한다. 단순 재부착은 B1 을 되열므로 금지 —
  공격자가 보낸 규격에 맞는 좌표도 같은 경로를 탄다. 성립하는 형태는 «검증 후 보관» 이다.
- **조치 완료**: `_adoptIfTheBridgeAcceptsIt()` — 익명 표면에서 받은 좌표는 그 페이지 한정으로
  즉시 쓰되(`ephemeral`), 그 좌표가 가리키는 브리지에 `ping` 을 쏘아 **수용될 때만** 보관한다.
  공격자 nonce 는 브리지가 `403 nonce` 로 거부하고(`compare_digest`), 공격자 포트는 연결
  자체가 실패한다. 즉 **앱이 연 창만 통과**한다. 뮤턴트 2종(배선 제거 · 검증 없이 보관)으로
  봉인 확인.

### H2 [HIGH] 로그인 링크 제거로 «열화» 3분기 전부에서 미로그인 진입이 0개

- Evidence: 배포 자산을 jsdom 에 올려 실제 가시성 측정 — ① 미로그인 × 앱 창 안 ② 미로그인 ×
  `download_url:null` ③ 미로그인 × macOS **셋 다** `링크 복사` 하나만 VISIBLE 이고
  `getElementById("shareLoginLink") === null`. 2R 이 이것을 이연한 근거(「로그인만 되살려도
  누를 버튼이 없다」)는 **하네스 자신의 ⑩ 이 반증한다** — 열화 분기에서 join/fork 를 가르는
  유일한 조건은 플랫폼이 아니라 `is_authenticated` 다.
- Location: `static/share.html`(삭제된 `shareLoginLink`) · `static/share.js`
- Reason: 열화를 **앱링크·받을곳·플랫폼** 세 축으로만 설계하고 **인증 축**을 빠뜨렸다. 열화의
  목적이 「종전 웹 경로를 살려 둔다」인데 그 경로의 미로그인 진입점만 함께 지운 것이라
  **열화가 스스로의 목적을 배반한다.** 대상 인구도 주변부가 아니다 — `_share_client_entry`
  docstring 이 「대개 로그인하지 않은 상태로 처음 연다」, `appPlatformSupported` 주석이
  「macOS·Linux·모바일 수신자가 흔하다」라 적고, 그 교집합이 바로 이 화면이다. 내장 WebView2
  껍데기는 시스템 브라우저와 **세션을 공유하지 않으므로** ①은 실제 상태다.
- Action: 링크를 되살리되 **열화 분기에서만** 노출한다(앱 전용 분기에서는 종전 결정대로 감춘다).
  하네스에 `ANON` 축을 같은 표에 추가한다 — 이 결함이 81건 전건 통과 속에 남은 직접 원인이
  그 누락이다.
- **조치 완료**: `wireShareAction(loginLink, directActions && !viewer.is_authenticated, null)` +
  **2차원 표**(열화 4분기 × 미로그인/로그인 후). 뮤턴트로 봉인 확인.

## 2. Cross-domain concerns — 전건 조치

- **C1 [MED] busy 타이머와 재렌더 경합** — 클릭이 라벨·`disabled` 를 걸어 둔 2.5초 사이 재렌더가
  라벨만 되돌려 **「정상 라벨 + 죽은 버튼」**이 된다(실행 재현). → `render` 가 busy 중 라벨
  대입을 건너뛴다(한 주인이 소유). 회귀 ⑤d.
- **C2 [MED] 안내문을 켜기만 하고 끄지 않는다** — 재렌더로 앱 진입이 사라져도 「참여·fork 는
  앱에서 합니다」가 남아 되살아난 웹 버튼 옆에서 서로를 반증한다. → `wireShareAction` 과 같은
  규약으로 **토글**(단 클릭 후 상태 문구는 유지). 회귀 ⑨.
- **C3 [MED] 인쇄 회귀에 가드가 없다** — 방금 고친 것이 다음 변경에서 무방비. → **T10** 신설
  (4폭 × `emulate_media("print")` → `padding-bottom == 0`). 뮤턴트(`!important` 제거)로 봉인 확인.
- **C4 [LOW] 딥링크 `base` 가 Host 헤더 파생** — `TrustedHostMiddleware` + 이번에 추가한
  동봉값 대조 두 완화가 서 있음을 리뷰어가 확인. **이연**(공개 base 설정값 고정은 별도 판단).
- **C5 [LOW] 하네스가 커밋된 증적 PNG 를 덮어쓴다** → `--evidence` 플래그 뒤로 옮기고, 이
  cycle 이 덮어쓴 2026-07-27 증적 3장을 **원복**했다.

## 3. Challenge to current spec (리뷰어 요지 — 기록)

> **H1 과 H2 는 같은 뿌리에서 나온다 — 이 cycle 은 «상태» 를 «한 페이지의 사실» 로 다뤘다.**
> 화면 하나를 새 진입점으로 만들면서 그 화면이 쓰는 두 값(브리지 좌표 · 로그인 여부)을 모두
> 그 페이지 안에서만 유효하게 설계했다. 그런데 이 진입점의 정의상 사용자는 **여기서 끝나지
> 않는다** — join·fork·로그인 셋 다 다음 화면으로 가는 동작이다. 「진입점을 만들었으나 진입
> 이후를 설계하지 않았다」가 두 HIGH 의 공통 형태다.
>
> 검증 설계에도 같은 비대칭이 있다. 세 하네스가 **축 하나를 고정하고 다른 축을 훑는** 방식이라
> (`AUTHED` 고정 × 플랫폼, 단일 페이지 × pathname) 두 축이 교차하는 칸이 통째로 비어 있었고,
> 두 HIGH 는 정확히 그 빈칸에 살았다.

이 진단을 조치에 반영했다 — 좌표는 «검증 후» 세션으로 올라가고(페이지가 아니라 세션이 정본),
하네스는 **2차원 표**(열화 × 인증, 좌표 × 이동 후)로 바꿨다.

## 4. 이연 (3R 리뷰어가 «유지 동의» 한 8건 + 이번 라운드 C4·C5)

2R artifact §이연의 8건은 그대로 유지한다. 근거 분류(리뷰어 정리):
- **(a) 이 cycle 이 만들지 않았고 범위가 클라이언트 신뢰 모델 전체**: `server.json` 미인증 ·
  mtime 시계 전진·symlink · `/static/*.html` 이중 pathname · `ai-connect.js` 좌표 사본 ·
  `verify_side_panel_exclusive.mjs` C3(main 동일 선재).
- **(b) 근본 해소가 이미 별도 cycle 로 지정됨**: 브라우저 명령줄·방문 기록의 공유 토큰
  (H1 의 «IPC 로 목적지 전달» 과 **같은 뿌리라 함께 다루면 효율적**) · 스킴 하이재킹 노출 빈도.
- **(c) 관측 개선이지 결함 아님**: 열화 모드가 로그·속성에 남지 않는다 — 다만 **H2 가 열화
  분기에서 났다는 사실이 이 항목의 우선순위를 한 칸 올린다**(리뷰어 부기).
- 이번 라운드 추가: **C4**(공개 base 설정값 고정) · **C5** 는 조치 완료.

## 리뷰어가 «성립 확인» 한 것 (재현 근거)

B1 극성 반전은 경로 6종에서 저장 없음이 실엔진으로 확인된다. C1 모양 검사는 정상값을 거부하지
않는다 — 실 nonce 는 32자 URL-safe 이고 검사식 안에 있으며, `panel_url` 이 좌표 키를 제거 후
마지막 두 개로 재부착하므로 순서 검사와 정확히 일치한다. `compactFooterForNarrow` 는
`wireShareAction` 의 1회 부착 계약과 충돌하지 않는다(`onClick=null`·`dataset` 보존·부모 비교로
멱등). B2·B3·C2·§3(3)·§3(4)·F1·F3 도 성립 확인.

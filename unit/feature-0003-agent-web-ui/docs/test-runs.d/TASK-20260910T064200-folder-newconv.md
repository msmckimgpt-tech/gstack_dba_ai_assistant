---
run_at: 2026-09-10T15:45:00+09:00
session: ai/claude/feature-0024-folder-newconv-trigger
scope: 좌측 대화목록 폴더 행 — '···'(메뉴) → '📝'(이 폴더에서 새 대화) 대체 · 폴더 관리 메뉴 우클릭 이관
verdict: PASS (행위 하네스) / 라이브·DQA 앱 Run 은 배포 후 append
---

# TASK-20260910T064200-folder-newconv — 검증 기록

## Run 1 — 행위 하네스 (jsdom)

```text
Environment: Node
Result: PASS
Build: worktree ai/claude/feature-0024-folder-newconv-trigger (배포 전) · base d4fee180
Scenario: 배포되는 `app/sidebar.js`·`app.js`·`app/composer.js` **원문**을 jsdom realm 에
  주입해 구동. 판정 계열(beginPendingConversation·_hasSelectionWithin·isOwnConversation·
  isGroupConversation·_assignNewConversationToFolder)은 stub 이 아니라 정본 소스를 추출해
  넣었다 — stub 이면 하네스가 계약을 vacuous 하게 통과시킨다.
  축 8종: ①'📝' 트리거 존재·구 '···' 부재 ②클릭 → pendingFolderId=그 폴더 + 헤더 접힘
  토글로 버블 안 됨 + 접힌 폴더 펼침 ③헤더 우클릭 → 폴더 메뉴 4항목 보존 + 커서 좌표 앵커
  ④키보드 컨텍스트 메뉴(좌표 0,0) → rect 폴백 ⑤pending 대화(draft·in-flight)의 폴더/최상위
  배타 분배 + 들여쓰기 + 폴더 소멸 시 최상위 폴백 ⑥conversation.create 미보유 시 트리거 미생성
  ⑦인자 없는 '+ 새 대화' 는 폴더 목표를 비움 ⑧cid 확정 시 PATCH /api/conversations/{cid}/folder
Evidence: `node unit/feature-0003-agent-web-ui/tests/verify_folder_newconv_trigger.mjs`
  → 총 **77건 PASS 77 / FAIL 0**
  ※ 최초 58건이었다. 적대 리뷰(ux)가 **이 하네스의 사각지대**를 지적했다 — `openFloatingMenu` 를
    stub 으로 둔 탓에 정본이 트리거에 기입하는 `is-open`/`aria-expanded` 가 재현되지 않아, 폴더
    헤더의 `aria-expanded`(=접힘 상태)를 메뉴가 덮어쓰는 접근성 회귀를 **58건 전부 초록인 채로**
    통과시키고 있었다. stub 을 폐기하고 `openFloatingMenu`·`closeFloatingMenus`·`makeMenuItem`
    **정본을 realm 에 주입**하도록 재작성했고(메뉴 관찰도 실제 DOM `#folderMenu` 로 전환),
    회귀 가드 5종을 추가해 77건이 됐다.
판별력(역검증): 뮤턴트 7종 **전부 KILL** — 각각 적용 후 재실행해 실패를 확인하고 복원했다.
  M1 `_CTX_MENU_TARGETS` 에 폴더 헤더 재삽입(우클릭이 새 대화를 만드는 회귀) → 1 FAIL
  M2 클릭 핸들러의 `stopPropagation()` 제거(폴더가 접히는 회귀)              → 2 FAIL
  M3 `startFolderConversation` 의 폴더 펼침 제거                              → 1 FAIL
  M4 pending entry 가 `folder_id` 를 안 들고 감                               → 1 FAIL
  M5 루트/폴더 분배 필터 무력화(중복 렌더 회귀)                               → 2 FAIL
  M6 early-cid 경로의 폴더 배정 호출 누락                                     → 1 FAIL
  M7 버튼 표시를 '···' 로 되돌림                                              → 1 FAIL
  ── 적대 리뷰 반영분의 가드(누적 12종) ──
  M8  `ownsAriaExpanded:false` 제거(메뉴가 폴더 aria-expanded 강탈)            → 4 FAIL
  M9  `closeFloatingMenus` 의 `.is-menu-open` 정리 제거(상태 박제)             → 2 FAIL
  M10 pending 을 다시 하위 폴더 재귀 뒤로(화면 밖 밀림)                        → 1 FAIL
  M11 헤더 title(우클릭 안내) 제거                                             → 1 FAIL
  M12 메뉴의 '이 폴더에서 새 대화' 항목 제거(hover 없는 입력수단 폴백 소멸)     → 1 FAIL
  복원 후 재실행 77 PASS / 0 FAIL.
회귀: 프론트 `tests/verify_*.mjs` 전수 실행 — **변경 전(baseline) 실패 17건과 동일**,
  신규 실패 0건. 새 테스트는 baseline 에서 FAIL → 변경 후 PASS(같은 전수 실행으로 확인).
  ※ baseline 17건은 이 변경 이전부터 실패하던 선재 결함이며 본 cycle 범위가 아니다.
  `verify_sidebar_reorder_anim.mjs` 1건만 내 변경으로 새로 깨졌는데, 원인은 그 테스트가
  import 목록의 **줄 배치**(`_prefersReducedMotion,` 이 마지막 줄)에 결합돼 있었던 것이라
  계약(모션 게이트를 app.js 정본에서 import)을 순서 무관으로 고쳤다 — 판별력은 유지
  (그 심볼을 import 에서 빼면 여전히 FAIL). 수정 후 160 PASS / 0 FAIL.
  `verify_sidebar_inline_rename.mjs` 의 «폴더 메뉴 순서» 단언도 갱신했다 — 우클릭 메뉴에
  '이 폴더에서 새 대화' 를 추가했기 때문이며, 그 테스트가 지키는 계약(ctxmenu-order-parity:
  첫=이름 변경 / 끝=설정)은 그대로 성립한다(같은 파일의 다음 두 단언이 그 규칙 자체를 잠근다).
  수정 후 80 PASS / 0 FAIL.
미검증: jsdom 은 실제 렌더 픽셀·이모지 폰트 메트릭·우클릭 네이티브 동작을 모형화한다.
  폴더 행의 시각 정렬(§16.6 픽셀-클래스)과 실제 클릭→전송→폴더 배정 왕복은 아래 Run 이 잰다.
```

## Run 2 — 실제 DQA 클라이언트 (배포 전 시점)

```text
Environment: DQA-client
Result: NOT-RUN
Build: worktree ai/claude/feature-0024-folder-newconv-trigger (아직 배포 전 — 실행 중인 앱은 옛 자산)
Scenario: 폴더 행 '📝' 클릭 → 그 폴더 안 '새 대화 (작성 중)' · 헤더 우클릭 → 관리 메뉴 4항목 ·
  첫 메시지 전송 후 생성 대화가 그 폴더에 배정
Reason: ① 이 시점의 라이브 자산은 아직 변경 전이라 앱에서 변경을 관측할 수 없다.
  ② 이 앱에는 CDP 등 자동화 진입점이 없다(`client/window.py` 에 remote-debugging 인자 부재 —
     9222/9223/9333/9229 스캔 결과 열린 포트 0).
  ③ 사용자의 DQA 앱이 실행 중이며(`DQAConnect.exe` PID 12344), §16.6 「기존 사용자 앱·연결을
     검증 편의로 종료하지 않는다」에 따라 종료·조작하지 않았다.
Alternative: Run 1(jsdom, 배포 파일 원문 구동) 58건 PASS + 뮤턴트 7종 KILL.
Next: 배포 후 ① 라이브 Windows Chrome(같은 Chromium 엔진, 로그인 세션)으로
  `tests/pb0008_folder_newconv.py` 실측 ② 실행 중인 DQA 앱 창을 `PrintWindow` 로 수동 관측
  (조작·종료 없음) — 두 결과를 이 파일에 append 한다.
```

## Run 3 — 라이브 실측, 실 Windows Chrome (보조 호환 검증, 배포 후 append)

```text
Environment: Windows-browser (라이브 서비스)
Result: PASS
Build: 서버 release=413151c5 (`/healthz` git_commit) · asset_stamp=e468c1bf1e49 (두 replica 일치) ·
  `bin/deploy-web.sh --web-only` soak PASS · Chrome/152.0.7977.83 · 전용 프로파일 `win-browser-cdp`
  (세션 bootstrap_admin/admin, 자기 생성 표면 한정)
Scenario / Evidence — `tests/pb0008_folder_newconv.py`, 총 21건 PASS 21 / FAIL 0:
  F1  폴더 행에 `.conv-folder-newconv-trigger` 존재 · textContent="📝" · aria-label="새 대화 시작"
      · role=button · tabindex=0 · 구 `.conv-folder-menu-trigger` **부재** · 행 높이 27px ·
      폴더명 말줄임 없음(nameEllipsized=0)
  F2  '📝' 클릭 → 옵션 메뉴 **안 열림** · '새 대화 (작성 중)' 행이 **그 폴더 안**(A=1 draft=2 nextHdr=3)
      · 들여쓰기 paddingLeft=22px · 클릭으로 폴더가 접히지 않음
  F3  폴더 헤더 **우클릭** → `#folderMenu` 열림(folderId 일치), 항목
      `["이름 변경","이 폴더에서 새 대화","하위 폴더 추가","설정"]` — 관리 기능 보존 확인
  F4  `POST /api/new_conversation` → `PATCH /api/conversations/{cid}/folder` 200 →
      `GET /api/conversations` 의 `folder_id` 가 그 폴더(125). cid=20260910085954-8cbbf464
  F4b 재적재 후 사이드바가 그 대화를 **폴더 A 하위**에 렌더(A=1 conv=2 next=3)
  F5  시각 캡처 `artifacts/feature-0024-folder-newconv/folder-newconv-row.png` —
      폴더 행 우측의 '📝' 가 폴더 아이콘·개수 배지와 같은 baseline 에 정렬, 행 높이 흔들림 없음.
      **판독 결과**: 🗂 와 📝 가 이 환경에서 **둘 다 흑백(텍스트 프레젠테이션)** 으로 해결돼,
      적대 리뷰가 우려한 «흑백 폴더 + 컬러 메모» 혼재는 관측되지 않았다.
  전역 pageerror 0
역검증(`--negative`, 구 '···' 계약으로 재기): F1 핵심 3건 FAIL(트리거 존재·표시=📝·구 트리거 부재)
  — 하네스가 실제로 이 변경을 재고 있다.
테스트 데이터: 본 스크립트가 만든 폴더·대화 전량 삭제(잔여 0 — 정리 로그가 각 id 의 200 을 남긴다).

미검증(정직 표기):
  - **「첫 메시지 전송 → 자동 폴더 배정」 의 프론트 배선은 라이브에서 못 쟀다.** 서버 LLM 폐기
    이후 질의는 DQA 앱의 로컬 브리지로만 가므로, 일반 브라우저에서는 `#promptInput` 이 비활성이다
    (실측: `element is not enabled`). 그래서 F4 는 프론트가 cid 확정 직후 호출하는 **바로 그 배정
    왕복**을 라이브 서버에 대고 쟀고, 「전송이 그 왕복을 부른다」는 배선은 jsdom(case7 + 대화 생성
    3경로 호출 소스 잠금)이 덮는다. 두 사실을 각각 얻었을 뿐 합산 관측은 아니다.
  - 일반 브라우저는 §15.4.1 상 **공유 HTML/CSS/JS 의 보조 검증**이다 — DQA 앱의 창·로그인 저장소·
    로컬 브리지·트레이를 대체하지 않는다.
  - 진입 게이트(client-entry-gate) 때문에 `?client_port=&client_nonce=` 신호를 실어 진입했고,
    연결 모달은 사이드바 클릭을 가로채므로 Escape 로 닫은 뒤 관측했다(제품 상태 변경 없음).
```

## Run 4 — 실행 중인 사용자 DQA 앱 (수동 관측, 조작 없음)

```text
Environment: DQA-client
Result: PASS (관측 범위 한정 — 아래 «확인하지 않은 것» 참조)
Build: 서버 413151c5 배포 직후 · `DQAConnect.exe` PID 34472 (사용자 실행 세션, 미종료)
Scenario: 배포로 새 자산이 나간 뒤 실행 중인 앱이 정상 대화 화면을 유지하는가
Evidence: `PrintWindow` 창 캡처 1936×1176 —
  `artifacts/feature-0024-folder-newconv/dqa-app-after-deploy.png`
  사이드바에 폴더 트리(`_휴지통`·`정리`·`쿼리 리뷰`·`g_mv`·`g_web`·`gz`·`k_dk`·`kr_web`·`DB 작업` …
  중첩 포함)와 대화 목록·본문·작성창이 모두 정상 렌더. 오류 화면·설치 안내로의 이탈 없음.
방법: **수동 관측만** — 앱을 종료·조작·재설치하지 않았고 입력도 넣지 않았다
  (§16.6 「기존 사용자 앱·연결을 검증 편의로 종료하지 않는다」).

확인하지 않은 것 (정직 표기):
  - **폴더 행의 '📝' 트리거는 이 캡처로 확인되지 않는다.** 설계상 평소 `opacity:0` 이고 hover·포커스
    에서만 드러나는데, 그 hover 를 만들려면 사용자 앱에 입력을 넣어야 하므로 하지 않았다.
    같은 자산의 같은 화면은 Run 3 이 실 Chromium 에서 21건으로 실측했다.
  - **이 앱이 이미 새 빌드로 재적재됐는지도 미확인.** 자동 반영은 «안전한 시점»에 적용되므로 아직 옛
    자산일 수 있다. 즉 「앱이 지금 정상」 과 「새 자산이 이 앱에 도달」 은 각각의 사실이며 합산이 아니다.
  - WebView2 고유 축(창 생명주기·로컬 브리지·트레이)은 이번 변경 범위가 아니라 미확인.
```

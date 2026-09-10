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

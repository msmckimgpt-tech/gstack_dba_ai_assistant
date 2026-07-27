---
run_at: 2026-07-27T10:30:00+0900
session: /_template:entry share-edit-usable (feature-0019 공유 대화 메시지 수정 상호작용)
scope: unit/feature-0003-agent-web-ui/src/static/{app.js,styles.css}
verdict: PRE PASS (라이브 실측 진단 + CSS 주입 폭 실증 + 단위 5/5) · POST-DEPLOY Windows-browser 예정
---

### Run (2026-07-27) — share-edit-usable: 공유(그룹) 대화 메시지 텍스트 수정 상호작용 회복 (Minor §12.3 — feature-0003 web/UI, 표시·기하 전용) — **Environment: Windows-browser**

- **사용자 신고**: "공유 대화에서, 사용자의 메세지 텍스트 수정에 대한 상호작용이 진행되지 않음".

- **PRE 진단 — 정상 경로 먼저 반증 (Environment: Windows-browser, `bin/win-browser.py` relay @ Chrome 150, https://localhost/, bootstrap_admin)**:
  공유(그룹) 대화 `20260722015451-d23ad939`(is_group=true·owner=본인)에서
  ① '수정' 버튼 렌더 PASS(`.message-edit-trigger` 1) ② 클릭 → 인라인 편집 UI 열림 PASS(버튼 =
  `[단순 수정, 취소]` — 그룹은 재답변 미노출, ANCHOR INV-4 정합) ③ `POST /messages/1287/edit`
  `mode=simple` → **200 `{ok:true,mode:"simple"}`** + `/api/history` 재조회에서 내용 반영·
  `meta.edited=true` PASS ④ UI 버튼 경로 e2e(hover→'수정'→'단순 수정' 클릭) → 편집 종료 +
  `(편집됨)` 배지 1 PASS ⑤ 백엔드 게이트 무해 프로브(그룹 + `mode=reanswer`) → **400 "그룹 대화는
  단순 수정만 가능합니다"** = 대화 접근·`conversation.ask`·per-message sender IDOR·@assistant 잠금
  게이트를 **모두 통과한 뒤**의 응답. → **API·authz·저장 경로 결함 없음**(신고를 이 축에서 반증).

- **PRE 근본원인 계측 (실사용 불가의 실체 = UI 기하 2건)**:
  - **R1 편집 창 축소**: 말풍선 폭이 content 기반 → `_startInlineEdit` 의 `innerHTML=""` 순간 원문 폭
    소실 → 편집 창이 `.message-edit-box` min-width(240px)로 축소. 실측:
    | 대화 | 편집 전 말풍선 | 편집 후 말풍선 | textarea | 내용 |
    |---|---|---|---|---|
    | 공유(그룹) `d23ad939` | **661px** | **272px** | **240×60px** | **377자** |
    | 1:1 `41496652` | 484px | 303px | 271×60px | 44자 |
    공유 대화는 **단순 수정 전용**(INV-4)이라 "요청사항 수정(재답변)" 우회로도 없다. 추가로 `ta.rows`
    가 개행 수만 세어 줄바꿈 없는 장문이 rows=2 로 고정. evidence/share-edit-usable-baseline.png.
  - **R2 ☰ 메뉴 가림**: user 말풍선에 `.message-actions` 컨테이너 **2개**(☰ 메뉴 + '수정')가 동일
    absolute 좌표(bottom:-28px; right:0)에 겹침 — ☰ rect(1164,512,30×21) ⊂ '수정' rect
    (1154,507,40×26). hover 후 hit-test: **☰ 중심점 → `.message-edit-trigger` 반환**(`same:false`),
    '수정' 중심점 → 자기 자신(`same:true`). ⇒ ☰ 메뉴('여기부터/여기까지 공유'·분기·샘플 등록)
    **영구 클릭 불가**. 공유 대화의 공유 범위 지정 진입도 함께 막혀 있었다.

- **PRE 수정 실증 (배포 전, CSS 주입 + `is-editing` 부여로 라이브 A/B)**: 같은 공유 대화·같은 메시지
  (377자)에서 대화 로그 폭 981px 기준 —
  | | 말풍선 | textarea |
  |---|---|---|
  | baseline(현행 서빙) | 272px | **240px** |
  | 수정 적용 | 918px | **886px (3.7×)** |
  evidence/share-edit-usable-predeploy.png (편집 창이 대화 폭 전체로 확장된 실화면).

- **PRE 단위**: `tests/test_share_edit_usable.py` **5 PASS**(F1 `is-editing` 부여·F2 rows wrap 추정·
  F3 액션 컨테이너 합류·F4 CSS stretch·F5 edit-box width) + `node --check app.js` OK +
  `make test` 회귀 0(잔여 4 실패 = TEST.md 기록된 pre-existing local-env: routine_dbanalysis·
  runtime_settings×2·item11_batch8 — 본 변경 무관, 프론트 정적 자산 전용).

- **Environment: Windows-browser — PRE-COMMIT 서빙본 미수행 사유**: 정적 자산은 이미지에 baked 되어
  merge+deploy 후에만 서빙된다(위 PRE 실증은 브라우저 주입 A/B). ⇒ **POST-DEPLOY PB-0008 실측** 으로
  서빙본 확인.

- **POST-DEPLOY 검증 항목(예정, `src/scenario.share-edit-usable.json`)**:
  ① 공유 대화 user 말풍선 hover 시 `.message-actions` 컨테이너 **1개** + ☰·'수정' **각각 hit-test 도달 가능**
  ② '수정' 클릭 → 행에 `is-editing` + textarea 폭이 baseline 240px 대비 대폭 확장(로그 폭 근접)·rows≥3
  ③ '취소' → 편집 상태 원복(`is-editing` 0·편집 박스 0) ④ pageerror 0.

---

### [POST-DEPLOY 2026-07-27, 배포본 bb66ef16] Environment: Windows-browser (AI 직접 — `bin/win-browser.py` relay, Chrome 150)

- **배포**: PR #950 머지(main **bb66ef16**) → `make deploy-web-only` 무중단 롤링(web-a/web-b 순차
  recreate·`git_commit=bb66ef16` ready·Caddyfile no-drift·90s soak 통과, edge blip 1회 자동 회복).
  `/healthz` = `{"status":"ok","git_commit":"bb66ef16","mysql_ok":true,"pg_ok":true}`.
- **서빙본 확증(curl)**: `app.js?v=1e6cd74df162` 에 `classList.add("is-editing")` 1건 ·
  `:scope > .message-actions` 1건, `styles.css?v=1e6cd74df162` 에 `.message.is-user.is-editing` 1건.
  (content-hash 스탬프 자동 주입 — 구 캐시 자동 무효화.)
- **시나리오**: `unit/feature-0019-message-editing/src/scenario.share-edit-usable.json`
  (codex P2 반영 — 전 수용 조건을 `eval` throw 로 단언, `stop_on_fail` override 없음).
  실행 결과 **`ok:true` · 13 step 전부 PASS**.

| AC | 단언 | 실측 | 판정 |
|---|---|---|---|
| 대상 확정 | cid 일치·is_group·user 메시지·'수정' 버튼 존재 | `d23ad939` / is_group=true / userRows 1 / editTriggers 1 | PASS |
| **AC1** ☰ 가림 해소 | `.message-actions` 컨테이너 == 1 · ☰·'수정' 각각 hit-test 도달 | **actionContainers 1**(수정 전 2) · editReachable **true** · **menuReachable true** | PASS |
| **AC2** 편집창 폭 | `is-editing` 부여 · textarea > 300px · 로그 폭의 60% 이상 · rows ≥ 3 | logWidth 981 · bubble **918** · **textarea 886px**(수정 전 240) · height **165**(수정 전 60) · **rows 7**(수정 전 2) · 377자 · 버튼 `[단순 수정, 취소]`(그룹 재답변 미노출 유지) | PASS |
| **AC3** 취소 원복 | 취소 후 `is-editing`·편집 박스 0 | editing 0 · editBoxes 0 · userRows 1 | PASS |

- **육안**: evidence/share-edit-usable-postdeploy.png — 편집 창이 대화 폭 전체로 확장되고 **377자
  전문이 7행으로 모두 보인다**(수정 전 240px·3행 잘림 대비). 그룹 규칙(단순 수정 전용)·'(편집됨)'
  배지·좌우 정렬 등 기존 UI 계약 불변.
- **Pass/Fail: POST-DEPLOY PB-0008 PASS** — 사용자 신고(공유 대화 메시지 텍스트 수정 상호작용
  미진행) 해소. pageerror 관측 안 됨.

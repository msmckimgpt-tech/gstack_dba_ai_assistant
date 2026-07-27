---
run_at: 2026-07-27T17:30:00+09:00
session: ai/claude/feature-0016-detail-db-groups
scope: [graph-view, detail-panel, db-groups, list-truncation]
verdict: PRE-COMMIT PASS (헤드리스 62/62 · node --check ES module · §18.8 적대 리뷰 2렌즈 흡수) · POST-DEPLOY PB-0008 라이브 PASS (a~g 전건, 2026-07-27 18:5x KST · 배포 66575331)
---

### Run (2026-07-27) — detail-db-groups (상세 패널 관련 노드 목록 DB 단위 접기/펼치기 + "… 외 N건" 생략 제거) — **Environment: Windows-browser (PB-0008 라이브는 배포 후 — 정적 자산이 web 이미지에 baked 되어 pre-commit 시점엔 서빙 불가. pre-deploy de-risk = `node --check --input-type=module` PASS + 신규 헤드리스 `test_detail_dbgroups.js` 62/62 PASS(소스 유닛·호출부 원문 추출 검증) + §18.8 적대 리뷰 2렌즈 BLOCKING 2·MAJOR 8 전량 흡수, visual_verification_scope: always)**

cycle: `ai/claude/feature-0016-detail-db-groups` · 정본 = feature-0016 TASK `## 20260727T1730-detail-db-groups` ·
CHG-20260727T1730-ai-claude-feature-0016-detail-db-groups.

- **변경**: `src/static/graph/graph-ctxmenu.js`(DB 그룹 유닛 신설 + 노드/관계 상세 목록을 DB 구획으로 전환 +
  하드코딩 상한 5종 제거 + 관계 행 바인딩 공통화 + 컬럼 아코디언 lazy + '모두 펼치기' + 상한 고지 배너),
  `graph-state.js`(`panelDbGroupState`), `graph.css`(머리글·본문·컨트롤·배너),
  cross-cut `feature-0002/src/modules/metadata_graph.py`(`neighborhood()` 이웃 상한 도달 시 `truncated` 전파 — additive).
  RBAC/스키마/마이그레이션 0 — 표시 계층 + 절단 고지 신호 한정.

- **PRE-COMMIT — `tests/headless/test_detail_dbgroups.js` 62/62 PASS**
  (소스에서 DB 그룹 유닛 + 호출부 `dirRowsHTML` + 컬럼 lazy 헬퍼 본문을 추출해 의존 test double 주입 —
  사본 아님, 소스와 결합. §18.8 적대 리뷰가 지적한 초판 사각을 흡수한 재작성판):
  1. ① 단일 DB + 짧은 목록(≤60) = 머리글 없는 평면(기존 UX 보존)
  2. ② 다중 DB 라도 총량이 적으면(≤60) **전 그룹 펼침** — 종전보다 덜 보이는 퇴행 차단(리뷰 B1)
  3. ③ self DB 그룹이 없어도 **첫 그룹은 펼침** — 크로스-DB 전용 사용에서 0행이 되지 않음(리뷰 B1)
  4. ④ **절단 부재** — 120건 입력에 `… 외 N건` 미출현 · 머리글 개수 = 총계 · 전량 렌더 · 단일 DB 장문도 머리글 생성
  5. ⑤ 대형 그룹(>300) 기본 접힘 + 초기 0행 + payload 전량 보관(머리글 총계는 정직)
  6. ⑥ 사용자 조작 상태 우선 / 단 **대형 그룹은 성능 가드가 사용자 기록보다 우선**(리뷰 M2)
  7. ⑦ **ROW_CAP 예산은 펼친 그룹만 소비** — 접힌 그룹이 예산을 먹어 펼치면 빈 목록이 되던 무음 실패 차단(리뷰 B2)
  8. ⑧ **'모두 펼치기/접기'** 컨트롤 방출 + 상태별 라벨(리뷰 M3)
  9. ⑨ 스키마 미상 후미(selfDbKey 공백에서도) · 비-스키마 라벨 유령 그룹 가드 · 멀티 scope 동명 DB scope 병기
  10. ⑩ 속성 이스케이프(esc 미지정 기본값도 escaping)
  11. ⑪ 토글 왕복 — lazy 주입 1회·bind 1회·상태 기록·'모두' 라벨 재동기화·재접기 보존
  12. ⑫ 같은 DB 형제 머리글 동기화(재귀 가드) · 스키마 미상은 전역 슬롯 미기록
  13. ⑬ stale payload 펼침 시 빈 목록 대신 안내(무음 실패 방지)
  14. ⑭ 컬럼 아코디언 lazy — 등록·첫 펼침 주입·컨테이너 한정 바인딩·재호출 no-op
  15. ⑮ **호출부 인자 매핑 회귀 고정** — `dirRowsHTML` 을 실제 실행해 out=(target,source,→)/in=(source,target,←) 확인
      (초판 스위트는 이 인자를 뒤집어도 전건 PASS 했다 — 리뷰 지적)
  16. ⑯ 백엔드 이웃 상한 고지 배너 + 종전 상한 slice 5종 정적 부재 + "생략 없음" 단언 부재

- **한계(정직)**: 이 스위트는 실 DOM·실 이벤트가 아니라 유닛 격리 검증이며, `.github/workflows/ci.yml` 은
  pytest 전용이라 **CI 회귀 게이트가 아니다**(cycle-내 검증 수단). 실 렌더·클릭 동작은 아래 POST-DEPLOY
  PB-0008 이 정본. 파이썬 스위트는 flaky(같은 main 2회 실행 실패 집합 상이)이며 본 cycle 의 파이썬 변경은
  `neighborhood()` 의 additive `truncated` 플래그뿐.

- **POST-DEPLOY PB-0008 라이브 append 예정**: (a) 테이블 노드 상세 → `사용하는 함수·프로시저` 에 DB 머리글
  (캐럿·DB명·개수) 노출, (b) 머리글 클릭으로 접기/펼치기 동작 + 펼침 시 전량 표시, (c) `… 외 N건` 미노출,
  (d) '모두 펼치기/접기' 동작, (e) `관계 상세`(참조함/참조받음) 동형, (f) 컬럼 아코디언(🔗 캐럿) 첫 펼침 시 관계 행 정상 렌더+클릭 동작, (g) pageerror 0.

### Run (2026-07-27, POST-DEPLOY) — **Environment: Windows-browser** (실제 Windows Chrome 150 / `bin/win-browser.py` relay, `https://localhost/admin`) — 라이브 배포본 `66575331` 실증 — **(a)~(g) 전건 PASS**

경로: 관리 콘솔 → 그래프 뷰 → 데이터소스 `mysql-gz-qa-global`(3 DB · 184 테이블: `gunzgame`/`gunzlog`/`gunzlogin`)
→ 제품 개요에서 데이터소스 노드 클릭 → 스키마 그래프 → `gunzgame` 카드 펼침(421 항목) → 검색으로 대상 노드 상세 진입.

- **(c) 목록 절단 제거 — 원 요구의 핵심** · `gunzgame.character` 노드 상세
  - 머리글 `사용하는 함수·프로시저 (60) · 읽기 42 · 쓰기 18`
  - 실렌더 행 = **읽기 42 + 쓰기 18 = 60 전량**(DOM `ul.amgr-list` 직속 `li` 카운트 42 / 18)
  - `… 외 N건` **정규식 매치 0건** — 종전 30건 상한이면 읽기 42 중 12건이 숨겨졌을 지점.
- **(a) DB 머리글 노출** · `gunzgame.account`(크로스-DB: 이웃 24 = gunzgame 22 + gunzlogin 2)
  - `읽기 (8)` 이 `▾ gunzgame 6` / `▾ gunzlogin 2` 두 DB 머리글로 구획(`li.amgr-dbgrp[data-dbgrp-key]`,
    key = `mysql-3d6eaf56ad40:gunzgame` / `…:gunzlogin`, `aria-expanded=true`).
  - `쓰기 (10)` 은 단일 DB 라 머리글 없이 평면 — 설계(단일 DB + 짧은 목록 = 평면) 대로.
  - 총 8건(≤60)이라 **두 그룹 모두 기본 펼침** — 리뷰 B1(다중 DB 라는 이유로 짧은 목록이 숨는 퇴행) 수정이 라이브에서 확인됨.
- **(b) 머리글 클릭 접기/펼치기 왕복** — `gunzgame` 머리글 클릭 → 그 그룹 행만 사라지고(`WebGM_GetAccountDate` 비가시)
  `gunzlogin` 그룹은 그대로 가시. 재클릭 → 원복(lazy 재주입 정상, 이중/누락 바인딩 없음).
- **(d) '모두 접기/펼치기'** — `▸ 모두 접기` 클릭 → 두 그룹 동시 접힘 + 라벨 `▾ 모두 펼치기` 로 전환 +
  **머리글 개수는 6 / 2 그대로 유지**(접혀도 총계는 정직). 재클릭 → 전 그룹 펼침 + 라벨 원복.
- **(e) 관계 상세 동형** — `gunzgame.account` → `🔗 관계 상세`: `참조함 3 · 참조받음 23 · 연관 용어 0`.
  `← 들어오는 관계 (23)` 에 `▸ 모두 접기` + `▾ gunzgame 21` / `▾ gunzlogin 2` 머리글, **23건 전량**, `… 외 N건` 0건.
  (종전 60건 상한 경로도 동일 유닛으로 전환됨을 확인.)
- **(f) 컬럼 아코디언 lazy** — `AID (→0 ←4)` 캐럿(`.amgr-col-caret`) 클릭 → `← 참조받음 (4)` 와 4건
  (`customizeitemequipmentslot.AID` / `customizeitem.AID` / `character.AID` / `accountitem.AID`) 이 그 자리에 주입.
  대상이 모두 `gunzgame` 단일 DB 라 머리글 없이 평면 — 설계대로.
- **(g) pageerror** — 콘솔 error 누적 = `ResizeObserver loop completed with undelivered notifications.` 1종뿐
  (그래프 캔버스 리사이즈 관측자에서 나오는 기존 benign 경고, 본 변경과 무관). 기능 예외 0.
- 증적 스크린샷: 스키마 그래프 진입 · `gunzgame` 펼침 · 관계 상세 DB 머리글(`▾ gunzlogin 2` + 2행 가시) 캡처 확인.

- **한계(정직)**: 본 라이브 실증은 총량이 FLAT_MAX(60) 이하인 그룹 집합에서 수행됐다 — 즉 **대형 그룹
  (> 300 = `_META_DBGRP_BIG`) 기본 접힘**과 **백엔드 이웃 상한(300) 도달 시 `truncated` 고지 배너**는
  현 데이터셋(최대 이웃 64)에 해당 사례가 없어 라이브에서 재현되지 않았고, 헤드리스 스위트 ⑤·⑯ 의
  유닛 검증에 머문다. 해당 규모의 실 데이터소스가 등록되면 재실증 대상.

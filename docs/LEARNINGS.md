---
doc_type: LEARNINGS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
---

# AI Learnings

AI 작업 중 발견된 교훈, 패턴, 주의사항을 누적 기록한다.
새 AI 세션은 이 문서의 최근 항목을 참조하여 동일한 실수를 반복하지 않는다.

## 기록 규칙
- 항목 ID: `LRN-YYYYMMDD-NNNN`
- 카테고리: `mistake` | `pattern` | `quirk` | `preference`
- 사용자 확인 후: `verified: true` 추가
- 아카이빙: 20건 초과 시 `_archive/LEARNINGS-archive-NNNN.md`로 이동

---

## Category: mistake

### LRN-20260415-0001 — Web UI 카드 적층 구조는 항상 외부 스크롤을 유발한다
- Source: feature-0003 UI 개편 작업 (2026-04-15)
- Mistake: `surface-card` 요소를 세로로 쌓으면 콘텐츠 총 높이 > 100vh가 되어 페이지 전체 스크롤이 발생한다. 이는 AI 채팅 앱에서 치명적인 UX 결함이다.
- Correct approach: `app-shell`을 `100vh grid`로 고정하고, 스크롤은 메시지 목록(`.messages { flex:1; overflow-y:auto }`) 영역에만 허용한다. 나머지 영역(topbar, sidebar, composer)은 고정 높이/flex-shrink:0으로 처리한다.

## Category: pattern

### LRN-20260415-0002 — Web UI 설계는 검증된 상용 앱 패턴을 우선 따른다
- Source: feature-0003 UI 개편 작업 (2026-04-15)
- Pattern: 채팅형 AI 도구 UI는 ChatGPT/Claude 검증 패턴인 `[Topbar | Sidebar + Chat Pane]` 2단 고정 레이아웃을 기본으로 한다. 상태 설명, 마케팅 카피, eyebrow 레이블은 기능적으로 필요할 때만 노출한다. 성공 레퍼런스를 먼저 파악하고 따르는 것이 사용자 피드백 반복보다 효율적이다.
- Applies to: feature-0003 이후 신규 Web UI feature 전체.

### LRN-20260415-0007 — UI 개편 시 기존 데이터 필드가 렌더링 경로에서 누락되지 않도록 검증해야 한다
- Source: feature-0003 쿼리 결과셋 복원 작업 (2026-04-15)
- Mistake: App-Shell UI 전면 개편 후 `renderMessageDetails`를 재작성하는 과정에서 `step.result_summary.preview_table`(인라인 쿼리 결과)이 렌더링 경로에서 누락됐다. 백엔드는 이미 `preview_table` 필드를 포함한 정규화된 데이터를 전송하고 있었으나, 프론트엔드에서 그 필드를 참조하지 않아 CSV 링크만 남게 됐다.
- Correct approach: UI 개편 후 `meta.steps`에 어떤 필드들이 있는지 실제 API 응답으로 먼저 확인(`curl /api/history` + `python3 -c` 파이프)하고, 렌더링 함수가 모든 표시 가능 필드를 커버하는지 체크한 뒤 브라우저로 검증한다. execute_sql 결과는 `result_summary.preview_table.{columns, rows, truncated}` → HTML 테이블로 렌더링해야 한다.
- Applies to: feature-0003 이후 `renderMessageDetails` 또는 step 렌더링을 수정하는 모든 작업.

### LRN-20260415-0006 — 드로어 내 정보가 많아지면 탭으로 분리해야 한다
- Source: feature-0003 프로필 드로어 탭 구조화 작업 (2026-04-15)
- Pattern: 드로어(슬라이드 패널)에 섹션을 수직으로 누적하면 스크롤이 길어지고 정보 계층이 불분명해진다. 권한 현황·활동 정보·비밀번호·API 설정처럼 카테고리가 다른 내용은 탭으로 분리한다. 탭 전환은 `data-*` 속성 기반 JS로 처리하고(`.is-active` + `hidden` 클래스 토글), 탭 헤더에는 계정 컨텍스트(아바타·이름)를 고정 노출해 탭 전환 중에도 현재 계정이 명확히 보이게 한다.
- Applies to: feature-0003 이후 드로어 패널이 3개 이상의 이질적 섹션을 포함할 경우 모두 적용.

### LRN-20260415-0005 — 계정별 설정은 탑바가 아닌 프로필 드로어에 배치한다
- Source: feature-0003 API Vault 통합 작업 (2026-04-15)
- Pattern: API Vault처럼 계정 단위로 저장되는 설정을 탑바에 두면 "전역 도구인가 계정 설정인가"가 모호해진다. ChatGPT·Claude 패턴처럼 계정별 설정은 프로필 드로어 안의 탭(API Vault 탭)으로 이동하고, 탑바는 전역 네비게이션(브랜드, 관리 콘솔)만 남긴다. 드로어로 기능이 이전되면 탑바 버튼도 함께 제거한다.
- Applies to: feature-0003 이후 신규 계정별 설정 추가 시 전체 적용.

### LRN-20260415-0004 — 로그아웃/인증 전환 시 열린 UI 상태와 폼 값을 반드시 초기화한다
- Source: feature-0003 로그아웃 버그 수정 (2026-04-15)
- Mistake: 프로필 드로어가 열린 채 로그아웃하면 인증 화면 위에 드로어가 그대로 남아 UI가 깨진다. 회원가입 후 로그아웃하면 다음 로그인 시 회원가입 폼에 이전 입력값이 노출된다.
- Correct approach: 로그아웃 핸들러 최상단에서 `closeProfile()`을 호출하고, 이후 `loginForm.reset()` / `signupForm.reset()` + 오류 메시지 초기화 + 로그인 탭 복귀를 순서대로 실행한다. 인증 상태를 바꾸는 모든 경로(로그아웃, 세션 만료 처리)에 동일 패턴을 적용한다.
- Applies to: feature-0003 이후 인증 상태 전환이 있는 모든 Web UI feature.

### LRN-20260415-0003 — 브라우저 자동화 접근 시 web 컨테이너는 `ignore_https_errors: true` + HTTPS URL 사용
- Source: feature-0003 브라우저 검증 작업 (2026-04-15)
- Quirk: web 컨테이너는 `ENABLE_WEB_TLS=1` 설정으로 HTTPS로 기동된다. browser 컨테이너에서 `http://web:8000`은 빈 응답을 반환한다. `https://web:8000` + `ignore_https_errors: true` 파라미터를 goto에 전달해야 정상 접근된다.
- Applies to: feature-0004-browser-automation을 이용한 모든 Web UI 검증 시나리오.

### LRN-20260414-0001 — GitHub 자동화 계약은 기계 판독 파일로 먼저 고정 (deprecated 2026-05-15, ADR-0018)
- Source: ADR-0017 (superseded by ADR-0018)
- Pattern (당시): 공개 브랜치 규칙, provider 라벨, 상태 라벨, 커밋 형식, required checks가 문서와 워크플로에 중복되면 쉽게 드리프트가 생긴다. `.github/automation-contract.json`을 정본으로 두고, 쉘 스크립트와 `policy-contract`가 이 파일을 읽게 하면 재발을 줄일 수 있다.
- 현재 적용성: 자동화 스택 자체가 폐기되어 본 패턴은 더 이상 유효하지 않다. PR 머지 게이트는 사람 리뷰 + 로컬 `bin/verify-completion.sh` 로 단순화했다.

### LRN-20260409-0001 — 템플릿 v3.0.0 마이그레이션 시 프로젝트 고유 섹션 보존
- Source: commit `d5ce1a2` (feat(project): 템플릿 v3.0.0 마이그레이션)
- Pattern: AGENTS.md를 Part A~G 구조로 재정렬할 때, 본 프로젝트 고유 섹션(**프로젝트 목표**, **연구 기반 방향 전환**, **웹 기준 업계 표준 반영**, **절대 금지 목록**, **Docker Compose 운영 규칙**, **.env 정책**)은 템플릿의 일반 조항을 덮어쓰지 않고 해당 Part에 그대로 배치한다. 템플릿의 섹션 재편을 기계적으로 따르면 프로젝트 고유 지침이 누락된다.
- Applies to: 차후 템플릿 버전 업 시에도 동일 원칙 적용. 프로젝트 고유 조항의 위치는 CODEBASE_MAP.md 또는 TEMPLATE_CHANGELOG.md의 마이그레이션 체크리스트에 기록한다.

### LRN-20260416-0001 — LLM 도구 호출 순서는 TOOL_DEFINITIONS 배열 순서에 영향받는다
- Source: feature-0002 Planner 자율성 개선 작업 (2026-04-16)
- Pattern: 로컬 LLM이 `search_tables` → `describe_table`을 반복하며 `execute_sql`을 늦게 호출하는 문제가 있었다. `TOOL_DEFINITIONS` 배열에서 `execute_sql`을 맨 앞으로 이동하고 각 도구 description에 사용 조건(예: "최후 수단", "오류 시에만")을 명시하자 탐색 단계가 줄어들었다. 휴리스틱(step count 기반 강제)이 아닌 도구 제시 순서와 자연어 지침만으로 LLM 행동을 교정할 수 있다.
- Applies to: feature-0002 agent_core.py + tools.py의 TOOL_DEFINITIONS 및 SYSTEM_PROMPT 수정 시.

### LRN-20260416-0002 — Progress Strip은 `<details>` 드롭다운으로 높이를 고정해야 한다
- Source: feature-0003 Progress Strip 드롭다운 구조화 (2026-04-16)
- Pattern: step이 누적되며 progress-strip 높이가 증가하면 채팅 영역이 점점 좁아진다. `<details>`/`<summary>` 네이티브 드롭다운으로 전환하고, summary에 `n단계 · 최근 작업` 요약을 표시하며, 펼침 영역은 `max-height: 40vh; overflow-y: auto`로 제한하면 채팅 영역을 보호하면서 전체 진행 상황 확인도 가능하다.
- Applies to: feature-0003 progress strip 구조를 수정하는 모든 작업.

### LRN-20260416-0003 — 다중 결과셋은 팝업이 아닌 말풍선 내 Navigator로 격리 탐색한다
- Source: feature-0003 SQL 결과 Navigator 도입 작업 (TASK-0025, 2026-04-16)
- Pattern: execute_sql step이 여러 개일 때 SQL+결과 테이블을 수직 누적하면 말풍선이 과도하게 길어진다. 반대로 별도 팝업(modal)은 레코드 수에 따라 창 크기가 흔들리고 말풍선 컨텍스트에서 벗어난다. 해결책은 말풍선 내에서 단일 패널을 유지하는 Navigator 패턴이다:
  - `◀` / `쿼리 n/N` 인디케이터 / `▶` + `대상: schema.table` 컨텍스트 헤더를 상시 노출
  - 패널을 한번 생성하고 `.is-active` 클래스로 display 토글 (DOM 재생성 없음 → 상태 안정)
  - 컨테이너에 `tabindex="0"` + `←/→/Home/End` 키보드 조작, 조작법은 버튼 `title` 툴팁으로만 노출(화면 내 상시 출력 금지)
  - 말풍선마다 Navigator 인스턴스를 독립 생성(클로저 상태)해 탐색 범위를 격리
  - 대용량 전체 데이터는 `/api/file`로 CSV fetch 후 클라이언트 파싱해 tbody 교체 + `max-height + overflow:auto`로 영역 보호
- Applies to: feature-0003 에서 말풍선 내 여러 결과셋을 다뤄야 하는 모든 UI (SQL 결과 외에도 step 기반 반복 결과 일반에 확장 가능).

### LRN-20260421-0001 — 한 줄 SQL은 표시 전용 포매터로 키워드 경계 줄바꿈을 적용한다
- Source: feature-0003 SQL 수평 확장 방지 작업 (TASK-0026, 2026-04-21)
- Pattern: LLM이 생성하는 SQL은 종종 한 줄로 길게 이어져 `<pre>` 블록이 말풍선을 수평으로 확장시킨다. `overflow-x: auto`를 쓰면 스크롤바가 생기지만 flex/grid `min-width` 계산으로 부모가 확장되는 경우는 방지하지 못한다. 해결책은 표시 전용 포매터 `formatSqlForDisplay()`를 `pre.textContent` 세팅 직전에 적용하는 것이다:
  - 이미 `\n`이 있으면 원형 유지 (LLM이 이미 포맷한 경우)
  - 문자열 리터럴(`'...'`, `"..."`, `` `...` ``)을 placeholder로 치환해 내부 키워드를 보호한 뒤, 주요 키워드(`SELECT`, `FROM`, `WHERE`, `GROUP BY`, `ORDER BY`, `INNER JOIN` 등) 앞 공백을 `\n`으로 교체
  - 복합 키워드(`LEFT JOIN` 등)가 분리되지 않도록 bare `JOIN`은 키워드 목록에서 제외
  - CSS에 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere` + 컨테이너 `min-width: 0`을 함께 적용해 포매터가 못 잡는 초장문 토큰도 wrap
- Applies to: feature-0003 에서 `sql-block` 렌더링을 수정하거나 SQL 표시 로직을 변경하는 모든 작업.

### LRN-20260421-0002 — 많은 권한 항목은 `<details>` collapsible + summary 카운트 배지로 접근성을 회복한다
- Source: feature-0003 RBAC 33-permission UX 개편 (TASK-0027, 2026-04-21)
- Pattern: 권한이 5그룹 33개로 세분화되자 관리 콘솔에서 "계정 1건당 33개 select × 페이지당 10계정 = 330개 select"가 한 화면에 쌓여 사실상 조작 불가능 상태가 됐다. 해결책은 네이티브 `<details>`/`<summary>` 접힘 + summary에 **실시간 카운트 배지** 노출 + 그룹별 **배치 액션 버튼**이다:
  - summary 구조: `그룹명 + 카운트 배지(상속 N · 허용 M · 거부 K 또는 N/M 선택됨)`
  - 기본 접힘, 선택/override가 있는 그룹만 자동 펼침으로 초기 렌더
  - 배치 액션: "모두 허용/거부/상속" 또는 "모두 선택/해제"를 그룹 헤더에 배치해 클릭 1회로 그룹 전체 반영
  - Profile 드로어처럼 "조회 전용" 맥락에서는 그룹별 `<section>` + pill chip 리스트로 충분 (접힘 불필요)
  - `PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "misc"]` 배열을 프론트 상수로 두고, permission 코드의 앞쪽 토큰(`console.manage` → `console`)으로 폴백 분류하면 백엔드 스키마와 독립된다.
- Applies to: feature-0003 이후 항목 수가 10개를 넘는 선택/편집 UI 전반 (권한 외에도 feature flag, 알림 설정, 역할 매핑 등).

### LRN-20260421-0003 — 백그라운드 서비스/숨은 서브시스템은 전용 문서로 분리해 "서비스 오류"로 오해받지 않게 한다
- Source: feature-0002 Insight 시스템 문서화 (TASK-0028, 2026-04-21)
- Pattern: `insight.py` 1400 줄이 넘는 백그라운드 워커가 5 초마다 DB 에 접속하고 자체 로그(`insight_worker.log`)를 쌓았으나, 어느 문서에도 기능 설명이 없어 사용자가 "서비스가 오류를 반복하고 있다"고 오해했다. 이런 숨은 서브시스템은 `FUNCTION.md` 본문에 몇 줄 추가하는 것만으로는 부족하고, **전용 문서 1종**을 아래 구조로 만들어야 한다:
  - 한 줄 요약 + "사용자 영향(왜 이 시스템이 존재하는가)"
  - 아키텍처 ASCII 다이어그램 (컨테이너/루프/저장소 관계)
  - 실행 경로 — 정상 루프 + fallback 경로(워커 부재 시 인라인 스캔처럼)
  - 저장 형식 (테이블/KV 키 패턴 표)
  - 환경변수 레퍼런스 표 (기본값 + 설명)
  - **"오류 같아 보이지만 정상인 신호" 해석 가이드** — `skip_locked`, `fingerprint_skip` 등
  - 헬스 체크 SQL snippet + **실제 런타임 출력을 문서 작성 시점에 캡처해 증빙**으로 삽입
  - 코드 참조표 (파일:줄번호) — 줄번호는 다른 작업자의 리팩터링 후 쉽게 드리프트하므로 함수명을 함께 적고, 문서 갱신 시 `grep`으로 재검증한다.
- Applies to: 향후 숨은 백그라운드 워커/큐/스케줄러/캐시 갱신 로직이 추가되면 동일 구조로 전용 문서를 작성한다. 기존 숨은 로직도 발견 즉시 동일 패턴으로 문서화한다.

### LRN-20260421-0004 — 관리 콘솔 다건 편집은 per-form save 대신 pending + bulk commit 모델이어야 한다
- Source: feature-0003 관리 콘솔 재구조화 (TASK-0029, 2026-04-21)
- Mistake: admin.js 가 각 계정/역할마다 독립된 `<form>` + 개별 "저장" 버튼을 두고, 저장 성공 후 `loadAdminData()` 로 전체 DOM 을 다시 렌더링했다. 결과: 사용자가 3개 계정을 순차 편집 중 한 계정에서 저장을 누르면 나머지 2개 계정의 pending DOM state 가 사라지는 크리티컬 버그. 사용자 테스트에서 "수정한 내용이 사라진다"는 피드백으로 확인됨.
- Correct approach: AWS IAM 콘솔 패턴을 따른다 —
  1. 편집 이벤트(input/change)는 **서버 호출 없이** JS 측 `pending = { accounts: Map<id, patch>, roles: Map<id, patch>, newRoles: Map<tempId, draft> }` 에만 반영.
  2. patch 값이 서버 원본과 동일해지면 pending 에서 auto-drop (noise 방지).
  3. 하단에 sticky commit bar 를 두고 "변경사항 N건 · 취소 / 모두 적용" 노출. `.has-pending` 클래스로 색상 강조(노란/주황).
  4. "모두 적용" 클릭 시에만 전체 pending entry 를 loop 로 PATCH/DELETE/POST 후 1회만 `loadAdminData()`.
  5. detail pane 은 `mergedAccount(id) = server + pending overlay` 로 렌더 — 리스트와 디테일 양쪽에서 pending 표시(`.has-pending` dot)가 일관되게 보이도록.
  6. 리스트 row 체크박스 기반 bulk 작업도 **즉시 API 호출 금지**. 선택된 각 row 에 대해 `setAccountPending(id, patch)` 만 호출 → 사용자가 commit bar 로 확인 후 적용.
  7. `beforeunload` 에서 pending 이 남아 있으면 이탈 경고.
- Verification: admin.js 의 pending 로직을 단순 node 스크립트로 분리해 "3개 계정 각기 다른 필드 편집 → 전부 pending 유지, revert-to-server 시 auto-drop" 시나리오를 assert 로 재현했다(`/tmp/verify_pending_logic.js`). API 레벨에서 partial PATCH(`is_active` 만 / `role_id` 만 / `permission_overrides` 만) 가 모두 200 OK 를 반환하는 것도 확인해 pending 모델이 서버 계약과 일치함을 검증.
- Applies to: 모든 관리/설정 콘솔 UI. "여러 행을 편집 가능한 테이블" UI 는 기본적으로 이 패턴을 적용한다. 단건 편집이거나 저장 후 즉시 새 화면으로 이동하는 경우는 예외.

### LRN-20260421-0005 — 관리 콘솔은 채팅 app-shell 과 동일한 전폭 grid 레이아웃을 써서 일관성을 유지한다
- Source: feature-0003 관리 콘솔 재구조화 (TASK-0029, 2026-04-21)
- Pattern: admin 페이지에 `max-width: 1100px; margin: 0 auto` 를 걸고 3개 surface-card 를 세로로 스택하면, 채팅 "작업 화면"(app-shell 전폭 grid + sidebar + chat pane) 과 톤이 크게 달라 사용자가 "위화감이 든다" 고 느낀다. 또한 좌우 여백이 정보 표현 공간을 낭비한다. 해결: admin 도 `body.admin-shell { display:grid; grid-template-rows: var(--topbar-h) 1fr auto; height:100vh }` + `.admin-body { grid-template-columns: 220px 1fr }` 구조로 전환해 topbar/sidebar/workspace/commit-bar 4 영역을 채팅 UI 와 동일한 축으로 배치한다. 탭 네비는 sidebar 에 둬 대시보드/계정/역할 영역을 독립 pane(`display:none` 토글)으로 분리하면 "한 화면에 세 섹션이 섞여 검색 범위가 모호해진다"는 피드백도 동시에 해소된다.
- Applies to: feature-0003 이후 모든 internal 관리/설정 UI. 별도 서브 앱(/admin, /settings 등)이라도 동일한 app-shell 골격을 재사용해 시각적 일관성을 유지한다.

### LRN-20260421-0006 — 확장 가능한 본문을 포함한 채팅 말풍선은 고정 폭 + 내부 max-height + scroll anchor 3 종 세트로 설계한다
- Source: feature-0003 말풍선 스크롤 드리프트 이슈 (TASK-0030, 2026-04-21)
- Mistake: assistant 말풍선 안에 `<details>` / SQL / 결과 테이블을 담으면서 `.message { max-width: 82% }` 와 `.message-details-body { /* no cap */ }` 만 적용했더니, 펼침/Navigator 이동/쿼리 결과셋 행 수에 따라 말풍선 크기와 채팅 로그 스크롤 위치가 비결정적으로 튀어 사용자가 방금 보던 문장을 놓치는 UX 버그가 발생했다.
- Correct approach: "확장 가능한 본문을 가진 채팅 말풍선" 은 세 장치를 동시에 적용한다 —
  1. **역할별 max-width 분기** — user 는 좁은 우측 정렬(`max-width: 72%`), assistant 는 `max-width: none` + `align-self: stretch` + `margin-right: 48px` 로 채팅 pane 전폭에 가깝게 고정. 우측 여백(≈48px) 만으로 시각 구분.
  2. **내부 본문 cap** — `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` 로 펼친 콘텐츠를 말풍선 내부에서 소비. 내부 요소(SQL block, 결과 테이블)에도 2차 cap(`.sql-block { max-height: 240px; overflow: auto }`, `.result-table-wrap { max-height: 320px; overflow: auto }`) 을 걸어 이중 안전망.
  3. **Scroll anchor** — `<summary>` 클릭 핸들러에서 스크롤 컨테이너 기준 `getBoundingClientRect().top` 을 측정 → `requestAnimationFrame` 2 프레임 후 delta 만큼 `scrollContainer.scrollTop` 을 보정. `<details>` 네이티브 동작만으로는 부족하고, 내부 cap + anchor 가 모두 있어야 "펼쳐도 위에 있는 메시지가 튀지 않는다".
- Verification: 브라우저 자동화에서 펼침 전/후 `summary.getBoundingClientRect().top` 동일(delta=0), Navigator 이동 시 `bubble.getBoundingClientRect().width` 불변(705→705), `message-details-body` 의 실계산 max-height 가 432px(60vh @ 720px viewport) 로 확인됨.
- Applies to: 챗봇/로그 뷰어/이벤트 피드 등 "고정 목록 내부에 확장 가능한 row" 가 있는 모든 UI. `<details>` 만으로 충분해 보여도 내부 콘텐츠가 동적이면 반드시 cap + anchor 를 동반한다.

### LRN-20260421-0007 — 마스터-디테일 관리 UI 는 "외부 스크롤 금지 + 컬럼별 내부 스크롤 + 하단 요소 sticky/flex-shrink:0" 로 구성한다
- Source: feature-0003 관리 콘솔 스크롤 정리 (TASK-0031, 2026-04-21)
- Mistake: admin 페이지에 `.admin-workspace { overflow-y: auto }` 를 걸고 양쪽 컬럼을 `align-items: start` 로 둔 채 `.admin-list { max-height: calc(100vh - 320px) }` 하드코딩 cap 만 넣었다. 디테일 pane 이 커지면 workspace 전체가 스크롤되면서 리스트 컬럼의 페이지네이션이 뷰포트 밖으로 밀려 "버튼이 없어진 것처럼" 보이는 UX 버그가 발생.
- Correct approach: 마스터-디테일 관리 UI 는 **외부(페이지 전체) 스크롤을 발생시키지 않는다**. 대신 —
  1. 최상위 shell 은 `height: 100vh; overflow: hidden` + `display: grid; grid-template-rows: topbar 1fr auto` (하단 commit bar 고정).
  2. workspace 는 `overflow: hidden; display: flex; flex-direction: column; min-height: 0` — 자체 스크롤 금지, 자식이 남은 공간을 채우게 위임.
  3. 활성 pane 은 `flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column`. head 영역은 `flex-shrink: 0`.
  4. list-detail 컨테이너는 `flex: 1 1 auto; min-height: 0; align-items: stretch`. 두 컬럼은 각각 `min-height: 0` 을 받아 자체 내부 스크롤을 가진다.
  5. **리스트 컬럼** 내부 수직 흐름: toolbar(shrink 0) + list-head(shrink 0) + `.admin-list`(`flex: 1; min-height: 0; overflow-y: auto`) + 페이지네이션/일괄 액션(`flex-shrink: 0`). 하드코딩 `max-height: calc(100vh - Xpx)` 는 제거 — 부모 flex 레이아웃이 자동 계산한다.
  6. **디테일 컬럼** 은 `overflow-y: auto` 로 내부 스크롤. 저장/삭제 같은 마지막 액션 영역은 **`position: sticky; bottom: 0; background: surface; border-top`** 로 디테일 길이와 무관하게 상시 하단 노출.
  7. 액션 영역의 sticky 가 detail-col padding 과 충돌하면 `margin: 0 -padX -padY` + `padding: padY padX` 로 padding 을 상쇄해 전폭 바로 만든다.
- Verification: 브라우저 자동화로 `document.documentElement.scrollHeight - clientHeight == 0`(외부 스크롤 없음), `detail-col.scrollHeight - clientHeight > 0`(내부 스크롤 활성), 양 컬럼 끝까지 scrollTop 을 밀어도 `.admin-detail-actions.getBoundingClientRect().bottom <= window.innerHeight` 가 유지되는 것을 확인.
- Applies to: 마스터-디테일/리스트-폼/설정 패널 등 "좌측 리스트 + 우측 편집" 레이아웃 전반. Admin · 프로필 · API Vault · 알림 설정 등 향후 유사 화면에 동일 패턴을 재사용한다.

### LRN-20260421-0008 — 권한으로 막힌 버튼은 숨기지 말고 "필요 권한 코드 + 서술"을 안내하는 blocked 상태로 노출한다
- Source: feature-0003 권한 안내 UX (TASK-0032, 2026-04-21)
- Mistake: RBAC 권한 확인이 실패하면 버튼을 `hidden` 토글로 DOM 에서 감추거나 핸들러 초입 `if (!can(X)) return;` 으로 **소리 없이 무시**했다. 동작이 안 보이거나 클릭해도 반응이 없어 사용자는 "왜 안 되는지" 를 알 수 없었고, 관리자에게 정확히 어떤 권한을 요청해야 하는지도 전달되지 않았다. 툴팁도 `title = code` 로 영문 id (`conversation.rename.own`) 만 노출해 비개발자가 해석하기 어려웠다.
- Correct approach: 권한 게이트는 **노출 + 명시** 두 축으로 재설계한다 —
  1. **`PERMISSION_DESCRIPTIONS` flat map** 을 단일 정본으로 둬서 모든 권한 코드를 "~할 수 있습니다" 형태의 완결된 한국어 문장으로 매핑한다. `PERMISSION_LABELS` 는 짧은 라벨(그룹 합계 등 좁은 공간용), `PERMISSION_DESCRIPTIONS` 는 서술 문장용으로 역할을 분리한다. 프로필 권한 pill 툴팁은 `` `${describePermission(code)}\n(${code})` `` 2줄 형식으로 노출해 사람이 읽는 문장과 개발자가 검색할 코드를 동시에 보여준다.
  2. **숨김 vs blocked 상태 분리** — 버튼 hidden 토글은 **컨텍스트**(예: 대화가 없음 → 이름변경 의미 없음, run 실행 중 아님 → 취소 의미 없음) 에만 사용한다. 권한 부재는 `markAccessBlocked(btn, action, conv)` 헬퍼가 `aria-disabled="true"` + `.is-access-blocked` (opacity .42, cursor: help, 중립 색) 을 붙이고, 네이티브 `disabled` 는 쓰지 않는다. 네이티브 `disabled` 는 click 이벤트 자체를 차단해 토스트를 띄울 기회를 잃기 때문이다.
  3. **클릭 경로를 유지한 채 토스트로 안내** — 각 액션 핸들러(`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 는 `if (!can(...)) { showPermissionDeniedToast(action); return; }` 로 교체. `showPermissionDeniedToast` 는 `requiredPermissionsFor(action, conversation)` 로 필요한 권한 코드 집합(any/own 양쪽 포함)을 계산해 `"'이름변경' 권한이 없습니다. 필요 권한: \`conversation.rename.own\` — 본인이 소유한 대화의 이름만 변경…"` 처럼 **동작명 + 코드 + 서술** 3종을 한 문장에 담는다.
  4. `any` 권한이 있으면 own 요구 없이 통과하고, own 만 있으면 `isOwnConversation()` 로 소유 여부를 한 번 더 검증하는 **dual-permission 패턴** 을 `requiredPermissionsFor` 에 집중시켜 호출부는 `action` 문자열만 넘긴다.
  5. 접근 차단 상태에서도 버튼 title 에 동일한 필요 권한 문구가 들어가도록 `markAccessBlocked` 에서 title 을 같이 갱신 — hover 와 click 양쪽에서 동일 정보가 나온다.
  6. `renderAccessNotice()` 처럼 페이지 전체가 잠기는 경우에도 안내 메시지에 필요 권한 코드(예: `` `conversation.ask` ``) 와 "관리자에게 권한 부여를 요청하세요." 를 명시해 **어떤 권한을 누구에게 요청해야 하는지** 를 일관된 톤으로 전달한다.
- Verification: 브라우저 자동화로 (a) bootstrap_admin(31 권한) 은 모든 버튼이 활성·토스트 미발생, (b) 신규 pending 계정(5 권한, `conversation.ask`/`.create`/`.delete.any` 없음) 으로 로그인 시 composer 의 "보내기" · "새 대화" 버튼이 `.is-access-blocked` + `aria-disabled` 로 보이고, 클릭 시 필요 권한 코드가 포함된 토스트가 뜨는 것을 확인. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png`.
- Applies to: RBAC/기능 플래그/구독 제한 등 권한 게이트가 존재하는 모든 UI. "의미 있는 컨텍스트에서 권한만 부족한 버튼" 은 숨기지 말고 blocked 상태로 노출하고, 클릭 경로를 유지해 **필요 권한 코드 + 서술 + 요청 대상(관리자)** 3요소를 토스트/title 로 안내한다. 권한 코드는 사용자 메시지에 코드블록으로 포함해 복사·검색이 가능하게 한다.

### LRN-20260421-0009 — 스크롤 컨테이너 중첩은 "턱턱" 끊김을 만들고, 결과 테이블에는 RowCount + sticky freeze 가 기본값이어야 한다
- Source: feature-0003 결과셋 말풍선 UX 정리 (TASK-0033, 2026-04-21)
- Mistake: TASK-0030 에서 말풍선 내부 스크롤 격리를 목적으로 `.message-details-body { max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain }` 를 도입했다. 하지만 내부의 `.sql-block`/`.result-table-wrap` 도 각자 `max-height` + `overscroll-behavior: contain` 을 가지고 있었다. 결과: 같은 말풍선 안에 세로 스크롤 컨테이너가 2-3개 겹치고, 마우스 휠이 "누가 휠을 소비할지" 매 프레임 바뀌면서 사용자 입장에서 **"턱턱" 걸리는** 느낌이 났다. 또 결과 테이블에 RowCount(행 번호) 컬럼이 없고 헤더/첫 열 freeze 도 없어 행/열이 많아지면 위치 파악이 불가능했다.
- Correct approach: "말풍선 안의 확장 본문" 은 스크롤을 중첩하지 말고 **단일 바깥 스크롤 + 단일 내부 스크롤** 원칙을 지킨다. 그리고 결과 테이블은 RowCount + freeze 를 기본값으로 탑재한다 —
  1. **말풍선 body cap 제거** — `.message-details-body` 의 `max-height`/`overflow`/`overscroll-behavior`/`padding-right` 를 모두 제거해 본문이 콘텐츠 높이만큼 자연스럽게 자라게 한다. 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 되고, 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 **근본 제거**.
  2. **내부 컨테이너의 `overscroll-behavior: contain` 제거** — `contain` 은 자식이 경계에 닿아도 휠을 부모로 전파하지 않는다. 결과 테이블/SQL 블록 내부에서 끝까지 스크롤하면 "막힌 벽" 느낌이 나며, 사용자는 마우스를 이동해 다시 바깥 스크롤을 잡아야 한다. `auto`(기본)로 되돌리면 경계에서 `.messages` 로 자연스럽게 휠이 넘어가 연속된 흐름이 된다. 단, 내부 `max-height` 는 유지 — 결과 테이블이 100행이면 말풍선이 화면을 완전히 차지해 다른 메시지를 못 보게 되기 때문.
  3. **sticky freeze 는 CSS 만으로 완전 구현** — `.result-table { border-collapse: separate; border-spacing: 0 }` + `thead th { position: sticky; top: 0 }` + `th.col-rownum, td.col-rownum { position: sticky; left: 0 }` + 교차점(`thead th.col-rownum { z-index: 3 }`) 으로 Excel 의 "Freeze first row + first column" 을 정확히 재현. `border-collapse: collapse` 에서는 sticky 셀의 border 가 렌더 타이밍에 따라 사라지므로 **`separate` + `box-shadow: inset` 으로 border 대체** 해야 시각적 경계가 유지된다.
  4. **RowCount 는 가상 컬럼으로 클라이언트에서 prepend** — 백엔드 응답(`preview_table.columns/rows`) 스키마는 건드리지 않고 `buildResultTable()` 에서 `<th class="col-rownum">#</th>` + 각 `<tr>` 앞 `<td class="col-rownum">{i+1}</td>` 를 추가. `loadFullCsvIntoTable()` 의 전체 데이터 교체 경로에도 같은 헬퍼(`appendRowNumCell`)를 재사용. meta 의 `"N열"` 카운트는 데이터 컬럼 수로 유지(사용자 기대와 일치).
  5. Sticky 측정 시 **`<tr>` 이 아니라 개별 `<th>` 요소의 BoundingClientRect** 를 확인. 대부분의 브라우저는 `position: sticky` 를 `<tr>` 에서 무시하고 `<th>`/`<td>` 에서만 적용하므로, `thead tr` 의 rect 는 scroll 만큼 이동해 보여도 내부 `th` 들은 실제로는 고정되어 있다. 검증 자동화 작성 시 함정.
- Verification: 기존 33행 × 3열 결과 테이블을 기준으로 (a) `.message-details-body` 의 `scrollHeight === clientHeight` (내부 스크롤 없음), `overflow = visible`, (b) `.result-table-wrap` `overscroll-behavior = auto`, (c) `thead th.position = sticky`, `td.col-rownum position = sticky, left = 0`, corner `z-index = 3`, (d) `wrap.scrollTop = 200` 시 각 `<th>` 개별 `top` 변동 0, (e) `wrap.scrollLeft = 100` (폭 강제 축소) 시 `td.col-rownum` 좌표 불변(`rnStayed: true`) + 데이터 컬럼은 이동(`dataMoved: true`). 스크린샷에서도 `# | hero_index | participation_count` 헤더가 상단에, `#` 열이 좌측에 고정된 채 행 6-19 가 보임.
- Applies to: 채팅/로그/인사이트 패널 등 **확장 가능한 본문을 포함한 카드형 UI**. 본문 스크롤은 컨테이너 계층마다 함부로 중첩하지 말고, 외부 페이지 스크롤을 대체할 만큼 큰 내부 영역에만 제한적으로 둔다. 또 모든 데이터 테이블(쿼리 결과/로그/리스트 등) 은 **기본값으로 행 번호 컬럼 + 헤더/첫 열 freeze** 를 제공한다 — 사용자가 스크롤 중에도 위치를 잃지 않는 것은 옵션이 아니라 기본 요구사항.

### LRN-20260422-0011 — 장시간 작업 폴링은 `setInterval` 고정 주기가 아니라 순번 기반 `setTimeout` 체인 + AbortController + 적응형 주기로 설계한다
- Source: feature-0003 `/api/progress` 폴링 리팩터 (TASK-0036 부수 변경, TASK-0037 사후 리뷰, 2026-04-22)
- Mistake: 초기 구현은 `state.progressPoller = setInterval(pollProgress, 1500)` 고정 주기였다. `/api/ask` 한 턴이 수분까지 걸리는 실사용 (TASK-0034 복잡 QA 테스트에서 평균 ~3분/턴) 에서 다음 4가지 문제가 동시에 발생:
  1. `setInterval` 은 이전 fetch 완료 여부와 무관하게 tick 을 발화 → `/api/progress` in-flight 요청이 누적되어 서버 커넥션/CPU 낭비
  2. `stopProgressPolling()` 이 `clearInterval` 만 호출 → 이미 발행된 fetch 는 응답이 올 때까지 서버/네트워크 리소스를 계속 소비
  3. `document.hidden` 감지 없음 → 탭을 배경화해도 1.5초마다 폴링이 계속되어 배터리/모바일 셀룰러 트래픽을 불필요하게 씀
  4. 서버는 `after_step` 필터를 받지만 `client_run_id` 가 없어서, 새 run 이 시작된 상황을 감지 못해 클라이언트가 "낡은 run 의 after_step" 으로 계속 요청 → 새 run 의 step 0..K 를 놓침
- Correct approach: 장시간 작업(분 단위) 을 백그라운드에서 추적하는 모든 폴링은 다음 5 원칙을 묶어서 적용한다 —
  1. **순번 기반 `setTimeout` 체인** — `state.progressPollSeq: number` + `scheduleProgressPolling(delayMs, seq)` 로 "[fetch] → [응답] → [다음 fetch 1회 예약]" 단일 체인을 유지. `pollProgress(seq)` 진입부에서 `seq !== state.progressPollSeq || state.progressPollInFlight` 이면 즉시 return — in-flight 요청이 1 을 넘는 게 **코드로 불가능** 하게 강제.
  2. **AbortController 로 취소 경로 완비** — 매 poll 마다 `new AbortController()` 를 `state.progressAbortController` 에 저장하고 fetch signal 로 전달. `stopProgressPolling({abort:true})` 이 `controller.abort()` 를 호출해 in-flight HTTP 를 즉시 끊는다. 대화 전환/로그아웃/상세 본문 닫기 등 "이 폴링이 더 이상 의미 없어진" 모든 경로에서 호출.
  3. **요청당 timeout 상한** — `setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS=4000)` 으로 서버 응답 지연도 상한 설정. `finally` 에서 `clearTimeout(timeoutId)`. 서버가 죽었을 때도 클라이언트가 무한 대기하지 않음.
  4. **적응형 주기 (상태 → 주기)** — `PROGRESS_POLL_ACTIVE_MS=1200`(새 step 스트리밍 중), `PROGRESS_POLL_IDLE_MS=3000`(기본), `PROGRESS_POLL_HIDDEN_MS=10000`(`document.hidden`), `PROGRESS_POLL_ERROR_MS=8000`(에러 후) 4단계. `scheduleProgressPolling(delayMs)` 진입 시 `document.hidden` 이면 `Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)` 로 하한을 끌어올려 어떤 경로로 짧은 delay 가 들어와도 탭 배경화 시 자동 감속.
  5. **서버측 delta + run_id 검증** — `/api/progress(conversation_id, after_step, client_run_id)` 3 파라미터. 서버는 `client_run_id` 가 없거나 현재 run_id 와 다르면 `after_step=0` 으로 리셋해 **새 run 의 모든 step 을 한 번에 반환** — 클라이언트는 `runId !== state.progressRunId` 를 `applyProgressPayload` 에서 감지해 캐시를 통째로 교체. `_load_steps_for_run(after_step=N)` 은 `WHERE step_index > N` 을 SQL 레이어에서 걸어 DB 필터링 비용을 O(N) → O(returned) 로 축소.
- 에러 백오프 + 포기: `progressErrorCount` 를 각 예외에서 증가시키고 `errorCount < 3` 이면 `PROGRESS_POLL_ERROR_MS=8000` 으로 재시도, 3회 이상은 `shouldSchedule = false` 로 아예 재스케줄링 중단. 네트워크가 완전히 끊긴 상황에서 지속적으로 실패 요청을 때리지 않는다.
- Verification (정적 검증): (a) `grep -c "setInterval" src/static/app.js` = 0 (고정 주기 루프 제거 확인), (b) 5 개 상수 모두 `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조, (c) 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 를 선언하고 불일치 시 `next_after_step=0` 재설정 조건이 있음 (line 4405-4406), (d) `curl -sk https://127.0.0.1:18080/api/progress?conversation_id=X` HTTP 401 (인증), 로그인 후 HTTP 200 + JSON 스키마 `{steps, status, status_at, step_count, run_id, conversation_id}` 반환.
- Applies to: 장시간(>수초) 비동기 작업을 클라이언트가 실시간 추적해야 하는 모든 웹 UI. `fetch` 폴링 루프를 새로 작성하거나 기존 `setInterval` 패턴을 발견했을 때 전면 적용. 짧은(<1초) 단일 요청에는 과설계이므로 제외.

### LRN-20260422-0012 — SQL 텍스트에서 `schema.table` 을 추출할 때는 반드시 **FROM/JOIN 구간만 slice** 한 뒤 그 안에서만 찾는다
- Source: feature-0003 `_extract_sql_schema_refs` context-aware 수정 (TASK-0040, 2026-04-22)
- Mistake: 기존 구현은 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 단일 regex 로 SQL 전체에서 `x.y` 토큰을 스캔했다. `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a WHERE bb.BattleType = 'X'` 같은 SQL 에서 SELECT 절 / WHERE 절 / ON 절의 **alias.column** 이 전부 `schema.table` 후보로 간주되어 schema refs = `{bb, be, dblog}` 가 되고, Product whitelist=`{dbauth,dbgame,dblog}` 에서 `{bb, be}` 가 허용 외로 판정 → 모든 턴이 `BLOCKED_SCHEMAS=bb,be` 로 거부. TASK-0034 Q4 재수행이 0 턴 성공 상태가 됐다.
- Correct approach: SQL 구문상 `schema.table` 이 나올 수 있는 위치는 명확히 **FROM 절**과 **JOIN 절** 뿐이다. 이 두 키워드 뒤 테이블 리스트 구간만 slice 하고, 그 slice 안에서만 `schema.table` 패턴을 추출한다. Slice lookahead 는 다음 절 키워드 `ON`/`WHERE`/`GROUP BY`/`ORDER BY`/`HAVING`/`LIMIT`/`UNION`/또다른 `JOIN`/`FROM`/`;`/`)`/문장 끝 이전으로 끊는다. 2 단계 스캐너:
  ```python
  _TABLE_LIST_RE = re.compile(
      r"\b(?:FROM|JOIN)\b(.*?)"
      r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
      r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
      re.IGNORECASE | re.DOTALL,
  )
  _INNER_REF_RE = re.compile(
      r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
  )
  ```
  1 단계 (`_TABLE_LIST_RE.finditer`) 로 FROM/JOIN 다음의 테이블 리스트 구간만 뽑고, 2 단계 (`_INNER_REF_RE.finditer`) 로 그 구간 안에서 `schema.table` 을 찾는다. SELECT/WHERE/ON 은 slice 바깥이라 alias.column 이 남더라도 매칭되지 않는다.
- Verification: in-process 15 케이스 (단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 schema / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치. TASK-0034 Q4(7 턴) + Q5(5 턴) 재수행이 모든 턴 HTTP 200 으로 완료.
- Applies to: SQL 텍스트를 비파서 방식으로 스캔해서 security decision 을 내리는 모든 코드. "regex 는 context-free — 문법상 구분이 필요하면 **구간 slice 후 내부 검색**" 이 기본 설계. 단일 단계 regex 로 SQL 문맥을 흉내 내려 하면 alias/hint/CTE/subquery 중 하나에서 반드시 오탐이 난다. 규모가 더 커지면 `sqlparse` 같은 경량 파서 도입을 검토한다.

### LRN-20260422-0013 — 에이전트 작업자 스레드 lifecycle 은 클라이언트 HTTP 연결과 독립이어야 하고, 별도 read-only 복구 경로를 제공해야 한다
- Source: feature-0003 클라이언트 타임아웃 시 Attach/Resume 구현 (TASK-0041, 2026-04-22)
- Pattern: 장시간 LLM agent 작업(우리 환경에서 `AGENT_TIMEOUT_SEC≈300s` × 여러 스텝, 실측 Q4 turn7=364s / 전체 1171s 등) 은 서버에서 `asyncio.to_thread(...)` 로 백그라운드 스레드에 분리되어 실행된다. 이 스레드는 FastAPI 의 `/api/ask` HTTP 요청 객체와 lifecycle 이 묶여있지 않다 — 클라이언트가 `httpx.ReadTimeout` 으로 끊어지거나 브라우저 탭을 닫거나 nginx/Cloudflare 가 504 를 던져도 **서버는 완료까지 계속 진행한다**. 결과도 `AgentMemoryMessages` + `AgentMemorySteps` + `AgentMemoryKv(last_status, last_status_run_id, last_duration_ms, last_error)` 에 정상 기록된다. 그러나 이 자원을 클라이언트가 회수할 read-only 경로가 없으면 "서버는 답했는데 유저는 못 본" 상태가 된다.
- Design: `/api/ask` (쓰기, 슬롯풀) 와 분리된 2 개의 read-only 엔드포인트로 복구 경로를 완성한다.
  1. **`GET /api/ask_status?conversation_id=CID`** — 1-shot 스냅샷. `AgentMemoryKv` 5 키를 단일 쿼리로 읽어 `{is_processing, status, status_at, run_id, step_count, duration_ms, has_answer, answer_preview}` 를 반환. 비용이 낮아 페이지 로드 시 auto-attach 여부 판단에 부담 없이 호출 가능.
  2. **`GET /api/ask_result?conversation_id=CID&run_id=RID&wait=N`** (N ≤ 60, 내부 0.5s interval) — long-poll. `_ASK_TERMINAL_STATUSES={done, error, canceled}` 도달 시 assistant(content + meta + steps_count) 전문 반환, 시간 초과 시 `{timeout:true, run_id}` 만 반환하고 클라이언트가 바로 재호출해 체인할 수 있다.
  - 두 엔드포인트는 기존 `conversation.read.own/any` 권한만 재사용하고, `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과는 완전히 분리되어 **attach 가 새로운 실행을 시작시키지 않는다**. 이것이 "재진입으로 인한 중복 실행" 을 막는 핵심 속성이다.
- Clients: 이 인프라를 활용하는 3 경로가 있다 —
  1. **브라우저 `sendPrompt()` catch 분기**: `/api/ask` 가 실패(`TypeError: Failed to fetch`, `AbortError`, 504, 502, …) 하고 `is_processing=true` 이면 `[요청 취소 / 즉시 답변 / 계속 기다리기]` 3 버튼 다이얼로그를 노출. 선택에 따라 `/api/cancel`·`/api/finalize` 를 호출한 뒤 `/api/ask_result` long-poll 로 이어받는다.
  2. **브라우저 boot-time auto-attach**: `initializeWorkspace()` 말미에 현재 대화의 `is_processing` 을 확인하고 true 면 다이얼로그 없이 자동 attach — 페이지 새로고침/탭 닫기 이후 재접속 시에도 이전 요청 결과를 자동 수신.
  3. **테스트 러너 `_attach_run`**: `httpx.ReadTimeout` 분기에서 `{"error":"client-read-timeout"}` 실패로 끝내지 않고 `ask_status` → `ask_result` long-poll 로 해당 턴을 정상 기록. turn dict 에 `attached_after_timeout=True` + `attach_verdict` 를 남겨 사후 분석이 가능.
- Anti-pattern (주의): Server-Sent Events / WebSocket 이 "더 현대적" 해 보이지만, 복구 경로의 목적은 "이미 있는 최종 상태를 꺼내오는 것" 이지 real-time stream 이 아니다. 기존 `AgentMemoryKv` + long-poll 2 엔드포인트만으로 완결되므로 프록시·TLS 종단·재접속 관리가 필요한 stream 인프라를 새로 세우지 않는다.
- Verification: Q4 1171s + Q5 251s 모두 HTTP 200 으로 완료 (단일 턴이 960s 를 안 넘어 attach 가 실제 발동되지는 않았지만, 인프라는 in-container 에서 `ask_status`(38ms)/`ask_result` 동작 확인). `/api/ask_status`/`/api/ask_result` 401 응답으로 라우팅 정상, terminal 상태 대화에 대한 스냅샷 38ms, 브라우저 JS `node --check` OK.
- Applies to: 장시간 LLM/batch 작업을 HTTP 로 시작시키는 모든 웹 UI. 작업자 lifecycle 을 HTTP 연결과 독립시키고, 완료된 작업 결과를 read-only 로 **재조회할 수 있는 별도 경로** 를 설계 초기부터 포함시킨다. 기존 진행 상태 저장소 (`AgentMemoryKv`/`Messages`/`Steps`) 가 있다면 그 위에 얇은 엔드포인트만 더 얹는다 — 새 상태 저장소를 만들지 않는 것이 핵심.

### LRN-20260506-0014 — "엔티티 생성 시점" 은 사용자 의도가 확정되는 시점에 lazy 로 — client-side pending state 패턴
- Source: TASK-0048 (REQ-20260506-0001) "새 대화" lazy 화 (2026-05-06)
- Pattern: UI 의 "신규 X 만들기" 버튼이 즉시 backend row 를 발급하면 사용자가 의도를 확정하지 않은 채로 빈 row 가 누적된다. 해법은 (1) 버튼 클릭 시 client-side pending state (`state.pendingNewConversation` + sentinel ID `__pending__`) 만 진입해 사이드바 placeholder 표시, (2) 첫 의미 있는 행위 (메시지 전송 / 폼 제출 / 저장) 시 backend 의 lazy creation path 를 호출, (3) 응답 ID 를 client 가 채택해 placeholder → 실 entity 로 전환. backend 는 기존 lazy creation path (e.g. `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)`) 가 이미 있는 경우가 많아 추가 endpoint 가 불필요하다. 사용자의 직전 의도 (TASK-0048 의 경우 product_mode/product_id) 는 첫 행위의 body 에 hint 로 첨부해 backend 가 cid 발급 직후 적용한다.
- Anti-pattern (주의): "버튼 클릭 = 즉시 backend POST" 모델은 단순하지만 사용자가 실수로 누르거나 마음을 바꾸면 빈 entity 가 남는다. 또한 destructive cleanup (NOT EXISTS subquery 로 빈 row 삭제) 으로 보정하면 §12.1 사람 승인이 필요한 작업으로 격상된다 — 신규 누적 차단을 client-side lazy 로 해결하는 것이 비용/위험이 가장 낮다.
- Trade-off: lazy create 단계 호출이 timeout/네트워크 오류로 실패하면 backend 가 cid 를 만들었는데 client 는 모르는 buried orphan 케이스가 1 발생 가능. 이는 사이드바 새로고침으로 visible 하게 되므로 데이터 유실은 아니지만 사용자 혼란 가능 — 실패 토스트가 "재시도/사이드바 새로고침" 을 명시해 회복 경로를 안내한다.
- Applies to: 모든 "신규 entity 생성" UX. 특히 LLM 요청처럼 시간이 오래 걸리거나 사용자가 의도를 확정 전에 버튼만 눌러볼 가능성이 있는 흐름. PATCH race 가드 같은 mutation 보호 로직과는 자연스럽게 호환된다 (cid 가 발급되기 전엔 PATCH 가 불가하므로).

## Category: quirk

### LRN-20260326-0001 — `repo/.env`의 운영 의미는 원본 `mysql_ai/.env` 기준으로 보존
- Source: ADR-0014
- Quirk: 본 저장소는 `mysql_ai` 원본의 **템플릿 이관 사본**이다. `.env`의 포트·모델·DB 자격증명은 원본과 같아야 하며, 동시 기동은 하지 않는다.
- Mitigation:
  - `.env.example`는 대체 기본값이 아니라 민감값 제거된 샘플로 취급한다.
  - 원본 의미와 다르게 수정할 필요가 생기면 ADR을 거쳐 승격한다.

### LRN-20260326-0002 — 런타임 산출물은 `../../artifacts/`로만 쓴다
- Source: ADR-0013
- Quirk: `shared/`는 공용 **코드** 예약 영역이며 런타임 산출물(로그/세션/데이터 파일)을 여기에 쓰면 Git 추적 대상이 된다.
- Mitigation: 모든 산출물은 `../../artifacts/` 하위로 쓰고, feature 코드는 그 경로만 참조하도록 helper를 경유한다.

### LRN-20260506-0001 — docker compose v5.1.1 + buildx v0.31.1 는 build 후 provenance metadata file 처리에서 EXIT=1 race 가 있다
- Source: TASK-0048 운영 검증 (2026-05-06)
- Quirk: `docker compose build <svc>` 또는 `compose up --build <svc>` 가 `#15 exporting to image` + `#15 naming to docker.io/library/...` 까지 정상 완료한 뒤 `#16 resolving provenance for metadata file` 단계에서 `open /tmp/.tmp-compose-build-metadataFile-<UUID>.json<NNNN>: no such file or directory` 메시지로 EXIT=1 종료한다. image 자체는 새 sha 로 정상 빌드되어 있다 — compose 측이 임시 파일 path 에 random suffix 를 잘못 붙여 stat/open 이 실패하는 회귀로 보인다 (정상이라면 `*.json` 으로 끝나야 하는데 `*.json<NNNN>` 형태). `--provenance=false`, `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, `COMPOSE_BAKE=true/false` 모두 효과 없음 — compose 본체 경로의 race.
- Mitigation: Makefile 에 `dc-build` reusable 타깃 (SERVICE 변수 인자) 을 추가하고, build 명령을 임시 로그에 캡처해서 EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화한다. 그 외 빌드 오류 (Dockerfile syntax, RUN 단계 실패 등) 는 그대로 전파된다. `web` 타깃은 `up -d --build web` 을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리해 image 를 미리 만들고 컨테이너 교체만 별도 단계로 수행한다.
- Applies to: `make web` 류의 image 빌드 + 기동 명령. 향후 docker compose 또는 buildx 가 fix 되면 가드를 제거할 수 있다 — 가드는 `compose-build-metadataFile` 문자열 매칭으로만 race 를 흡수하므로 race 가 사라지면 자연스럽게 일반 build 경로로 흐른다.
- Verification: `make web` EXIT=0, 로그에 "[make] note: ... provenance metadata file race 우회 ... compose EXIT=1 무시" 출력 후 `Container repo-web-1 Recreate/Recreated/Started` + `Web UI (HTTPS): https://localhost:18080`. `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 새 코드 반영 확인.

### LRN-20260604-0001 — WSL2 에서 Windows Chrome CDP 는 항상 127.0.0.1 에만 바인딩된다 (relay 필수)
- Source: feature-0008-windows-browser-testing spike (2026-06-04)
- Quirk: WSL 에서 Windows Chrome 을 `--remote-debugging-port=9222 --remote-debugging-address=0.0.0.0` 로 띄워도, 최신 Chrome 은 보안상 `--remote-debugging-address` 를 무시하고 **127.0.0.1 에만 CDP 를 바인딩**한다 (`netsh netstat` 으로 `TCP 127.0.0.1:9222 LISTENING` 확인). NAT 모드 WSL2 는 Windows loopback 에 직접 도달할 수 없어, 단순히 게이트웨이 IP(`172.x.x.1:9222`)로 접속하면 실패한다. 또한 WSL 경로(UNC) cwd 에서 `cmd.exe` 를 호출하면 "UNC 경로는 지원되지 않습니다" 경고를 **stderr** 로 내보내며 cwd 를 C:\Windows 로 바꾼다 — stdout 파싱 시 마지막 유효 라인만 취하고 cwd 를 `/mnt/c` 로 고정해야 안전하다.
- Mitigation: (1) Chrome 은 127.0.0.1 바인딩 그대로 두고, Windows 측 `netsh portproxy` relay 를 **vEthernet(WSL) IP 한정** 으로 세워 `<wsl-host>:9223 → 127.0.0.1:9222` forward (0.0.0.0 금지 — CDP 는 무인증이라 LAN 노출 시 브라우저 탈취). 또는 mirrored networking(`.wslconfig`)으로 loopback 공유 — 인바운드 hole 불요. (2) Playwright `connect_over_cdp(http_endpoint)` 는 endpoint host 로 ws host 를 정규화하므로 relay 경유 가능. `--remote-allow-origins` 는 `*` 대신 loopback+relay 의 구체 origin 으로 scope (DNS rebinding 방어 유지).
- Applies to: WSL2 에서 실제 Windows 브라우저를 CDP 로 구동하는 모든 작업. `bin/win-browser.py` + `bin/WIN-BROWSER-SETUP.md` 참조.

## Category: preference

### LRN-20260326-0001 — `AGENTS.md`가 정책 정본, `CLAUDE.md`는 참조 shim
- Source: ADR-0002
- Preference: 저장소 수준 AI 정책은 `AGENTS.md` 하나로만 관리한다. `CLAUDE.md`는 호환성을 위해 유지하되 정책 내용을 중복 서술하지 않는다.

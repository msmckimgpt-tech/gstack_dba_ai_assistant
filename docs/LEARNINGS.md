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

### LRN-20260414-0001 — GitHub 자동화 계약은 기계 판독 파일로 먼저 고정
- Source: ADR-0017
- Pattern: 공개 브랜치 규칙, provider 라벨, 상태 라벨, 커밋 형식, required checks가 문서와 워크플로에 중복되면 쉽게 드리프트가 생긴다. `.github/automation-contract.json`을 정본으로 두고, 쉘 스크립트와 `policy-contract`가 이 파일을 읽게 하면 재발을 줄일 수 있다.
- Applies to: `.github/workflows/*`, `.github/scripts/*`, `docs/GITHUB_AUTOMATION.md`, `CONTRIBUTING.md`, `AGENTS.md`

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

## Category: preference

### LRN-20260326-0001 — `AGENTS.md`가 정책 정본, `CLAUDE.md`는 참조 shim
- Source: ADR-0002
- Preference: 저장소 수준 AI 정책은 `AGENTS.md` 하나로만 관리한다. `CLAUDE.md`는 호환성을 위해 유지하되 정책 내용을 중복 서술하지 않는다.

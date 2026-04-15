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

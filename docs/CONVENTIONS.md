---
doc_type: CONVENTIONS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.53.2
domain: [workflow, context]
ai_read_priority: 3
---

# Conventions

## 1. 네이밍
- 기능 폴더: `feature-<nnnn>-<purpose>`
- 문서 파일명: 대문자 고정
- 테스트 파일명: 대상 코드와 대응되도록 유지
- 산출물 폴더명: 목적 중심으로 명확하게 작성
- 런타임 산출물은 이 문서 기준 `../../artifacts/<purpose>` 패턴을 사용

## 2. 문서 작성 규칙
- 현재 상태 문서는 최신 상태만 유지한다.
- 이력 문서는 append-only를 기본으로 한다.
- 불확실한 내용은 단정형 문장으로 쓰지 않는다.
- 각 문서 상단에는 메타데이터 블록을 둔다.

## 3. 추적성 규칙
문서와 코드에 아래 식별자 사용을 권장한다. **spec 앵커 `REQ`/`AC`/`ADR`/`TEST` 는
timestamp+slug 형식으로 통일** (정본 AGENTS.md §6·§13.1, ADR-20260625T023049-spec-anchor-timestamp-id —
병렬 cycle 머지 시 순번 충돌 제거). 기존 순번 `*-XXXX` 도 유효(fallback·기존 항목, 소급 재번호 없음).
- `REQ-<YYYYMMDDTHHMMSS>-<slug>` (cycle 당 1개라 날짜형 `REQ-<YYYYMMDD>-<slug>` 도 허용; 순번 `REQ-XXXX` fallback)
- `AC-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (부모 REQ 의 timestamp+slug 공유, 다수 AC 는 `-<n>`; 순번 `AC-XXXX` fallback)
- `CHG-YYYYMMDD-XXXX` (또는 timestamp+branch `CHG-<YYYYMMDDTHHMMSS>-<branch>`)
- `REV-YYYYMMDD-XXXX` (또는 timestamp+branch `REV-<YYYYMMDDTHHMMSS>-<branch>`)
- `ADR-<YYYYMMDDTHHMMSS>-<slug>` (순번 `ADR-XXXX` fallback·기존 항목)
- `TEST-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (순번 `TEST-XXXX` fallback)

## 4. 커밋 및 변경 단위
- 하나의 의미 있는 작업 단위 안에서 코드와 문서를 함께 갱신한다.
- 서로 무관한 변경은 가능한 한 분리한다.
- 대규모 구조 변경은 결정 문서와 함께 진행한다.

## 4.1 경로 규칙
- Git-tracked 문서와 설정에는 호스트 파일시스템 절대경로를 사용하지 않는다.
- 문서의 파일 참조는 현재 문서 위치 기준 상대경로를 사용한다.
- Docker 컨테이너 내부 경로(`/app`, `/shared`, `/certs`, `/etc/mysql/...`, `/var/lib/mysql`)는 절대경로를 유지한다.

## 5. 주석 및 보고
- 코드 주석은 구현 의도와 제약을 설명하는 데 사용한다.
- 문서는 사람과 다른 AI가 빠르게 맥락을 파악하도록 작성한다.
- `REPORT.md`는 간결하고 실행 가능한 정보 위주로 유지한다.
- 검증 범위가 제한적이면 `REPORT.md`와 `TEST.md`에 명시한다.

## 6. 테스트 프레임워크 및 실행
- 프로젝트의 테스트 실행 방법은 `PROJECT.md` §8에서 정의한다.
- 각 기능의 `tests/` 폴더에는 실행 가능한 테스트 코드를 둔다.
- 수동 테스트 시나리오는 `TEST.md`에 기록한다.
- 테스트 결과는 `TEST.md` §3 Test Run History에 append-only로 기록한다.
- 구조/기동 검증과 도메인 검증은 별도 항목으로 구분한다.

### 6.1 테스트 종류 및 정합성 의무 (AGENTS.md §8 연동)

각 작업자 AI는 코드 추가·수정 후 **단위 테스트 + 전체(통합) 테스트** 두 단계를 모두 완료해야 한다.

| 종류 | 위치 | 의무 |
|------|------|------|
| 단위 테스트 | `unit/<feature-id>/tests/` | 추가·수정 로직에 대응하는 테스트 작성 후 실행. PASS 필수 |
| 전체/통합 테스트 | `repo/tests/integration/` | 기능 간 인터페이스·공유 모듈 변경 시 작성 후 실행. 미작성 시 `TEST.md §4`에 사유 기록 |

- 단위 테스트 FAIL 상태로 완료 선언하지 않는다.
- 통합 테스트가 미작성인 영역은 `unit/<feature-id>/docs/TEST.md` §4 Untested Areas에 명시한다.
- 상세 정책은 `../AGENTS.md §8`(구현 정책)을 따른다.

## 7. AI 에이전트 매핑 규칙
- 이 저장소의 정본 정책 파일은 `../AGENTS.md`이다.
- Claude Code: `../CLAUDE.md` → `../AGENTS.md` 참조
- 다른 도구용 호환 파일이 필요하면 AGENTS.md 참조 파일로만 둔다.
- AI 컨텍스트 제외: `../.aiignore` — AI가 읽지 않을 파일 패턴을 정의한다 (AGENTS.md §10.4 참조).

## 8. 환경변수 및 설정 관리

### 8.1 기본 원칙
- 프로젝트 루트에 `.env.example`을 두고 모든 환경변수의 키와 설명을 유지한다.
- 기능별 설정이 필요하면 `src/config/` 디렉토리에 계층 구조를 둔다:
  - `config/default.env` — 공통 기본값 (커밋 대상)
  - `config/profiles/<profile>.env` — 프로필별 오버라이드 (커밋 대상)
  - `config/credentials/*.cnf` — 자격증명 (git-ignored, `*.example`만 커밋)
- 환경변수 이름은 `SCREAMING_SNAKE_CASE`를 사용한다.
- 카테고리가 있으면 접두사로 구분한다 (예: `MYSQL_*`, `AGENT_*`, `WEB_*`).
- 환경변수 추가/변경 시 `.env.example`과 `MODIFY.md`를 동시에 갱신한다.
- 환경변수의 의미 변경(이름 유지 + 동작 변경)은 `REVIEW.md`에 근거를 기록한다.

### 8.2 설정 파일 주석 표준
설정 파일(`.env`, `.cnf` 등)의 변수에는 다음 기준에 따라 주석을 작성한다.
AI 작업자가 변수의 역할과 허용 범위를 즉시 파악할 수 있도록 하는 것이 목적이다.

#### 파일 헤더
파일 최상단에 아래 내용을 배너 주석으로 작성한다.
- 파일의 목적 (무엇의 기본값인지)
- 상속/오버라이드 관계 (어떤 파일이 이 값을 덮어쓰는지)
- 민감정보 경고 (자격증명을 여기에 두지 말 것)

```bash
# -----------------------------------------------------------------------------
# <component> shared defaults
#
# 이 파일은 모든 profile이 공통으로 상속하는 기본값입니다.
# 인스턴스별 차이는 ./profiles/<name>.env 에서 override 하세요.
# 비밀번호 같은 민감정보는 여기에 두지 말고 ./credentials/ 에만 두세요.
# -----------------------------------------------------------------------------
```

#### 섹션 구분
관련 변수를 의미 단위로 묶고, 배너 주석 안에 `[카테고리명]`을 표기한다.

```bash
# -----------------------------------------------------------------------------
# [Storage roots]
# ...변수 설명...
# -----------------------------------------------------------------------------
BACKUP_ROOT_DIR="/backup"
STATE_ROOT_DIR=".state"
```

#### 변수별 주석 — 필수 항목
모든 변수에 최소한 아래 항목을 포함한다.

| 항목 | 설명 | 필수 |
|------|------|------|
| **변수명** | 주석 첫 줄에 변수명을 명시 | O |
| **역할 설명** | 이 값이 무엇을 제어하는지 1~2줄로 기술 | O |
| **허용값 (열거형)** | `허용값:` 키워드 뒤에 파이프(`\|`)로 구분하여 나열 | 열거형일 때 O |
| **각 옵션 설명** | 열거형의 각 값이 어떤 동작을 하는지 기술 | 열거형일 때 O |
| **단위** | 숫자값의 단위 명시 (초, 일, GB 등) | 숫자형일 때 O |
| **경로 해석** | 상대경로 기준점, 절대경로 여부 | 경로형일 때 O |
| **템플릿 토큰** | 지원되는 치환 토큰 목록 | 템플릿일 때 O |
| **기본 동작** | 빈 값이나 생략 시 동작 | 선택 |

#### 변수별 주석 — 유형별 예시

**열거형 (enum)**
```bash
# LOW_SPACE_POLICY
#   허용값: warn | block | auto_shrink
#   warn       : 경고만 남기고 계속 진행
#   block      : 임계치 미만이면 즉시 중단
#   auto_shrink: temp → logs → archive 순으로 자동 정리 후 재시도
LOW_SPACE_POLICY="auto_shrink"
```

**숫자형 (단위 필수)**
```bash
# RETENTION_DAYS
#   archive/binlog 보관 기준 일수입니다.
RETENTION_DAYS="35"
```

**경로형 (해석 기준 필수)**
```bash
# ARCHIVE_METADATA_DIR
#   sidecar metadata 저장 경로입니다.
#   상대경로면 BACKUP_ARCHIVE_DIR 기준으로 해석됩니다.
ARCHIVE_METADATA_DIR=".metadata"
```

**템플릿형 (토큰 목록 필수)**
```bash
# BACKUP_FILENAME_TEMPLATE
#   archive 파일명 base template입니다. 확장자 .tar.zst 는 자동으로 붙습니다.
#   지원 토큰:
#     {profile}   profile 이름
#     {type}      full | incr | partial
#     {date}      YYYYMMDD
#     {timestamp} YYYYMMDDTHHMMSSZ
BACKUP_FILENAME_TEMPLATE="{profile}_{type}_{date}_{time}"
```

**불리언형 (각 값의 동작 명시)**
```bash
# TEMP_CLEANUP_ON_SUCCESS
#   1: 성공한 명령 이후 TTL 지난 temp를 자동 정리합니다.
#   0: 성공 후에도 자동 temp cleanup을 하지 않습니다.
TEMP_CLEANUP_ON_SUCCESS="1"
```

## 9. 용어집

| 용어 | 정의 |
|------|------|
| unit | 기능 단위 작업 폴더 (`../unit/<feature-id>/`) |
| feature-id | 기능 폴더의 고유 식별자 |
| source of truth | 특정 사실의 정본 문서 |
| rewrite | 문서 전체를 최신 상태로 덮어쓰는 수정 정책 |
| append-only | 기존 항목을 수정/삭제하지 않고 새 항목만 추가하는 수정 정책 |
| runtime artifacts | 로그, 세션, MySQL 데이터, 인증서처럼 `../../artifacts`에 저장되는 파일 |
| execution root | `docker-compose.yml`, `Makefile`, `.env`가 위치한 저장소 실행 루트 |
| .aiignore | AI 컨텍스트 제외 패턴 파일. `.gitignore` 문법을 따르며, 매칭된 파일을 AI 읽기 대상에서 제외 |
| playbook | 반복 작업 절차를 표준화한 문서. `playbooks/` 디렉토리에 `PB-NNNN` 형식으로 관리 |
| plan-review | 비사소한 작업 전 AI가 구현 계획을 작성하고 위험도에 따라 사람 승인을 거치는 프로토콜 |
| worktree | Git worktree를 활용한 물리적 작업 디렉토리 분리. 병렬 AI 작업 시 권장 |
| LEARNINGS.md | AI 학습 기록 문서. 실수, 패턴, 특이사항, 선호를 append-only로 누적 |
| CODEBASE_MAP.md | 저장소 파일 구조와 주요 진입점을 AI가 빠르게 참조할 수 있도록 요약한 문서 |
| DQA Connect | 개인 머신 AI 를 이 서비스에 연결하는 클라이언트의 제품 명칭. 명칭 정본은 `shared/dqa_identity.py` **4축** — 설치·패키징 층에서 사람이 읽는 `APP_NAME`(`DQA Connect`) · 창·트레이·대화상자·바로 가기에 뜨는 `DISPLAY_NAME`(`DQA`, 사용자 결정 2026-09-04 — 설치 폴더·레지스트리 키는 `APP_NAME` 그대로 두어 업그레이드 경로를 보존한다) · URL 스킴 = 머신 전역 네임스페이스 `SCHEME`(`dqa-connect`) · 역-DNS `APP_ID`(`com.masangsoft.dqa-connect`). 축마다 지배하는 규약이 달라 한 토큰으로 합치지 않는다. 옛 이름 `mysql-ai-bridge` 는 하위호환 별칭 없이 하드 컷오버(2026-09-03) — 소스에 리터럴로 적지 않고 정본을 읽는다(`feature-0043/tests/test_name_ssot.py` 가 강제) |

## 10. Admin Console UI 일관성

관리 콘솔 (`feature-0003-agent-web-ui` 의 `admin.html` / `admin.js` + `admin/` pane 모듈 / `css/` 7파일 — 구 `styles.css` 는 feature-0038 Cycle 1 에서 분할·소멸) 의 카테고리별 UI (Accounts, Roles, Products, 이후 추가될 모든 카테고리) 는 본 섹션의 정책을 따른다.

상세 컴포넌트 명세 · HTML · CSS · JS contract · keyboard map · a11y · cross-page selection · optimistic rollback · confirm · RBAC partial-failure UI · runtime assertion 은 `../unit/feature-0003-agent-web-ui/docs/DESIGN.md` 정본을 따른다. 본 섹션은 project-level 강제 정책만 명시한다.

### 10.1 다중선택 (multi-select) 적용 룰

카테고리가 다음 조건을 모두 만족하면 다중선택을 **의무 지원** 한다:
1. 동질 row entity 리스트 (한 row = 한 entity 인스턴스).
2. 일괄 적용 가치가 있는 작업 (활성/비활성, 삭제, 내보내기 등) 이 ≥ 1 개 존재.
3. row 당 별도 detail panel 또는 inline form 이 있다.

위 조건을 만족하지 않는 카테고리 (단순 viewer, dashboard, 비교 view 등) 는 다중선택 면제. 면제 카테고리는 row-hover inline action 패턴을 사용한다 (Vercel deployments 패턴).

### 10.2 DOM anchor 표준

모든 다중선택 카테고리는 동일한 5단 구조를 따른다:

```
<section class="admin-pane">
  <header class="admin-pane-head">
    <div>... drawer-label + h2 ...</div>
    <div class="admin-pane-head-right"><!-- primary action ONLY --></div>
  </header>
  <div class="admin-list-detail">
    <div class="admin-list-col">
      <div class="admin-list-toolbar">      <!-- 검색 + 필터 -->
      <div class="admin-list-head">         <!-- select-all + count -->
      <div class="admin-list">              <!-- row list -->
      <div class="admin-bulk-actions">      <!-- ★ bulk toolbar 표준 위치 (list 직하단) -->
      <div class="admin-list-pagination">   <!-- 페이지네이션 -->
    </div>
    <div class="admin-detail-col"></div>
  </div>
</section>
```

**불변 규칙:**
- `.admin-pane-head-right` 는 **카테고리 primary action 전용** (`+ 새 X` / 카테고리-scope navigation). bulk toolbar 또는 동적 action 슬롯으로 사용 금지.
- Bulk toolbar 는 **항상 `.admin-bulk-actions` 컨테이너** 에 위치하며, list 직하단 sticky 로 배치한다. 다른 위치 (floating, header, footer fixed 등) 채택은 본 컨벤션의 명시적 개정을 통해서만 가능.
- 거부 근거: Notion 식 "헤더 morph" 패턴 (헤더 자체가 bulk toolbar 로 변형) 은 본 컨벤션이 명시 거부. 이유는 `.admin-pane-head-right` 슬롯의 semantic 단일성 (primary action 전용) 을 깨뜨리기 때문.

### 10.3 표준 자료구조

- 다중선택 상태: `adminState.<entity>Selected: Set<KEY>` 형태.
  - KEY 타입은 entity 의 wire-format 기본형 (정수 ID → `Number`, key string → `String`). 한 entity 내에서 통일.
- 신규 미저장 row 는 multi-select checkbox `disabled` + Set 에서 자동 제외.
- 데이터 reload 후 invariant: `<entity>Selected = <entity>Selected ∩ visibleIds` (stale entry 자동 제거).
- 페이지 이동 시 Set **보존** (cross-page selection). 페이지 1·2 합산 count 가 ≥ 2 페이지에 걸치면 banner 노출 (상세는 DESIGN.md §6).

### 10.4 단위 어휘 표준

| Entity 종류 | 단위 |
|---|---|
| 사람 (Accounts, Members 등) | 명 |
| 시스템 entity (Roles, Products, Conversations 등) | 개 |

선택 count label 형식: `{N}{단위} 선택됨`.

### 10.5 신규 카테고리 추가 체크리스트

새 admin 카테고리 (예: future `Settings`, `Audit Log`, `Integrations`) 를 추가할 때 다음을 차례로 평가한다:

- [ ] §10.1 적용 룰 — 다중선택 의무 카테고리인지 판정
- [ ] §10.2 DOM anchor 표준 구조 사용
- [ ] §10.3 자료구조 (Set, invariant, cross-page) 적용
- [ ] §10.4 단위 어휘 따름
- [ ] feature-0003 `DESIGN.md` 의 컴포넌트 / a11y / keyboard / confirm / RBAC partial-fail / runtime assertion 적용
- [ ] 적용 후 `assertBulkBarContract(<entity>)` 가 통과하는지 brower devtools 또는 e2e 에서 확인

위 체크리스트가 PASS 되지 않은 카테고리 추가는 PR 단계에서 사람 리뷰가 반려한다.

### 10.6 화면별 권한 섹션·정렬 정책 (REQ-20260512-0002)

권한 (Permission) 리스트는 백엔드 단일 `PERMISSION_DEFINITIONS[*].group` (`console` / `account` / `role` / `quota` / `product` / `datasource` / `kb` / `conversation_own` / `conversation_any` / `attachment` / `audit` / `settings` / `misc`) 으로 분류되지만, **사용자가 보는 정렬·섹션 구조는 화면 맥락에 따라 다르게 적용한다.** 같은 정렬을 두 화면에 공유하면 한쪽은 항상 핵심 권한이 묻힌다.

#### 화면별 2단 section

| 화면 | 시각 | 섹션 순서 (상→하) |
|---|---|---|
| 작업 화면 (`index.html` + `app.js`) | 본인이 보유한 권한을 보여주는 자기 자신 시점 | **운영 권한** (`conversation_own`, `conversation_any`, `product`, `model_access`, `attachment`) → **관리 권한** (`console`, `account`, `role`, `quota`, `datasource`, `audit`, `kb`, `settings`) → **기타** (`misc`) |
| 관리 콘솔 (`admin.html` + `admin.js`) | 타인의 권한을 배치하는 관리자 시점 | **관리 권한** (`console`, `account`, `role`, `quota`, `product`, `datasource`, `audit`, `kb`, `settings`) → **운영 권한** (`conversation_own`, `conversation_any`, `product_access`, `model_access`, `attachment`) → **기타** (`misc`) |

> TASK-0073: `audit` group 은 두 화면 모두 "관리 권한" 묶음에 합류한다. 작업 화면은 본인 `audit.read.own` 보유 여부에 따라 placeholder 만 (실 entry point 는 admin 콘솔). 관리 콘솔은 audit.read.own / .any / .export / .purge 4 권한이 모두 grid 에 노출된다.
>
> TASK-0094 Sprint 1 Phase 12: `attachment` group 신설 (8 group → 9 group). 첨부 sandbox SQL 실행 권한 (`attachment.execute_sql_on.{own,any}`) 이 본 group 에 등재. `conversation.attachment.*` 4 권한은 group="conversation" 유지 (대화 흐름의 일부). 작업 화면 + 관리 콘솔 모두 운영 권한 묶음에 합류.
> TASK-0095: `settings` group 신설 — 전역 시스템 프롬프트 (`system_prompt.global.*`). 작업 화면/관리 콘솔 모두 관리 권한 묶음에 합류 (운영자 한정).
> TASK-0269: 구 `conversation` group 을 **`conversation_own`(내 대화 권한) / `conversation_any`(전체 대화 권한)** 2 group 으로 분리. `conversation.*` 권한 중 `.any` 접미는 `conversation_any`, 그 외(create/ask/list.own/`*.own`/share.create + `conversation.attachment.*.own`)는 `conversation_own`. 권한 code·enforce 불변(group=UI 분류 메타). 각 group 내 종속은 "목록 조회"(`list.own`/`list.any`) 게이트 카테고리 — list.own/list.any 루트, 동작 권한(create 포함, perm-category-hier 2026-07-14)은 해당 group 의 list 를 부모로(`.any→.own` 1:1 종속 폐기).
> **perm-atomic-split (Critical §12.3, 사용자 승인 2026-07-15, SECURITY.md §22.4)**: 권한의 최소 단위를 원자화 — 사전 4종(용어/ENUM/테이블/컬럼)×{read,create,update,delete}·product/datasource {create,update,delete(,test)} 신설, 엔드포인트 enforcement 액션별 전환. **레거시 묶음 7종(kb.ingest.manual·metadata.*.manage·product.manage·datasource.manage)은 두 화면 권한 grid 에서 숨긴다**(`LEGACY_BUNDLE_PERMISSIONS`, BE/FE parity 테스트) — 코드·기존 grant·묶음→원자 transitive 함의(개별 DENY 우선)는 하위호환 안전망으로 유지. 검수(승급·거부)는 단일 단위 유지 + 원본 사전 read 하위 종속. 서브탭 진입 게이트 = read.
> **perm-category-hier (Critical §12.3, 사용자 승인 A안 2026-07-14, SECURITY.md §22)**: 관리 권한 section 을 관리 콘솔 좌측 nav 카테고리와 정합하는 **카테고리 '접근' 계층**으로 재구성. 신규 카테고리 접근 5종 `console.{account,product,audit,kb,system}.access`(= 각 카테고리 최상위 조회 게이트, `console.access` 하위)가 도입되고, 같은 카테고리의 모든 권한(탭 조회 → 추가/수정/삭제 → 승인/작동)은 그 접근 권한 하위로 재귀 종속된다. GroupName 재배치(code·enforce 불변): `console.usage.read`·`console.aiops.read`·`conversation.archive.read.any` → `audit`(감사 카테고리 4개 탭 조회 권한 통합), `insight.reset` → `product`(실행 표면=제품 상세). group 라벨 `kb`="지식베이스"(구 "지식베이스(KB) 검수"). 탭 노출은 `canSeeTab = 카테고리 접근(AND) && 탭 권한(OR)`(`admin.js` `ADMIN_TAB_CATEGORY_ACCESS`). 기존 배포는 `_backfill_console_category_access_v1` 1회 backfill 로 접근 무손실.

#### 정합 규칙

- 백엔드 group 키 (`console` / `account` / `role` / `quota` / `product` / `datasource` / `kb` / `conversation_own` / `conversation_any` / `product_access` / `model_access` / `attachment` / `audit` / `settings` / `misc`) 가 진실의 근원. FE 의 section 정의는 group 키를 묶기만 한다.
- **관리 권한 section 의 group 순서는 관리 콘솔 좌측 nav 카테고리 순서와 정합한다** (perm-category-hier): `console` → 계정 카테고리(`account`·`role`·`quota`) → 제품 카테고리(`product`·`datasource`) → `audit`(감사) → `kb`(지식베이스) → `settings`(시스템).
- 작업 화면은 사용자가 그 section 안의 어느 group 권한도 보유하지 않으면 **section 자체를 미렌더**한다. 특히 일반 사용자의 "관리 권한" section 은 자동 hide.
- 관리 콘솔은 사용자(관리자) 가 보유한 권한과 무관하게 **모든 section 을 항상 표시**한다. 관리자가 배치 가능한 권한 전체를 보여주는 grid 이기 때문이다.
- 두 화면의 section 정의는 코드 상수 1 곳에서 한다: 작업 화면 = `app.js` 의 `WORK_SCREEN_PERMISSION_SECTIONS`, 관리 콘솔 = `admin.js` 의 `ADMIN_PERMISSION_SECTIONS`.
- 새 group 키가 백엔드에 추가되면 위 두 상수에 명시적으로 매핑한다. 매핑이 빠지면 "기타" section 으로 fallback 한다 (자동, but 권장 아님).
- group 키별 한글 label (`console`="관리 콘솔", `account`="계정", `role`="역할", `quota`="LLM 사용 한도", `datasource`="데이터소스", `kb`="지식베이스", `conversation_own`="내 대화 권한", `conversation_any`="전체 대화 권한", `product`="제품"(관리 콘솔은 "제품 관리"), `model_access`="모델 사용"(관리 콘솔은 "모델 사용 (작업 화면)"), `attachment`="첨부", `audit`="감사", `settings`="시스템 설정", `misc`="기타") 은 두 화면에서 동일하게 유지한다.

#### 동적 권한 (`product.access.<key>`, `model.access.<value>`, `system_prompt.*`)

- `product.access.<key>` (dynamic, IsDynamic=1) 는 백엔드에서 `group="product"` 로 들어오므로 두 화면 모두 자동으로 product 섹션에 합류한다.
- **`model.access.<value>` (dynamic, IsDynamic=1, `group="model_access"`) — model-access-rbac(2026-07-28, Critical §12.3, 사용자 승인)**:
  계정/역할별로 작업 화면 대화에서 **선택 가능한 LLM 모델**을 통제한다. `shared/model_catalog.PUBLIC_API_MODEL_OPTIONS`
  순회로 부트스트랩이 권한 row 를 seed 하며(`_ensure_model_access_permissions`), 코드 namespace 는
  `model_catalog.model_permission_code(value)` 가 SSOT 다. 집행은 `/api/ask` **단일 choke-point**
  (`_account_has_model_access` → 403)이고 표시는 `/api/api-vault/options` 의
  `_filter_models_for_account_access` 가 담당한다(표시·집행 동시 닫힘).
  · **기본 부여 = 전 역할**(사용자 결정 2026-07-28 — 배포 무회귀). grant 는 권한 row 가 **새로 생성된
    순간에만** 수행한다 — 매 부트스트랩 re-grant 하면 관리자의 해제를 재기동이 조용히 되살린다
    (제품 권한 `DefaultRoleAccess=1` 경로와 의도적으로 다른 지점).
  · `product_access` 와 달리 전용 subcatalog UI 가 없고 **일반 권한 row 로 렌더**된다 → admin.js
    `groupedPermissions` 의 `excludeDynamic` 은 `group === "product_access"` 로 좁혀 둔다.
  · API 토큰(feature-0023)은 `model.access.*` 를 **scope allowlist 면제**로 다룬다(scope=동작 축,
    모델=계정 역할 축). 통제는 계정 권한 + 절대 denylist + ask() 게이트가 유지한다.
- `system_prompt.*` 코드는 백엔드 정의가 `group="product"` 이고, 작업 화면 FE 의 `permissionGroupOf()` 는 prefix-only 추론이므로 `system_prompt.` 접두사를 명시적으로 `product` 로 매핑한다 (app.js).

#### 점진적 세분화 (progressive disclosure) — 표시 단계 계층 (TASK-0257)

§10.6 의 section/group **정렬·구조는 불변**이며, 그 위에 권한 row 단위의 표시 단계
계층을 둔다. 관리 콘솔 권한 grid (`admin.js` `renderPermissionGrid`) 는
`PERMISSION_DEPENDENCIES` (child → 선행 parent) 에 따라 선행 권한이 충족돼야
(역할 체크박스 = 체크 / 계정 override = "허용" 또는 "상속(허용)") 해당 종속 권한 row 를 노출한다. 규칙:

- **마스터 게이트 → 카테고리 접근 (perm-category-hier, 2026-07-14)**: `console.access`
  (관리 콘솔 접근) 가 관리 권한 section 의 마스터 게이트이고, 그 하위에 **카테고리 접근 5종**
  (`console.{account,product,audit,kb,system}.access`) 이 온다. 각 카테고리의 탭 조회 base
  (`account.read`/`role.read`/`quota.read`/`product.read`/`datasource.read`/`audit.read.own`/
  `conversation.archive.read.any`/`console.usage.read`/`console.aiops.read`/`kb.ingest.manual`/
  `metadata.graph.read`/`kb.*.curate`/`system_prompt.global.read`/`system.runtime.read`) 의 부모 =
  소속 카테고리 접근 → 미체크 시 해당 카테고리 그룹이 접힌다(마스터 게이트 미체크 시 전체 접힘).
- **운영 권한 (TASK-0269 + perm-category-hier)**: 대화는 `conversation_own`(내 대화 권한) /
  `conversation_any`(전체 대화 권한) 2 그룹으로 분리. 각 그룹의 "목록 조회"(`list.own`/`list.any`)가
  카테고리 접근(=조회) 게이트 — list.own/list.any 루트, 동작 권한(create 포함)은 같은 그룹의
  list 를 선행으로 둔다.
- **계정 override 게이트 = 허용/상속(허용) (TASK-0270)**: override 모드 게이트는 값이
  "허용"이거나 "상속"이면서 계정 역할이 그 권한을 부여(상속(허용))할 때 충족된다. "거부"는
  역할 부여와 무관하게 게이트 OFF(거부 우선). 상속(허용) 판정 baseline = 역할 `permission_codes`.
- **게이트 체인 가시성 + 부여 도달성 (BLOCKING, TASK-0264 개정)**: row 는 선행 게이트
  체인이 모두 충족(checkbox: 각 조상 체크 / override: 각 조상 허용·상속(허용))돼야만 노출한다 —
  **부여 여부와 무관**(게이트 OFF 면 부여된 세부 권한도 "더 보기" 뒤로 접힘. 이전
  `forceVisible`=부여 항목 항상 표시 규칙은 "최대한 단순화" 사용자 요구로 제거).
  disclosure 는 row 를 *접을(collapse)* 뿐 *제거(strip)* 하지 않으며, 저장 경로는 hidden
  row 의 상태도 그대로 읽는다(부여 권한이 화면에서 접혀 있어도 누락 저장되지 않음).
  **부여 도달성**: 부여된 row 가 있는 그룹은 게이트 OFF 라도 vanish 하지 않고, "세부 권한
  N개 더 보기 · M개 부여됨"(`.has-granted`) + 그룹 헤더 `선택 N/M` 카운트로 접힌 부여
  권한의 존재를 표면화한다 — 부여된 권한이 영구히 가려지지 않는다.
- **그룹/섹션 vanish 는 checkbox(역할) 모드 한정**: 마스터 게이트 OFF 시 종속 그룹이
  통째 사라지는 동작은 역할 편집기(체크박스)만 적용한다 — 마스터 게이트 체크박스가 항상
  보이는 복원 레버이기 때문. 계정 override 편집기(select)는 위 "관리자가 배치 가능한
  권한 전체를 보여주는 grid" 보장을 지키기 위해 **그룹/섹션을 숨기지 않고** row 만 접는다.
- **트리 레이아웃 (TASK-0267)**: 그룹 내 권한은 트리 순서(부모 먼저, 자식 들여쓰기,
  `admin.js` `_orderItemsAsTree` + `data-perm-depth`)로 **단일 열**(`.permission-grid-list`
  = flex column) 렌더한다. 2열 grid 는 자식 row 숨김 시 가로 reflow 로 기존 항목을
  뒤틀므로 금지 — 단일 열이라 자식이 접혀도 부모는 제자리에 남는다.

#### 검증

화면 정렬이 본 §10.6 와 어긋나면 그 PR 은 사람 리뷰가 반려한다.

### 10.7 변경 적용 모델 — Pending → 일괄 적용 (batch-apply) 강제 (REQ-20260619-0331)

관리 콘솔에서 **사용자가 작업하는 모든 데이터 변경(mutation)** 은 편집 시점에 즉시 서버에 반영하지 않고, 전역 pending 상태에 스테이징한 뒤 사용자가 footer **"모두 적용"** 을 누를 때 한 번에 일괄 확정(batch-apply)한다. 이는 카테고리·에디터 종류와 무관한 관리 콘솔 전역 불변 규칙이다 (admin.js 헤더 "pending changes + bulk commit" 아키텍처, TASK-0029·TASK-0239 정책의 일반화).

#### 정본 경로

- **스테이징**: 모든 편집은 `adminState.pending.<entity>` (admin.js) 에만 누적한다 — 편집 클릭 시점에 서버를 호출하지 않는다.
- **일괄 확정**: footer 단일 "모두 적용" 버튼(`applyAllPending`) 만이 서버 쓰기를 수행하며, baseline 스냅샷 대비 diff 로 최소 호출한다.
- **취소 가능성**: "모두 적용" 전까지 모든 변경은 되돌릴 수 있어야 한다 (`pendingChangeCount() > 0` 이면 화면 이탈·새로고침 시 미저장 경고).
- 미저장 신규 row·삭제 대기는 "모두 적용 시 생성/삭제됩니다" 로 표기한다.

#### 불변 규칙

- **개별 에디터·버튼이 자체 즉시-쓰기 경로(클릭 → `apiFetch` POST/PUT/DELETE 직접 호출 → 즉시 반영)를 가지지 않는다.** 새 편집 UI 는 반드시 전역 pending 에 스테이징하고 "모두 적용" 흐름에 합류한다.
- **보안 경계 mutation 은 예외 없음**: 접근 가능 데이터베이스 allowlist, 권한·RBAC, 역할 배치 등 보안 경계를 바꾸는 변경은 절대 즉시 반영하지 않는다 — 반드시 pending 경유 + "모두 적용" 확정.
- **읽기성 호출은 mutation 아님**: 서버 상태를 바꾸지 않는 호출(연결 테스트, 정규식/규칙 preview 조회 등)은 본 규칙의 적용 대상이 아니므로 즉시 호출해도 된다. **조회(GET) 자체가 서버 상태를 바꾸면 안 된다** (lazy-on-view 자동 반영 금지).

#### 자율 동기화 carve-out (시스템 동작 ≠ 콘솔 편집)

확정된 설정이 데이터 변화에 반응해 **백그라운드에서 자율적으로 동기화**하는 동작(예: 정규식 자동 규칙이 데이터소스의 DB 추가/삭제를 주기적으로 반영)은 "사용자가 콘솔에서 작업하는 변경" 이 아니므로 본 §10.7 의 pending 대상이 **아니다**. 단, 그 자율 동작을 **켜고/끄고/바꾸는 사용자 행위**(규칙 추가·수정·삭제·pending 승인)는 콘솔 편집이므로 pending → "모두 적용" 을 따른다. 즉 *규칙의 정의 변경*은 pending, *확정된 규칙의 standing 자동 동기화*는 carve-out.

#### 검증 과정 (관리 콘솔 mutation UI 추가·수정 시)

관리 콘솔에 데이터 변경을 일으키는 UI 를 추가·수정할 때 다음을 차례로 확인한다. PASS 하지 않으면 PR 단계에서 사람 리뷰가 반려한다.

- [ ] 편집 핸들러가 클릭 즉시 `apiFetch(POST/PUT/DELETE …)` 로 서버를 변경하지 않는다 (스테이징만 수행).
- [ ] 변경이 `adminState.pending` (또는 동등한 전역 pending 스토어)에 누적되고 `pendingChangeCount()` 에 반영된다.
- [ ] footer "모두 적용"(`applyAllPending`) 한 번으로 해당 변경이 일괄 확정된다.
- [ ] "모두 적용" 전까지 변경을 취소할 수 있고, 화면 이탈 시 미저장 경고가 뜬다.
- [ ] 보안 경계(allowlist·권한·RBAC) 변경이면 즉시-반영 경로가 전혀 없음을 재확인한다 (조회/렌더만으로 GRANT 되지 않음 포함).
- [ ] 남아 있는 즉시 호출이 있다면 그것이 서버 상태를 바꾸지 않는 읽기성(연결 테스트·preview)이거나 위 carve-out 의 자율 시스템 동작임을 명시 확인한다.
- [ ] 가능하면 staging→apply 계약을 jsdom 단위 테스트로 고정한다 (스테이징 시 쓰기 0 / "모두 적용" 만 쓰기 / 엔드포인트·순서).

#### 적용 이력

- 정규식 자동 규칙 에디터(`cov-db-rule`, admin.js TASK-20260618T044318)는 "규칙 추가/수정 저장"·"승인"·"삭제"·조회 시 곧바로 `…/db-rules` 를 호출해 allowlist(보안 경계)를 **즉시 반영**하여 본 §10.7 을 위배했다. **TASK-20260619 (REV-20260619)** 에서 규칙 추가/수정/삭제/승인을 `adminState.pending.productDbRules` 스테이징 → "모두 적용" 으로 재배선하고, GET 의 lazy-on-view 자동 reconcile 를 제거했다(범위 A). 확정된 규칙의 백그라운드 자동 동기화는 위 carve-out 으로 보존한다.

## 10. 자동화 / 실행 진입점 (Makefile 채택 시)

`repo/Makefile` 을 도입한 경우 (AGENTS.md §20) 다음 target 네이밍을 권장:

- `up` / `down` — 서비스 시작/중지
- `build` / `test` / `clean` — 표준 빌드 사이클
- `<feature>-<verb>` — feature 별 entry (예: `mysql-restore`, `xtrabackup-up`). `<feature>` 부분은 `unit/feature-NNNN-<name>` 의 `<name>` 과 일치시켜 추적성 확보.
- `help` — target 목록 자동 출력. 권장 구현:

  ```makefile
  help:
  	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
  		awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
  ```

- 새 target 추가/제거 시 `docs/DECISIONS.md` 의 ADR 작성 (Makefile = "실행 진입점" anchor, §18).
- **테스트 경로 등재는 양쪽 모두 (2026-09-01 확립)** — `Makefile` 의 `test` 타깃과 `.github/workflows/ci.yml` 의 pytest 인자 목록은 **같은 집합**이어야 한다. `pytest.ini` 의 `testpaths` 는 인자를 명시하면 무시되므로, 한쪽에만 등재하면 «로컬은 green 인데 CI 는 그 축을 보지 않는» 상태가 **아무 신호 없이** 생긴다(2026-08~09 동일 누락 4회 재발 — feature-0014·0020 / 0023 / 0041·0043·0008; 2026-09-04 feature-0046 에서 한 번 더 — `pyproject.toml` `testpaths` 에만 등재되고 `Makefile`·`.github/workflows/ci.yml` 은 **여전히 미등재**라 CI 는 그 스위트를 돌리지 않는다. 정본 `unit/feature-0046-native-client/docs/REVIEW.md` REV-20260904T121000). 새 테스트 디렉토리를 만들면 두 곳 모두 등재하고, 집합 일치는 `unit/feature-0043-external-llm-bridge/tests/test_ci_testpath_parity.py` 가 잠근다.
- 본 § 은 PROJECT.md §9.1 (자동화 도구) 의 categorization 과 일관 — Makefile 은 테스트 프레임워크가 아닌 자동화 영역. CI/CD 도구는 PROJECT.md §10 참조.

## 11. Wikilink 및 Wiki vault 표기 (v3.12.0+)

`repo/wiki/` (Obsidian vault, AGENTS.md §21) 를 도입한 v3.12.0 부터 적용. 운용 정본은 `docs/WIKI.md`. 본 § 는 *AI 와 사람이 문서 본문에 쓰는 link 표기* 만 정의.

### 11.1 vault 내부 link

| 패턴 | 예시 | 설명 |
|---|---|---|
| 같은 디렉토리 | `[[Overview]]` | `wiki/Architecture/Overview.md` 안에서 `[[Data-Flow]]` |
| 다른 sub-디렉토리 | `[[../Decisions/_Index]]` | relative path 우선 |
| 별칭 (한국어) | `[[../docs/PROJECT\|프로젝트]]` | alias 로 표시명 자유 지정 |
| heading anchor | `[[../docs/DECISIONS#ADR-001\|ADR-001]]` | `#` 뒤에 heading text |

### 11.2 vault → 정본 docs link

wiki 노트에서 정본 문서로 link 할 때:

```markdown
[[../../docs/PROJECT|Project]]
[[../../docs/DECISIONS#ADR-001|ADR-001 — 분리 결정]]
[[../../unit/feature-0001-example/docs/FUNCTION|Feature 0001 — FUNCTION]]
```

### 11.3 정본 docs → vault link (선택)

정본 docs 는 일반적으로 vault 를 참조하지 않는다 (정본은 vault 의 mirror 가 아니다). 단, 다음 경우는 예외로 link 가능:
- `docs/WIKI.md` — vault 운용 가이드 자체
- `AGENTS.md §21` — vault 책임 분배
- 사람용 onboarding (`README.md`, `CONTRIBUTING.md`) 에서 "graph 로 탐색하려면 wiki/ 를 Obsidian 으로 열어라" 안내

이 외의 정본은 vault 를 참조하지 않는다 (정본 ↔ mirror 단방향 의존).

### 11.4 표기 일관성

- **markdown link 와 wikilink 의 혼용**: vault *내부* 는 `[[wikilink]]` 우선, 정본 docs *내부* 는 `[markdown](relative/path.md)` 우선. 정본은 GitHub web preview 에서 가독성 우선이라 markdown link 가 portable.
- **alias 권장**: link target 의 path 가 길거나 한국어 표시명이 필요할 때.
- **anchor 사용**: heading 이 있는 문서로 link 할 때는 anchor 명시 (`#ADR-001`, `#§21.2-ai-의무`).

### 11.5 namu-style 사람 facing 형식 (v3.13.0+)

본 프로젝트의 `wiki/` 안의 모든 사람 facing 노트 (즉 `Log.md` 와 `raw/<원본>` 외) 는 [나무위키 표준 형식](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) 을 따른다 (사용자 명시 요청, AGENTS.md §21.8).

**필수 표기**:

- 제목 직후 *인포박스* (`| 항목 | 값 |` 표) — 메타데이터 한 눈에.
- `## 1. 개요` → `## 2. 상세` → (선택 `## 3. 특징`, `## 4. 비교`, `## 5. 평가`) → `## n. 관련 문서` (최대 4개) → `## n+1. 둘러보기` → `## n+2. 외부 link` → `## 분류` (footer tag).
- *비교* sub-section 은 namu 의 "언어 모델" entry ([https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8)) 의 "A vs B" 표 패턴.
- *각주* `[^N]` markdown footnote 활용.

자세한 spec: `docs/WIKI.md §11.3` 와 `AGENTS.md §21.8`.

## 12. 마이그레이션 안전 — expand/contract (무중단 배포 전제, feature-0014)

web 은 무중단 롤링 배포(Caddy 뒤 web-a/web-b, 한 번에 하나씩 재시작)되므로, 배포 중
**OLD 코드와 NEW 코드가 같은 DB 를 잠시 동시에** 사용한다. 이 mixed-version 창에서
안전하려면 모든 alembic revision 이 **backward-compatible(expand/contract)** 여야 한다.

### 12.1 원칙

- **Expand (안전, 자유 적용)**: 컬럼/테이블/인덱스 **추가**, nullable 또는 `server_default`
  있는 컬럼 추가, 신규 제약을 `NOT VALID` 로 추가 후 별도 검증 — OLD 코드가 모르는 객체를
  더하는 변경.
- **Contract (위험, 2-phase 필수)**: OLD 코드가 여전히 읽고/쓰는 컬럼·테이블·제약의
  **DROP / RENAME / 타입 변경 / `NOT NULL` 추가(server_default 없이)**. 이런 변경은
  **NEW 코드가 모든 replica 에 배포된 뒤, 다음 별도 cycle 에서** 떼어낸다(2-phase):
  - Phase 1 (이번 cycle): 새 컬럼/구조 추가(expand) + 코드가 양쪽 모두 쓰게.
  - Phase 2 (후속 cycle): 모든 replica 가 NEW 코드일 때 구 컬럼/구조 제거(contract).

### 12.2 강제 게이트

- 신규/변경 revision 은 **`bin/migrate-lint.sh`** 가 `upgrade()` 본문(+`op.execute()` 가
  참조하는 모듈 상수 SQL)을 스캔해 비가산 DDL 을 적발한다. `op.execute(UPGRADE_SQL)` 처럼
  상수로 감싼 raw SQL 도 따라간다.
- `bin/deploy-web.sh` 가 **마이그레이션 적용 직전 hard gate** 로 호출한다(실패 시 배포 ABORT,
  스키마/컨테이너 무변경).
- alembic revision 을 만질 때는 AGENTS.md §10.5 조건부 규칙에 따라 본 §12 를 참조한다.

### 12.3 정말 contract 가 필요할 때 (escape)

2-phase 로 분리할 수 없는 불가피한 경우에 한해, revision 파일에 **서명 annotation** 을 남겨
게이트를 통과시킨다 (책임 명시):

```python
# migrate-lint: contract-deferred — <사유: 왜 안전한지/언제 OLD 코드가 사라지는지> (서명: <name> <YYYY-MM-DD>)
# 또는
# migrate-lint: allow drop_constraint — FK 제약만 제거, 앱 동작 비의존 (서명: <name> <YYYY-MM-DD>)
```

annotation 없이 비가산 DDL 이 있으면 `migrate-lint` 가 exit 1 로 배포/머지를 차단한다.

## 13. MySQL online DDL — 무중단 스키마 변경 (feature-0015)

MySQL agent_memory 는 **단일 인스턴스(replica 없음)**다. `ALTER TABLE` 이 silent COPY 알고리즘으로
떨어지면 해당 테이블 DML 이 락에 걸려 사용자 체감 중단이 발생한다. 8.0 online DDL 을 강제한다.

### 13.1 규칙
- 신규/변경 MySQL `ALTER TABLE` 은 **`ALGORITHM=INPLACE, LOCK=NONE`** 을 명시한다(끝-컬럼 추가는
  8.0.29+ 에서 `ALGORITHM=INSTANT` 도 가능하나, 미지원 op 에서 에러나므로 INPLACE 가 안전 기본).
- `LOCK=NONE` 의 의도는 **online 불가 시 에러로 표면화**(silent COPY-lock 차단). 에러나면 그 변경은
  online 불가 → `gh-ost`(본 스택 binlog ON 이라 단일 인스턴스에서도 동작) 또는 정비창으로 전환.
- **online-DDL 을 bare `try/except: pass` 로 감싸지 말 것** — 비-online 에러가 silent skip 되어 필요한
  스키마가 누락된다. 멱등 가드가 필요하면 ALTER 전에 컬럼/인덱스 존재를 먼저 확인하라.
- type 변경/rename/drop 등 본질적 비-online 변경은 expand/contract 2-phase(§12) 로 분해한다.

### 13.2 강제
- `bin/mysql-ddl-lint.sh` (`make mysql-ddl-lint`) 가 origin/main 대비 **신규/변경** MySQL ALTER 중
  `LOCK=NONE` 누락을 적발한다(diff-mode). 기존 사이트는 grandfathered.
- 불가피한 예외: 해당 라인에 `# mysql-ddl-lint: allow — <사유> (서명: <name> <YYYY-MM-DD>)`.
- online 절(`LOCK=NONE`)은 `ALTER TABLE` 과 **같은 소스 라인**에 둘 것 — multi-line 문자열 concat 으로
  쪼개면 lint 가 첫 라인을 false-positive 로 잡는다(단일 라인 검사).
- 적용 제외(자동): `agent_runtime.`/`agent_kb` 수식(PG — §12 alembic 게이트 담당), alembic/, 사용자
  업로드 SQL 실행(sandbox).

## 12. 사용자 대면 텍스트 (UI copy, v3.43.0+)

정본은 `AGENTS.md §16.8`. 본 섹션은 프로젝트가 채택할 **예산 값과 대상 패턴**만 정한다.

**원칙**: 안내는 *이 화면이 무엇인가* 까지다. 조작법(펼치기/정렬/클릭)·다른 화면 경로
(`설정 > …`)·내부 계약(정렬 키·상한·폴백)·설계 정당화는 넣지 않는다 — 앞의 둘은 화면과
메뉴가 이미 말하고, 뒤의 둘은 `FUNCTION.md`·`REVIEW.md` 가 정본이다.

**판정 질문**: "이 문장이 없으면 사용자가 무엇을 못 하는가?" 답이 "없음"이면 지운다.

| 대상 | 예산 | 비고 |
|---|---|---|
| 섹션/화면 안내 | 1문장 · 약 60자 | <!-- 프로젝트 실측에 맞게 조정 --> |
| 설정 항목 hint | 2문장 | 오설정 비용이 큰 항목만 |
| 빈 상태·에러 | 1~2문장 | 무슨 일이 있었나 + 다음 행동 |

**기계 게이트 (opt-in)**: `.template/ui-copy-budget.conf` 를 두면 `verify-completion`
check #17 가 이번 cycle 에 **추가·수정된 라인**의 텍스트를 검사한다. 시작 템플릿은
`.template/ui-copy-budget.conf.example`. 기존 잔여는 막지 않으므로(추가 라인만 검사) 도입
시점에 정리 부채를 한 번에 갚을 필요가 없다.

## 14. 프론트엔드 code-modularity (feature-0038, ITEM-P5b 재발 방지 — 2026-08-04)

모놀리스 재발을 막는 프론트 파일 크기 규약. 근거: admin.js/app.js/styles.css 가 3주 만에
+23~59% 성장해 AI 전체 로드·정확 편집이 불가능해진 실측 (ssot-consolidation ROADMAP
ITEM-P5b — 2026-08 에 css/ 7분할 + admin/ 9모듈 + app/ 4모듈로 분할).

### 14.1 임계 (신규 기여 기준)

| 조건 | 요구 |
|---|---|
| 단일 프론트 파일(JS/CSS)이 **3,000줄 초과** | 신규 기능 코드는 그 파일에 추가하지 않고 도메인 모듈(`admin/`·`app/`·`css/` 선례)로 분리 |
| **5,000줄 초과** 파일에 **+200줄 이상** 추가하는 PR | PR 본문에 추출 계획(어느 도메인 모듈로 언제 뺄지) 1줄 동반 — 없으면 리뷰 반려 |
| 신규 정적 파일 | JS 는 ES module + import specifier `?v=dev` 고정, CSS 는 link `?v=dev` (빌드 inject_asset_stamp 가 content-hash 주입 — 수기 bump 금지) |

### 14.2 분할 방법 정본 (feature-0038 확립)

- **byte-동치 이동**: 본문 무수정, import/export 배선만. "분할본 재조립 == 원본" 을 기계
  증명(concat cmp 또는 역재구성)하고 PR 에 기록한다.
- **상태 초기화·공유 가변 let 은 이동 금지 축**: `adminState.X = {…}` top-level init 은
  entry 파일 잔류(ESM 순환 TDZ). 여러 파일이 재할당하는 `let` 은 ESM import-binding
  write(TypeError) — **양방향 재할당 전수 검사**(주석 제거 후) 없이 이동하지 않는다.
- **acorn-globals 자유 식별자 0 게이트**: 분할 후 각 모듈의 비표준 자유 식별자 0 을
  기계 확인 (문자열/regex 스캔은 `$` 류를 놓친다 — Cycle 2 실증).
- **소스-추출형 테스트 동반 갱신**: 파일 경로에 결합된 테스트(py `_read_static`·mjs
  `readFileSync`)는 같은 PR 에서 합본(read concat) 전환. 리터럴-대조 스캔("구본에 있고
  신본에 없는 문자열을 단언하는 테스트")으로 누락을 잡는다.
- **검증 사다리**: make test + 적대 패널(§18.8) + (JS 는) POST-DEPLOY PB-0008 — 미머지
  docker cp 사전 QA 는 CSS 만 안전(JS 는 모듈 캐시·스탬프 함정).

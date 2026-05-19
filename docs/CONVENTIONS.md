---
doc_type: CONVENTIONS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.8.0-rc.1
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
문서와 코드에 아래 식별자 사용을 권장한다.
- `REQ-XXXX`
- `AC-XXXX`
- `CHG-YYYYMMDD-XXXX`
- `REV-YYYYMMDD-XXXX`
- `ADR-XXXX`
- `TEST-XXXX`

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

## 10. Admin Console UI 일관성

관리 콘솔 (`feature-0003-agent-web-ui` 의 `admin.html` / `admin.js` / `styles.css`) 의 카테고리별 UI (Accounts, Roles, Products, 이후 추가될 모든 카테고리) 는 본 섹션의 정책을 따른다.

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

권한 (Permission) 리스트는 백엔드 단일 `PERMISSION_DEFINITIONS[*].group` (`console` / `account` / `role` / `conversation` / `product` / `misc`) 으로 분류되지만, **사용자가 보는 정렬·섹션 구조는 화면 맥락에 따라 다르게 적용한다.** 같은 정렬을 두 화면에 공유하면 한쪽은 항상 핵심 권한이 묻힌다.

#### 화면별 2단 section

| 화면 | 시각 | 섹션 순서 (상→하) |
|---|---|---|
| 작업 화면 (`index.html` + `app.js`) | 본인이 보유한 권한을 보여주는 자기 자신 시점 | **운영 권한** (`conversation`, `product`) → **관리 권한** (`console`, `account`, `role`) → **기타** (`misc`) |
| 관리 콘솔 (`admin.html` + `admin.js`) | 타인의 권한을 배치하는 관리자 시점 | **관리 권한** (`console`, `account`, `role`) → **운영 권한** (`conversation`, `product`) → **기타** (`misc`) |

#### 정합 규칙

- 백엔드 group 키 (`console` / `account` / `role` / `conversation` / `product` / `misc`) 가 진실의 근원. FE 의 section 정의는 group 키를 묶기만 한다.
- 작업 화면은 사용자가 그 section 안의 어느 group 권한도 보유하지 않으면 **section 자체를 미렌더**한다. 특히 일반 사용자의 "관리 권한" section 은 자동 hide.
- 관리 콘솔은 사용자(관리자) 가 보유한 권한과 무관하게 **모든 section 을 항상 표시**한다. 관리자가 배치 가능한 권한 전체를 보여주는 grid 이기 때문이다.
- 두 화면의 section 정의는 코드 상수 1 곳에서 한다: 작업 화면 = `app.js` 의 `WORK_SCREEN_PERMISSION_SECTIONS`, 관리 콘솔 = `admin.js` 의 `ADMIN_PERMISSION_SECTIONS`.
- 새 group 키가 백엔드에 추가되면 위 두 상수에 명시적으로 매핑한다. 매핑이 빠지면 "기타" section 으로 fallback 한다 (자동, but 권장 아님).
- group 키별 한글 label (`console`="관리 콘솔", `account`="계정", `role`="역할", `conversation`="대화", `product`="제품", `misc`="기타") 은 두 화면에서 동일하게 유지한다.

#### 동적 권한 (`product.access.<key>`, `system_prompt.*`)

- `product.access.<key>` (dynamic, IsDynamic=1) 는 백엔드에서 `group="product"` 로 들어오므로 두 화면 모두 자동으로 product 섹션에 합류한다.
- `system_prompt.*` 코드는 백엔드 정의가 `group="product"` 이고, 작업 화면 FE 의 `permissionGroupOf()` 는 prefix-only 추론이므로 `system_prompt.` 접두사를 명시적으로 `product` 로 매핑한다 (app.js).

#### 검증

화면 정렬이 본 §10.6 와 어긋나면 그 PR 은 사람 리뷰가 반려한다.

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
- 본 § 은 PROJECT.md §9.1 (자동화 도구) 의 categorization 과 일관 — Makefile 은 테스트 프레임워크가 아닌 자동화 영역. CI/CD 도구는 PROJECT.md §10 참조.

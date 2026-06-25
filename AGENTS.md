---
doc_type: REPOSITORY_AGENT_POLICY
scope: repository
status: active
edit_policy: human-guided
source_of_truth: true
template_version: v3.35.0
domain: [governance, workflow, context, safety]
ai_read_priority: 1
---

# Repository AI Operating Policy

> **주의:** 이 문서가 포함된 폴더 구조가 템플릿에서 복사된 직후라면,
> `FIRST_REQUEST.md`의 **시나리오 0 (템플릿 초기화)**를 먼저 수행해야 한다.
> 템플릿의 예시 콘텐츠(`feature-0001-example`, 템플릿 ADR 등)가 남아 있으면
> 이를 실제 프로젝트 요구사항으로 오해할 수 있다.

---

# Part A — 기본 원칙

## §1. 목적

이 저장소에서 AI는 사용자의 요구를 바탕으로 기능을 설계, 구현, 테스트, 문서화한다.
모든 작업은 코드와 문서가 함께 갱신되어야 하며, 여러 AI와 사람이 함께 접근해도 충돌과 모호성을 최소화해야 한다.

## §2. 작업 범위

- `/repo`는 버전관리 대상이다.
- `/artifacts`는 실행 결과와 산출물을 저장한다.
- `artifacts`는 기본적으로 파생 결과물이며, 별도 명시가 없으면 source of truth가 아니다.

### §2.1 Git 루트 경계 (필수)

- **Git 저장소(`.git`)는 반드시 `/repo` 디렉토리 내에 초기화한다.**
- 상위 작업 폴더(`/repo`의 부모)에 `.git`을 생성하면 안 된다.
- `git init`은 `/repo` 안에서만 실행한다.
- `.gitignore`, `.gitattributes` 등 git 설정 파일도 `/repo` 내에 둔다.
- `FIRST_REQUEST.md`, 최상위 `README.md`, `/artifacts`는 git 추적 대상이 아니다.
- 이 규칙을 위반하면 artifacts, FIRST_REQUEST.md 등 비추적 대상 파일이 git에 포함되어 저장소 오염이 발생한다.

### §2.2 Template base vs 소비자 프로젝트 (필수 자가 검증)

본 repo 가 **template base** 인지 **소비자 프로젝트** 인지 판정해야 하는 작업
— 특히 `FIRST_REQUEST.md` 시나리오 0 의 cleanup checklist 적용, `_template_maintainer/`
영역 수정, `.claude/commands/_maintainer/` 영역 수정 — 은 작업 시작 전에
`bin/template-base-check.sh` 를 호출해 기계 검증을 거친다.

#### 판정 기준

| Verdict | 신호 (모두 만족) |
|---|---|
| `template-base` | `_template_maintainer/HISTORY.md` 의 `## META-CYCLE-` heading ≥ 1 occurrence AND `bin/migrations/registry.sh` 존재 |
| `consumer` | 위 신호 1개 이상 부재 |

#### 호출 패턴

```bash
# 자가 진단 (exit code: 0=template-base, 1=consumer, 2=usage)
bash repo/bin/template-base-check.sh

# 소비자 cleanup 직전 — template base 에서는 STOP
if bash repo/bin/template-base-check.sh --quiet 2>/dev/null; then
  echo "STOP: template base 에서는 소비자 cleanup checklist 를 실행하지 않는다." >&2
  exit 1
fi
```

#### 사고 배경 (2026-05-19)

PR #12 가 본 repo (template base) 에 소비자 cleanup checklist 를 잘못 적용하여
`_template_maintainer/` (24 파일), `.claude/commands/_maintainer/improve.md`,
`unit/feature-0001-example-*` 등을 삭제. PR #13 에서 revert 복구 후, 본 §2.2 와
`bin/template-base-check.sh` 가 재발 방지 가드로 도입됨.

#### Bypass 정책

- `bin/template-base-check.sh` 의 verdict 를 무시하는 옵션은 제공하지 않는다.
- verdict 가 모호하거나 잘못되었다고 판단되면, 본 정책의 신호 정의 자체를 갱신
  (별도 cycle) 한 후 진행한다 — 명시적 정책 수정 없이 우회 금지.

## §3. 문서 체계

### §3.1 우선순위

문서와 지시가 충돌할 경우 아래 우선순위를 따른다.

1. 사용자의 현재 직접 지시
2. `/repo/AGENTS.md`
3. `/repo/docs/PROJECT.md`
4. `/repo/docs/ARCHITECTURE.md`
5. `/repo/docs/CONVENTIONS.md`
6. `/repo/docs/SECURITY.md`
7. `/repo/docs/DECISIONS.md`
8. `/repo/docs/REQUEST.md`
9. `/repo/playbooks/*.md`
10. 기능 폴더의 `/docs/AGENTS.md`
11. 기능 폴더의 `/docs/FUNCTION.md`
12. 기능 폴더의 `/docs/TASK.md`
13. 기능 폴더의 `/docs/REPORT.md`
14. 기능 폴더의 `/docs/MODIFY.md`, `/docs/REVIEW.md`, `/docs/TEST.md`, `/docs/DECISIONS.md`

### §3.2 충돌 해석 원칙

- **주 규칙:** 상위 문서가 하위 문서보다 우선한다 (§3.1 순서 기준).
- **같은 계층 내:** 더 구체적인 문서가 더 일반적인 문서보다 우선한다.
- 승인된 결정이 초안보다 우선한다.
- 현재 상태 문서가 과거 이력 문서보다 현재 동작 판단에 우선한다.
- 불일치가 발견되면 임의 확정하지 말고 `REVIEW.md`와 `REPORT.md`에 기록한다.

---

# Part B — 작업 구조

## §4. 기능 생성 규칙

- 새 기능이 필요하면 `/repo/unit/_template`를 복사해 `/repo/unit/<feature-id>`를 생성한다.
- `feature-id`는 기능 목적이 드러나는 안정적인 이름을 사용한다 (예: `feature-0001-auth-module`).
- 기능별 문서는 `/repo/unit/<feature-id>/docs`에 둔다.
- 공통 로직은 가능하면 `/repo/shared` 또는 적절한 공통 모듈에 둔다.
- 기능 생성 후 `/repo/docs/STATUS.md`에 해당 기능을 등록한다.

### §4.1 Playbook 사용

- `/repo/playbooks/` 디렉토리에 반복적인 작업 절차를 Playbook으로 정의한다.
- AI가 Playbook에 해당하는 작업을 수행할 때는 해당 Playbook의 Steps를 순서대로 따른다.
- Playbook 목록은 `/repo/playbooks/README.md`에서 확인한다.
- 새 Playbook 추가는 프로젝트 수준 `DECISIONS.md`에 ADR로 기록한다.

## §5. 문서 역할 및 수정 정책

### §5.1 현재 상태 문서 (rewrite)

| 문서 | 역할 |
|------|------|
| `FUNCTION.md` | 현재 기능 명세 |
| `TASK.md` | 현재 작업 상태와 다음 액션 (작업 진행의 source of truth) |
| `REPORT.md` | 사람이 빠르게 파악할 최신 스냅샷 |

### §5.2 이력 문서 (append-only)

| 문서 | 역할 |
|------|------|
| `MODIFY.md` | 실제 반영된 변경 이력 |
| `REVIEW.md` | 변경 이유, 대안, 리스크, 판단 근거 |
| `DECISIONS.md` | 기능 수준 및 프로젝트 수준 의사결정 기록 |
| `LEARNINGS.md` | AI 학습 기록 — 실수, 패턴, 특이사항, 선호 (프로젝트 수준) |

### §5.3 품질 문서 (혼합)

- `TEST.md`: 케이스 정의(§1, §2)는 rewrite, 실행 결과(§3)는 append-only

### §5.4 수정 규칙

- `HUMAN-LOCKED` 구간은 명시적 사용자 지시가 없으면 수정하지 않는다.
- 기존 결정이 더 이상 유효하지 않더라도 과거 기록을 삭제하지 않고 `superseded` 또는 `deprecated`로 남긴다.

### §5.5 아카이빙

- append-only 문서의 항목이 **20건을 초과**하면 아카이빙한다.
- 오래된 항목을 `_archive/<DOC>-archive-NNNN.md`로 이동한다.
- 현행 파일에는 최근 항목만 유지하되, 파일 상단에 아카이브 참조 링크를 남긴다.

```md
> 이전 기록: [MODIFY-archive-0001.md](./_archive/MODIFY-archive-0001.md)
```

- `REPORT.md`에 "총 변경 횟수: N, 최근 변경 요약" 형태의 압축 정보를 유지한다.

### §5.6 거버넌스 문서 hygiene (분량·staleness)

append-only / 현재상태 문서가 무한 성장하면 §10.1 priming read-set 의 signal-to-noise 가
떨어지고, AI 가 stale·과대 문서를 읽느라 현행 작업을 놓친다 (실측: STATUS/DECISIONS/LEARNINGS
가 수십~수백 KB 로 누적된 소비자에서 "작업이 정립되지 못함" 보고). 다음 hygiene 를 적용한다:

- **분량 임계**: 단일 거버넌스 문서가 **~50KB 또는 ~400줄** (또는 단일 셀/라인 4KB+) 를
  초과하면 통합·아카이빙 플래그를 세운다 (§5.5 아카이빙 + §10.3 ARCHIVED 물리 이탈 규약 연동).
  임계는 도메인별로 조정 가능하나, "읽으면 현행 판단을 흐리는 분량" 을 넘으면 작업으로 본다.
- **staleness**: 현재상태 문서(§5.1)가 실제 코드/작업과 어긋나면 (예: 완료된 작업을 "진행 중"
  으로 기술) 같은 cycle 에서 rewrite 한다 — stale 현재상태 문서는 ARCHIVED 라벨 없이도 AI 를
  완료작업 재구현으로 오도한다.
- hygiene 위반 발견 시 별도 사용자 요청을 기다리지 않고 SSOT 통합·아카이빙을 작업 항목으로 제안한다.

## §6. 추적성 규칙

가능하면 아래 식별자를 사용한다.

| 식별자 | 용도 | 형식 |
|--------|------|------|
| `TASK-<id>` | Task Queue 항목 | timestamp+branch 권장 / 순번 fallback |
| `REQ-<id>` | 요구사항 | **timestamp+slug 권장** `REQ-<YYYYMMDDTHHMMSS>-<slug>` / 날짜+slug `REQ-<YYYYMMDD>-<slug>` / 순번 `REQ-XXXX` fallback |
| `AC-<id>` | 수용 기준 | **timestamp+slug 권장** `AC-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` / 순번 `AC-XXXX` fallback |
| `CHG-<id>` | 변경 | timestamp+branch 권장 / 날짜+순번 fallback |
| `REV-<id>` | 리뷰 | timestamp+branch 권장 / 날짜+순번 fallback |
| `ADR-<id>` | 결정 | **timestamp+slug 권장** `ADR-<YYYYMMDDTHHMMSS>-<slug>` / 순번 `ADR-XXXX` fallback |
| `TEST-<id>` | 테스트 | **timestamp+slug 권장** `TEST-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` / 순번 `TEST-XXXX` fallback |
| `LRN-<id>` | 학습 | timestamp+branch 권장 / 날짜+순번 fallback |

`feature-id` (기능 단위 폴더/worktree/branch) 는 §4 의 안정적 순번 형식 `feature-NNNN-<name>`
(예: `feature-0001-auth`) 을 유지한다 — 기능은 수명이 길고 추적 참조가 많아 안정적 식별자가 적합.

**병렬 할당 식별자 — timestamp+branch 권장 (v3.32.0+; spec 앵커 REQ/AC/ADR/TEST 확장 ADR-20260625T023049-spec-anchor-timestamp-id)**: 여러 세션이 같은
순번을 병렬 할당하면 `origin/main` 머지 시 충돌하므로(§13.1), **대량 병렬 생성되는 식별자 —
`TASK-`(Task Queue) · `CHG-`(변경 로그) · `REV-`(리뷰) · `LRN-`(학습)** 의 신규 항목은
(spec 앵커 `REQ-`/`AC-`/`ADR-`/`TEST-` 는 아래 별도 단락)
**timestamp+branch 형식 `<PREFIX>-<YYYYMMDDTHHMMSS>-<branch|slug>`** (예:
`TASK-20260615T185057-ai-claude-login`) 을 기본으로 한다. timestamp(초 해상도) 와 worktree
branch 명 조합이 세션 간 자연 분기를 만들어 순번 점유-경합을 제거한다. `<branch>` 는 현 worktree
branch 명을 쓰되 `[A-Za-z0-9._-]` 외 문자는 `-` 로 치환한다 (REV 자동생성기가 동일 규칙을 적용해
check #9 와 정합). 같은 초·같은 branch 충돌 시 §13.1 점유-감지 규약이 backstop 이다. 기존 순번/날짜+순번 형식 (`TASK-0001`,
`REV-20260615-0001`) 도 그대로 유효하다 (additive) — 순번 사용 시 §13.1 의 감지-후-재번호
규약이 적용된다. `TASK-`/`CHG-`/`LRN-` 은 자유 텍스트 항목이라 스크립트 형식 강제가 없고,
`REV-` 만 `bin/run-review-panel.sh`·`bin/review-md-append-from-subagent-output.sh` 가 자동
생성한다 (v3.32.0+ timestamp+branch 산출, `bin/verify-completion.sh` check #9 는 두 형식 모두
인식). **`feature-id`(`feature-NNNN`)/`META-id`(`META-NNNN`) — 수명 길고 추적 참조 많은 폴더/worktree/
branch 식별자 — 만 안정적 순번 형식을 유지한다** (이전 "순번 유지" 정책의 잔존 부분). 그 외 spec 앵커
`REQ-`/`AC-`/`ADR-`/`TEST-` 는 아래 timestamp+slug 로 전환한다.

**spec 앵커 `REQ-`/`AC-`/`ADR-`/`TEST-` 는 timestamp+slug 형식으로 전환한다 (v3.34.x+,
ADR-20260625T023049-spec-anchor-timestamp-id — 본 §6/§13.1 의 기존 "spec 앵커 순번 유지" 정책을
갱신, v3.32.0 의 timestamp+branch 컨벤션을 spec 앵커로 확장)**: 신규 항목은
**`<PREFIX>-<YYYYMMDDTHHMMSS>-<slug>`** 로 할당한다.
- `REQ-<YYYYMMDDTHHMMSS>-<slug>` (cycle 당 1개가 일반적이라 날짜형 `REQ-<YYYYMMDD>-<slug>` 도 허용).
- `AC-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` — 부모 REQ 의 **slug 를 공유**하고 cycle 의 초 timestamp 를 붙인다.
  REQ 당 **AC 2개 이상이면 `-<n>`(1-based) 필수, 단일이면 생략 가능**(또는 `-1`). REQ 가 날짜형이어도 AC 는
  cycle 의 초 timestamp 를 쓴다 (예: `REQ-20260625-gc-member-kick-ban` →
  `AC-20260625T020410-gc-member-kick-ban-1`,`-2`…).
- `ADR-<YYYYMMDDTHHMMSS>-<slug>` (본 ADR 이 첫 적용 예시이다).
- `TEST-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (다수면 `-<n>` 필수, 단일 생략 가능).

timestamp(초) + slug 가 cycle 별 자연 분기를 만들어, 여러 세션이 같은 순번(`AC-0625` 등)을 병렬
할당해 `origin/main` 머지 시 충돌하던 마찰(관찰 사례: 한 날 3개 동시 PR 이 `AC-0625` 를 동시 점유
→ 반복 재번호)을 제거한다 — 따라서 spec 앵커는 더 이상 §13.1 의 감지-후-재번호 대상이 아니다.
`<slug>` 는 cycle/feature slug 를 쓰되 `[A-Za-z0-9._-]` 외 문자는 `-` 로 치환한다. **기존 순번
`REQ-XXXX`/`AC-NNNN`/`ADR-XXXX`/`TEST-XXXX` 는 그대로 유효하다 (additive — 소급 재번호 없음, 신규
항목부터 적용)** — 한 문서에 과거 순번과 신규 timestamp 항목이 혼재해도 형식 자체로 구분된다.

문서 간에는 가능한 범위에서 `REQ → CHG → TEST → FILE` 추적이 가능해야 한다.

---

# Part C — 작업 워크플로

## §7. 요구사항 진입 프로토콜

- 사용자가 기능 요구를 전달하면 해당 기능의 `FUNCTION.md` §2 Goal에 `REQ-XXXX`를 기입한다.
- `TASK.md`에 초기 태스크를 나열한다.
- AI는 `FUNCTION.md`의 REQ와 `TASK.md`의 태스크를 기준으로 작업을 시작한다.
- 작업 중 추가 요구사항이 발생하면 동일한 방식으로 REQ를 추가하고 `MODIFY.md`에 변경 사유를 기록한다.

### §7.1 Plan-Review-Execute 프로토콜

비사소한 작업(2개 이상 파일 변경)을 시작하기 전에 AI는 구현 계획을 먼저 작성한다.

**계획 작성 위치:** `TASK.md` §2.1 Implementation Plan

**계획에 포함할 항목:**
- 영향받는 파일의 **구체 경로** (예: `repo/src/auth.ts`, `unit/feat-001/docs/TASK.md`)
- 변경 대상 **symbol name** — 함수·클래스·변수명 (예: `AuthService.login`, `USER_TABLE`)
- 접근 방법 요약 (3~5줄)
- **완료 판정 기준 (acceptance criteria)**: 변경 항목마다 "이 조건이 충족되면 완료" 1줄 이상
- 위험도 평가 (§12.3 기준: Minor / Major / Critical)

> **원칙 — structure in, structure out**: 계획에서 file path·symbol name·acceptance
> criteria를 고정할수록 구현 산출물이 예측 가능해지고, human review gate(아래 표)가
> 실질적으로 작동한다.

**위험도별 진행 규칙:**

| 위험도 | 계획 작성 | 실행 개시 | 비고 |
|--------|----------|----------|------|
| **Minor** | 작성 후 즉시 진행 | 계획은 문서화 목적 | 단일 파일 변경은 계획 생략 가능 |
| **Major** | 작성 → `plan-review` 상태 | 사람 승인 후 | 비-승인 작업은 계속 진행 |
| **Critical** | 작성 → `plan-review` + REPORT.md 교차 기록 | 사람 승인 후 | §12.1 행동 규칙 적용 |

사람 승인은 TASK.md에 다음 마커로 기록한다:
```md
<!-- PLAN-APPROVED by <user> on YYYY-MM-DD -->
```

## §8. 구현 정책

- 구현 전에 관련 상위 문서를 읽고 요구사항을 정리한다.
- 기능 구현은 최소 일관 단위로 나눈다.
- 코드 변경과 문서 갱신은 같은 작업 단위 안에서 같이 수행한다.
- 테스트 가능한 항목은 테스트를 작성하거나 수행한다.
- 불확실한 내용은 사실처럼 단정하지 않는다.
- 외부 의존성, 비용, 보안, 데이터 손실 가능성은 `REVIEW.md`와 `REPORT.md`에 분명히 남긴다.

### §8.1 개선 제안 정책

AI는 작업 중 다음을 발견하면 해당 기능의 `REPORT.md` §8 또는 프로젝트 수준 `STATUS.md`에 기록한다:
- 코드 중복 제거 기회
- 테스트 커버리지 누락
- 문서와 코드의 불일치
- 성능 또는 보안 강화 가능 지점

**제안은 기록만 하며, 사용자 지시 없이 실행하지 않는다.**

## §9. 불명확성 대응 정책

AI가 구현 중 요구사항이 불명확하거나 모순을 발견한 경우:

### §9.1 AI 자율 판단 가능 범위
- 변수명, 내부 자료구조, 코드 구조 등 외부 동작에 영향 없는 결정
- 합리적 가정이 가능한 수준의 모호함 → 가정 내용을 `REVIEW.md`에 기록하고 진행

### §9.2 사람 확인 필요 범위
- 비즈니스 로직 해석이 분기하는 경우
- 핵심 설계에 영향을 주는 모호함
- → `REPORT.md`에 `BLOCKED: clarification-needed` 표시 후 대체 가능한 작업으로 전환
- → 질문 내용과 AI가 고려한 선택지를 `REVIEW.md`에 함께 기록

---

# Part D — AI 컨텍스트 관리

## §10. AI 읽기 범위

컨텍스트 효율을 위해 AI는 아래 범위를 따른다.

### §10.1 필수 읽기 (작업 시작 시)

1. `/repo/AGENTS.md`
2. 해당 기능의 `TASK.md`
3. 해당 기능의 `FUNCTION.md`
4. 해당 기능의 `REPORT.md`

### §10.1.1 소비자 프로젝트 세션 시작 — worktree context 필수 확인

소비자 프로젝트 (§2.2 consumer 판정) 에서 AGENTS.md 을 첫 turn 에 읽은 후,
`/_template:entry` 미사용 직접 세션도 다음을 수행한다:

1. `git worktree list --porcelain` 으로 cwd 가 ai/* worktree 인지 main
   checkout 인지 판정.
2. 사용자 요청이 `repo/` 파일 생성·수정·삭제를 포함하면 mutation 의도로 간주.
3. main checkout + mutation 의도 조합이면 §13.2.7 F0 위반 — 작업 진입 전
   표면화:
   > 현재 main checkout. `repo/` 직접 수정은 §13.2.7 F0 위반.
   > `bash repo/bin/cycle-init.sh --feature <feature_id>` 로 worktree 생성 후
   > 새 세션에서 시작하세요. (또는 `/_template:entry <task>` 사용)

§13.2.4 carve-out 인 경우 (`/_local:*`, template base maintainer, `git
pull`/`git fetch`/submodule update, `/_template:init` 부트스트랩) 위 단계는
skip.

### §10.2 참조 읽기 (필요 시)

- `/repo/docs/ARCHITECTURE.md`
- `/repo/docs/CONVENTIONS.md`
- `/repo/docs/SECURITY.md`
- `/repo/docs/STATUS.md`
- `/repo/docs/LEARNINGS.md` (최근 10건 권장)
- `/repo/docs/CODEBASE_MAP.md` (파일 탐색 시)
- 해당 기능의 `MODIFY.md`, `REVIEW.md`

### §10.3 읽기 불필요 (명시적 요청 시만)

- 다른 기능의 문서
- 아카이브 파일 (`_archive/`)
- `/repo/docs/DECISIONS.md` (결정 확인 필요 시에만)

**불변식 — ARCHIVED 라벨 ⇒ 물리적 read-path 이탈 (MUST)**: 문서 헤더가 `ARCHIVED` /
`superseded` / `deprecated` 를 선언하면, **같은 변경에서** 그 파일을 `_archive/` 로 이전
(또는 `.aiignore` 에 등재)해 §10.1 필수 읽기(priming read-set)에서 물리적으로 빠지게 한다.
라벨만 붙이고 파일을 repo 루트·active 디렉토리에 남기는 것은 **위반**이다 — ARCHIVED 인데
read-path 에 남은 문서(예: 루트의 `GOAL.md`)는 AI 가 priming 단계에서 읽어 **이미 완료된
작업을 재구현**하게 만든다 (실측 마찰). 라벨(논리적 폐기)과 위치(물리적 read-path)의 정합을
한 불변식으로 보장한다. (§5.5 아카이빙 절차 + §5.6 hygiene 와 연동.)

### §10.4 컨텍스트 제외 (.aiignore)

- `/repo/.aiignore` 파일에 나열된 패턴에 매칭되는 파일은 AI 읽기 대상에서 제외한다.
- `.gitignore` 문법을 따른다.
- 제외된 파일을 읽어야 하는 경우 사용자가 명시적으로 지시한다.
- `.aiignore`는 §10.1~10.3의 읽기 범위보다 우선한다.
  단, **AGENTS.md와 TASK.md는 제외 불가**하다.
- 프로젝트 초기화 시 `.aiignore`를 도메인에 맞게 커스터마이징한다.

### §10.5 조건부 규칙 활성화

특정 파일 유형을 수정할 때 추가로 적용되는 규칙을 아래에 정의한다.
AI는 작업 대상 파일의 패턴을 확인하고, 매칭되는 규칙을 추가로 참조한다.

| 파일 패턴 | 추가 참조 문서 | 비고 |
|-----------|--------------|------|
| `unit/feature-0003-agent-web-ui/**`, `**/*.html`, `**/templates/**`, `**/static/**` | AGENTS.md §15.4.1 + `playbooks/PB-0008-windows-browser-verification.md` | 웹/UI 변경 — 완료 검증은 실제 Windows 브라우저(`bin/win-browser.py`)로 수행, `TEST.md` §3 에 `Environment: Windows-browser` Run 기록 |
<!-- 프로젝트 초기화 시 도메인에 맞게 최소 3~5개 이상을 채운다. 예시는 아래 주석 참조. -->
<!-- | *.sql | docs/SECURITY.md §3 | SQL 인젝션 방지 규칙 확인 | -->
<!-- | *.env*, *.cnf | docs/SECURITY.md §2 | 민감정보 처리 규칙 확인 | -->
<!-- | Dockerfile*, docker-compose.yml | docs/CONVENTIONS.md | 컨테이너 규칙 확인 | -->
<!-- | **/*.sh | docs/CONVENTIONS.md | ShellCheck 통과, set -euo pipefail 포함 | -->
<!-- | shared/** | docs/DECISIONS.md | 공유 경계 — 변경 시 ADR 경유 | -->
<!-- | Makefile | docs/ARCHITECTURE.md | 실행 진입점 — 타깃 추가/제거는 ADR 경유 | -->
<!-- | artifacts/** | docs/DECISIONS.md | Git 외부 — 커밋 금지, 경로만 참조 | -->

## §11. 컨텍스트 및 학습 관리

### §11.1 세션 컨텍스트

- 대화가 길어지면 핵심 결론을 문서(`TASK.md`, `REPORT.md`)에 반영하고, 문서를 기준으로 작업을 재개한다.
- 대화 중 확정된 내용은 대화가 아닌 문서가 정본이다.
- 하나의 대화 세션에서 하나의 기능을 다루는 것을 원칙으로 한다.
- 여러 기능을 동시에 다뤄야 하면 각 기능의 `TASK.md`와 `REPORT.md`를 기준으로 전환한다.

### §11.2 학습 기록 정책

- AI가 작업 중 예상과 다른 결과, 반복 실수, 효과적 패턴을 발견하면 `/repo/docs/LEARNINGS.md`에 기록한다.
- 기록은 append-only이며, 아카이빙 정책(§5.5)을 따른다.

| 카테고리 | 기록 대상 |
|---------|----------|
| `mistake` | 실수한 패턴과 올바른 접근법 |
| `pattern` | 효과적이었던 접근법, 재사용 가능한 패턴 |
| `quirk` | 프로젝트 특이사항, 외부 시스템 제약 |
| `preference` | 사용자가 선호하는 스타일, 관례 |

- 새 AI 세션 시작 시 최근 10건을 참조하는 것을 권장한다.
- 사용자 피드백으로 확인된 학습은 `verified: true`를 추가한다.

### §11.3 KB Fact 등록 정책 (Manual ingest vs 자동 수집)

`AgentMemoryFactEntries` 의 fact row 는 출처별로 Weight scale 이 분리된다.
`AgentMemoryFacts` VIEW 의 tie-break (Weight DESC → UpdatedAt DESC → Id DESC) 가
어떤 row 를 active fact 로 노출할지 결정하므로 Weight 가 우선순위 source-of-truth.

| Source | SourceType | Weight | ConversationId | 비고 |
|---|---|---|---|---|
| Manual ingest (admin curation) | `manual` | **90** | `__kb_manual__` (reserved sentinel) | BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3. admin 콘솔 "스키마 정의서 KB 등록" pane (`attachment.kb.write.any` RBAC). |
| 자동 수집 (insight worker, agent loop) | 기존 source 별 | **1** (default) | 실 ConversationId | memory.py / insight.py 의 INSERT 기본 동작. |

**Manual fact supersede 정책 (Status 컬럼 회피)**:

- 동일 (`ConversationId='__kb_manual__'`, `ScopeKey=<key>`, `FactKey=<key>`) 에
  새 본문 ingest 시 기존 `Weight > 0` row 는 `Weight=0` 으로 logical supersede.
- 새 row 는 `Weight=90` 로 INSERT (또는 동일 `FactFingerprint` 의 이전 row 가
  이미 있으면 `ON DUPLICATE KEY UPDATE` 로 reactivate — `superseded_count` 응답에
  반영).
- `AgentMemoryFacts` VIEW 가 `Weight DESC` 정렬이라 `Weight=0` row 는 자동 hide
  — 별 `Status` 컬럼 없이도 active fact 만 노출. 회귀 0.

**Manual ingest 책임 분담**:

- Frontend 표시 제어 (admin pane) 는 `attachment.kb.write.any` 보유자만 보지만,
  표시 누락은 fail-safe 가 아님 — backend endpoint 가 단일 RBAC gate.
- ScopeKey 는 manual fact 의 격리 기준이자 FactKey 역할 (한 ScopeKey = 한 active
  manual fact). 동일 ScopeKey 재ingest 는 의도적 update 흐름.
- `attachment.kb.ingest` action 의 audit ChangeJson 은 `attachment_id`, `scope_key`,
  `body_size`, `body_sha256_prefix`, `superseded_count`, `fact_entry_id`, `reactivated`
  를 포함 (D12 정합 — raw filename / bytes / object_key 미포함).


**`/model`, `/effort` — 작업 난이도별 model·effort 선택 (v2.1.154+)**

작업 난이도에 따라 model 과 effort level 을 맞춘다. **단, entry persona 가 런타임에
risk 를 판단해서 자기 model/effort 를 바꿀 수는 없다** — frontmatter `model:`/`effort:`
는 선언적 지정(skill 활성 동안 적용 후 세션 model 복귀)이라 "진입 후 동적 자기전환" 은
불가하고, `/model`·/effort` 는 사용자 입력만 인식한다. 따라서 자율 조절이 아니라
**사용자에게 권장하는** 패턴이다.

- **Critical 등급 (§12.3)** 또는 복잡한 분석·설계: `/model opus` + `/effort xhigh`
  (Opus 4.8 고노력). entry persona 가 Critical 추정 시 1줄 권장 표면화 (전환은 사용자).
- **단순·반복 작업** (lint fix, 포맷, 오타): 기본 model + effort 낮춤으로 비용 절감.
- subagent 단위 model 분기는 §18.8 참조 (per-invocation 지정은 프로그래매틱 가능).

**`/fast` — fast mode 정책 (Opus 4.8/4.7/4.6 대상)**

`/fast` 는 Opus 4.8 기준 2× 단가·2.5× 속도로 동작하는 throughput 모드이다.
**기본값: 비활성 (사용 금지)**. AI 는 사용자가 명시적으로 fast mode 사용을 요청한 경우에만
`/fast` 를 자율적으로 판단해 적용할 수 있다. 사용자 명시 없이 AI 가 먼저 fast mode 를
제안하거나 자동 활성화하는 것은 금지한다.

- **허용**: 사용자가 "fast mode 써줘", "/fast 켜줘" 등 명시 요청 시 AI 재량 적용.
- **금지**: 작업 속도·비용 이유로 AI 가 사전 제안·자동 활성화.
- 멀티 소비자 위임 등 throughput 개선이 필요한 경우에도 사용자 지시가 선행되어야 한다.

**`/recap` — 세션 재진입 컨텍스트 복원 (v2.1.x, 2026-05)**

`/recap` 은 세션 재진입 시 이전 작업 컨텍스트를 자동 요약·복원한다 (`/config` 에서
활성화 설정, 수동 호출도 가능). 장기 delegation 세션을 quota 만료·세션 종료 후 다시
열 때, harness-native 요약으로 직전 흐름을 빠르게 되살리는 보조 수단이다.

- **권장 시점**: 며칠에 걸친 장기 작업의 세션 재진입, context rollover 직후 재개.
- **정본은 여전히 문서**: `/recap` 은 §11.1 의 문서 기반 재개(TASK.md/REPORT.md 정본)를
  *대체하지 않고 보완*한다. `/config` 활성화 여부가 환경마다 다르므로 **권장 수준**이며,
  확정 사항은 항상 문서에서 확인한다.
- subagent/workflow 의 비재개성과 재개 전략은 §22.3.2 참조.
---

**`/usage` — plan limit 소진 요인 관측 (v2.1.149+)**

`/usage` 는 plan limit(요금제 rate-limit) 소진 요인을 **skill · subagent · plugin · MCP 서버별로
분해**해 표시한다. 멀티 소비자 운영 + §22.3 dynamic workflow fan-out(수십~수백 subagent)으로
plan limit 을 빠르게 소진하는 환경에서, 어느 차원이 비용을 끄는지 진단하는 수단이다.

**사용 권장 시점:**
- 대규모 fan-out / 장기 위임 세션 직후 — 어떤 skill·subagent·MCP 가 limit 을 끌었는지 점검.
- rate-limit 경고를 만났을 때 driver 식별.

```
/usage
```

**`/context` 와 차원 구분**: `/context`(§11.1 보조)는 **context window**(단일 세션 토큰 점유)를,
`/usage` 는 **plan rate-limit**(요금제 한도 소진)을 본다 — 측정 대상이 다르므로 혼동하지 않는다.

**`/context all` + skill `defaultEnabled: false` — 컨텍스트 예산 가시성·회수 (v2.1.x, 2026-06)**

`/context all` 은 현재 세션의 context window 점유를 **skill·provider 별 토큰 비용으로 분해**해
표시한다 (`/context` 의 요약보다 세분화 — 어느 skill manifest 가 window 를 끄는지 수치 확인).
skill manifest 의 `defaultEnabled: false` 설정은 해당 skill 을 **opt-in 로딩**으로 전환해, 특정
작업 타입에서만 on-demand 로 올린다 — heavy skill 세트(`/browse`·`/codex`·`/design-review` 등)를
상시 로딩하지 않아 비핵심 skill 의 manifest 점유를 줄인다.

**사용 권장 시점:**
- heavy-skill 장기 위임 세션(다수 skill + subagent fan-out)에서 context rollover **전** 예산 점검 —
  `/context all` 로 driver skill 식별 후 비핵심 skill 을 `defaultEnabled: false` 로 opt-out.
- rollover 가 빈발하는 세션의 manifest bloat 진단.

```
/context all
```

- **한계 — rollover 직접 차단 아님**: `/context all` 가시성 + `defaultEnabled: false` opt-out 은
  skill-manifest 점유를 줄이는 **보조책**이다. rollover 의 직접 원인이 실작업량(대량 Read/Edit/Bash)
  이면 manifest opt-out 만으로는 막지 못한다 — 예산 *여유 확보*용으로 활용하고, 근본 회수는 §11.1
  의 문서 기반 재개(작업 분할·세션 경계)와 병행한다.
- **`/usage` 와 차원 구분**: `/context all` 은 **context window**(단일 세션 토큰) 점유의 skill 별
  분해, `/usage` 는 **plan rate-limit**(요금제 한도)의 skill·subagent·MCP 별 분해다 — 측정 대상이
  다르다.

# Part E — 안전 및 협업

## §12. 승인 필요 항목

다음 항목은 사람이 최종 승인해야 한다.
- 인증/인가 구조 변경
- 파괴적 데이터 변경 또는 삭제
- 외부 계약 또는 비용 구조에 영향을 주는 변경
- 개인정보 및 민감정보 처리 변경
- 보안 수준 저하 가능성이 있는 변경
- 롤백이 어려운 마이그레이션

### §12.1 승인 대기 시 행동 규칙

AI가 위 항목에 해당하는 작업에 도달하면:
1. 해당 부분을 `REPORT.md`에 `BLOCKED: awaiting-human-approval` 상태로 표시한다.
2. `TASK.md`의 해당 태스크를 `Blocked` 섹션으로 이동하고 사유를 명기한다.
3. 승인이 필요 없는 다른 태스크를 계속 진행한다.
4. 모든 비-승인 태스크가 완료되면 `REPORT.md`에 승인 대기 항목 목록을 정리하여 사람에게 전달한다.

### §12.2 사전 승인 범위 (Pre-approved Scope)

`FUNCTION.md`에 사람이 다음과 같이 사전 승인을 선언할 수 있다:

```md
## Pre-approved Changes
- 이 기능에서 인증 토큰 갱신 로직 변경은 사전 승인됨
- DB 스키마 마이그레이션은 비파괴적 추가만 사전 승인됨
```

사전 승인된 범위 내의 변경은 §12 승인 없이 진행 가능하되, `REVIEW.md`에 사전 승인 근거와 함께 기록한다.

**`deploy_scope` 선언 (배포 포함 여부)**: 기본적으로 배포(컨테이너 재빌드/재시작,
CD hook, 외부 배포 명령)는 외부 영향 행동이라 cycle-final(commit/push) 이후 **별도
confirm** 대상이다. 그러나 프로젝트가 `FUNCTION.md` 의 `## Pre-approved Changes` 에
`deploy_scope: included` 를 선언하면, 해당 feature 의 cycle-final 후 배포까지가 사전
승인 범위에 포함되어 AI 가 confirm 없이 배포를 이어서 진행한다.

- **선언 위치 + 우선순위**: 프로젝트 전역 기본값은 `FIRST_REQUEST.md` 의 `deploy_scope:`
  키 (init 시점 사람 Q&A 하에 선언). feature 단위는 `unit/<id>/docs/FUNCTION.md` 의
  `## Pre-approved Changes`. **feature-level `deploy_scope: included` 가 cycle 시작
  시점에 이미 존재했을 때만 자동 배포** — cycle 진행 중 같은 AI 가 새로 추가한 선언은
  그 cycle 에서 자동 배포 근거로 쓰지 않는다 (1회 confirm 필요). 자율 확대 방지.
- **미선언 시 (기본)**: cycle-final 후 entry Phase 6.8 이 deploy script 감지 시 1회
  confirm. 사용자가 "배포까지 진행" 답하면 그 turn 한정 수행 (사전 승인 아님).
- **발효 가시화**: `deploy_scope: included` 가 활성인 cycle 의 첫 배포 직전, AI 는
  "deploy_scope: included 활성 — 이후 자동 배포" 를 1줄 표면화한다 (silent 자동배포 금지).
- **파일이 ground truth**: 세션 간 지속·context rollover 에도 선언이 보존되며, 자율
  배포라도 승인 근거가 `REVIEW.md` 에 기록되어 §12.2 정합. (별도 in-memory mode flag
  방식은 외부영향 경계 우회 + rollover 망각 위험으로 불채택.) 단 F0 와 마찬가지로 본
  선언은 **anti-friction 편의 장치이지 인가 통제가 아니다** — 파일 보유자가 편집 가능.

### §12.3 위험도 등급 분류

| 등급 | 대상 | 대응 |
|------|------|------|
| **Critical** | 인증/인가, 파괴적 데이터, 개인정보 | 반드시 사람 승인 |
| **Major** | 외부 비용, 롤백 어려운 마이그레이션, 보안 저하 | 사전 승인 없으면 사람 승인 |
| **Minor** | 비파괴적 스키마 추가, 내부 API 변경 | AI 자율 진행 + `REVIEW.md` 기록 |

> **2차-효과 비용 주의 (v3.35.0)**: 위 "외부 비용 = Major" 는 **1차 diff 가 양성으로 보여도**
> 적용된다. 특히 **cache-key/fingerprint/hash 계산을 바꾸는 변경**은 1차 diff(예: 문자열 정규화)는
> 작지만, 그로 인해 무효화되는 캐시·파생 산출물의 재생성이 큰 외부 비용을 유발한다. 배포 전 §16.3
> 의 blast-radius 사전측정 게이트로 무효화 규모를 추정해 Major 격상 여부를 판정한다.

## §13. 다중 AI 협업

### §13.1 충돌 방지 규칙

- 한 문서에 현재 상태와 변경 이력을 섞지 않는다.
- append-only 문서는 기존 항목을 의미 변경 수준으로 덮어쓰지 않는다.
- 기능 단위로 작업 범위를 쪼개고, 동시에 같은 파일을 수정해야 할 때는 상위 지침을 먼저 따르며 충돌 사실을 기록한다.
- 문서 상단 메타데이터의 `edit_policy`를 따른다.
- **프로젝트 수준 rewrite 문서**(ARCHITECTURE.md, CONVENTIONS.md 등)는 동시에 하나의 AI만 수정할 수 있다. 구조 변경이 필요하면 프로젝트 수준 `DECISIONS.md`에 제안을 기록하고 사람이 반영한다.
- **append-only 문서 동시 추가 시** 각 항목에 타임스탬프와 작업자 ID(AI 세션 또는 기능 ID)를 포함하여 자동 병합이 가능하도록 한다.
- **동시 세션 병렬 할당 식별자 충돌 — timestamp+branch 형식으로 회피 (v3.32.0, §6 식별자 표·prose)**:
  대량 병렬 생성되는 식별자(`TASK-` Task Queue · `CHG-` 변경 로그 · `REV-` 리뷰 · `LRN-` 학습)
  의 ID 를 여러 세션이 순번(`TASK-0001`, `TASK-0002` …)으로 병렬 할당하면 `origin/main` 머지 시
  같은 번호가 충돌한다 (관찰된 주요 마찰 지점). **신규 항목은 timestamp+branch 형식
  `<PREFIX>-<YYYYMMDDTHHMMSS>-<branch>`** (예: `TASK-20260615T185057-ai-claude-login`) 으로
  할당한다 (§6 참조) — timestamp(초) + worktree branch 명 조합이 세션 간 자연 분기를 만들어 점유
  확인·재번호가 불필요하다. `<branch>` 는 `[A-Za-z0-9._-]` 외 문자를 `-` 로 치환해 얻고 (REV
  자동생성기가 동일 규칙 적용 — check #9 정합), 같은 초·같은 branch 충돌 시 아래 감지-후-재번호
  규약이 backstop 이다.
  `TASK-`/`CHG-`/`LRN-` 은 자유 텍스트라 스크립트 검증 대상이 아니고, `REV-` 는 review-panel
  스크립트(`bin/run-review-panel.sh`·`bin/review-md-append-from-subagent-output.sh`)가 자동
  생성한다 (v3.32.0+ timestamp+branch). spec 앵커 `REQ-`/`AC-`/`ADR-`/`TEST-` 는 §6 의
  timestamp+slug 형식 (`<PREFIX>-<YYYYMMDDTHHMMSS>-<slug>[-<n>]`,
  ADR-20260625T023049-spec-anchor-timestamp-id) 으로 전환되어 아래 감지-후-재번호 대상이 아니다
  (병렬 점유-경합 자연 제거). **순번 유지 + 감지-후-재번호 대상은 `feature-id`(`feature-NNNN`, §4)·
  `META-id`(`META-NNNN`) 뿐이다** (수명 길고 폴더/branch 식별자라 timestamp 부적합).
- **동시 세션 feature/META 식별자 충돌 — 감지 후 재번호 (v3.25.0)**: 순번 기반 식별자
  (`feature-NNNN`, `META-NNNN`; 및 전환 전 잔존 순번 spec 앵커)를 여러 세션이 병렬 할당하면 번호가
  충돌할 수 있다. 새
  식별자 할당 직전, 동일 번호가 이미 점유됐는지(다른 worktree/세션의 meta 문서 또는
  `origin/main`) 확인하고, 충돌이면 **현재 점유된 최대 번호 + 1 로 1-step 재번호**한 뒤
  그 사실을 작업 로그에 한 줄 기록한다. 이 재번호는 정상 운영 동작이며 마찰로 간주하지
  않는다 — reservation registry / timestamp 식별자 전환은 `docs/DECISIONS.md` ADR-0022
  에서 검토 후 보류(불필요한 인프라 복잡도). 고병렬 위임으로 충돌 빈도가 높으면 doc-only
  편집도 worktree-first(§13.2.1)로 격리해 race 표면을 줄인다.
- **Feature-bound REPORT.md 충돌 방지** (v3.11.0+): `unit/<feature-id>/meta/REPORT.md`
  는 해당 feature 의 단일 worktree mutator 에 의해서만 mutation 된다 (F2 정책의
  feature-scoped 확장). 다른 worktree 가 동일 path 의 read 는 허용. 충돌 발생
  시 §13.2.5 의 ai/\* main drift gate 가 보충. `bin/list-shared-paths.sh` 가
  feature-bound REPORT.md 를 동적으로 열거한다.
- 아래 마커를 지원한다.

```md
<!-- HUMAN-LOCKED:START -->
이 구간은 사람 명시 지시 없이는 수정 금지
<!-- HUMAN-LOCKED:END -->

<!-- AI-EDITABLE:START -->
AI가 자유롭게 갱신 가능한 영역
<!-- AI-EDITABLE:END -->
```

### §13.2 작업 격리 정책 (Manual Parallel AI Worktree Isolation, v0.1)

단일 AI 가 순차적으로 작업하는 경우는 별도 격리 없이 §13.1 의 충돌 방지 규칙을
따른다. 이하 §13.2.1 ~ §13.2.5 는 **manual parallel AI** (사용자가 명시적으로 여러
Claude Code 세션을 띄워 각자 별 worktree 에서 독립 기능을 병렬 작업하는 시나리오)
전용 정책이다.

```
Lifecycle (state machine, manual parallel AI):

  [main worktree]                                          [linked ai/* worktree]
      │  trigger (user 명시 / entry arg dispatch)               │
      ├── git worktree add ../worktrees/<feat>                  │
      │   -b ai/<agent>/<feat>           ─────────────────►     │  Work (mutate
      │                                                         │   in this path
      │                                                         │   only; F1 binding)
      │     ◄────── PR / 자동 merge (§16.3 + §13.2.5) ──────────┤
      │                                                         │
      ├── self-merge ⇒ AI 자동 cleanup                          ├── other-merge
      │   (git worktree remove + git branch -d)                 │   ⇒ orphan
      │                                                         │   ⇒ user manual
      ▼                                                         ▼   sweep
   continue work                                            cleanup pending
```

#### §13.2.1 적용범위 및 Trigger

본 §13.2 는 **소비자 프로젝트의 모든 `repo/` mutation** 에 적용한다 (단일 AI
순차 작업 포함). v3.8.0 이전 (v3.8.0-rc.1) 의 "manual parallel AI feature 작업
한정" 범위는 §13.2.7 의 Consumer repo Immutability 정책 도입으로 확장되었다.
Variant exploration / 장기 risky refactor / QA worktree 시나리오는 별도 ADR
범위 (`docs/DECISIONS.md` ADR-0020 / ADR-0021).

**고병렬 활성 세션 — doc-only 편집도 worktree-first 권장 (v3.25.0)**: 여러 Claude
세션이 동시에 같은 소비자 `main` 을 전진시키는 환경에서는 단순 정책문서 수정조차 공유
`main` 과 race 한다 (`git pull --ff-only` 실패, TASK 번호 충돌 §13.1, MEMORY.md index
병렬 소실 등). 이 경우 doc-only 편집도 default-main 직접 작업 대신 worktree-first 로
격리하기를 권장한다 — §18.8.1 의 docs-only 경량 *검증* dispatch 와 보완 관계이며, 검증이
아닌 *격리* 측면을 담당한다. 단일 세션·저병렬 환경에서는 기존 default(§13.1 순차
충돌방지)로 충분하다.

`git worktree add` 호출 가능한 trigger 는 다음으로 제한한다:
1. **사용자 명시 지시** — 세션 안에서 "worktree 만들어서 X 작업해라" 류 직접 지시.
2. **`/_template:entry` arg-given dispatch** — entry persona 의 Phase 3.6 worktree
   decision tree (`_template/commands/entry.md`) 가:
   - task envelope 의 `worktree.feature_id` hint 를 보거나
   - **main checkout + `repo/` mutation 신호** 를 감지하면 (§13.2.7 F0)
   worktree create 권유 결정.
3. **§13.2.7 F0 gate 자체** — `bin/verify-completion.sh` check #11 이 main
   checkout 의 `repo/` mutation 을 detect 한 후 사용자에게 "worktree 로 전환"
   권유.

그 외 AI 의 자율 `git worktree add` / cwd 변경 / 다른 worktree 진입은 금지
(이하 **P1 trigger** — Position 1 trigger gating).

**P1 carve-out (v3.10.0+)**: trigger #2 (`/_template:entry` arg-given dispatch)
에서 worktree create 결정 이후, **AI 가 본 세션에서 새 worktree path 로 cd +
Phase 6 진입까지 같은 흐름으로 진행한다**. 사용자가 entry persona 를 명시 호출
했다는 사실 자체가 "이 세션이 해당 작업의 본체" 의도 표명이므로 cwd 변경은
사용자 의도와 정합. cd 후 다른 mutation 도 그 worktree path 안에서만 진행 — 그
worktree 가 binding branch 의 본체 (F1 보존). 본 carve-out 의 범위:

- entry persona Phase 3.6 의 자동 cycle-init 흐름 한정 — 다른 SKILL 의 자율 cwd
  변경에는 적용 안 됨
- 새 worktree 가 ai/* binding branch 인 경우 한정 (main / shared 보호)
- cd 후 작업이 그 worktree path 안에 머무는 한 — 다른 worktree 진입은 여전히
  P1 금지
- **디렉토리 이동은 `/cd` 로 (v2.1.170+)**: worktree path 로의 진입은 `/cd <path>`
  명령으로 수행해 prompt cache 를 보존한다. worktree 다회 진입이 본 템플릿 표준
  워크플로라, bash `cd` 로 이동하면 매번 prompt cache 가 깨져 재구축 비용이 누적된다.

trigger #1 (사용자 명시 worktree 지시) 도 동일한 carve-out 자연 적용 — 사용자가
명시 지시했으므로 cd 도 사용자 의도.

**Precedence (carve-out 우선)**: `/_template:entry` dispatch 대상이 `/_local:*` 류
명령이면 §13.2.4 carve-out 이 trigger 보다 우선한다 — 즉, entry 가 자동으로
worktree 진입을 결정하지 않고 main worktree 컨텍스트를 강제 유지한다. 마찬가지로
§13.2.4 의 다른 carve-out (template base, git pull, `/_template:init`) 도
§13.2.7 F0 보다 우선한다.

#### §13.2.2 Forbidden Actions

세 등급 (강→약). 각 forbidden 위반은 detection gate 가 별도 존재한다.

- **F1 (강)**: 단일 worktree 안에서 `git checkout <other-branch>` / `git switch
  <other-branch>` **금지**. 한 worktree = 한 branch 영구 binding (binding 유효 기간:
  해당 worktree 존재 동안). 다른 branch 작업은 새 worktree add 로 분리한다.
  **Detached HEAD 상태 mutation 도 동일하게 금지** (F1 회피 경로 차단).
  Detection: `bin/verify-completion.sh` check #10 (worktree binding) — 본 §13.2.2
  F1 enforcement gate. detached HEAD / binding mismatch 시 FAIL, escape hatch 는
  `GSTACK_SKIP_WORKTREE_CHECK=1` 또는 `--skip-worktree-check`.

- **F2**: 두 worktree 가 다음 path 들을 동시 수정 금지. 단일 worktree mutator
  지정, 나머지는 read-only (`git log`, `git diff`, `git show` 포함). path 목록은
  **동적 enumeration** — `bin/list-shared-paths.sh` 출력을 single source of truth
  로 사용한다. 정적 release artifact (`VERSION`, `CHANGELOG.md`,
  `TEMPLATE_CHANGELOG.md`, `package.json`) 도 해당 출력에 포함된다 (스크립트
  내부에서 정적 추가). hardcoded list 는 폐기 — `edit_policy: human-guided`
  frontmatter 또는 `<!-- HUMAN-LOCKED:START -->` 마커 + `repo/shared/**` 재귀 +
  release artifact 정적 추가의 합집합이 F2 path set.
  **Release/ship 행위 자체가 main worktree 전용** (§13.2.4 carve-out 보강).

- **F3**: append-only 문서 (`docs/LEARNINGS.md`, `docs/DECISIONS.md` 본문 history,
  `docs/STATUS.md` history) 에 **timestamp + session-ID 누락 추가 금지**.
  §13.1.a 참조. Detection: §18 cycle entry + reviewer manual scan.

#### §13.2.3 Lifecycle

- **Create (actor: trigger 받은 AI)** — §13.2.1 trigger 충족 시 AI 가 직접 실행:

  **Step 0 — base 브랜치 선검증 (worktree 생성 전)**:
  사용자 요청이 기존 기능·UI·코드를 참조하는 경우, worktree 를 만들기 전에 해당 기능이
  base 브랜치(main)에 존재하는지 grep 으로 선검증한다.
  ```bash
  # 참조 기능이 main에 있는지 확인
  git grep -l "<참조_식별자>" main
  ```
  grep 결과 0 hits 이면 `git worktree list` + 최근 미병합 브랜치 목록(`git branch -a --no-merged main`)을
  확인해 관련 base 후보를 조기 제시하고 사용자에게 어느 브랜치를 base로 할지 확인한다.
  main에 없는 기능을 main base worktree에서 작업하면 탐색 루프(다회 Explore/Read)와
  base 재선택이 반복될 수 있어 이 step을 생략하지 않는다.

  ```bash
  git worktree add ../worktrees/<feature-id> -b ai/<agent-id>/<feature-id>
  ```
  branch naming 은 `ai/<agent>/<feature>` 권장 (prescriptive, 강제 enforce 아님 —
  check #10 의 binding 검증과 분리). 사용자 명시 실행도 허용.

- **Work** — 한 worktree 안에서만 file write/delete (mutation 정의: write 또는
  delete). 다른 worktree path 의 **read 는 허용** (read = file system read + git
  read-only command). branch checkout / worktree-level mutation 은 read 아님 — F1
  적용. `shared/` 변경 의도 시 단일 mutator 지정 + REPORT.md 기록 + 머지 단계
  통합.

- **Merge** — ai/* → main. PR 또는 자동 머지 (§16.3 + §13.2.5).

- **Cleanup ownership** (P1 trigger 의 자연 예외 — 머지 시점 자동 허용):
  - **자기 머지**: trigger 받은 AI 가 자기 PR 머지 직후 동일 세션에서
    `git worktree remove <path>` + `git branch -d ai/<agent>/<feature>` 실행.
    P1 의 "생성 금지" 와 별개로 cleanup 은 자동 허용.
  - **타 worktree 머지 / orphan**: 다른 worktree AI 가 PR 머지를 트리거한 경우,
    원 worktree AI 는 머지 사실을 모름 → orphan worktree 누적. 본 사이클은
    **사용자 manual sweep**:
    ```bash
    git worktree prune
    git branch --merged main | grep '^  ai/' | xargs -r git branch -d
    ```
    자동 orphan sweep 은 본 사이클 외 (Reviewer Concerns 참조, ADR-0020).
  - `/_local:*` cron 은 worktree carve-out 이므로 자동 sweep 책임 없음.


#### §13.2.3-A Worktree / Branch 만료 판정 기준

> 근거 세션: root_download_docker_mysql_ai_delegated_dev `5eb851e9-5839-4812-a245-47808db68a01` (2026-06-04T08:28~08:29 KST)
> 사용자 원문: "만료된 워크트리 및 브랜치를 정리하기 위한 기준을 개선사항으로 알려줄 수 있을까요? 이후 inbox에 명시하여 template base에 배포할 예정입니다."

**상태 분류 및 판정 흐름**:

수치는 "언제 점검할지"를 결정하는 트리거이며, 실제 폐기 판정은 AI 맥락 질문으로 수행한다.

**1단계 — SAFE_REMOVE (수치 판정, 즉시 적용)**:

| 판정 조건 | 조치 |
|---|---|
| `git branch --merged main` = true (behind=0, ahead=0) | 즉시 제거 |
| `gh pr list --state merged --head <branch>` + main에 동일 내용 확인 | 즉시 제거 (squash merge 대응) |

**2단계 — 점검 트리거 (behind ≥ 50 OR last commit ≥ 7일)**:

위 조건 중 하나라도 해당하면 AI는 아래 맥락 질문 3가지를 수행한다.
SAFE_REMOVE가 아닌 branch에만 적용 (ahead = 0 AND Open PR 없는 경우).

**맥락 판정 질문 (AI 직관 판정)**:
1. 이 작업의 목적이 현재 main에 더 나은 구현으로 대체됐는가?
2. 이 branch가 해결하려던 요구사항이 아직 유효한가, 아니면 사라진 요구인가?
3. TASK.md에 BLOCKED 또는 HOLD 마커가 있는가?

판정 결과:
- 질문 1·2에서 "대체됨/사라짐" → **LIKELY_ABANDON** (사용자 확인 후 폐기)
- 질문 3에서 BLOCKED/HOLD AND 질문 1·2에서 유효 → **NEEDS_REVIEW** (TASK.md + PR 이력 검토 후 판정)
- 나머지 → **ACTIVE** (유지)

**예외 — 무조건 ACTIVE 처리**:
- Open PR 존재
- ahead = 0 AND 커밋 없음 (작업 준비 중, 세션 내 신규 생성)

**감지 Gap — squash merge 미감지**:
`git branch --merged main`은 squash merge를 인식하지 못한다 (behind > 0으로 표시).
→ 판정 시 `gh pr list --state merged --head <branch>` 조회를 git check와 병행 필수.

**감지 Gap — remote-only 브랜치 누락**:
`git worktree list`에는 나타나지 않는 remote-only 브랜치가 누적될 수 있다.
→ 감사 범위에 `git branch -r | grep ai/` 포함. MERGED PR 대응 remote branch는 `git push origin --delete <branch>` 대상으로 별도 목록화.

**정리 주기 권장**:

| 조건 | 주기 |
|---|---|
| 워크트리 수 ≥ 6 | 즉시 감사 |
| 워크트리 수 < 6 | 격주 |
| main에 대형 PR 병합 직후 | 해당 도메인 worktree 즉시 점검 |

**bin/worktree-audit.sh 구조 (권장 구현)**:
각 worktree를 위 4단계로 분류해 출력하는 감사 스크립트 — 실제 구현은 소비자 프로젝트 repo/bin/ 에 추가 권장:
1. `git branch --merged main` → SAFE_REMOVE 후보
2. `gh pr list --state merged --head <branch>` → SAFE_REMOVE 후보 (squash 대응)
3. ahead / behind / last_commit_days 계산
4. 기준표 적용 → 상태 출력
5. NEEDS_REVIEW 항목만 TASK.md 발췌 + 마지막 PR 제목 병기

#### §13.2.4 Carve-outs

- **`/_local:*` 명령과 scheduled-inspection cron 은 main checkout 전용**. 임의
  worktree 에서 호출 금지. 3-layer sentinel (cwd + hostname + 인프라) 깨짐 방지.
- **Release/ship 행위** (VERSION bump, CHANGELOG 정리, tag, npm publish 등) 도
  main checkout 전용. ai/* worktree 에서 release artifact 직접 수정 금지 (§13.2.2
  F2 와 결합).
- **Template base maintainer**: `repo/_template_maintainer/HISTORY.md` 가 존재하는
  영역 = template base 자체 (ai_delegated_dev_template 의 source-of-truth). 본
  §13.2 정책 비적용 — maintainer 가 main checkout 에서 직접 정책 doc / hop /
  gate 를 수정하는 것이 정상 워크플로우. 소비자 프로젝트에는 본 sentinel 부재
  → §13.2.7 F0 적용.
- **`git pull` / `git fetch` / `git submodule update --remote`**: read-only 또는
  fast-forward update 는 mutation 아님 — §13.2.7 F0 외. 단 conflict resolution
  merge commit 이 발생할 경우는 worktree 에서 수행 (이는 customization 영역).
- **`/_template:init` 부트스트랩**: `<wrapper>/repo/init 졸업 신호 (.template-init-marker / initialized_at / bootstrap=false)`
  마커 부재 시 1회 carve-out — 신규 consumer 의 첫 setup 시점은 worktree 없는
  main checkout 에서 진행. init 종료 시 마커 생성으로 carve-out 자동 만료.
- **Escape hatch (긴급 회피)**: `GSTACK_SKIP_REPO_IMMUTABILITY=1` env 또는
  `--skip-repo-immutability` cli flag — check #11 SKIP+WARN. 사용 의도는 hop
  emergency fix, CI 환경 차이 등 일시적 우회. 상시 사용 금지 (REPORT.md 에
  명시).
- **Entry persona inline execution (v3.10.0+)**: `/_template:entry` arg-given
  dispatch 의 Phase 3.6 worktree decision 이 worktree create 를 결정한 경우,
  AI 가 `bin/cycle-init.sh` 자동 실행 + 본 세션에서 새 worktree path 로 cd +
  Phase 6 진입까지 같은 흐름으로 진행한다 (§13.2.1 P1 carve-out 와 동일 기반).
  사용자가 별도 세션을 시작할 필요 없음 — `/_template:entry` 호출 1회로 cycle
  진입 완료. cycle 종료 시 `bin/cycle-finalize.sh` 의 자동 cleanup 정책 (§16.3
  Step 6) 과 정합 — 양쪽 끝 모두 단일 세션 자동 흐름.
- **Carve-out 의 의미**: "정책 외" = 본 §13.2 의 forbidden actions / lifecycle /
  trigger 룰이 적용되지 않음. 단 §13.1 일반 충돌방지 룰은 계속 적용. Conductor
  / IDE multi-tab 자동 worktree 및 Codex `-C` 옵션 worktree 활용도 본 사이클
  §13.2 정책 외 — 향후 별도 ADR.

#### §13.2.5 §16.3 worktree-aware Addendum (Normative)

**Normative source for §16.3 worktree-aware behavior.** §16.3 본문은 단일 checkout
가정으로 유지되고, 본 §13.2.5 가 worktree 환경에서의 보충 룰을 정한다. 두 곳에
같은 룰을 중복하지 않는다 (§16.3 에는 본 §13.2.5 로 cross-ref pointer 만).

- §16.3 조건표는 **per-worktree per-branch** 적용. 각 ai/* worktree 가 자기 PR /
  자동 push / main merge 결정을 독립으로 수행.
- **ai/\* 머지 후 main worktree pull** (actor: main worktree 의 다음 turn 진입자):
  ai/* PR 머지 후 main worktree 의 사용자/AI 가 다음 turn 의 first action 으로
  `git fetch && git pull --ff-only` 실행. Trigger 메커니즘: main worktree entry
  preamble (entry.md Phase 3.6 Step 1) 의 `git fetch origin` + `git rev-list
  --count HEAD..origin/main` 검사. behind > 0 일 때만 사용자 화면에 1줄 표면화.
  fetch 실패 = WARN ("remote unavailable") + 계속 진행 (D11A — 네트워크 가용성
  ≠ correctness). TTL cache 없음.
- 동시 push race 는 wedge B (manual parallel) 하 이론적 가능성. 발생 시 **사용자
  수동 직렬화** 가 권장 해결. 자동 재시도 알고리즘은 본 사이클 외.
- **ai/\* worktree 의 main drift 검출** (actor: ai/\* worktree 의 다음 turn
  진입자, v3.11.0+): ai/\* worktree 의 entry preamble 에서 다음을 수행한다.

  ```bash
  git fetch origin main 2>&1 || true
  behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
  ```

  `behind > 0` 일 때만 사용자 화면에 1줄 표면화 + 권유 (자동 실행 아님):

  > 본 worktree (`ai/<agent>/<feature>`) 는 main 보다 `<behind>` commit 뒤짐.
  > `git pull --rebase origin main` 권유 — drift 누적 시 PR 머지 conflict ↑.

  사용자 명시 confirm 후 rebase. fetch 실패 = WARN ("remote unavailable") +
  계속 진행 (main worktree behavior 와 동일 정책, D11A: 네트워크 가용성 ≠
  correctness). TTL cache 없음 — 매 turn 의 first action.

  본 gate 는 §16.3 의 main worktree pull 룰의 ai/\* 미러.

#### §13.2.6 샌드박스 실행

AI 가 코드를 실행 (테스트, 빌드 등) 할 때:
- 프로덕션 데이터에 접근하지 않는다.
- 네트워크 호출은 테스트 대상 또는 명시적으로 허용된 엔드포인트에만 수행한다.
- 파일 시스템 변경은 작업 디렉토리 내로 제한한다 (§13.2.2 F1/F2 와 결합).
- 구체적 범위는 §15.2 도메인 절대 금지사항에서 프로젝트별로 정의한다.

#### §13.2.7 Consumer repo Immutability (F0, Hard Gate, v3.8.0+)

소비자 프로젝트에서 `repo/` directory 의 직접 mutation 을 차단한다. v3.8.0-rc.1
의 §13.2 v0.1 정책이 "manual parallel AI feature 작업" 에 한정되어, 단일 AI 가
main checkout 에서 `repo/` 를 그냥 수정하는 시나리오를 막지 못한 결함을 보강
한다 (ADR-0021).

**적용 대상**: `_template_maintainer/HISTORY.md` 가 부재한 모든 git working tree
(= 소비자 프로젝트). 즉 `<wrapper>/repo/` 안에서 호출되는 verify-completion 이
sentinel 검사 후 본 정책을 발동.

**F0 (강) — Forbidden action**: 소비자의 **main worktree** 에서 `repo/` 안 path
mutation 금지. 단 §13.2.4 carve-out 외.

**Update path (유일한 수단)**:
```bash
cd <wrapper>/repo
git fetch origin
git pull --ff-only origin main
```
non-fast-forward 발생 시 (consumer 가 customize 했거나 main 이 history rewrite
된 경우) → `git pull` 거부 + 사용자 manual resolve. customization conflict 는
**ai/<agent>/<feat> worktree 에서 resolve 후 PR**.

**Customization path (작업 수단)**:
```bash
cd <wrapper>
git -C repo worktree add ../.worktrees/<feat> -b ai/<agent>/<feat>
cd .worktrees/<feat>
# ... 작업 ...
git push -u origin ai/<agent>/<feat>
# GitHub PR 또는 자동 머지 (§16.3 + §13.2.5)
```
머지 후 main worktree 의 다음 turn first action 으로 `git pull --ff-only` (§13.2.5
addendum 동일).

**Detection**: `bin/verify-completion.sh` check #11 (`check_11_repo_immutability`)
— `--pre-commit` 시점에 main checkout 의 `repo/` mutation 을 감지하여 FAIL.
META mode 우회 정책은 check #10 와 동일 (META mode 에서도 호출 — 정책 doc
변경 자체가 worktree 에서 일어나야 함).

**Sentinel 우선순위** (위에서 아래로, 매칭 시 즉시 PASS):
1. Escape hatch (`GSTACK_SKIP_REPO_IMMUTABILITY=1` / `--skip-repo-immutability`)
2. Non-git working tree (gate 비적용)
3. Template base (`_template_maintainer/HISTORY.md` 존재)
4. ai/* worktree (main worktree 아닌 linked worktree)
5. `/_template:init` 부트스트랩 (`init 졸업 신호 (.template-init-marker / initialized_at / bootstrap=false)` 마커 부재)
6. Clean working tree (mutation 없음)

위 6 조건 모두 부정 → FAIL with actionable guidance.

**Rationale** (왜 hard gate 인가):
- 소비자가 `repo/` 직접 수정 → template policy doc / hop / gate 망가짐 →
  upstream `git pull` 시 conflict 누적 → customization drift detection 불가
- customization 자체는 환영 — 단 worktree + branch + PR review 경로로
- main checkout 은 **template 의 read-only mirror** (upstream main 의 상태)
  로 유지

**Edge cases**:
- 신규 consumer 첫 commit (`/_template:init` 직후): `init 졸업 신호 (.template-init-marker / initialized_at / bootstrap=false)`
  마커가 init 종료 시 생성됨. init 자체는 carve-out 으로 통과, init 종료 후
  첫 commit 시점부터 F0 발동.
- consumer 가 `_template_maintainer/HISTORY.md` 를 잘못 복제: template base
  sentinel 오인. consumer 의 `bin/template-bake-check.sh` 가 본 파일을
  부수적으로 검출 (§19.2). 발견 시 manual cleanup 권유.
- WSL / Mac 경로 normalization 차이: `realpath` 로 main worktree path 정규화
  후 비교.


#### §13.2.8 Foreign Change Detection & Notification (v3.14.0+)

**목적**: `/_template:entry` 가 main worktree 에서 다른 AI 세션이 남긴
uncommitted 변경을 감지할 때, 해당 세션에 즉시 고유 worktree 진입을 알리는 정책.

**발동 조건**:
- 소비자 프로젝트 (template base 는 §13.2.4 carve-out 으로 제외)
- `cwd_inside_policy_root_main_worktree = true`
- `git status --porcelain` 결과 ≥ 1건 (uncommitted changes)

**발동 시점 (lifecycle)**:

| 시점 | entry.md Phase | 설명 |
|---|---|---|
| 세션 시작 (시작) | Phase 2.6 | entry persona 첫 bootstrap 시 즉시 탐지 |
| 배포·커밋 직전 (중간 검토) | Phase 6.4 Step 0 | commit 직전 re-check — 작업 도중 외부 주입 차단 |

두 시점 모두 동일한 서브 프로시저(탐지 → SendMessage → filesystem fallback → 표면화)를 실행한다.

**SendMessage 권한 제약 (v2.1.166+)**: SendMessage 는 세션 간 *알림·조정* 전용이며 권한
escalation 을 매개하지 않는다. 2.1.166+ 부터 타 세션이 보낸 SendMessage 는 user authority
를 전달하지 않아, 수신자는 relayed permission request 를 거부하고 auto mode 에서도 차단된다.
아래 알림 메커니즘은 이 제약 안에서 (승인 요청이 아닌 *상태 통지* 로만) 동작하도록 설계됐다 —
멀티에이전트 위임 세션이 SendMessage 로 권한을 우회·escalate 하도록 설계하면 조용히 차단된다.

**알림 메커니즘 (우선순위 순)**:
1. **SendMessage (FleetView / multi-agent 환경)**: `<project_root>/worktrees/REGISTRY.md`
   의 해당 세션 entry 의 `session_id:` 필드를 `to:` 인자로 사용.
   `session_id` 부재 시 fallback.
2. **Filesystem fallback (항상 수행)**: `<policy_root>/meta/FOREIGN_CHANGE_ALERT.md`
   에 1 entry append. 세션 폴링 또는 다음 entry 호출 시 자동 감지.

**알림 메시지 형식**:
```
⚠ [/_template:entry foreign-change alert]
main worktree 에 미커밋 변경 <N>건이 감지됩니다.
AGENTS.md §13.2.7 F0 위반 — 즉시 고유 worktree 에서 작업해 주세요.

  bash bin/cycle-init.sh --feature <slug>

변경을 새 worktree 로 이동 (git stash → cd <new_worktree> → git stash pop) 후 계속 작업하세요.
```

**수신 세션의 의무**:
- 알림 수신 즉시 (또는 다음 entry preamble 에서) F0 위반 해소:
  ```bash
  bash bin/cycle-init.sh --feature <feature_id>
  git stash
  cd <new_worktree_path>
  git stash pop
  ```
- `meta/FOREIGN_CHANGE_ALERT.md` 의 해당 entry 를 `status: resolved` 로 갱신 후 작업 계속.

**REGISTRY.md `session_id` 필드 규약 (v3.14.0+)**:
- 활성 세션 등록 시 `session_id:` 필드를 포함한다.
- FleetView 환경: `Agent(name=<session_id>)` 로 시작된 에이전트의 name 값과 일치.
- standalone CLI 환경: `claude-session-<PID>` 형식 (예: `claude-session-12345`).
- 부재 시 SendMessage 는 skip 되고 filesystem fallback 만 동작 (degraded mode).

**FOREIGN_CHANGE_ALERT.md entry 형식**:
```markdown
## [YYYY-MM-DD HH:MM:SS UTC] foreign-change alert
- detected_by: /_template:entry Phase 2.6
- dirty_count: <N>
- responsible_session_id: <session_id | unknown>
- message_sent: <yes | no>
- status: pending
```
`status` 값: `pending` → 미해소, `resolved` → 수신 세션이 worktree 로 이동 완료.

**template base 예외**: `_template_maintainer/HISTORY.md` 가 존재하는 repo (template
base 자체) 는 §13.2.4 carve-out 에 따라 본 §13.2.8 이 비적용. maintainer 의
main checkout 직접 수정은 정상 워크플로.
#### §13.2.9 배포 단계 격리 (Deploy-Stage Isolation, v3.28.0)

**배경**: worktree-first 정책(§13.2)은 편집·빌드를 격리하지만, docker compose 기반
deploy-backed 소비자는 `docker compose build` + `.env.secret` + `docker-compose.override`
가 단일 공유 REPO checkout 에 묶인다. 고병렬 환경에서 다른 세션이 그 공유 checkout 을
다른 브랜치로 점유하면 — (a) 잘못된 브랜치 코드로 이미지가 빌드되고, (b) 배포 중
main 이 전진해 ff-merge 가 반복 실패하며, (c) override 수동 수술이 필요해져 AI 가
push/merge 를 종착으로 오인하고 "완료" 를 조기선언한다.

**정의 — 배포 단계**: 이 절에서 "배포 단계" 란 다음을 포함한다:
- `docker compose build` / `docker compose up -d` / `docker-compose.override` 적용
- 컨테이너 재시작 + 환경변수(`KEK`, `.env.secret`) 주입
- healthz/서빙 assert 검증 (§16.3 deploy-backed 완료 기준 참조)

**정책 (apply — deploy-backed 소비자에만)**:

배포 단계 진입 직전, AI 는 다음 read-only 확인을 수행한다:

```bash
# 배포 직전 공유 REPO checkout 상태 확인
cd <consumer_repo_root>
DEPLOY_BRANCH=$(git -C repo branch --show-current 2>/dev/null || echo "unknown")
DEPLOY_DIRTY=$(git -C repo status --porcelain | grep -v '^??' | wc -l)
echo "shared REPO branch=$DEPLOY_BRANCH dirty=$DEPLOY_DIRTY"
```

판정:

| 조건 | 조치 |
|---|---|
| `DEPLOY_BRANCH = main` AND `DEPLOY_DIRTY = 0` | 정상 경로 — 공유 트리에서 배포 진행 |
| `DEPLOY_BRANCH ≠ main` OR `DEPLOY_DIRTY > 0` | 격리 경로 또는 단일 AI carve-out (아래 참조) |

**격리 경로 — 공유 트리 무수정 override 배포**:

공유 checkout 을 건드리지 않고, 본인 worktree 의 코드 기반 이미지를 배포한다:

```bash
# 1. 본인 worktree 에서 이미지 빌드 (공유 트리 미사용)
cd <my_worktree_path>
docker compose -f docker-compose.yml -f docker-compose.override.yml build

# 2. image 이름을 격리 override 파일에 고정 후, env-secret + no-build 로 한 번에 up
#    (공유 트리의 docker-compose.override.yml / .env.secret 미수정)
cat > /tmp/docker-compose.isolation.yml << EOF
services:
  <service>:
    image: <project>_<service>:latest   # step 1 에서 빌드된 이미지명으로 교체
EOF
docker compose   -f docker-compose.yml   -f /tmp/docker-compose.isolation.yml   --env-file <my_worktree_path>/.env.secret   up -d --no-build
```

공유 트리의 파일(`.env.secret`, `docker-compose.override.yml`)을 수정하지 않는다.
수정 시 다른 세션의 배포 환경을 오염시킬 수 있다.

**단일 AI / 공유 트리 단독 사용 carve-out**: `git worktree list` 결과가 1개 (main only)
이고 dirty 가 본인 커밋 예정 변경이라면 — 공유 트리가 다른 세션에 점유되지 않은 상황.
이 경우 격리 경로 대신 "커밋 후 main 에서 정상 배포" 경로로 진행한다.

**완료 기준 — deploy-backed 소비자**: §16.3 의 `#### deploy-backed 소비자 완료 기준` 참조.
push / PR merge 는 코드 완료이지 배포 완료가 아니다.

**template base 예외**: template base 자체 (§13.2.4 carve-out) 는 docker 배포 대상이
아니므로 본 §13.2.9 비적용.


### §13.3 계획-실행 분리 에이전트 (선택적 고급 패턴)

프로젝트가 계획 에이전트와 실행 에이전트를 분리 운용하는 경우:

| 에이전트 | 역할 | 수정 가능 | 읽기 전용 |
|---------|------|----------|----------|
| **계획** | FUNCTION.md, TASK.md §2.1 작성 | FUNCTION.md, TASK.md, REPORT.md | 코드 파일 |
| **실행** | 승인된 계획에 따라 코드 구현 | src/, tests/, MODIFY.md, REVIEW.md | FUNCTION.md, TASK.md |
| **검증** | TEST.md 케이스 실행·기록 | TEST.md §3 | src/, tests/ |

이 패턴은 선택 사항이며, 단일 AI 운용 시에는 §13.1의 기본 규칙만 따르면 된다.

---

# Part F — 환경 및 도메인

## §14. 환경변수 및 설정 관리

- **`.env` 실제 값은 저장소에 커밋하지 않는다** (반드시 `.gitignore` 포함, 자세한 자격증명 패턴은 `docs/SECURITY.md §4` 참조).
- 환경변수 및 설정 파일의 표준 작성 규칙·계층 구조·주석 표준은 `docs/CONVENTIONS.md §8` 을 참조한다.
- AI 가 새 환경변수를 추가하면 `.env.example` 과 `MODIFY.md` 를 동시에 갱신한다.
- 의미 변경(이름 유지 + 동작 변경)은 `REVIEW.md` 에 근거를 남긴다.

## §15. 도메인 커스터마이징 가이드

이 섹션은 프로젝트가 실제 도메인에 적용될 때 커스터마이징해야 할 영역을 안내한다.

### §15.1 도메인 우선순위 및 로드맵
프로젝트의 도메인별 구현 우선순위를 정의한다. 예시:

```md
### P0 (즉시)
- 핵심 기능 A가 실제 데이터 결과를 반환해야 한다

### P1 (단기)
- 기능 B의 품질 시나리오 검증

### P2 (중기)
- 기능 C 확장 및 최적화
```

### §15.2 도메인 절대 금지사항
프로젝트 도메인에서 AI가 절대 해서는 안 되는 행동을 나열한다. 예시:

```md
- 하드코딩된 매직넘버로 비즈니스 로직을 분기하지 않는다
- 외부 API 응답을 검증 없이 신뢰하지 않는다
- 사용자 데이터를 로그에 평문으로 기록하지 않는다
```

### §15.3 도메인별 환경변수 정책
`.env.example`에서 관리하는 변수의 카테고리와 변경 규칙을 정의한다.

### §15.4 도메인별 품질 게이트
기능 완료 시 도메인 특화 검증 항목이 있으면 여기에 추가한다.

#### §15.4.1 웹/UI 변경 — Windows 브라우저 검증 게이트 (필수)

본 프로젝트는 WSL2 위에서 동작하고 실제 사용자는 **Windows 브라우저**를 사용한다.
AI 가 CLI(curl) 또는 WSL 내부 headless 브라우저로만 검증하면 실제 사용자 화면과
괴리가 발생한다 (feature-0008-windows-browser-testing 도입 배경). 따라서:

- **웹/UI(화면·상호작용) 변경의 완료 검증은 실제 Windows 브라우저에서 수행한다.**
  AI 가 `bin/win-browser.py` 로 Windows Chrome/Edge 를 CDP 자동 구동(connect_over_cdp)하여
  조작·스크린샷한다 — 절차는 **PB-0008** (`playbooks/PB-0008-windows-browser-verification.md`).
- **검증 환경 분류** (각 feature `docs/TEST.md` §3 의 `Environment`):

  | Environment | UI 검증 인정 |
  |---|---|
  | `CLI` (curl / pytest / API 계약) | ✗ — 서버 계약 검증만 |
  | `WSL-headless` (feature-0004 browser service, gstack /browse) | ✗ — 화면 검증 불가 |
  | `Windows-browser` (`bin/win-browser.py` CDP 자동 구동) | ✓ |

- **웹/UI 변경은 `TEST.md` §3 에 `Environment: Windows-browser` Run 이 1건 이상 없으면
  "완료" 로 선언하지 않는다.** CLI·WSL-headless 결과만으로 "검증함"을 주장하지 않는다.
- 1회 브리지 setup 은 `bin/WIN-BROWSER-SETUP.md` (NAT+portproxy relay 또는 mirrored).
  `python3 bin/win-browser.py doctor` 가 준비 상태를 게이팅한다.
- **예외**: 브리지 setup 이 환경상 불가하거나(공용 CI 등) 변경에 UI 표면이 전혀 없으면,
  그 사유를 `TEST.md` §3 또는 `REPORT.md` 에 명시한다 — 누락을 "검증함"으로 오인 금지.
- **enforcement (staged)**: `bin/verify-completion.sh` check #13 이 웹 대상 파일 변경에
  `Windows-browser` Run 누락을 감지하면 경고한다 (v1 WARN-only, PR block 아님; 후속
  cycle MUST 격상 예정 — wiki check #12 와 동일한 staged rollout).

---

# Part G — 완료 및 동기화

## §16. 완료 기준 및 검증 절차

### §16.1 완료 기준

작업은 아래를 만족해야 완료로 본다.
- 기능 동작이 구현되었다.
- `FUNCTION.md`가 현재 동작과 일치한다.
- `TASK.md`, `MODIFY.md`, `REVIEW.md`, `REPORT.md`, `TEST.md`가 필요한 수준으로 갱신되었다.
- **웹/UI 변경인 경우** `TEST.md` §3 에 `Environment: Windows-browser` Run 이 1건 이상 기록되었다 (§15.4.1 · PB-0008). UI 표면이 없거나 브리지 setup 불가 시 사유가 명시되었다.
- `ANCHOR.md` §1~§3이 작성되었다 (24h bootstrap grace 이후).
- `ANCHOR.md` §4 human 검증 로그는 일반 TASK cycle 완료 조건이 아니며, release/milestone 검토 또는 방향 전환 검증이 필요할 때만 요구된다 (§18 참조).
- 남은 리스크와 후속 작업이 `REPORT.md`에 정리되었다.
- `/repo/docs/STATUS.md`에 기능 상태가 반영되었다.
- `/repo/docs/CODEBASE_MAP.md`에 새 파일/모듈이 반영되었다 (해당 시).

### §16.2 완료 선언 (Completion Checklist)

AI가 작업 완료를 선언할 때는 `TASK.md`의 Completion Checklist를 명시적으로 체크한다:

```md
## 7. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 자동 테스트가 통과한다
- [ ] 웹/UI 변경 시 실제 Windows 브라우저 검증을 수행하고 TEST.md §3에 `Environment: Windows-browser` Run을 기록했다 (§15.4.1 · PB-0008) — 또는 UI 표면 없음/브리지 불가 사유 명시
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] ANCHOR.md §1~§3이 채워져 있다 (또는 24h bootstrap grace 범위 내이다) (§18)
- [ ] `bin/verify-completion.sh --pre-commit <feature-id>`가 PASS한다 (§16.3)
- [ ] Git 커밋이 완료되었다 (§16.3)
- [ ] Git 원격 동기화가 완료되었다 또는 동기화 불가 사유가 기록되었다 (§16.3)
- [ ] (웹 UI 프로젝트만) 웹 UI 변경 시 `/browse` 스킬로 Windows 브라우저 렌더링 시각적 확인 완료 — WSL curl/wget/playwright 응답만으로 완료 보고 금지 (§16.6)
- [ ] (deploy-backed 소비자만) 라이브 재배포 검증 완료 — cycle-finalize(PR 머지) 후 `docker compose up --build` + healthz PASS + KEK/secret 주입 확인 (§16.3 deploy-backed 소비자 완료 기준)
```

### §16.3 Git 동기화 절차 (verify-completion 기반)

작업 완료 선언 전에 AI는 반드시 `bin/verify-completion.sh`를 호출한다.
이 스크립트가 기존 완료 체크리스트 검증과 Git 동기화 절차를 흡수한다.
AGENTS.md §1 AI 전권위임 원칙에 부합한다 — 스크립트는 **AI가 호출하는 도구**이지
인간 개입이 아니다.

**기본 원칙: AI 작업자는 완료 가능한 cycle을 사용자 확인 대기로 멈추지 않는다.**
pre-commit 검증이 PASS하고 BLOCKED/Critical/Major 승인 대기 항목이 없으면 AI가
직접 commit한다. 원격 저장소가 설정되어 있고 push 가능하면 AI가 직접 push한다.
`commit/push 결정은 사용자에게 위임` 같은 응답은 정책 위반이다.

#### Step 0: 완료 선언 정의

"완료 선언"이란 AI가 사용자에게 "작업 완료" 메시지를 전달하기 직전의 지점이다.
이 시점 이전에 working tree는 정리된 상태여야 한다.

#### Step 1: 사전 검증 (pre-commit)

```
1. 코드 + docs 변경 (working tree에서)
2. ANCHOR.md §1~§3 확인 — §4 human 검증 로그는 release/milestone 또는 방향 전환 검증 시에만 확인 (§18 참조)
3. git add <변경된 모든 파일> (prefer named add, never -A)
4. bash bin/verify-completion.sh --pre-commit <feature-id>
   → FAIL: stderr의 누락 항목 해결 후 step 1로 복귀
   → PASS: step 2로 진행
```

#### Step 2: 커밋

커밋 메시지 형식은 `CONTRIBUTING.md`의 커밋 규칙을 따른다. **필수 trailer**:

```
<type>(<scope>): <summary>

<body>

Task-Cycle: <feature-id>
```

`Task-Cycle` trailer는 이 커밋이 어느 TASK cycle에 속하는지 명시한다
(§18의 Cycle Boundary 정의 참조). 이 trailer가 없는 commit은 post-commit hook의
verify 대상이 되지 않는다.

#### Step 3: 사후 검증 (post-commit)

`.git/hooks/post-commit`이 자동으로 `verify-completion.sh --post-commit <feature-id>`
를 호출한다 (`bin/install-hooks.sh`가 설치). FAIL 시:
- hook은 commit을 차단하지 않는다 (이미 발생). 경고만 출력.
- AI는 출력을 읽고 **새 commit**으로 누락 항목을 수정한다. `git commit --amend` **금지**.

#### Step 4: 원격 동기화 판정

원격 저장소(`origin`)가 설정되어 있는 경우, 아래 조건표에 따라 동기화 범위를 판정한다.

| 조건 | 동작 |
|------|------|
| BLOCKED 항목 없음 + Critical/Major 승인 대기 없음 | **AI가 commit 후 자동 동기화** (push) |
| BLOCKED 항목 있음 또는 Critical/Major 승인 대기 | **AI가 commit만** 수행, `REPORT.md`에 동기화 보류 사유 기록 |
| 원격 저장소 미설정 | **커밋만** 수행, 원격 설정은 사람에게 위임 |

#### Step 5: 결과 기록

Git 동기화 결과를 `REPORT.md`에 기록한다.

```md
### Git 동기화 결과
- 커밋: <commit-hash> (<branch>)
- verify-completion: PASS / FAIL (재시도 N회)
- Push: 완료 / 보류 (사유: ...)
- main 병합: 완료 / 해당없음 / 보류 (사유: ...)
- 충돌 해결: 없음 / AI 자율 해결 (건수, 요약) / 사람 위임 (사유)
```

> **REPORT.md "Git 동기화 결과" 정합 명세 (v3.9.0+)**: 본 section 은 PR push *전*
> (cycle commit 안) 또는 PR description body 에 명시한다. 머지 후 별 commit 으로
> 추가 시 `verify-completion` 새 cycle gate 가 트리거되어 overhead 가 크다 —
> 권장하지 않는다. PR 머지 결과 (target HEAD, 머지 commit hash) 는 Step 6 의
> cleanup 종료 보고와 GitHub PR UI 로 충분.

#### Step 6: Cycle Cleanup (PR 머지 후, v3.9.0+)

PR 머지 + cleanup 은 본 Step 의 자동화 대상이다 — cycle 종료 시점에서 BLOCKED
신호가 없으면 사람 명시 요청 없이 자동 진행한다. Step 4 (원격 동기화 판정)
조건표가 commit/push/병합 자동화를 정의한 것과 동일한 정책으로 cleanup 까지
확장한다.

> **자동 진행 정책 (v3.9.0+)**: cycle 종료 시점 (verify-completion PASS + PR
> 생성 완료) 에서 다음 normal 경로는 사람 명시 요청 없이 진행한다:
> - PR 상태가 MERGEABLE + mergeStateStatus CLEAN → `gh pr merge --<strategy>`
>   (`--delete-branch` 미사용 — worktree-first 에서 gh 의 머지-후 로컬 체크아웃 전환이
>   거부돼 매 cycle 실패. 로컬 브랜치는 아래 `branch -d`, 원격 브랜치는 best-effort
>   `git push origin --delete` 가 분리 처리)
> - 머지 직후 main worktree `git fetch + pull --ff-only origin main`
> - 자기 worktree clean + worktree remove + local branch -d + 원격 브랜치 best-effort 정리
>
> 다음 abnormal 경로는 자동 중단 + 사용자 결정 (AGENTS.md §16.3 Step 4 의
> 충돌/blocked 처리 동일):
> - PR mergeable != MERGEABLE / state == CLOSED — 즉시 중단
> - 자기 worktree dirty — 중단 + stash/discard/commit 안내
> - `pull --ff-only` non-fast-forward — 중단 + manual resolve 안내 (silent
>   merge/rebase 금지)
> - `branch -d` unmerged (squash/rebase merge 의 경우 정상) — WARN + force-delete
>   안내 (silent `-D` 차단, 사용자 명시 confirm 후 진행)
>
> AI 작업자가 본 Step 진입을 결정하는 trigger 는 사용자 명시 요청이 아니라
> "cycle 종료 + verify-completion PASS + BLOCKED 신호 없음". `bin/cycle-finalize.sh`
> 는 위 정책을 codify 한 reference 구현이며, dry-run 으로 사전 검증 후 자동 실행
> 또는 직접 실행 모두 가능하다.

##### Step 6.1: main 최신화

main worktree (또는 main checkout) 에서:

```bash
git fetch origin
git pull --ff-only origin main
```

- `fetch` 실패 (네트워크/인증): WARN + 사용자 결정 (계속 / 중단). §13.2.5 의
  fail-loud 회피 패턴 동참.
- `pull --ff-only` 가 non-fast-forward 로 실패: 본 cleanup 중단 + 사용자 manual
  resolve. 자동 `merge` / `rebase` 금지 (silent history rewriting 차단).

##### Step 6.2: 자기 worktree working tree clean 검증

`git status --porcelain` 가 비어 있어야 함. dirty 시 사용자 결정:
- `stash` (later restore)
- `discard` (사용자 명시 + 데이터 손실 경고)
- `commit + 머지 재진행` (cleanup 중단)

##### Step 6.3: cwd 이동 (자기 worktree 내부일 때만)

자기 working dir 안에서 worktree 를 remove 할 수 없다. cwd 가 자기 worktree
내부면 main worktree 로 `cd` 후 진행.

##### Step 6.4: worktree remove

```bash
git -C <main-worktree> worktree remove <self-worktree-path>
```

##### Step 6.5: local branch delete

```bash
git -C <main-worktree> branch -d <self-branch>
```

`-d` 가 unmerged 로 실패하면 사용자 confirm 받은 후 `-D` (force). PR 이 squash /
rebase 머지된 경우 local branch 의 commit hash 가 main 에 없을 수 있다 (squash
merge 패턴) — 이 때 `-D` 가 정상 경로. **squash/rebase 머지 시 -D 사용은
강제 자율 결정이 아니라 사용자 confirm 후 진행** (silent force-delete 차단).

##### Step 6.6: §13.2.4 채택 consumer REGISTRY entry 이동

`<project_root>/worktrees/REGISTRY.md` 존재 시 (consumer 가 §13.2.4 채택) 자기
session entry 를 `## 활성 세션` → `## 종료 세션` 으로 이동 + `meta/SESSIONS_LOG.md`
한 줄 append. 부재 시 silent skip.

##### 자동화 (cycle-finalize.sh, v3.9.0+)

위 6 sub-step 의 reference 구현은 `bin/cycle-finalize.sh` 다 — 호출 패턴:

```bash
bash bin/cycle-finalize.sh --pr <PR-NUMBER> \
  [--merge-strategy merge|squash|rebase] \
  [--keep-worktree] [--keep-branch] [--dry-run]
```

`--dry-run` 으로 사전 검증 후 실제 호출. idempotent (이미 머지된 PR / 이미
삭제된 worktree 호출 시 step 별 skip).

> **실행 위치 (v3.35.0)**: cycle-finalize 는 **finalize 대상 worktree 안에서 실행**하도록
> 설계됐다 (Step 6.3 가 자기 worktree 내부면 자동으로 main 으로 cd 후 remove). 제거 대상
> worktree 를 cwd 로 둘 수 없다는 이유로 **main 에서 실행하면 `self == main` 판정 →
> worktree/branch 정리가 skip** 되어 머지된 feature worktree 가 stale 로 남는다. main 에서
> named worktree 를 정리하려면 `--target-worktree <path>` (또는 `--branch <name>`) 로 대상을
> **명시**한다 — 이 때 SELF 대신 그 worktree 를 정리 대상으로 삼는다 (target ≠ main 가드·clean
> 검증 유지). 대상 미지정 + `self == main` 이면 silent skip 대신 actionable 경고를 출력한다
> (leftover 누적 차단).

#### SPOF 대응 (bypass 금지)

`verify-completion.sh`는 모든 commit의 gate이며 bypass 경로를 제공하지 않는다
(SPOF 복구 방법은 §18.4 "운영 vs 메타 층위" 참조).

#### Worktree 환경에서의 적용

본 §16.3 sync 결정 로직은 단일 checkout 가정으로 유지된다. manual parallel AI
worktree 환경에서는 main worktree stale 위험이 추가되며, 이에 대한 보충 룰은
**Normative source: §13.2.5 (Manual Parallel AI Worktree Isolation Addendum)** 에
정의된다. ai/* PR 머지 후 main worktree 에서의 일회성 `git fetch && git pull
--ff-only` 권유 및 fetch 실패 처리 (WARN + 계속) 룰은 그곳을 참조한다.

#### 캐시-키/fingerprint 변경의 blast-radius 사전측정 (v3.35.0)

**적용 대상**: cache-key / fingerprint / content-hash 계산식을 바꾸는 변경 (예: 정규화 규칙 추가,
해시 입력 필드 변경, 직렬화 포맷 변경). dev/staging 분리가 없는 **라이브=운영** 소비자에 특히 중요하다.

**원칙**: 1차 diff 가 양성(예: casefold 정규화)으로 보여 §12.3 Major("외부 비용") 게이트가
트리거되지 않더라도, **fingerprint 가 바뀌면 그 키에 묶인 모든 캐시·파생 산출물이 무효화**되어
대량 재생성으로 번질 수 있다 (실측: 정규화 1건 배포 → 도달가능 ~1,979 테이블 전수 LLM 재생성
~2,000 호출 폭주). 따라서 이런 변경을 **라이브에 적용하기 전** 다음을 수행한다:

1. **무효화 규모 추정**: 바뀐 fingerprint 로 무효화될 캐시/파생 산출물 수를 추정한다
   (예: 영향 테이블·문서·임베딩 수).
2. **재생성 단가 곱산**: 추정 수 × 산출물당 재생성 비용(LLM 호출·외부 API·연산)으로 예상 외부
   비용을 산출한다.
3. **임계 판정**: 예상 외부 비용이 임계를 초과하면 **Major 로 격상**(§12.3) — 사람 승인 후 배포.
   임계 이하면 자율 진행하되 추정치를 `REVIEW.md` 에 기록한다.

이 게이트는 §22.6 spawn blast-radius·§13.2.9 deploy-stage isolation 과 보완 관계다 — 그것들은
fan-out 규모·배포 단계를 다루고, 본 게이트는 **변경 자체의 2차 무효화 비용**을 다룬다.

#### deploy-backed 소비자 완료 기준 (v3.28.0)

**적용 대상**: docker compose 기반 배포(`docker compose up`, `docker compose build`)
가 완료 기준에 포함되는 소비자 프로젝트. CLI 전용·API 전용·데이터 파이프라인 프로젝트에는
적용하지 않는다.

**원칙**: push / PR merge 는 **코드 완료**이지 **배포 완료**가 아니다. deploy-backed
소비자에서 "작업 완료" 선언은 다음 두 조건을 **이 순서대로** 충족한 이후에만 허용된다:

1. **cycle-finalize 완료**: §16.3 Step 6 (PR 머지 + worktree cleanup) 가 완수됨.
   → PR merge 후 main 에 feature code 가 반영된 상태.

2. **라이브 재배포 검증 (Live Redeploy Verify)** — main 기반 이미지로 수행:
   - `docker compose up -d --build` 또는 동등한 재빌드·재시작이 실제 수행됨
   - healthz / 서빙 엔드포인트 assert (예: `curl -sf http://localhost:<port>/healthz`) 가 PASS
   - 핵심 환경변수 (`KEK`, secret 등) 가 컨테이너에 정상 주입됨 확인
     (예: `docker exec <container> env | grep KEK`)

순서 중요: cycle-finalize 전 재배포 검증(격리 경로 배포 등)은 **staging validation** 으로,
완료 조건 2 를 충족하지 않는다. feature code 가 main 에 merge 된 이후의 재빌드·healthz
PASS 만이 최종 완료 기준이다.

**금지 패턴**:
- `git push` 또는 `gh pr create` 후 "배포 완료" 선언 — push 는 코드 업로드이지 배포가 아님
- `gh pr merge` 후 "완료" 선언 — 머지는 코드 통합이지 컨테이너 재배포가 아님
- healthz 없이 `docker compose up -d` 로그만 확인 후 "서비스 정상" 선언
- KEK / secret 미주입 컨테이너를 "배포 완료" 처리

**공유 REPO checkout 경합 대응**: 배포 전 공유 checkout 이 다른 세션에 의해 점유된
경우 §13.2.9 의 격리 경로(override 배포)를 적용한다. 경합 중에 배포 단계를 진행하면
잘못된 코드가 컨테이너에 올라갈 수 있다.


### §16.4 병합 충돌 해결 정책

병합 충돌 발생 시 AI는 아래 분류 기준에 따라 자율 해결 또는 사람 위임을 판정한다.
**판정 원칙: 충돌의 양쪽 의도가 모두 명확하고 공존 가능하면 AI가 해결한다. 의도가 상충하거나 판단이 필요하면 사람에게 위임한다.**
단, "사람 판단 필요"는 작업 중단의 기본값이 아니다. 처음 요청 의도가 왜곡될 우려가
없고 검증 결과가 명료하면 AI는 PASS로 판정하고 cycle을 계속 진행한다.

#### AI 자율 해결 가능 (명료한 충돌)

| 유형 | 해결 방법 |
|------|----------|
| **append-only 문서** 양쪽 신규 항목 추가 | 양쪽 항목 모두 유지 (시간순 정렬) |
| **서로 다른 섹션** 변경이 충돌 마커로 표시 | 양쪽 변경 모두 반영 |
| **섹션 번호** 재조정 충돌 | 전체 번호를 순차적으로 재정렬 |
| **주석·포맷·공백** 변경 충돌 | 최신 의도 반영 |
| `.gitignore` 패턴 추가 충돌 | 양쪽 패턴 모두 유지 |
| `STATUS.md` 상태 갱신 충돌 | 최신 상태 우선, 이전 상태는 이력에 보존 |
| **설정 파일 주석** 추가/수정 충돌 | 더 상세한 쪽 채택 |
| **독립적 파일 변경**이 동일 커밋에 묶인 경우 | 각 파일의 변경을 개별 반영 |
| `ANCHOR.md` §4에 서로 다른 human 엔트리 append | 두 엔트리를 모두 보존하고 시간순 정렬 |
| 일반 TASK cycle에서 `ANCHOR.md` §4 엔트리 부재 | 사용자 확인 요청 없이 PASS (§18.2, §18.5) |

#### 사람 판단 필수 (모호한 충돌)

| 유형 | 사유 |
|------|------|
| **동일 함수/로직**에서 서로 다른 구현 | 비즈니스 의도 판단 필요 |
| `HUMAN-LOCKED` 구간에 영향 | 사람 승인 없이 수정 불가 (§13.1) |
| **비즈니스 로직/의사결정** 상충 | 요구사항 해석 분기 |
| **보안 관련** 코드·설정 충돌 | 보안 수준 판단 필요 (§12) |
| `source_of_truth` 문서에서 **동일 사실에 다른 내용** | 정본 판단은 사람 권한 |
| **삭제 vs 수정** 충돌 (한쪽 삭제, 다른 쪽 수정) | 삭제 의도 확인 필요 |
| **외부 계약·비용·인증** 관련 변경 충돌 | Critical/Major 등급 (§12.3) |
| `ANCHOR.md` §4 작성이 완료 조건으로 명시됨 | §4는 `human:<name>` only라 AI가 대체 작성 불가 (§18.2) |
| 요청이 `ANCHOR.md` §1~§3과 명백히 충돌함 | 방향 전환 검증 또는 `direction-drift`가 필요 (§18.3) |

#### 해결 절차

```
충돌 발생
  │
  ├─ 각 충돌 파일에 대해 명료/모호 분류
  │
  ├─ 모든 충돌이 명료 → AI 자율 해결
  │    ├─ 충돌 마커를 제거하고 해결 방법에 따라 내용 병합
  │    ├─ git add → git commit (병합 커밋)
  │    ├─ REVIEW.md에 해결 내역 기록
  │    └─ 동기화 계속 (push)
  │
  ├─ 하나라도 모호 포함 → 부분 해결 + 사람 위임
  │    ├─ git merge --abort (병합 중단)
  │    ├─ REPORT.md에 BLOCKED: merge-conflict-needs-review 기록
  │    │    ├─ AI 해결 가능 항목 목록
  │    │    ├─ 사람 판단 필요 항목 + 양쪽 내용 요약
  │    │    └─ AI의 권장 해결 방향 (참고용)
  │    └─ 사람 검토 후 재시도
  │
  └─ 판단 불가 → 전체 사람 위임
       ├─ git merge --abort
       └─ REPORT.md에 BLOCKED: merge-conflict 기록
```

#### 자율 해결 시 커밋 메시지

```
merge(<scope>): <feature-branch>를 main에 병합

- <파일1>: <충돌 유형> — <해결 방법>
- <파일2>: <충돌 유형> — <해결 방법>
```

### §16.5 완료 응답 금지 패턴

AI 작업자는 완료 가능한 cycle에서 아래 응답으로 작업을 멈추면 안 된다.

- `자동 commit/push는 하지 않았습니다`
- `commit 결정은 사용자에게 위임합니다`
- `push 여부를 확인해 주세요`

허용되는 예외는 다음뿐이다:

- `verify-completion` FAIL 또는 테스트 FAIL이 남아 있고 AI가 같은 cycle 안에서 복구할 수 없음
- `BLOCKED` 항목 또는 Critical/Major 승인 대기가 `REPORT.md`에 기록됨
- 원격 저장소가 없거나 인증/권한 문제로 push가 기술적으로 불가능함
- 사용자가 명시적으로 "commit/push 하지 말라"고 지시함

예외가 아니면 AI는 §16.3에 따라 commit하고, 가능한 경우 push까지 완료한 뒤 결과를
`REPORT.md`와 최종 응답에 기록한다.


### §16.6 웹 UI 프로젝트 시각적 검증 기준

**적용 대상**: 웹 브라우저 UI(HTML/CSS/JS 렌더링)가 포함된 프로젝트에만 적용.
CLI 전용·API 전용·데이터 파이프라인 프로젝트에는 적용하지 않는다.

**원칙**: AI 작업자가 웹 UI 변경을 완료했다고 선언하려면 실제 브라우저 렌더링 확인이 필요하다.
WSL 내 curl, wget, requests, pytest 등 HTTP 응답 검사만으로는 시각적 완료 조건을 충족하지 않는다.

**필수 확인 방법**: `/browse` 스킬(gstack headless-but-real-engine)로 변경된 페이지를 열고
레이아웃·버튼·폼·모달 등 변경 영역을 시각 캡처(스크린샷/element-screenshot)와 element
상태로 확인한다 (아래 *evidence 의 변경-클래스 분기* 참조).
`/browse` 스킬은 내부적으로 MCP 브라우저 도구를 사용하며, 기본 정본 경로로 인정한다.

**검증 evidence 의 변경-클래스 분기 (MUST)**: "스크린샷 또는 element 상태" 의 OR 는
변경 클래스에 따라 갈린다. **존재·동작·데이터 표출** 검증(요소가 있는지, 클릭이
동작하는지, 데이터가 렌더되는지)은 element 상태(DOM-eval: 클래스/속성 존재, hit-test,
복사 텍스트 실측 등)로 충분하다. 그러나 **레이아웃·정렬·간격·줄바꿈·overflow·겹침 등
"픽셀로만 드러나는" 변경**은 element 상태로 검증할 수 없다 — DOM-eval 은 요소의 존재·
동작은 확인하지만 렌더된 픽셀의 정렬·간격·줄바꿈은 보지 못한다. 이 클래스는 변경 영역이
**판독 가능하게 담긴 시각 캡처(스크린샷/element-screenshot/clip)** 를 필수로 하며 element
상태로 대체할 수 없다.

**캡처 도구 한계 시 — escalate, 다운그레이드 금지 (MUST)**: 전체화면 스크린샷이 변경
영역을 판독불가 크기로만 담으면 검증은 **미완**이다. element-screenshot·clip·뷰포트 축소·
DOM 복제 확대 등으로 판독 가능한 캡처를 확보한다. 확보에 실패하면 "라이브 eval 로 충분"
으로 마무리하지 말고 **시각검증 미충족(WARN/미완)으로 명시**한다 — "핵심 검증은 eval 로
완료" 식 자기-충족 선언으로 픽셀-클래스 변경의 PASS 를 선언하지 않는다.

**기본 추정 — UI-affecting 변경은 픽셀-클래스로 간주 (MUST)**: 변경이 렌더 결과에
영향을 줄 수 있으면(UI-affecting) 기본값은 "픽셀-클래스"이며 판독 가능한 시각 캡처를
요구한다. element 상태만으로 충분하다고 판단하려면 **그 변경이 렌더된 기하(위치·정렬·
간격·줄바꿈)에 영향을 주지 않는 이유를 명시**해야 한다 — 분류의 입증 책임은 "element
상태로 충분" 쪽에 있다 (값 표시 텍스트 변경, 순수 핸들러 연결 등 기하 무관 변경이 예외).
이 기본 추정은 "behavioral 이라 eval 로 충분" 식 회피로 픽셀 회귀가 재발하는 것을 막는다.

**headless `/browse` 도달불가 환경 — host-side real-browser 동등 인정 (v3.29.1)**:
`/browse` (gstack headless MCP) 가 타깃에 **도달할 수 없는** 환경 — 관리콘솔 HTTPS 로그인
게이트, WSL2 네트워킹 한계, 인증 토큰 주입 불가 등 — 에서는, 프로젝트가 운용하는 **host-side
real-browser 검증**(예: WSL 밖 Windows 브라우저로 실 화면을 띄워 확인)을 `/browse` 와 **동등한
시각적 확인 경로**로 인정한다. 단 동등 인정의 전제는 다음을 모두 만족할 때다:
- **스크린샷 evidence 필수** — real-browser 로 확인했다는 선언만으로는 불충분. 변경 영역이
  렌더된 실제 화면 스크린샷을 응답에 첨부한다 (`/browse` 와 동일 기준). 픽셀-클래스 변경
  (레이아웃·정렬·간격·overflow)은 위 *evidence 의 변경-클래스 분기* 에 따라 element 상태
  캡처로 대체할 수 없다.
- **anti-"curl=완료" 가드 유지** — host-side 경로를 인정해도 WSL curl/wget/requests/playwright-CLI
  의 HTTP 응답 검사만으로 완료를 선언하는 것은 여전히 금지(아래 금지 패턴). real-browser 인정은
  "실제 렌더 화면 + 스크린샷" 을 갖춘 경우에 한하며, 검증 강제력을 약화시키지 않는다.
- **도달불가의 실재성** — 단순 편의가 아니라 `/browse` 가 구조적으로 도달 못하는 환경(로그인
  게이트·네트워킹)일 때만 적용. `/browse` 로 도달 가능한데 host-side 로 우회하는 것은 비인정.

**gstack 검증 스킬 호출 위치 (wrapper-layout 소비자)**: `/browse`·`/design-review`·`/qa` 등
gstack 검증 스킬은 git-root(cwd) 를 전제로 동작한다. 소비자가 wrapper-layout(cwd ≠ git-root,
git repository 는 `repo/` 내부)인 경우, 이들 스킬은 **git-root(`repo/`) 기준 cwd 에서 호출**한다
(§13.2 의 `repo/` 격리 관례 및 prompt.md 운영 경로 관례와 정합). wrapper cwd 에서 직접 호출하면
스킬이 git repo·바이너리 경로를 못 찾아 reconciliation 에 소모된다.

**데이터 의존 UI 요소 (v3.25.0)**: DB 컬럼·API 응답 등 데이터에 의존해 렌더되는 UI 요소
(예: 특정 레코드의 reason 텍스트)는 **대표 live data 가 실재·충전된 상태에서 user-facing
outcome 렌더를 확인한다**. element 가 정상 동작해도 소스 데이터가 비면 화면은 공백이고,
`/browse` 의 빈 상태 element 존재 점검이 이를 "정상" 으로 오판할 수 있다. 대표 데이터를
1건 이상 생성·주입한 뒤 그 값이 실제 화면에 표시되는지까지 확인해야 완료로 인정한다 —
빈 상태 element 점검만으로 UI feature 완료를 선언하지 않는다.

Playwright를 사용해야 하는 경우, `/browse` 스킬의 MCP 경로를 통해 실행해야 한다.
WSL bash에서 `playwright` CLI를 직접 실행하는 것은 렌더링 확인으로 인정되지 않는다.

**금지 패턴**:
- "curl 응답 200 OK — 완료" (렌더링 미확인)
- WSL bash에서 `playwright test` 직접 실행 후 "테스트 통과 — 완료" (`/browse` MCP 경로 미사용)
- 스크린샷 없이 "UI 정상 확인" 선언
- "Ctrl+Shift+R 후 확인해 주세요" 등 사용자에게 새로고침·재확인을 위임하고 완료 선언 — 위임 자체는 검증이 아님
- "검증 단계가 누락됐습니다" 인정 후 브라우저를 실행하지 않고 완료 처리 — 인정만으로 검증이 완료되지 않음
- "라이브 eval(element 상태)로 충분" — 캡처가 변경 영역을 판독 가능하게 담지 못하자
  레이아웃·정렬 등 픽셀-클래스 변경을 element 상태로 PASS 선언 (위 *evidence 의 변경-클래스
  분기* 위반; 캡처 escalate 또는 시각검증 미완 보고가 정답)

**완료 선언 게이트**: UI-affecting 변경(HTML/CSS/JS 수정, 컴포넌트 추가·삭제, 레이아웃 변경 등)은
`/browse` 스킬(또는 위 동등 인정 host-side real-browser 경로)로 브라우저 렌더링을 직접 확인하고
그 evidence(존재·동작은 element 상태, 픽셀-클래스 변경은 시각 캡처 — 위 *evidence 의 변경-
클래스 분기*)를 응답에 첨부하기 전까지 완료 선언 불가. 위 세 금지 패턴("위임" / "인정 후
미실행" / "eval 로 충분 자기-충족")은 이 게이트의 명시적 위반으로 간주한다.

**인터랙션 결과 검증**: 변경이 상호작용 동작(버튼 클릭 결과, 드롭다운 선택·추가 흐름, 폼 제출 등)에
영향을 주면, rendering(정적 렌더) 확인에 더해 **변경된 인터랙션을 실제로 실행하고 그 결과를
evidence 로 첨부**한다 — 버튼이 보이는 것과 눌렀을 때 동작하는 것은 다르다. 정적 렌더만 확인하고
완료 선언하면 인터랙션 결함(예: 연결 테스트 버튼 무동작, 드롭다운 추가 시 항목 리셋)이 게이트
후에도 사용자에게 노출된다.

**생성 HTML 산출물 + 복수 surface (MUST)**: 위 인터랙션 검증은 서비스 feature-UI 뿐 아니라 AI 가
생성하는 HTML/CSS **산출물**(프레젠테이션·리포트·대시보드)에도 적용된다 — 그 안의 모든
**author-added clickable 요소(CTA·링크·인덱스 네비게이션)** 가 검증 대상이다. "산출물이라 웹 UI
프로젝트가 아니다" 라는 이유로 렌더만 시각검증하고 클릭 동작을 건너뛰지 않는다. 액션이 연결되지
않은 요소는 완료 선언 전 **wire(연결) 또는 flag(사용자에게 명시·제거 제안)** 한다 ("버튼 보임=완료"
금지). 또한 **동일 논리 액션이 복수 surface/entry-point(목록 패널·말풍선 칩·툴바 등)에 노출되면 각
surface 에서 개별 실행 검증**이 필수다 — 한 경로 동작 확인을 전체 동작으로 추정하지 않는다(코드패스가
갈릴 수 있음: 예 navigation vs fetch+blob — 한 surface 만 검증하면 다른 surface 의 실패가 누출된다).

**체크리스트 연동**: §16.2 Completion Checklist 의 `(웹 UI 프로젝트만)` 항목으로 자동 참조 — 생성
HTML 산출물의 author-added clickable 도 이 항목의 범위에 포함한다.
해당 항목 미체크 상태로 완료 선언 시 §16.5 금지 패턴과 동일하게 처리.

## §17. shared/ 거버넌스

- `/repo/shared/`에는 `README.md`(목적과 구조 설명)을 루트에 유지한다.
- `/repo/shared/docs/`에는 다음 두 문서를 유지한다:
  - `MODIFY.md` (append-only) — 변경 이력
  - `REPORT.md` (rewrite) — 현재 상태 스냅샷, 의존성 맵, cross-feature 참조
- shared 코드를 변경하는 AI는 자신의 기능 `MODIFY.md`에 변경을 기록하고, `/repo/shared/docs/MODIFY.md`에도 교차 참조를 남긴다.
- shared **단독** 변경 (feature 디렉토리 touch 없음)은 `bin/verify-completion.sh --shared` 모드로 검증한다.
- shared + feature 혼합 commit은 양쪽 MODIFY.md 모두 갱신이 필요하며 `--pre-commit <feature-id>` 모드로 검증한다.
- shared 변경이 다른 기능에 영향을 줄 수 있으면, 영향받는 기능의 `REPORT.md`에 알림을 기록한다.
- 대규모 shared 변경은 별도의 unit(`shared-xxxx-module-name`)으로 관리하는 것을 권장한다.

## §18. 외부 앵커 정책 (ANCHOR.md)

이 섹션은 AI-delegated 개발의 **폐쇄 루프 문제** — 외부 관점 진입 지점의 부재 —
를 해결하기 위한 구조적 정책이다. 각 기능의 `docs/ANCHOR.md`가 방향성 stable reference
역할을 한다.

### §18.1 ANCHOR.md 문서 구조

각 feature (`unit/<feature-id>/docs/ANCHOR.md`)는 4개 섹션을 갖는다:

| 섹션 | 역할 | edit 정책 |
|------|------|----------|
| §1. 외부 관점 요약 | 기능을 모르는 사람이 의문을 가질 지점 (3~5줄) | rewrite |
| §2. 대안 분기 | 선택하지 않은 옵션 + 페르소나 (≥ 2개) | rewrite |
| §3. 가정된 사용 시나리오 | 외부 또는 미래 관점의 구체 시나리오 1개 | rewrite |
| §4. 외부 검증 로그 | release/milestone 또는 방향 전환 검증 시 human 검증 엔트리 | append-only |

§1~§3은 방향이 **명시적으로** 바뀌면 갱신한다 (자연 drift는 §18.3 Conflict Protocol이
탐지한다).

### §18.2 §4 author 제한 — human-only

§4 엔트리는 `source: human:<name>` 만 허용한다. **AI는 §4 writer가 아니다.**

이유: AI가 §4를 채우면 self-certification paradox가 발생한다 — "외부"라는 이름이지만
실제로는 AI의 내부 산출물. §4의 externality는 인간이 직접 append하는 방식으로 보장된다.
다만 일반 TASK cycle마다 §4를 요구하지 않는다. 반복적인 human 검증 강제는 형식적
확인 로그를 만들 가능성이 높으므로, §4는 release/milestone 검토, 방향 전환, 사용자가
명시한 외부 검증 시점에만 요구한다. 처음 요청했던 의도가 왜곡될 우려가 없고
검증 결과가 명료하면 §4 확인 요청 없이 PASS로 판정한다.

### §18.3 Conflict Protocol

AI는 사용자 요청을 수신하면, 해당 feature의 `ANCHOR.md` §1~§3과 교차 검토한다.
요청이 §1(외부 관점) 또는 §3(가정된 시나리오)와 **명백히 상충**할 경우, 작업을 시작하지 않고
사용자에게 다음을 요청한다:

1. `/office-hours` 또는 `/plan-ceo-review`로 방향 재정립, 또는
2. 사용자 본인이 §4에 명시적 `direction-drift` 엔트리 추가

충돌 감지 없으면 작업을 진행한다. 판단이 "단순히 오래됨", "혹시 다를 수 있음",
"더 확인하면 좋음" 수준이면 사용자 확인을 요구하지 않는다. 이 프로토콜이 §1~§3의
stale 문제를 active detection으로 전환 — 별도의 staleness scanner가 불필요하다.

### §18.4 운영(operational) vs 메타(meta) 층위 구분

§1 AI 전권 위임 원칙은 **운영 층위**(기능 개발 실행)에 적용된다. **메타 층위**
(템플릿 자체 설계, AGENTS.md 개정, ANCHOR 스켈레톤 재설계 등)에는 인간이 개입한다.

#### 층위 판정 (path convention)

`bin/verify-completion.sh`가 path convention으로 자동 판정한다. 아래 경로 편집은 META:

- `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`
- `TEMPLATE_CHANGELOG.md`
- `_template/**` (기능 스켈레톤)
- `bin/**` (검증 도구 자체)
- `shared/docs/**` (shared 정책 문서)
- `docs/**` (프로젝트 수준 정책 문서)
- `unit/META-*/` (명시적 META feature)

#### META 작업 워크플로

META 작업도 일반 feature와 동일한 8-doc + ANCHOR.md 구조에 편입된다.
형식: `unit/META-NNNN-<name>/` (예: `unit/META-0001-external-anchor/`).
**`[META]` commit prefix는 지원하지 않는다** — path convention만 유효 게이트.

#### Pure-meta commit의 verify mode (check #9 단일 예외)

변경 파일이 **전부** META 경로면 `verify-completion.sh`가 "META mode" 진입하여
**check #1~#8을 skip한다.** 단 **check #9** (cycle 내 accepted REVIEW.md index entry ≥ 1 —
§18.10.1 META REVIEW location 참조)는 **META mode에서도 적용된다.** META 작업도
verification panel(§18.8) 호출 또는 명시 [SKIPPED:*] 트레이스를 남겨야 cycle을
통과한다 — META skip 정책의 **단일 예외**. `[REJECTED:*]`는 diagnostic trace이며
그 자체로는 check #9를 만족하지 않는다.

이는 템플릿 자체 유지 작업을 가능하게 하면서도 (스크립트 버그 복구 시,
AGENTS.md 개정 시 등) verification panel 호출이 manual habit이 아니라 enforced
protocol로 격상됨을 보장한다.

**Mixed commit (META + operational)**은 operational로 취급되어 full gate를 거친다.
이로써 AI가 operational 작업에 META 경로를 끼워 우회하는 패턴이 차단된다.

#### SPOF 복구

`verify-completion.sh` 자체에 버그가 발생해 모든 feature 작업이 차단되면,
AI는 META mode로 자동 진입하여 스크립트를 수정한다. bypass env var는 존재하지 않는다.

### §18.5 TASK Cycle 정의 (META cycle 경계 포함)

"TASK cycle"은 하나의 TASK 수명 기간이다. cycle 시작은 아래 중 **나중의** commit:

- `Task-Cycle: <feature-id>` trailer를 가진 가장 이른 commit (이 feature에 대해)
- 해당 TASK의 첫 TASK.md 수정 commit
- (migration day 이후라면) `anchor-migrate.sh`가 생성한 seed commit

일반 TASK cycle 완료에는 §4 엔트리가 필요하지 않다. `verify-completion.sh` check #7은
§4 엔트리가 존재할 때 형식과 최소 품질만 검증하며, 엔트리 부재 자체는 실패로 보지 않는다.
release/milestone 또는 방향 전환 검증에서 §4가 필요하면 해당 작업의 `TASK.md` 또는
`REPORT.md`에 별도 완료 조건으로 명시한다.

#### META cycle 경계

META 작업은 별도의 cycle scope를 가진다. META cycle 시작은 아래 중 **나중의**
commit:

- `Meta-Cycle: <meta-cycle-id>` trailer를 가진 가장 이른 commit
- project-wide META의 경우 `meta/TASK.md` 첫 수정 commit
- feature-bound META의 경우 `unit/<feature-id>/meta/TASK.md` 첫 수정 commit

`<meta-cycle-id>`는 자유 형식 슬러그(예: `verification-panel-v0.1.5`,
`agents-md-evolution-2026-04`). trailer가 없으면 path-based scope로 fallback —
`meta/**` (project-wide) 또는 `unit/<id>/meta/**` (feature-bound) 첫 수정
commit이 cycle 시작이 된다.

META cycle 내 REVIEW.md(§18.10.1) index entry가 `[SUBAGENT:*]` /
`[AGENT-TEAM:*]` / `[SKIPPED:*]` / `[CODEX:*]` 중 ≥ 1개 존재해야 check #9가 PASS한다.
`[CODEX:*]`는 docs-only 정책 변경(§18.8.1)에서 codex-review로 panel을 대체한
accepted verdict다.
`[REJECTED:*]`는 실패 진단용 trace이며 accepted review로 계산하지 않는다. META
cycle은 §18.4의 "check #1~#8 skip + check #9 적용" 정책 하에서 운영된다.

### §18.6 §4 엔트리 품질 기준

§4 엔트리를 작성하는 경우에만 아래 기준을 적용한다. 일반 TASK cycle에서 §4 엔트리
부재는 완료 실패 사유가 아니다.

각 엔트리 필수 필드:

- `source: human:<name>` — 유일 허용 형식
- `timestamp:` — ISO8601
- `body:` — 실제 내용 ≥ 200자 (non-whitespace)
- `challenge:` — 한 줄, 이 검증이 무엇을 반박하거나 확인했는지

단순 confirmation(`"pass"`, `"looks good"` 등 단독)은 FAIL로 처리한다.
이는 cargo cult 검증을 방지하기 위한 최소 장벽이다 — 완전 방어는 아니며,
설계상 한계로 명시되어 있다 (§4 내용의 semantic 품질은 script가 보장하지 못한다).

### §18.7 Bootstrap grace (24h)

새로 생성된 `ANCHOR.md`는 `created_at` 기준 24시간 이내면 §1~§3 빈칸 검사와
§4 품질 검사가 skip된다. 이 유예 시간 안에 작성자가 §1~§3를 채운다.
§4 엔트리는 일반 TASK cycle 완료 조건이 아니므로 최초 엔트리 추가를 강제하지 않는다.

`created_at`은 frontmatter 값과 git log first-add timestamp 중 **더 이른 쪽**을
canonical로 사용한다 (frontmatter 조작 방지).

### §18.8 Verification Panel Dispatch Policy

main session은 새 TASK 또는 변경 요청을 처리한 뒤 완료 선언 전에 verification
panel protocol을 실행한다. `/review-panel` slash command는 같은 protocol을 실행하기
위한 Claude Code entrypoint일 뿐이며, 사용자 실행을 전제로 하지 않는다. AI 작업자는
check #9 evidence가 없으면 스스로 이 protocol을 수행해야 한다.
**위임 세션 내 built-in review 직접 호출**: Skill tool 이 허용된 위임 세션에서 model 은
Claude Code 내장 슬래시명령 `/review`·`/security-review` 를 스스로 호출해 review 를
선제적으로 시작할 수 있다 — 사용자 실행을 기다리지 않고 AI 작업자가 직접 review 루프를
개시하는 경로다. 단, 이 채널만으로 check #9 를 충족하지 않는다. review 산출물은
§18.9 형식에 따라 REVIEW.md index entry 로 기록해야 check #9 가 인식한다. 이 채널은
§18.8.1 경량 dispatch 와 §22.4 `security-guidance` plugin 의 보완재이며,
§18.8 panel protocol 자체를 대체하지 않는다.

다음 dispatch 표에 따라 관련 도메인 subagent subset을 결정한다.
**no separate planner LLM** — main session prompt context에 이 표가 포함되어 main이
직접 라우팅한다 (0 추가 LLM call).

| Task signal (current TASK.md 내용 기준) | Required subagents |
|---|---|
| auth, password, key, token, session, credential / 인증, 비밀번호, 세션, 자격증명 | security |
| schema, migration, foreign key, query, index, ORM / 스키마, 마이그레이션, 외래키, 쿼리, 인덱스 | backend, qa |
| UI, button, page, form, dialog, modal, screen, layout / 버튼, 페이지, 폼, 모달, 화면, 레이아웃 | ux, design |
| API, endpoint, contract, response shape, REST, GraphQL / API, 엔드포인트, 응답 스키마 | backend, security, qa |
| performance, memory, latency, N+1, caching, throttle / 성능, 메모리, 지연, 캐싱 | backend, qa |
| 비정책 doc-only OR comment-only | (panel SKIP) |
| 정책 doc (`AGENTS.md`, `CLAUDE.md`, `_template/`, `docs/CONVENTIONS.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/PROJECT.md`, ANCHOR.md skeleton) doc-only | §18.8.1 경량 경로 (security subset / codex-review / opt-in full panel) |
| Code change (line-count 무관) | dispatch 키워드 매칭 → subset, 매칭 0건이면 full panel |
| 키워드 0개 + cross-domain 키워드 ≥ 2개 | full panel (5명) |

규칙:

- 중복 도메인은 dedupe.
- main session은 dispatch 결정의 근거(매칭된 키워드)를 REVIEW.md entry의
  `Trigger` 필드에 기록한다 — 어느 신호로 어느 subagent가 호출됐는지 추적 가능.
- 사용자가 명시적으로 "전체 panel"을 요청하면 full panel.
- 매칭 0건 + code change → full panel default. **fallback 빈도
  자체가 측정 신호** — 자주 발화 시 "병렬 처리 불필요 영역"이라는 evidence.
  (정책 doc-only는 이 측정의 결론을 반영해 §18.8.1 경량 경로로 분기한다 — v3.24.0.
  META-CYCLE-021/025의 반복 [SKIPPED]가 docs full panel의 저가치를 입증.)
- 사용자 노출 surface (REVIEW.md verdict 라벨, `/review-panel` summary stderr)는
  영어 keyword + 한국어 명사 병기 (예: `Trigger: schema/스키마 keyword matched`).
  internal dispatch 매칭 자체는 영어 그대로.
- skip 결정 시에도 REVIEW.md에 `[SKIPPED:non-policy-doc]` index entry 1줄을
  남겨야 한다 — check #9가 인식하여 SKIP cycle도 통과시킨다 (§18.10.1).

#### §18.8.1 docs-only 정책 변경 경량 dispatch (v3.24.0+)

위 표의 "정책 doc ... doc-only" 행(순수 prose/§ 추가·수정)은 full panel(5 reviewer)
대신 다음 경량 경로를 **기본**으로 한다. 근거: bundle-only reviewer(repo 접근 없음)는
대용량 정책 doc의 cross-ref/factual 정확성을 검증할 수 없고, ux/design 도메인은 정책
prose에 대부분 N/A다. (evidence: META-CYCLE-021/025의 반복 `[SKIPPED]` — docs 변경에
full panel은 저가치로 측정됨.)

1. **subset dispatch (기본):** `security`를 기본 호출하고, 변경된 doc 내용이 위 표의
   키워드(schema/migration/API/performance 등)에 매칭되면 해당 도메인(backend/qa)을
   추가한다. ux/design은 명시적 UI 정책 변경일 때만.
2. **codex-review (대안, check #9 accepted):** factual/cross-ref 정확성 검증이 핵심인
   변경은 `codex review --uncommitted`(또는 `/codex review`)로 대체할 수 있다. 결과를
   REVIEW.md에 `[CODEX:<scope>]` index entry로 기록하면 check #9가 accepted review로
   인식한다 (§18.4, §18.9). codex P1(GATE) 0건이면 PASS, P1 ≥ 1이면 수정 후 재실행.
3. **full panel은 opt-in:** 사용자가 명시적으로 "전체 panel"을 요청하거나, 변경이
   cross-domain 정책(보안+백엔드+UX 동시 영향)일 때만 full panel을 호출한다.

**모든 경로 공통 (MUST):** docs-only 정책 변경은 위 경로 선택과 무관하게 기계적
cross-ref/anchor 무결성 점검을 1회 수행한다 — 내부 §-참조가 실제 heading으로 resolve되는지,
삽입 anchor가 존재하는지, 표/링크 정합성. 정책 doc은 모든 후속 cycle의 판단 기준이라
blast radius가 가장 크고, 이 기계적 점검은 bundle-only reviewer가 검증 못하는 영역을 메운다.

순수 비정책 doc은 기존대로 표 첫 행의 `[SKIPPED:non-policy-doc]`로 처리한다.
#### Subagent per-invocation model 분기 (v2.1.154+, 비용·품질 최적화)

subagent 는 entry persona 와 달리 **호출 시점에 model 을 지정할 수 있다**
(Task/Agent tool 의 per-invocation `model` parameter). dispatch 한 subagent 의
작업 난이도에 따라 model 을 맞춘다:

- **고난도 도메인** (security 인증·인가, 복잡한 backend·migration): Opus 계열.
- **경량·기계적 검토** (포맷·lint·단순 정합): Haiku 계열 — 비용 절감.
- **기본**: main 세션 model 상속 (지정 안 하면 inherit).

⚠️ 신규 기능은 사용 환경 Claude Code 버전에서 실작동 확인 후 채택. 미지원 환경은
inherit fallback. entry persona 자신의 model 은 진입 전 고정 (§11.3) — 본 분기는
subagent 에만 적용.
#### Agent Team escalation

AI 작업자는 일반 subagent panel만으로 판단이 닫히지 않으면 agent team을 스스로
구성할 수 있다. 사용자 명시 호출이 없어도 다음 경우에는 `[AGENT-TEAM:<topic>]`
entry를 남긴다:

- subagent verdict가 서로 충돌하고 main session이 단독으로 결론을 낼 근거가 부족함
- security/data-loss/destructive operation처럼 단일 관점 누락 비용이 큰 결정
- all-subagents rejected가 반복되어 prompt/context 설계 자체를 재검토해야 함
- 요구사항/acceptance criteria가 서로 충돌해 구현 방향을 다시 선택해야 함


#### `context: fork` Subagent 격리 패턴 (v2.1.126+)

WebSearch / WebFetch 등 **지연 도구 (Deferred Tools)** 를 subagent 에서 첫 번째 턴부터 사용하려면 `context: fork` 옵션을 설정한다. Fork subagent 는 부모 세션과 격리된 컨텍스트에서 실행되므로, 외부 정보 수집 작업을 주 컨텍스트 오염 없이 분리할 수 있다.

다음은 개념 pseudocode 예시 (실제 SDK call 형식은 사용 환경에 따라 다름):

```javascript
Agent({
  subagent_type: "Explore",
  context: "fork",
  prompt: "WebSearch로 최신 트렌드 수집 후 요약 보고..."
})
```

**권장 사용 케이스:**
- scheduled-inspection cron 내 Web Search 트렌드 수집을 주 컨텍스트와 분리
- MCP 도구 등 지연 로딩 도구를 첫 턴부터 필요로 하는 subagent

**참고:** `alwaysLoad` 옵션 (v2.1.121+) 으로 MCP 서버 도구의 tool-search 지연 로딩을 제어할 수도 있다.

### §18.9 REVIEW.md Subagent Index + Artifact Schema

§18.2는 ANCHOR.md §4가 `human:<name>` only임을 규정한다. AI subagent 출력은
§4가 아니라 **2-tier 분리 구조**로 저장된다:

1. **Full artifact:** `unit/<feature-id>/docs/reviews/<ISO-timestamp>-<agent>.md`
   (또는 META의 경우 §18.10.1 path) — 4-section + 4 required fields 출력 전문.
2. **Index entry:** per-feature `docs/REVIEW.md` (또는 META의 경우 §18.10.1 path) —
   1줄 verdict + artifact 링크.

이로써 §4의 externality(인간 검증)와 REVIEW.md의 navigability(timeline 인덱스)가
의미적으로 분리된다.

#### 신규 REV entry — Subagent index (1-line index format)

> **REV id 형식 (v3.32.0+, §6 식별자 표)**: 아래 예시의 `REV-YYYYMMDD-NNN` 은 날짜+순번 표기이나,
> §6 에 따라 review-panel 스크립트는 v3.32.0 부터 timestamp+branch
> `REV-<YYYYMMDDTHHMMSS>-<branch>` 를 생성한다. `bin/verify-completion.sh` check #9 는 두 형식을
> 모두 인식한다 (additive). 스키마의 나머지 필드는 형식과 무관하게 동일하다.

```
## REV-YYYYMMDD-NNN [SUBAGENT:<agent-name>] — <verdict>
- Related TASK: <feature-id | _meta_>
- Trigger: <matched keyword/한국어 명사>
- Timestamp: <ISO8601>
- Verdict: PASS | CONCERN | BLOCK
- Artifact: <feature: unit/<feature-id>/docs/reviews/<ISO-timestamp>-<agent>.md
            META project-wide: meta/reviews/<ISO-timestamp>-<agent>.md
            META feature-bound: unit/<feature-id>/meta/reviews/<ISO-timestamp>-<agent>.md>
- Critical issue (if BLOCK/CONCERN): <1-line excerpt from artifact>
- Human Approval Needed: yes/no
```

#### 신규 REV entry — Agent Team escalation

```
## REV-YYYYMMDD-NNN [AGENT-TEAM:<topic>]
- Related TASK: <feature-id>
- Source: agent-team:<topic>:<n-teammates>
- Trigger: <AI escalation reason | manual escalation by user>
- Timestamp: <ISO8601>

### 1. Initial positions (per teammate)
### 2. Discussion / contradictions
### 3. Consensus
### 4. Dissent / residual risks

- Human Approval Needed: yes/no
```

#### 신규 REV entry — SKIPPED (non-policy doc trace)

```
## REV-YYYYMMDD-NNN [SKIPPED:non-policy-doc]
- Related TASK: <feature-id | _meta_>
- Reason: changed paths are docs/comments only outside policy-doc list
- Timestamp: <ISO8601>
```

#### 신규 REV entry — CODEX (codex-review in lieu of panel)

docs-only 정책 변경(§18.8.1)에서 codex-review로 panel을 대체한 경우. check #9는
accepted review로 인식한다(§18.4).

```
## REV-YYYYMMDD-NNNN [CODEX:<scope>] — <verdict>
- Related TASK: <feature-id | _meta_>
- Source: codex review (<codex-version> --uncommitted)
- Trigger: docs-only 정책 변경 (§18.8.1 경량 경로)
- Timestamp: <ISO8601>
- Verdict: PASS (P1 0건) | CONCERN (P2만) | BLOCK (P1 ≥ 1)
- Critical issue (if BLOCK/CONCERN): <1-line excerpt>
- Human Approval Needed: yes/no
```
#### 신규 REV entry — REJECTED (diagnostic trace)

wrapper post 단계에서 일부 또는 모든 subagent가 validator에 reject되거나
wrapper-level fail-loud로 차단되면 다음 entry 1줄을 append한 뒤 stderr 보고하고
exit 0:

```
## REV-YYYYMMDD-NNN [REJECTED:partial-subagents | REJECTED:all-subagents]
- Related TASK: <feature-id | _meta_>
- Reason: <reject reason 요약, ≥ 30 char>
- Rejected agents: <list>
- Timestamp: <ISO8601>
```

`[REJECTED:partial-subagents]`는 accepted artifact가 1개 이상 있고 일부만
reject된 경우다. 이때 check #9는 REJECTED entry가 아니라 이미 append된
`[SUBAGENT:*]` entry 때문에 PASS한다.

`[REJECTED:all-subagents]`는 accepted artifact가 0개인 경우다. 이 entry는 시도
흔적을 남기지만 check #9를 만족하지 않는다. 즉 모든 reviewer 출력이 schema/quality
gate를 통과하지 못했다면 AI는 prompt/context/artifact를 고쳐 panel을 다시 실행해야
하며, trace만으로 완료 선언할 수 없다.

#### Artifact 파일 (full output)

각 subagent의 4-section + 4 required fields 출력 전문 + frontmatter:

```yaml
---
doc_type: REVIEW_ARTIFACT
feature_id: <feature-id | "_meta_">
agent: <agent-name>
timestamp: <ISO8601>
trigger: <matched keyword/한국어 명사>
verdict: PASS|CONCERN|BLOCK
---

### 1. Blocking issues
### 2. Cross-domain concerns
### 3. Challenge to current spec
### 4. Verdict
```

#### 품질 gate (validator enforced)

`bin/review-md-append-from-subagent-output.sh`가 다음 규칙을 enforce한다:

- **Schema는 exact match만 허용**: header `### 1. Blocking issues`,
  `### 2. Cross-domain concerns`, `### 3. Challenge to current spec`,
  `### 4. Verdict` 정확 토큰. bold/code-fence 변형, trailing whitespace 외 변형은
  모두 reject. 각 header가 정확히 1회만 발견되어야 함 — duplicate (예: code-fence
  안 가짜 + 진짜 둘 다) → reject.
- 4 section header 모두 present.
- Section 1·2의 각 finding은 **`Evidence`**, **`Location`**, **`Reason`**,
  **`Action`** 4 required fields 모두 present.
- `Evidence`, `Reason`, `Action`: markdown markup strip 후 ≥ 30 char.
- `Location`: non-empty + 패턴 매칭 — `<path>:<line>`(예: `src/auth.ts:42`)
  또는 UI selector(`#submit-btn`) 또는 URL path(`/api/v1/users`) 또는
  Field path(`form.email`). char minimum 없음.
- Section 1 `(no findings)` 단독이면 section 1 필드 검사 skip하지만 section
  3·4는 substantive 강제.
- **Section 4 verdict tightened**: 정확히 PASS | CONCERN | BLOCK 토큰 매칭 +
  일관성 검사:
  - §1 critical/high blocker ≥ 1 → BLOCK 강제 (다른 verdict 시 reject).
  - §1 medium blocker 또는 §2 cross-domain concern ≥ 1 → CONCERN 또는 BLOCK
    허용 (PASS 시 reject).
  - §1 (no findings) AND §2 (no findings) → PASS만 허용.
- Forbidden minimal patterns: 각 required field가 단독으로
  `^\s*(pass|ok|fine|n/a|none|—)\s*$` 이면 reject.
- Lock scope: `flock` 획득 → 마지막 NNNN 읽기 → NNNN+1 포맷팅 → REVIEW.md index
  entry 작성 → temp file → `mv` → release. 모두 lock 안에서.

**v0.1 SKIP 의도**: code-fence 가짜 헤더 무시·bold header 허용·복잡 markdown
변형 허용은 v0.2. v0.1은 **strict exact-schema validator** — bash로 Day-0 안정
구현 가능한 최소 수준.

### §18.10 Meta TASK Convention

Project-wide cross-cutting meta 작업과 feature-bound meta 작업의 저장 경로 분리:

| 작업 종류 | 위치 | 사용 사례 |
|---|---|---|
| Project-wide cross-cutting meta | `meta/TASK.md` (append-only 권장, doc_type: `META_TASK_PROJECT`) | verification protocol v0.X backlog, render-agents 도구, AGENTS.md 진화, cross-project 정책 변경 등 |
| Feature-bound meta | `unit/<feature-id>/meta/TASK.md` | 특정 feature와 결합된 meta 작업 (예: feature 자체 설계 디시전 변경) |
| Operational TASK | `unit/<feature-id>/docs/TASK.md` (기존) | 변경 없음 — 운영 층위 |

`verify-completion.sh`의 META mode (§18.4)는 `meta/**` 와
`unit/<feature>/meta/**` 둘 다 META 경로로 자동 인식한다. mixed commit (META +
operational)은 operational로 취급된다.

### §18.10.1 META mode REVIEW location

Day-0 자체 작업이 META 경로에서 발생할 때, panel 출력의 저장 위치를 path
convention으로 자동 분기한다:

| 변경 범위 | REVIEW 저장 위치 (index + artifact) | check #9 cycle scope |
|---|---|---|
| Operational (단일 feature 코드/문서) | `unit/<feature-id>/docs/REVIEW.md` (index) + `unit/<feature-id>/docs/reviews/<ts>-<agent>.md` (artifact) | per-feature cycle |
| **Project-wide META** (AGENTS.md, CLAUDE.md, `_template/`, `bin/`, `settings.json`, `docs/CONVENTIONS.md` 등) | **`meta/REVIEW.md`** (index) + `meta/reviews/<ts>-<agent>.md` (artifact) | meta cycle (§18.5 META cycle) |
| **Feature-bound META** (`unit/<feature-id>/meta/TASK.md`-driven) | `unit/<feature-id>/meta/REVIEW.md` (index) + `unit/<feature-id>/meta/reviews/<ts>-<agent>.md` (artifact) | feature cycle |
| Mixed commit (META + operational) | operational 우선 — `unit/<feature-id>/docs/REVIEW.md` | per-feature cycle |

### §18.11 Subagent invocation contract

Subagent는 frontmatter `tools:` 필드 부재 — 어떤 도구도 호출하지 못한다 (git,
Read, Grep 모두 불가). main session이 다음 4개 정보를 **각 subagent invocation
prompt에 명시 inject**해야 subagent가 변경 범위를 알 수 있다:

```
[Context bundle injected by main session per subagent invocation]
- changed_files: <git diff --name-only output, 1줄당 1 path>
- diff_excerpt: <git diff output — 큰 경우 단일 hunk별 잘라서 첫 N hunks 또는 핵심 hunks>
- task_md_content: <verbatim contents of unit/<feature-id>/docs/TASK.md
                   또는 META의 경우 meta/TASK.md / unit/<id>/meta/TASK.md>
- acceptance_criteria: <if TASK.md frontmatter has it, otherwise "(none specified)">
```

이게 contract — main session이 이 4개를 inject하지 않으면 subagent는 변경 범위를
알 수 없다. `/review-panel` entrypoint와 AGENTS.md §18.8 protocol은 같은 contract를
따른다. Subagent prompt 첫 줄에는 다음이 추가된다:

```
You will be given a context bundle below containing changed_files, diff_excerpt,
task_md_content, acceptance_criteria. Your audit MUST cite specific files/lines
from this bundle. Do not search the repo independently — the bundle is your only input.
```

---

### §18.12 AskUserQuestion 패턴 정책 (v3.29.0)

**배경**: VSCode extension 호스트 UI 에서 AskUserQuestion `option.description` 필드에
긴 한글 텍스트(ELI10 / Stakes / Recommendation / pros·cons 등)를 packing 하면 줄바꿈·
마크다운·한국어 인코딩이 깨져 답변 자체가 차단된다 (확인됨: 2026-05-07, 2026-06-11).

**정책 (모든 AI agent / SKILL에 적용)**:

AskUserQuestion 호출 직전 결정 brief 본문을 **prose 로 먼저 출력** 한 뒤, 짧은 질문 +
짧은 옵션 형식으로 호출한다:

```
[직전 prose 출력 — 사용자 화면에 표시됨]
Issue / Recommendation / Trade-off 등 — 마크다운 자유 사용 가능

[이어서 AskUserQuestion 호출]
question: "<action-oriented 1문장, ≤80자>"
options:
  - label: "<1~5단어 chip>"
    description: "<핵심 trade-off 1~2줄, ≤200자>"
  - ...
```

**필드 제약**:

| 필드 | 제약 |
|---|---|
| `question` | 1문장, action-oriented, ≤80자 |
| option `label` | 1~5단어 (chip 표시) |
| option `description` | 1~2줄, ≤200자 — 핵심 trade-off 한 줄 요약만 |

**금지 패턴**:
- `question` 필드 또는 `description` 필드에 ELI10 / Stakes / Recommendation /
  Completeness / Net / pros·cons 등 결정 brief 전체 packing
- `description`에 여러 단락 / 마크다운 헤딩 / 코드 블록 삽입
- 한국어 긴 문장을 `description`에 넣어 인코딩 깨짐 유발

**재호출 억제 (1턴 1회, MUST)**: AskUserQuestion 은 **한 턴에 1회만** 호출한다. 호출 후 응답이
수신되지 않으면(빈 결과·툴이 즉시 리턴·멀티세션 병렬 컨텍스트에서 미수신) **같은 내용으로 재호출하지
않는다** — 다음 사용자 턴까지 대기한다. 동일 질문을 응답 대기 없이 반복 호출하면(관찰: 1분 내 4회
연속) 사용자 UI 가 중복 프롬프트로 막히고, 외부 영향 confirm 게이트(§16.3)에서는 승인 의미가
모호해진다. 응답이 비었거나 모호하면 재호출 대신 **사용자 입력을 기다리거나**, 정말 진행 차단이
필요하면 prose 로 1줄 안내 후 턴을 종료한다. **빈/미수신 결과는 승인이 아니다 (fail-closed)** — §16.3
외부 영향 행동은 명시적 affirmative 응답이 없으면 진행하지 않는다.

**SKILL 작성 지침**: 본 정책이 `~/.claude/CLAUDE.md` 전역 정책과 동일 내용이다.
SKILL 지문에서 "AskUserQuestion 으로 … 호출" 이라고 지시할 때 직전 prose 출력 단계를
명시하거나 `(~/.claude/CLAUDE.md §AskUserQuestion 분리 패턴 준수)` 를 주석으로 달아
AI 가 전역 정책 적용을 인지하도록 한다.

---


## §19. Request-Form Protocol

### §19.1 목적

사용자 요청이 AI 작업에 투입되기 전, **구조화된 form 으로 조립** 되도록 한다.
§18 (ANCHOR 외부 앵커) 과 구분된다:
- §18: 프로젝트 **방향성** 재앵커 (외부 관점 / 대안 분기 / 가정 / 외부 검증)
- §19: 기능 단위 **요청** 조립·실행 (요청의 section 조립 + 필요 시 실제 적용)

§18 은 *무엇을 왜 만드는가* 의 외부 증거. §19 는 *지금 이 요청을 어떻게 다룰 것인가* 의 구조.

### §19.2 Persona 호출

`/_template:<persona>` (template-owned, project-agnostic) 또는 `/_persona:<name>` (project-owned) 로 **명시 호출** 한다. 자동 호출하지 않는다.

Persona 는 두 모드 중 하나로 작동한다:

1. **조립 (assembly-only)**: `repo/docs/REQUEST.md` 의 특정 section 을 append 한다. 실제 코드·문서 변경 권한 없음.
2. **조립 + 실행 (worker)**: section 조립 + 변경안 초안 작성 + **사용자 명시 승인 게이트** 를 통과한 후 AI 가 직접 Edit/Write 로 실제 적용. 이 모드의 persona 는 **`worker-*` prefix** 를 관례적으로 따른다 (강제 아님, 식별용).

### §19.2.1 Codex command compatibility

Codex 에서는 Claude Code 의 `.claude/commands/_template` 를 직접 source of truth 로
사용하지 않는다. Codex 전용 원본은 다음 repo-local 구조다:

- `.codex/commands/_template/*.md` — `/_template:<persona>` 의 Codex canonical prompt.
- `.codex/skills/_template-*/SKILL.md` — Codex skill discovery 를 위한 최소 wrapper.
- `.agents/plugins/marketplace.json` + `plugins/ai-delegated-dev-template/` — local marketplace/plugin 노출 표면.

규칙:

- `~/.codex`, Codex marketplace cache, installed plugin cache 는 **설치 대상**일 뿐
  source of truth 가 아니다. 마켓플레이스 업데이트로 repo-local command 를 덮어쓰지 않는다.
- `bin/codex-template-install.sh --check` 로 구조를 검증하고,
  wrapper cwd 지원이 필요하면 `--link` 로 `<wrapper>/.codex -> repo/.codex` 를 만든다.
- 현재 확인된 Codex skill 호출 표면은 `$<skill-name>` 이다. 따라서
  `_template` skill 자동완성은 Codex 가 시작된 workspace 에서 `.codex/skills` 를
  발견할 수 있어야 한다.
- copy-base 를 파일 복사로 전달하면 symlink 가 누락될 수 있다. 첫 AI 작업자는
  skill 이 없다고 판단하기 전에 wrapper 위치에서 다음을 먼저 실행한다:

  ```bash
  bash repo/bin/codex-template-install.sh --check
  bash repo/bin/codex-template-install.sh --link
  bash repo/bin/codex-template-install.sh --check
  ```

  이미 `/repo` 안에서 작업 중이면 `bash bin/codex-template-install.sh --check` 를
  사용한다. `--link` 가 플랫폼 정책상 실패하면 Codex 를 `/repo` 에서 시작하고,
  wrapper-level 자동완성 제한을 작업 로그에 명시한다.
- Codex 가 exact `/_template:<persona>` namespace 를 거부하는 버전에서는
  `--install-prompts` 가 `$CODEX_HOME/prompts/_template:<persona>.md` 와
  `$CODEX_HOME/prompts/_template-<persona>.md` 호환 링크를 생성한다.
- `.codex/**`, `.agents/plugins/**`, `plugins/ai-delegated-dev-template/**` 변경은
  META-class 변경이며 §18.8 verification panel 정책 대상이다.

### §19.3 REQUEST 문서 거버넌스

Request 로그는 2 파일 구조로 운영한다:

- `repo/docs/REQUEST.md` — **Active 요청 로그** (status: in-progress). append-only.
- `repo/docs/REQUEST_ARCHIVE.md` — **완료·폐기 요청 로그** (status: completed | abandoned). append-only.

양쪽 모두 §3.1 우선순위 8번 (project-level) 에 위치한다.
각 entry 는 `REQ-YYYYMMDD-NNNN <request-slug>` 식별자로 구분된다.

Persona 실행 시 기본적으로 **active 만 Read** 한다. 사례 참조가 필요한 경우에 한해 ARCHIVE 도 Read (명시적 판단, 무조건 Read 금지).

### §19.4 Entry 구조

각 entry 는 아래 최소 구조를 따른다:

```markdown
## REQ-YYYYMMDD-NNNN <request-slug>
- submitted_at: <ISO8601>
- target: project | feature-<id> | shared | multi
- personas_invoked: [<name>, ...]
- source_log: ~/.gstack/projects/<slug>/template-personas/<branch>-<request-slug>-*.md

### <Section Name>
(persona 가 조립한 section 내용)

### Outcome
- status: in-progress | completed | abandoned
- completed_at: <ISO8601>  (status: completed 일 때만)
- consumed_by: <feature-id | commit-hash | file-path list>
- notes: <요약 1~2 줄>
```

신규 entry 생성 시 `target` 은 사용자에게 묻는다. `personas_invoked` 는 참여 persona 가 추가될 때마다 append.

### §19.5 Archive move protocol

전체 REQUEST 가 완료되면 (Outcome.status = completed) 다음 절차를 수행한다:

1. `REQUEST.md` 에서 해당 entry 전체를 잘라냄.
2. `REQUEST_ARCHIVE.md` 말미에 append. 파일 부재 시 frontmatter 포함 생성:
   ```yaml
   doc_type: REQUEST_ARCHIVE
   scope: project
   status: active
   edit_policy: append-only
   source_of_truth: true
   ```
3. 두 파일 변경을 **한 commit 에 atomic 으로** 포함 권장 (move 가 중간 상태로 git 에 노출되지 않도록).

**책임 주체**:
- **Worker-class persona** (§19.2 모드 2): 자기 실행 직후 해당 entry 에 대해 수행.
- **조립-only persona** (§19.2 모드 1): Archive move 를 수행하지 않는다. Outcome.status 를 `in-progress` 로 설정하고 active 에 남긴다.
- **사용자**: 여러 section 이 누적된 entry 의 전체 완료 판단 시 수동 move.

### §19.6 Persona 분업 원칙

- 각 persona 는 자기 section 을 **주로** 책임진다. 다른 section 을 덮어쓰지 않는다.
- 실행 중 다른 persona 의 로직이 필요하면 해당 `persona.md` 를 **Read 로 in-context 합성** 한다 (Agent tool 으로 subagent spawn 하지 않음). gstack `/autoplan` 패턴 준용.
- 실행 완료 후 다음 persona 호출은 **권유만** 한다 — 자동 chain 없음. 사용자가 명시적으로 호출해야 한다.

### §19.7 Scope 원칙

- `_template/` 의 persona 는 **project-agnostic** 이어야 한다. 특정 feature 이름·도메인을 가정하지 않는다. Template 은 자신을 적용할 project 의 feature 가짓수·구조를 예측하지 못한다.
- Project-specific persona (예: 프로젝트 고유 scope 정의, 도메인 특화 체크리스트, 팀 고유 review 기준) 는 **`_persona/` 에 project 가 직접 생성** 한다 (via `/_template:persona-new` factory).
- `_persona/` 는 project git 이 직접 버전관리. `_template/` 은 submodule 로 외부 source 를 참조 (배포 시 일괄 update 가능).
- Codex project-specific persona 는 `.codex/commands/_persona/<name>.md` 와
  `.codex/skills/_persona-<name>/SKILL.md` 를 함께 둔다. Claude 호환이 필요한
  경우에만 `.claude/commands/_persona/` 를 추가한다.

### §19.8 Pain-response 책임 구분

사용자가 pain (문제·불만·혼란) 을 호소할 때 처리 책임은 다음 순서로 배분된다:

1. **`verify-completion.sh`** gate (§16.3) — 기계적 완료 조건 검증.
2. **ANCHOR Conflict Protocol** (§18) — 방향성·가정 충돌 재앵커.
3. **gstack skill** (`/office-hours`, `/plan-ceo-review` 등) — 프로젝트 수준 재앵커.

Request-Form persona 는 **요청 조립·실행 도구** 이며 pain 해소 자체가 목적이 아니다.
Persona 가 pain 을 "감지해서 처리" 하는 구조는 수단과 목적의 역전 (도구가 목적을 품음) 을 유발한다.
pain 호소는 위 1~3 에서 먼저 처리된 후, 필요 시 persona 호출로 이어진다.

---

## §20. Makefile 권유 정책

소비자 프로젝트가 진입점 다수 / feature 디렉토리별 스크립트 실행 패턴을 가질 때 `repo/Makefile` 작성을 권유한다. 본 § 은 권유 메커니즘 (when / where / how) 의 single source of truth.

### §20.1 적용 시점 (when)

다음 신호 중 하나 이상이 감지되면 권유 대상:

- **진입점 ≥ 2** — 서로 다른 디렉토리에 위치한 실행 스크립트, 또는 README / `docs/PROJECT.md` / `FIRST_REQUEST.md` 에 산재한 build/test/run 명령 ≥ 2.
- **Feature 디렉토리별 스크립트 실행** — `unit/feature-*/` 안에 자체 실행 entry (예: `unit/feature-NNNN-name/scripts/*.sh`) 가 존재하고, 호출 명령이 README / docs 에 명시되어 있음.
- **명령 산재** — README / `FIRST_REQUEST.md` / docs 에 명시된 실행 명령 (`bash …`, `npm …`, `python …`, `docker …` 등) 이 **3 개 이상** + `repo/Makefile` 부재.

신호가 모호하면 권유하지 않는다 (false positive 회피 — 1 회 명령만 있는 단순 프로젝트는 Makefile 불요).

### §20.2 권유 책임 분담 (where)

- **`/_template:init`** (Phase 6 보고에서 Q3/Q4 답변 평가 시) — 신호 감지 시 보고 형식의 `### Makefile 권유` § 출력.
- **`/_template:entry`** (Phase 3.5 pre-load 단계) — `repo/Makefile` 부재 + §20.1 신호 silent detection 시 Phase 5 의 후속 안내에서 hint 출력.
- **일반 작업 중 (모든 AI 행동)** — 작업 진행 중 §20.1 신호를 새로 감지하면 1 회 hint. **자동 chain 금지** (§19.6 권유-only 원칙 — AI 가 Makefile 을 자동 생성하지 않는다).

#### §20.2.1 Cross-source dedup marker (필수)

권유 emission 은 **소비자 repo 전체에 대해 1 회만**. emission point 가 분산되어 있으므로 공유 dedup marker 사용:

- **Marker path**: `repo/.template/makefile-hint-shown` (zero-byte sentinel)
- **Touched on**: 첫 emission 시 자동 `touch`
- **Checked on**: 모든 emission point 가 §20.1 신호 평가 *직전* `[ -f repo/.template/makefile-hint-shown ]` 확인. 존재 시 emission skip.
- **자동 cleanup 안 함**: 사용자가 `/_template:makefile` 완료 후에도 marker 유지 → 재권유 차단.

사용자의 **명시적 거절** 경로:

- `repo/.template/MAKEFILE_DECLINED` (zero-byte sentinel) — Makefile 영구 불요 표명. 모든 emission point 가 marker 검사 후 영구 skip.
- `docs/DECISIONS.md` 의 ADR — 정식 결정 (선호). ADR 본문에 "Makefile 불채택" 명시 시 영구 skip (AI 가 ADR grep 책임).

`MAKEFILE_DECLINED` 또는 ADR-기반 거절이 발견되면 `/_template:makefile` SKILL 호출 시 SKILL 이 사전 차단 + 재확인.

### §20.3 권유 형식 (how)

권유 hint 는 **schema 강제** 로 emit (자유형식 placeholder 금지):

```
[Makefile 권유] §20.1 신호 감지
- signal_kind: <multi-entry-readme | feature-scripts | docs-commands>
- evidence: <≤80 char concrete reference>
`repo/Makefile` 작성을 권유합니다. 호출: `/_template:makefile`
(영구 skip 원하면 `repo/.template/MAKEFILE_DECLINED` 파일 생성 또는 `/_template:makefile` 호출 후 "영구 skip" 분기 선택)
```

#### 예시 (worked examples)

```
[Makefile 권유] §20.1 신호 감지
- signal_kind: multi-entry-readme
- evidence: README.md L12,L18,L24 의 bash/npm 명령 3개 + repo/Makefile 부재
`repo/Makefile` 작성을 권유합니다. 호출: `/_template:makefile`
(영구 skip 원하면 `repo/.template/MAKEFILE_DECLINED` 파일 생성 또는 `/_template:makefile` 호출 후 "영구 skip" 분기 선택)
```

```
[Makefile 권유] §20.1 신호 감지
- signal_kind: feature-scripts
- evidence: unit/feature-0001-mysql-restore/scripts/restore.sh + unit/feature-0002-xtrabackup/scripts/run.sh
`repo/Makefile` 작성을 권유합니다. 호출: `/_template:makefile`
(영구 skip 원하면 `repo/.template/MAKEFILE_DECLINED` 파일 생성 또는 `/_template:makefile` 호출 후 "영구 skip" 분기 선택)
```

권유 출력 후 사용자 명시 호출이 있어야만 `/_template:makefile` SKILL 진입. AI 가 자동 생성하지 않는다.

### §20.4 Makefile 위치 및 anchor 정합

- **위치**: `repo/Makefile` (consumer-side path)
- **Anchor 정합**: AGENTS.md anchor table (주석 예시) 의 `Makefile | docs/ARCHITECTURE.md | 실행 진입점` 행과 일치. target 추가/제거는 §18 (ADR 경유) 정책 준수.
- **Customization 보호**: consumer 가 작성한 Makefile 은 template upgrade 시 보존 — 마이그레이션 hop 이 덮어쓰지 않는다 (`bin/migrations/lib/customization-detect.sh` 의 `is_marker_protected` 패턴 따름).
- **`/_template:makefile` SKILL 의 scope**: project-agnostic (§19.7) — 특정 feature 이름·도메인을 가정하지 않는다. 사용자가 입력한 entry 명령을 Q&A 로 수집한 후 Makefile 본문을 조립.
- **Shell-injection 경고 (필수)**: SKILL 의 Q1 (entry-point inventory) 으로 수집한 명령은 Makefile recipe 본문에 그대로 들어가며 `make <target>` 실행 시 `/bin/sh -c` 로 evaluate 된다. metachar (`;`, `&&`, `|`, backticks, `$()`, `>`, `&`) 가 active 이므로 SKILL 이 Q1.5 단계에서 수집 명령 echo + 1줄 경고 + 사용자 confirm 을 강제한다.

---

## §21. Obsidian LLM Wiki Integration

본 프로젝트는 v3.12.0 부터 `repo/wiki/` 라는 **Obsidian 호환 vault** 를 사람용 graph 입구로 분리 운영하며, v3.13.0 에서 **Karpathy LLM Wiki 패턴 (raw / wiki / schema 3-layer)** 을 완성하고 **namu.wiki 표준 entry 형식** 을 사람 facing 노트에 적용했다. 본 § 는 영역 분리·AI 의무·운용 명령의 정책 정본이다. 운용 디테일 (frontmatter, wikilink, lint) 정본은 [`docs/WIKI.md`](docs/WIKI.md).

**v3.13.0 web evidence (4 high-star repo, 누적 9.6k stars)**:
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (33,388 stars) — 3-layer 원전
- [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) (5.5k) — vault 구조 + 10 skill
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) (2.7k) — `CLAUDE.md` + `AGENTS.md` + `GEMINI.md` multi-agent + Ingest/Query/Lint workflow spec
- [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki) (971), [nvk/llm-wiki](https://github.com/nvk/llm-wiki) (468) — 보조 검증

**namu.wiki 표준 형식 출처**: [나무위키:편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C), [언어 모델 entry](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8) — 표준 섹션 (`## 1. 개요`, `## 2. 상세`, `## n. 관련 문서`, `## 분류`), 인포박스 ("틀"), 관련 문서 ↔ 둘러보기 분리 (관련 4개 한도), 비교 sub-section ("A vs B").

### §21.1 영역 구분 (Karpathy 3-layer + namu-style 사람 입구)

| Layer | 위치 | 작성 주체 | 읽는 주체 | source of truth |
|---|---|---|---|---|
| **raw layer** (immutable sources) | `repo/wiki/raw/` | 사람 (큐레이션) | AI (read-only, ingest 시) | **immutable 원본** |
| **wiki layer** (LLM-maintained) | `repo/wiki/{sources,entities,concepts,syntheses,overview.md,Index.md,Log.md,Architecture/,Features/,Decisions/,Glossary/}` | AI 가 maintain, 사람이 view | 사람이 graph 탐색 | **mirror** (정본 X) |
| **schema layer** | `repo/AGENTS.md` (정본), `repo/CLAUDE.md` (thin redirect), `repo/GEMINI.md` (Gemini compat) | 사람이 정책 결정 (PR) | AI 가 작업 시 *반드시* 읽음 | **정본** |
| **AI context** | `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` | 사람이 정책 / AI 가 작업 시 갱신 | AI 가 §3.1 우선순위대로 읽음 | **정본** |

**Rule of thumb**: 사실·결정·정책은 AI 영역 정본에. 사람이 graph 로 탐색할 *입구점*·*mirror*·*시각화* 는 wiki layer. raw layer 는 *immutable 원본 누적*. **충돌 시 정본 우선** — wiki layer 가 따라간다.

### §21.2 AI 의무 (5가지 — v3.13.0 SHOULD, 후속 cycle MUST 예정)

AI 가 본 프로젝트에서 작업할 때 다음을 **권장 (SHOULD)** 으로 따른다. v3.13.0 에서는 self-discipline + opportunistic 동반 + WARN-only enforcement (`check #12` + `bin/wiki-lint.sh` structural) 이며, 후속 cycle 에서 **의무 (MUST)** 로 격상 예정.

1. **Feature 신규 생성 시 wiki 카드 동반 작성 (SHOULD)**
   - `unit/feature-XXXX-<slug>/` 신규 생성 시 `wiki/Features/feature-XXXX-<slug>.md` 카드 동반.
   - baseline: `repo/wiki/Features/_template-card.md` 또는 `repo/wiki/_templates/feature-card.md` (namu-style).
   - `repo/wiki/Features/_Index.md` 표에 1줄 entry add.
   - 검증: `bin/verify-completion.sh` check #12 (WARN-only).

2. **ADR 신규 생성 시 wiki mirror 동반 작성 (SHOULD)**
   - `docs/DECISIONS.md` 에 새 ADR append 시 `wiki/Decisions/<adr-id>-<slug>.md` mirror 동반.
   - baseline: `repo/wiki/_templates/adr-mirror.md` (namu-style).
   - `repo/wiki/Decisions/_Index.md` 표에 1줄 entry add.

3. **wiki/ 안의 모든 create/update 는 Log.md append (SHOULD)**
   - format: `[<ISO timestamp>] <operation> | <wiki_role> | <path> | <one-line note>`
   - `<operation>`: `create` | `update` | `link` | `lint-fix` | `graduate` | `ingest` | `query`
   - append-only — 기존 entry 수정·삭제 금지.

4. **`/wiki-ingest` 시 5-domain 갱신 (v3.13.0 신설, SHOULD)** — 출처: SamurAIGPT/llm-wiki-agent CLAUDE.md "Ingest Workflow" 10-step verbatim
   - `wiki/raw/<file>` 의 새 source 처리 시 `wiki/sources/<slug>.md` 생성 + `wiki/Index.md` Sources 행 갱신 + `wiki/overview.md` 합성 revise + `wiki/entities/`, `wiki/concepts/` 의 관련 page 생성/갱신 + contradiction flag + `Log.md` ingest entry append.
   - SKILL: [`.claude/commands/_template/wiki-ingest.md`](.claude/commands/_template/wiki-ingest.md).

5. **`/wiki-query` 답변 시 inline citation 필수 (v3.13.0 신설, SHOULD)** — 출처: SamurAIGPT/llm-wiki-agent CLAUDE.md "Query Workflow" 4-step
   - 답변의 *모든 claim* 은 source wikilink citation 필수.
   - 사용자 옵션 yes 시 `wiki/syntheses/<slug>.md` 로 답변 저장 + `Log.md` query entry append.
   - SKILL: [`.claude/commands/_template/wiki-query.md`](.claude/commands/_template/wiki-query.md).

### §21.3 운용 디테일

frontmatter 컨벤션, wikilink 표기, provenance (extracted/inferred/ambiguous), tag, lint 정책 정본은 [`docs/WIKI.md`](docs/WIKI.md). 본 § 는 *영역 분리와 의무* 만 정의한다.

### §21.4 v3.12.0 enforcement 상태 (정직 표기)

위 §21.2 의무의 자동 catch 는 v3.12.0 에서 *부분적* 이다. reviewer (META-CYCLE-009) 의 권유를 받아 다음 보강이 본 cycle 에 함께 들어갔다:

- **§18.8 dispatch table** 에 wiki keyword (`wiki/`, `Features/`, `Decisions/`, `Log.md`) 가 등록 — 정책 doc 변경 시 review-panel 이 META mode 로 dispatch 되며, feature 작업에서 wiki keyword 매칭 시 적합 reviewer 가 호출됨.
- **`bin/verify-completion.sh` check #12** 가 WARN-only 로 추가 — diff 가 신규 feature 디렉토리 (`unit/feature-*`) 를 추가했는데 `wiki/Features/<slug>.md` 동반이 없으면 stderr warn (exit 0 유지, PR block 아님).

**v3.12.0 에서 의도된 한계**: PR block 까지의 strict enforcement 는 v3.13.0+ 의 후속 cycle 에서 다음과 함께 격상. (a) check #12 의 WARN → BLOCK 분기 (`--strict` flag 또는 default 변경), (b) wiki-reviewer subagent persona 신설, (c) Mirror staleness 시간 sentinel (30 일 이상 누락 시 warn). v3.12.0 buildup 의 feature 들은 backfill 강제 대상이 아니다.

이 staged rollout 은 reviewer (qa-reviewer Q-2 finding) 의 "v3.12.0 SHOULD → v3.13.0 MUST" 권유를 직접 채택한 결과이며, "정책 선언만 + enforcement 미보강 으로 ship" 의 anti-pattern (v3.8.0 worktree drift 누적 패턴) 을 회피한다.

### §21.5 Lint (v3.13.0 부터 structural 자동화)

`wiki/` 의 health 점검 — 출처: SamurAIGPT/llm-wiki-agent CLAUDE.md "Lint Workflow" 6-category verbatim.

**Structural (v3.13.0 자동화)** — `bin/wiki-lint.sh` 또는 [`/_template:wiki-lint`](.claude/commands/_template/wiki-lint.md):

1. **Orphan pages** — 어떤 page 에서도 wikilink 가 들어오지 않는 page.
2. **Broken wikilinks** — `[[...]]` 의 target 이 vault 안에 부재.
3. **Missing entity pages** — name 이 3+ page 에 언급되었지만 `entities/` 에 page 부재.

**Semantic (v3.13.0 AI reasoning 보조)** — SKILL 호출 시 AI 가 처리:

4. **Contradictions** — page 간 claim 모순.
5. **Stale summaries** — 새 source ingest 후 관련 기존 page 미갱신.
6. **Data gaps** — `wiki/overview.md` §4, §5 의 (TBD) — *suggest specific sources*.

**Suggested action (v3.13.0 신설, namu 편집지침 출처)**: page 의 *개요·관련 문서·둘러보기 제외* sub-문단 150자 이상 5개 이상이면 *page 분리 권장* — `bin/wiki-lint.sh` 가 stderr 에 안내. 출처: [나무위키:편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) — 본 프로젝트의 wiki 가 *살아있는 namu 문서처럼 성장* 하는 시점 가이드.

### §21.6 vault config

`repo/wiki/.obsidian/` 의 4 config 파일 (`app.json`, `core-plugins.json`, `appearance.json`, `templates.json`) 은 sane defaults 만 포함한다. consumer 가 community plugin·theme 을 추가하면 `wiki/.gitignore` 에 의해 제외된다 (vault 의 portability 유지).

### §21.7 Customization 보호

consumer 가 wiki/ 안의 노트를 자체 작성한 경우 template upgrade 시 hop 은 그것을 덮어쓰지 않는다 — `bin/migrations/lib/customization-detect.sh` 의 marker / 존재 기반 보호. consumer 가 `wiki/Features/feature-0001-XXX.md` 를 이미 갖고 있다면 그 카드는 보존되고, `wiki/Features/_template-card.md` 만 갱신된다.

### §21.8 namu-style 사람 facing 형식 (v3.13.0 신설)

본 vault 의 **모든 사람 facing 노트** (즉 `Log.md` operational 외 모든 markdown) 는 [나무위키 표준 형식](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) 을 따른다 — 한국 사용자에게 친숙한 패턴 (사용자 명시 요청).

**필수 sections**:

| § 번호 | section 명 | 역할 |
|---|---|---|
| (title 직후) | 인포박스 (`\| 항목 \| 값 \|` 표) | 메타데이터 한 눈에 |
| `## 1. 개요` | overview | 1~2 문장 요약 |
| `## 2. 상세` | detail | 본문, sub-section 자유 |
| `## 3. 특징` (선택) | features | 글머리표 핵심 특성 |
| `## 4. 비교` (선택) | comparison | "A vs B" 표 (namu 의 "언어 모델" entry 패턴) |
| `## 5. 평가` (선택) | evaluation | 장단점·위험·trade-off |
| `## n. 관련 문서` | related docs | 종속 관계가 아닌 *밀접 연관* page **최대 4개** (출처: namu 편집지침) |
| `## n+1. 둘러보기` | navigation | 상위/하위/sibling page wikilinks (관련 문서와 분리) |
| `## n+2. 외부 link` | external links | http(s) URLs |
| `## 분류` (footer) | classification | `#wiki/<role>` · `#status/<state>` · `#confidence/<level>` |

**규칙**:

- 사용자 명시 reference: [namu.wiki RecentChanges](https://namu.wiki/RecentChanges) — *활발히 update 되는 entry* 의 형식 trend 와 일관 (인포박스 + section 번호 + 관련/둘러보기 분리 + footnote `[^N]`).
- 사람 facing 노트는 `Log.md` 와 `raw/` 의 immutable 원본 외 모두 적용 — `Index.md`, `overview.md`, `README.md`, `sources/*.md`, `entities/*.md`, `concepts/*.md`, `syntheses/*.md`, `Architecture/*.md`, `Features/*.md`, `Decisions/*.md`, `Glossary/*.md`, `_templates/*.md`.
- *비교 sub-section* 의 표 형식은 namu 의 "언어 모델" entry ([https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8)) 의 "생성형 vs 판별형", "대규모 vs 소규모" 같은 패턴 그대로.
- *각주* 는 `[^N]` markdown footnote 활용 — 본문 anchor + footer block.

#### §21.8.1 광범위 entry 카테고리 출처 (편중 회피, generic 화)

사용자 명시 정정 — sports entry (LCK, KBO) 편중 회피, *광범위 entry* 의 generic 패턴으로 추상화:

| 카테고리 | namu 출처 entry 예시 | 본 vault 의 매핑 | 사용 sub-section |
|---|---|---|---|
| **모든 entry 공통** | [namu 편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) | 모든 사람 facing 노트 | 개요 / 상세 / 관련 문서 / 분류 (4 필수) |
| **도구 / 기술** | [Python](https://namu.wiki/w/Python), [Git](https://namu.wiki/w/Git), [Docker](https://namu.wiki/w/Docker), [NumPy](https://namu.wiki/w/NumPy) | Features/, Architecture/, concepts/ | + 특징 / 사용법 |
| **학문 / 개념** | [알고리즘](https://namu.wiki/w/%EC%95%8C%EA%B3%A0%EB%A6%AC%EC%A6%98), [언어 모델](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8) | concepts/, Decisions/ | + 종류·분류 / 비교 |
| **인물 / 조직** | (namu 인물 template) | entities/ | + 역사·이력 |
| **시기·변천 (선택 한정)** | [KBO 한국시리즈](https://namu.wiki/w/KBO%20%ED%95%9C%EA%B5%AD%EC%8B%9C%EB%A6%AC%EC%A6%88) (sports 의 변천 — 패턴만 채택, sport-specific section 은 미적용) | 주요 architectural 결정 또는 long-lived feature 만 | + 변천·역사 (시기별 sub-section) |
| **평가 분리 (선택)** | [LCK Characteristics](https://namu.wiki/w/League%20of%20Legends%20Champions%20Korea) (긍정·부정 평가) | 도구/제품/feature 평가 | + 평가 (7.1 장점 / 7.2 단점 / 7.3 한계) |

**편중 회피 원칙** — 다음 sport/뉴스/만화 entry 특수 sub-section 은 SW 프로젝트 wiki 에 *적용하지 않음*:

- 영구 결번 / 응원 문화 / BGM (sport)
- broadcast and VOD / cast and crew (방송)
- 우승 트로피 (시기별 sport)
- "Controversies / 논란" 의 *gossip-style* — SW context 의 *위험·trade-off* 명시 (객관) 와 구분.

**generic SW wiki 적용 가이드**:

- *대개 비어있는 sub-section 은 본문에서 제거*. 본 cycle 의 template 노트 (`_template-card.md`, `_templates/feature-card.md`, `_templates/adr-mirror.md`) 가 *full sub-section* 을 보여주지만, 실 작성 시 *불필요 sub-section 제거 권장*.
- 4 필수 section + 카테고리별 1~2 선택 sub-section 만으로 *대다수 SW feature* 표현 가능.
- 본 spec 은 *광범위 entry 카테고리* 에서 추출된 *generic* 형식 — 특정 도메인 특수 section 은 *프로젝트 자체 ADR* 로 결정 후 *AGENTS.md 의 customize* 로 추가.

### §21.9 운용 slash command (v3.13.0 신설)

본 § 의 SKILL 들은 정본이 `.claude/commands/_template/` 에 있고, Codex 호환 shim 이 `.codex/commands/_template/` 에 있다.

| SKILL | 본문 길이 | 자연어 trigger | 책임 |
|---|---|---|---|
| [`/_template:wiki-ingest <raw-path>`](.claude/commands/_template/wiki-ingest.md) | 10-step | "ingest <path>" | raw/ → sources/entities/concepts/overview/Index/Log |
| [`/_template:wiki-query <question>`](.claude/commands/_template/wiki-query.md) | 4-step | "what does the wiki say about X" | Index → relevant pages → 답변 + 옵션 syntheses/ 저장 |
| [`/_template:wiki-lint`](.claude/commands/_template/wiki-lint.md) | 6-category | "lint the wiki" | structural (자동) + semantic (AI) |

**자연어 trigger 호환**: Codex / Gemini / OpenCode 같이 slash command 외 자연어 호환 — `GEMINI.md` 에 mapping 명시.

### §21.10 v3.13.0 web evidence 출처

본 §21 의 모든 design 결정은 다음 web evidence 에 매핑:

| 결정 | 출처 (stars) |
|---|---|
| 3-layer (raw / wiki / schema) | Karpathy gist (33k) + 4 high-star repo 의 4/4 채택 |
| `raw/` 디렉토리 | SamurAIGPT (2.7k) + AgriciDaniel (5.5k) + nvk (468) = 8.7k 누적 |
| `wiki/sources/` + source page schema (frontmatter + 5 body sections) | SamurAIGPT (2.7k) CLAUDE.md verbatim |
| `wiki/overview.md` "living synthesis" | SamurAIGPT + AgriciDaniel + lucasastorian = 9.2k 누적 |
| `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/` | SamurAIGPT (2.7k) + AgriciDaniel (5.5k) |
| `GEMINI.md` schema 파일 | SamurAIGPT (2.7k) 의 CLAUDE.md + AGENTS.md + GEMINI.md 3-schema |
| `wiki-ingest` 10-step + `wiki-query` 4-step + `wiki-lint` 6-category | SamurAIGPT CLAUDE.md verbatim |
| Contradiction detection at ingest | SamurAIGPT (2.7k) + nvk `/wiki:audit` |
| namu-style section 구조 (`1. 개요`, `2. 상세`, `n. 관련 문서`, `분류`) | [나무위키:편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) (사용자 명시) |
| 비교 sub-section 패턴 ("A vs B") | namu "언어 모델" entry (사용자 명시) |
| 관련 문서 (최대 4개) ↔ 둘러보기 분리 | namu 편집지침 (web search 확인) |
| 150자 ≥ sub-문단 5개 ≥ 이상 시 분리 권장 | namu 편집지침 (web search 확인) |

본 cycle (v3.13.0) 에서 모든 설계 결정은 *내부 판단 단독* 이 아닌 *web evidence 매핑* — 사용자 명시 정책.

---

## §22. Claude Code 운영 확장 패턴

### §22.1 PreCompact Hook — 컨텍스트 압축 정책 제어

Claude Code v2.1.105+ 는 `PreCompact` hook 을 통해 컨텍스트 압축(compaction) 발생 직전에 스크립트를 실행할 수 있다. 압축을 차단하려면 stdout 에 `{"decision":"block"}` JSON 을 출력하고 exit code 2 를 반환한다. JSON stdout 이 우선 파싱되며 exit 2 는 fallback 신호이므로, 두 신호를 함께 사용하는 것이 권장 패턴이다.

**`.claude/settings.json` hook 등록 예:**

```json
{
  "hooks": {
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash repo/bin/hooks/pre-compact.sh"
          }
        ]
      }
    ]
  }
}
```

**`pre-compact.sh` 예시 — in-progress TASK 존재 시 압축 차단:**

```bash
#!/usr/bin/env bash
# TASK.md에 in-progress 항목이 있으면 압축 차단 — 중요 컨텍스트 손실 방지
if grep -q "status: in-progress" repo/meta/TASK.md 2>/dev/null; then
  echo '{"decision":"block","reason":"in-progress TASK exists — context loss risk"}'
  exit 2
fi
exit 0
```

**참고:**
- `$CLAUDE_EFFORT` 환경변수로 현재 effort level 을 확인할 수 있다 (예: hook 로그에 기록).
- 압축 허용이 기본값이므로, 차단이 필요한 조건만 명시적으로 체크하는 것이 권장 패턴.


### §22.1.1 Stop / SubagentStop Hook — 능동적 피드백 반환 (v2.1.166+)

Claude Code v2.1.166+ 는 `Stop` / `SubagentStop` hook 이 `hookSpecificOutput.additionalContext`
를 반환해 **턴을 종료하지 않고 Claude 에 비차단(non-error) 피드백을 주입**할 수 있다. §22.1 의
PreCompact 패턴(`{"decision":"block"}` + exit 2 — *차단형*)과 달리, 본 패턴은 **exit 0 + 텍스트
컨텍스트 반환**으로 대화를 이어가며 다음 턴에 Claude 가 그 정보를 활용하게 한다 (*안내형*).

**`.claude/settings.json` 등록 예 (Stop hook):**

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash repo/bin/hooks/stop-feedback.sh"
          }
        ]
      }
    ]
  }
}
```

**`stop-feedback.sh` — 미완료 TASK 알림 (exit 0 + additionalContext):**

```bash
#!/usr/bin/env bash
# 세션 종료 시점에 in-progress TASK 가 남아 있으면 Claude 에 알림 (차단하지 않고 안내)
if grep -q "status: in-progress" repo/meta/TASK.md 2>/dev/null; then
  cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": "in-progress TASK 가 meta/TASK.md 에 남아 있습니다. 완료 여부를 재확인하세요."
  }
}
JSON
fi
exit 0
```

**활용 시점:**
- 세션 종료 직전 TASK.md / REPORT.md 의 미완료·BLOCKED 항목을 1차 환기 (§16 완료 게이트 보조).
- subagent 완료 후(`SubagentStop`) 오케스트레이터에 결과 요지·다음 단계 컨텍스트 주입 (§18.8 panel 결과 브리핑).
- 현재 브랜치·배포 타깃·읽기전용 디렉토리 등 *환경 상태* 를 다음 턴 판단 재료로 전달.

**차단형(§22.1)과의 구분 (혼용 금지):**
- *차단이 목적* (압축 방지, 위험 종료 방지) → PreCompact `decision:block` + exit 2.
- *피드백이 목적* (정보 전달 후 진행) → Stop/SubagentStop `additionalContext` + exit 0.
- additionalContext 로 반환하는 내용도 §12 민감정보 처리 규칙을 따른다 (secret·credential 비노출).

**차단형 block 의 런타임 한도 (8-block cap, v2.1.143+):** §22.1 PreCompact 와 Stop/SubagentStop 의
*차단형*(`{"decision":"block"}` + exit 2)은 **무한 hard-gate 가 아니다** — 반복 block 이 8회에 도달하면
Claude Code 가 강제 종료(force-stop)를 허용한다(무한루프 방지). 한도는 `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`
환경변수로 조정한다. 따라서:
- 차단형 hook 은 "자동 해소 가능한 조건의 ≤8회 soft 환기"(예: 미완료 TASK 재확인)에만 쓴다.
- **자동 해소 불가한 결정적 차단**(소비자 repo mutation·force-push·외부 영향 행동 등)은 차단형 hook 으로
  hard-gate 화하지 않는다 — §22.6 L1 `permissions.deny` 로 인코딩한다(정본 결정적 차단). cap 은 **8 을
  보장하지 않는다**: env 로 1·0 까지 하향 가능하고 세션 내 무관한 block 으로 이미 소진될 수 있어, 보안
  목적 block 은 **1회도 발동을 보장받지 못한다** — "≤8 은 안전 마진" 으로 읽지 말 것.
- §16 완료 게이트·verify-completion 보조로 차단형 Stop hook 을 설계할 때, "사람 개입 필요" 같은
  자동 해소 불가 BLOCKED 상태를 무한 block 으로 강제하면 *false sense of hard-gate* 가 된다 — 8-block
  cap 을 인지하고 결정적 경계는 deny 측에 둔다.
- 단 `permissions.deny` 도 `bypassPermissions`/`--dangerously-skip-permissions` 모드에서는 미강제다.
  진짜 비가역 경계(공유 main force-push 등)는 에이전트 밖 **server-side / branch-protection** 으로도
  보강한다 — deny 단독을 절대 보증으로 의존하지 않는다.

**PostToolUse `continueOnBlock` — 도구 차단 후 사유 피드백 + 자기수정 (v2.1.139+):** `PostToolUse` hook 의
`continueOnBlock` 옵션은 **도구 호출을 차단할 때 거부 사유를 Claude 에 되먹여**, 턴을 종료하지 않고 다음
행동에서 자기수정하게 한다. 위 두 패턴과 적용 *단위*가 다르다:
- §22.1 PreCompact `decision:block` — *압축/종료 시점* 차단.
- §22.1.1 Stop/SubagentStop `additionalContext` — *턴 종료 시점* 비차단 피드백.
- PostToolUse `continueOnBlock` — ***개별 도구 호출 시점*** 차단 + 사유 피드백(턴 유지).

ANCHOR·verify-completion·META 경로 가드(예: 금지 경로 write, 미승인 force-push 시도)를 PostToolUse 로
차단할 때 `continueOnBlock` 으로 사유를 반환하면, AI 가 차단 이유를 보고 *같은 턴*에 올바른 행동으로
재시도한다 — 사유 없는 단독 차단(turn 종료) 대비 위임 세션의 자기수정 루프를 짧게 한다. ⚠ 반환 사유
문자열은 **hook 이 생성**하므로(모델 prose 아님) 모델의 §12 자기검열이 적용되지 않는다 — 차단을 유발한
토큰을 그대로 echo 하면 secret·경로가 transcript/컨텍스트로 누출된다. **hook 작성자가 매칭된 secret·경로를
사유 반환 전 redact** 해야 한다(§12 는 hook 출력에도 적용).

### §22.2 `/fewer-permission-prompts` — 권한 설정 자동화

Claude Code v2.1.105+ 는 `/fewer-permission-prompts` 명령으로 transcript 를 분석해 `.claude/settings.json` 의 `allowedTools` allowlist 를 자동 제안한다. 신규 소비자 init 직후 또는 초기 작업 세션 후 실행하면 반복 권한 승인 프롬프트를 크게 줄일 수 있다.

**사용 시점:**
- `/_template:init` 완료 후 첫 번째 또는 두 번째 작업 세션 종료 시점
- 반복적으로 동일한 Bash / MCP 도구에 대한 권한 프롬프트가 발생할 때

```
/fewer-permission-prompts
```

명령 실행 후 Claude 가 제안한 allowlist 를 검토하고 `.claude/settings.json` 에 반영한다.


> **보완 관계**: 본 § 는 *사전(pre-built) allowlist* 를 구축한다. 런타임에 권한을 classifier 로
> 처리하는 **auto mode** 와 절대 차단 규칙은 §22.6 참조 — 두 패턴은 대체가 아닌 보완 관계다.

**`disableBundledSkills` — 번들 skill/command 숨김으로 clean surface 구성 (v2.1.169+):** `disableBundledSkills`
설정(또는 `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1` 환경변수)은 Claude Code 에 번들된 skill·workflow·
slash command 를 listing 에서 숨긴다. 소비자가 **template 이 제공하는 커스텀 skill 만 노출**하려 할 때
사용한다 — `_template:*` / `_local:*` 같은 프로젝트 skill 의 discovery 를 빌트인 명령 noise 와 분리해
clean surface 를 만든다.

```json
{
  "disableBundledSkills": true
}
```

- 활용 시점: `/_template:init` 직후, 또는 위임 세션에서 빌트인 skill 자동완성이 프로젝트 skill 선택을
  방해할 때.
- ⚠ 숨김은 **표시(discovery)** 만 제어한다 — **권한 경계가 아니다**. 실제 실행 차단은 §22.6
  `permissions.deny` 가 담당한다(§22.2 allowlist 와 동일하게 *표시 ≠ 보안 경계*).
- env 변수(`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`)는 settings 키와 동등한 대안 — CI/cron 위임처럼
  `settings.json` 을 건드리지 않고 토글하려는 경우에 쓴다.

### §22.3 Dynamic Workflow Tool 운용 — 신뢰성·subagent lifecycle

Claude Code 의 `Workflow` tool 은 다수 subagent 를 `parallel()` / `pipeline()` 으로
fan-out 해 결정적으로 오케스트레이션한다. 대규모 위임 작업(심층 감사, 마이그레이션,
광범위 sweep)에 강력하지만, 두 가지 구조적 함정이 실제 소비자 작업에서 마찰로
표면화됐다. 본 § 는 그 경감 정책이다. (subagent **panel** 의 dispatch·context bundle
정본은 §18.8 / §18.11. 본 § 는 *dynamic workflow* 실행 신뢰성에 한정.)

**Dynamic workflow 트리거 경로 (v2.1.160+)**: dynamic workflow 는 자동으로 켜지지
않는다. 트리거 키워드는 `ultracode` 다 — 2.1.160 에서 `workflow` → `ultracode` 로
리네임됐고, 이제 `workflow` 라는 단어 자체는 실행을 트리거하지 않는다 (자기 말로
워크플로를 요청하면 여전히 동작). 키워드는 `/config` 의 "Workflow keyword trigger"
설정으로 조정한다. `/effort ultracode` 는 **xhigh 강제 + dynamic workflow 자동 판단**
을 결합한 별개 effort 레벨로, xhigh 미지원 모델에서는 노출되지 않는다 (2.1.160 이전의
"dynamic workflows 설정 탓" 오진은 수정됨). Critical·대규모 위임 세션의 최신 진입
경로이며, §11.3 의 `/effort xhigh` 권장과 함께 고려한다 (Critical 등급은 `/model opus`
+ `/effort ultracode` 도 후보).

#### §22.3.1 StructuredOutput 신뢰성 — 복잡 schema fan-out 의 대량 실패 위험

`agent(prompt, {schema})` 는 subagent 에게 `StructuredOutput` tool 호출을 강제한다.
**schema 가 복잡하거나(다차원·중첩) context 가 길면 subagent 가 StructuredOutput 을
끝내 호출하지 못하고 실패**할 수 있다 (`subagent completed without calling
StructuredOutput`). 병렬 슬롯 전체가 동일 원인을 공유하면 단일 실행이 통째로
전멸하기도 한다.

**경감 패턴 (MUST when schema 가 복잡하거나 fan-out 폭이 클 때):**

- **text-first → 별도 synthesis 단계 schema 강제**: 1차 fan-out 은 `schema` 없이
  raw text 로 수집하고, 그 결과를 모아 **별도의 단순 synthesis agent 1개**에서만
  schema 를 강제한다. 수집과 구조화를 분리하면 병렬 슬롯의 schema 부담이 사라진다.
- **schema 단순화**: 한 agent 가 채워야 할 schema 는 flat·소수 필드로 유지한다.
  중첩 객체·대형 배열·교차 의존 필드는 실패율을 높인다. 필요하면 schema 를 여러
  단계로 쪼갠다.
- **부분 실패 내성 (관측 동반)**: `parallel()` 의 thunk 실패는 `null` 로 떨어지므로
  `.filter(Boolean)` 로 거르되, **거른 개수를 반드시 로깅·검증**한다
  (`results.length` 와 기대치 비교). silent drop 은 fail-open 이다 — 필수 reviewer/감사
  agent 가 실패로 누락됐는데 "전부 통과" 로 오인될 수 있다. 전멸 시 재시도(예: quota
  리셋 후 재실행)나 schema 완화로 재구성하고, 단일 실행 결과를 "전부 성공" 으로
  가정하지 않는다.

```js
// 안티패턴: 75-agent 병렬이 전부 복잡 schema 강제 → 슬롯 전멸 위험
const all = await parallel(items.map(it => () => agent(prompt(it), {schema: BIG_SCHEMA})))

// 권장: text-first 수집 → 단순 synthesis 1개에서만 schema 강제
const raw = await parallel(items.map(it => () => agent(prompt(it))))        // schema 없음
const merged = await agent(`다음 수집 결과를 구조화: ${raw.filter(Boolean).join("\n---\n")}`,
                           {schema: FLAT_SCHEMA})                            // 단일·flat
```

**harness bound — schema 검증실패 ≤5회 abort (v2.1.186+)**: `agent(prompt, {schema})` /
`Agent({schema})` subagent 는 StructuredOutput 검증에 **무한히** 매달리지 않는다 — v2.1.186+
부터 검증실패가 **5회에 도달하면 abort** 한다. 따라서 실패 agent 는 *bounded 비용*(≤5 시도) 후
종료하고 `null` 을 반환한다. 이는 위 "부분 실패 내성" 가이드와 정합한다: 실패는 무한루프가 아니라
bounded-then-null 이므로, `.filter(Boolean)` 로 거른 뒤 **거른 개수를 반드시 카운팅**해야 전멸을
"전부 성공" 으로 오인하지 않는다. 운영자 mental model 을 "무한루프 우려" → "≤5회 abort 후 null"
로 정정하되, text-first·schema 단순화 경감 패턴은 (여전히 비용·품질상 우선이므로) 유지한다.

#### §22.3.2 Subagent lifecycle — quota 만료/세션 종료 시 비재개 원칙

Subagent(및 workflow 가 spawn 한 agent)는 **부모 세션에 종속된 비영속 프로세스**다.
quota 만료·세션 종료·context rollover 로 중단되면 **그 subagent 는 이어서 재개되지
않는다**. "기존 subagent 들을 이어서 진행" 같은 지시는 subagent 를 독립 영속
프로세스로 오인한 것이며, 실제로는 새 실행이 필요하다.

**중첩 subagent (v2.1.172+)**: subagent 는 v2.1.172 부터 자기 자신의 subagent 를
**최대 5단계까지** 스폰할 수 있다 (agent→agent 중첩 트리; workflow→agent 1단계만
다루던 위 모델의 확장). 중첩이 깊어질수록 위 비재개성·토큰 비용·blast radius 가
**복리로** 커진다 — 중단 시 한 노드가 아니라 그 하위 트리 전체가 비재개로 날아가고,
깊이마다 fan-out 폭이 곱해진다. 따라서 중첩 깊이는 의식적으로 제한하고(필요한 만큼만),
깊은 트리를 띄우기 전 §11.1 누적 산출물 기준의 재개 가능성을 먼저 확보한다. 또한
v2.1.154 가 고친 "background subagent 의 worktree-isolation 우회" 가 중첩에서
재현되지 않도록, 파일을 동시 변경하는 중첩 subagent 는 **전 레벨에서
worktree-isolation 을 재확인**한다 (한 레벨만 isolation 을 설정해도 그 자식이 부모
worktree 를 공유하면 충돌).

**재개 전략 (중단 후):**

- **`Workflow({scriptPath, resumeFromRunId})`**: 동일 세션 내에서 직전 workflow 의
  완료된 `agent()` 호출은 캐시로 즉시 반환되고, 미완료분만 live 재실행된다 (같은
  스크립트+같은 args → 100% 캐시 hit). 중단된 대규모 workflow 재개의 정본.
- **새 workflow 시작**: 세션이 바뀌었거나 journal 이 없으면 새 workflow 를 실행한다.
  TASK.md / REPORT.md 에 누적된 결론(§11.1)을 입력으로 삼아 이미 끝난 부분은 건너뛰게
  스크립트를 구성한다.
- **개별 `Agent` 호출 재시도**: workflow 가 아닌 단발 subagent 는 단순히 다시 호출한다.

⚠️ **재개 시 §12 승인 게이트 재평가 (MUST)**: 재개되는 workflow/subagent 가 §12 의
승인 필요 항목(인증·인가, 파괴적 변경)이나 외부 영향 행동(PR 생성, deploy, 외부
알림)을 포함하면, **중단 전 세션에서 받은 승인을 유효한 것으로 간주하지 않는다**.
세션이 종료된 시점에 승인 컨텍스트도 함께 만료된 것으로 보고, 재개 시점에 §12 게이트를
다시 평가한다. stale 승인으로 외부 영향 행동을 자동 실행하지 않는다.

작업 중단 가능성이 있는 장기 위임은 **중간 산출물을 문서(TASK.md/REPORT.md)에
누적**(§11.1)해, subagent 비재개성과 무관하게 문서 기준으로 재개할 수 있게 한다.

### §22.4 security-guidance plugin — 작업 중 inline 취약점 리뷰 (v2.1.150+)

Claude Code v2.1.150 (Week 22) 부터 제공되는 `security-guidance` plugin 은
AI 가 코드를 변경하는 동안 **실시간으로** 보안 취약점을 리뷰한다.

**현재 보안 리뷰 워크플로우와의 관계:**

| 채널 | 시점 | 성격 |
|---|---|---|
| `/cso` (gstack) | 작업 완료 후 | 최종 게이트 — 보안 전담 리뷰어가 전체 변경 감사 (권위 있는 판단) |
| `codex review` | 작업 완료 후 | 최종 게이트 — 독립 관점 코드 리뷰 |
| `security-guidance` plugin | 작업 **중** | 조기 경보 — 변경 즉시 취약점 경고 (자동화된 1차 시그널) |

세 채널은 대체 관계가 아닌 보완 관계다. `security-guidance` 는 **조기 경보**(빠른 피드백·
방어 선제), `/cso`·`codex review` 는 **최종 게이트** (완성 후 심층 감사, 더 높은 권위).

**등록 방법 (소비자 선택적, v2.1.150+ 필요):**

`.claude/skills/` 디렉토리에 플러그인을 배치하면 Claude Code 세션 시작 시 자동으로 로딩된다:

```bash
# 스캐폴딩 생성 (소스 직접 확인 후 사용 권장)
claude plugin init security-guidance --dir .claude/skills/
```

⚠️ `claude plugin install <name>` 패턴은 외부 마켓플레이스에서 코드를 내려받는다.
설치 전 반드시 소스 출처·버전·서명을 확인하고, 팀 배포 시 `plugins/ai-delegated-dev-template/`
경로 파일의 무결성을 repo admin 권한으로 관리한다.

**비활성화:**

```bash
# 세션 비활성화 (스캐폴딩 제거)
rm -rf .claude/skills/security-guidance/
# 또는 플러그인 비활성화 명령 (v2.1.150+ CLI 버전에 따라 다름)
claude plugin disable security-guidance
```

**참고:** 실시간 리뷰는 응답 지연을 유발할 수 있다. 고빈도 단순 수정 작업에서는
비활성화 후 작업 완료 시점에 `/cso` 최종 게이트로 감사하는 것도 유효한 패턴이다.
`/cso` 는 항상 최종 판단 권위를 가지며 `security-guidance` 가 없는 것을 대체하지 않는다.


**plugin 상태 조회 — `/plugin list` (v2.1.163+):**

등록(`claude plugin init`) · 비활성화(`claude plugin disable`) 와 대칭으로, 현재 설치·활성화
상태를 확인하는 명령이다. lifecycle 의 "점검" 단계를 채운다.

```
/plugin list              # 설치된 plugin 전체
/plugin list --enabled    # 활성화된 것만
/plugin list --disabled   # 비활성화된 것만
```

장기 위임 세션에서 plugin 설치 상태를 확인하거나, cron 점검 스크립트에서 `security-guidance`
등 plugin 활성 여부를 진단할 때 사용한다.

### §22.5 worktree 설정 금지 항목 — F0/F1 isolation 정책과의 충돌

Claude Code v2.1.162 에서 신설된 `worktree.bgIsolation` / `worktree.baseRef` 설정은
§13.2.7 F0 · F1 binding 정책과 충돌할 수 있다.

**`worktree.bgIsolation: "none"` — 사용 금지**

이 설정은 배경 세션이 별도 worktree 없이 **현재 working copy(`./repo`)를 직접 편집**
하도록 허용한다. 이는 다음 정책과 정면 충돌한다:

- §13.2.7 **F0** (주 위반): consumer main checkout 의 `repo/` 직접 수정 금지
- §13.2 **F1** binding: `repo/` mutation 은 전용 ai/* worktree + branch 경유 필수

**소비자 설정에서 반드시 제거하거나 기본값(worktree 격리) 유지:**

```json
// .claude/settings.json — 다음 설정은 금지
{
  "worktree": {
    "bgIsolation": "none"   // ← 이 설정 금지: F0/F1 정책 위반
  }
}
```

**감지:** `grep -r '"bgIsolation"' .claude/settings.json` 으로 수동 확인 가능.
향후 `bin/verify-completion.sh` 에 자동 감지 check 추가 예정.

**`worktree.baseRef: "fresh" | "head"` — 사용 가능 (격리 유지 시)**

bgIsolation 이 기본값(격리 활성) 상태에서 baseRef 는 배경 세션의 worktree 기준 커밋을
지정하는 설정으로, F0/F1 정책과 무충돌이다. 필요 시 소비자 설정에서 사용 가능.


### §22.6 Auto mode — 자율 위임 세션의 런타임 권한 모델 (v2.1.136+)

본 템플릿은 "최대한 공격적/적대적" 자율 위임을 일상적으로 수행한다 (예: `/goal` 기반
무중단 반복). 이때 권한 처리에는 세 가지 선택지가 있다:

| 모드 | 성격 | 위험 |
|---|---|---|
| approve-all (모든 프롬프트 수락) | 무분별 승인 | 파괴적/비가역 동작도 통과 |
| `--dangerously-skip-permissions` | 권한 시스템 우회 | 안전망 전무 |
| **auto mode** | classifier 가 각 도구 호출을 평가 — 비가역·파괴적·환경 외부 동작은 차단, 안전 동작은 무중단 | **중간지대 (권장)** |

auto mode 는 위 둘의 **안전한 중간지대**다. 활성화·기본 차단 규칙·가용성(Anthropic API
전체 사용 가능, Bedrock/Vertex/Foundry 는 `CLAUDE_CODE_ENABLE_AUTO_MODE` 필요)은
Claude Code `permission-modes` 문서를 따른다. 자율/적대적 위임 세션의 **안전 기본값으로 권장**한다.

**Subagent 스폰 사전 평가 (spawn pre-launch classifier, v2.1.178+):** v2.1.178 부터 auto mode 는
**각 도구 호출**(위 표) 평가에 더해, **subagent 스폰 요청 자체**를 spawn *전* classifier 로 한 번 더
분류한다. §18.8 키워드 매칭 dispatch·§22.3 dynamic workflow·§22.3.2 nested subagent(최대 5단계)
스폰이 모두 이 사전 게이트를 통과하며, nested 스폰은 각 레벨에서 재평가된다. 즉 위임 세션의 subagent
fan-out 은 "스폰 시점"과 "도구 호출 시점"의 2중 게이트를 받는다 — 적대적 위임에서 의도치 않은
대규모 fan-out(예: 비용·blast radius 폭증)이 스폰 단계에서 선제 차단될 수 있다.

#### 2-layer 차단 모델 — 결정적 차단 vs classifier

§절대금지(소비자 repo mutation, `git push --force`, `.env`/secret 읽기, `--admin`, submodule
pointer 강제변경 등)를 인코딩할 때 **두 메커니즘을 혼동하지 않는다**:

**L1 — `permissions.deny` (결정적, classifier *이전* 차단, override 불가):**

구조화 패턴 `Action(pattern)` 으로 표현. classifier 가 consult 되기 전에 차단되며 사용자 의도로도
우회 불가. **절대 강제가 필요한 결정적 항목은 반드시 이 레이어** (가능하면 managed settings).
`permissions.deny` 는 committed project `.claude/settings.json` 에서도 읽힌다.

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Bash(git push --force*)",
      "Bash(git push -f*)"
    ]
  }
}
```

**파라미터-레벨 매칭 — 도구 파라미터 specifier (v2.1.178+):** 권한 규칙은 도구명뿐 아니라 **도구 파라미터
값**까지 좁혀 매칭한다 — 단 specifier 형태는 **도구마다 다르므로** 설치 버전의 `claude` 권한 docs
(`permissions`)를 정본으로 삼는다:

- **WebFetch** — `domain:` colon specifier: `WebFetch(domain:docs.anthropic.com)` /
  `WebFetch(domain:*.example.com)` (대소문자 무시, `*` 는 한 레이블 내).
- **Read/Edit** — gitignore-스타일 **경로 패턴**(colon 아님): `Read(.env)`, `Read(~/.ssh/**)`,
  `Edit(./src/**)`.
- **Bash** — **command-prefix 매칭**: `Bash(git push --force*)`, `Bash(rm -rf *)`. colon 형이 아니라
  명령 문자열 prefix + `*` 와일드카드다(`Bash(ls:*)` 는 trailing-wildcard 약식 = `Bash(ls *)` 일 뿐
  일반 param 문법이 아니다).
- **MCP** — canonical 도구명: `mcp__server__tool`(param specifier 아님).

이 specifier 를 `permissions.deny` 에 쓰면 **L1 결정적 차단을 인자 단위로 좁힌다**(차단 정밀화).
`permissions.allow` 에 쓰면 §22.2 의 **프롬프트-억제 allowlist 를 좁힌다** — allow 는 차단 통제가
아니라 auto-approve 이므로 **보안 경계가 아니다**(deny 와 혼동 금지).

```json
{
  "permissions": {
    "deny": [
      "Bash(rm -rf *)",
      "WebFetch(domain:evil.example)",
      "Read(.env)"
    ],
    "allow": [
      "Bash(git status)",
      "Bash(git diff *)",
      "WebFetch(domain:docs.anthropic.com)"
    ]
  }
}
```

> ⚠ **인자 제약 패턴은 fragile**: 명령 인자를 권한 패턴으로 제약하는 것은 변수 치환·공백·옵션 재배열로
> 우회될 수 있다(docs 경고). `rm -rf /` 류 파괴적 명령의 견고한 차단은 넓은 deny(`Bash(rm *)`)+안전
> 동작 allow-list, 또는 PreToolUse hook 으로 보강한다 — 파라미터 specifier 단독에 의존하지 않는다.
> §22.2(`/fewer-permission-prompts`)가 *어떤 도구를* 허용할지 제안한다면, 이 specifier 는 deny 측에서
> *그 도구의 어떤 인자까지* 차단할지 좁힌다 — 보완 관계다.

**L2 — `autoMode` (classifier 가 평가하는 prose 규칙):**

`autoMode.{environment, allow, soft_deny, hard_deny}` 4개 배열은 **자연어(prose) 규칙**이며
classifier 가 해석한다. 결정적 패턴이 아니라 "맥락 판단" 용도다.

- `hard_deny`: 무조건 차단 (사용자 의도·allow 예외 무효).
- `soft_deny`: 차단하되 명시적 사용자 의도/allow 로 override 가능.
- `allow`: soft_deny 예외.
- `environment`: 신뢰 인프라(repo·bucket·domain) 명시 — 무엇이 "외부"인지 classifier 가 판단.

```json
{
  "autoMode": {
    "soft_deny": ["$defaults", "Never run database migrations outside the migrations CLI"],
    "hard_deny": ["$defaults", "Never send repository contents to third-party code-review APIs"]
  }
}
```

> ⚠ **`"$defaults"` 누락 금지**: 배열에서 `"$defaults"` 를 빼면 해당 섹션의 **빌트인 규칙
> 전체가 폐기**된다 — `soft_deny` 의 force-push/`curl|bash`/prod-deploy 빌트인, `hard_deny`
> 의 data-exfiltration/auto-mode-bypass 빌트인이 사라진다. 항상 `"$defaults"` 를 포함하고
> 그 위에 프로젝트 규칙을 얹는다.

#### 적용 시 주의 (배포 경로)

- **`autoMode` 는 committed project settings 에서 읽히지 않는다.** classifier 가 읽는 scope 는
  `~/.claude/settings.json`(개발자), `.claude/settings.local.json`(per-project, gitignored),
  managed settings(조직 배포), `--settings`/SDK inline 뿐이다. 즉 **템플릿이 소비자 repo 의
  committed `.claude/settings.json` 으로 autoMode 규칙을 배포할 수 없다** — `permissions.deny`
  (committed 가능) 또는 managed settings 로 분리 배포해야 한다.
- classifier 는 `CLAUDE.md` 내용도 읽는다. "never force push" 같은 행동 규칙을 CLAUDE.md 에
  두면 Claude 와 classifier 를 동시에 지도한다 — 본 템플릿의 §절대금지 요지를 소비자
  CLAUDE.md 에서 닿게 두면 classifier 차단에도 반영된다.
- §22.2(`/fewer-permission-prompts`, 사전 allowlist)와 **보완 관계**: §22.2 는 정적 allowlist,
  §22.6 은 런타임 classifier. 함께 쓰면 반복 프롬프트 감소 + 위험 동작 차단을 모두 얻는다.

#### 점검 명령

```bash
claude auto-mode defaults   # 빌트인 규칙 출력
claude auto-mode config     # $defaults 전개된 effective 규칙 확인
claude auto-mode critique   # 커스텀 규칙의 모호·중복·오탐 위험 AI 검토
```

설정 변경 후 `claude auto-mode config` 로 effective 규칙을 검증한다. 거부 이력은 `/permissions`
의 Recently denied 탭에 기록되며, 반복 거부는 보통 `autoMode.environment` 컨텍스트 부족 신호다.

### §22.7 위임 세션 트러블슈팅 — `--safe-mode` customization 격리 진단 (v2.1.169+)

본 템플릿은 PreCompact/Stop hook · AGENTS.md 정책 · `/_template:*` · `/_maintainer:*` skill ·
`settings.json` 커스터마이징에 강하게 의존한다. 위임 세션이 예기치 않게 동작할 때 "이 오작동이
내 customization 탓인가, Claude Code core 탓인가" 를 가르는 1차 진단 도구로 `--safe-mode`
플래그(또는 `CLAUDE_CODE_SAFE_MODE` 환경변수, v2.1.169+)를 사용한다. 이 모드는 모든
customization(hooks·settings·skills)을 비활성화한다:

- core 동작에서도 문제가 재현되면 → Claude Code 자체 또는 외부 요인(환경·네트워크·소비자 코드).
- safe-mode 에서 문제가 사라지면 → 본 템플릿의 hook/정책/skill customization 이 원인 → 해당
  영역(어떤 hook·어떤 §·어떤 skill)을 좁혀 진단한다.

진단 후에는 safe-mode 없이 정상 세션으로 복귀한다. safe-mode 는 **디버깅 격리 전용**이며 상시
운영 모드가 아니다 — 거버넌스 hook(F0 gate, verify-completion, PreCompact TASK 보호 등)도 함께
비활성화되므로, 이 모드에서는 mutation/commit/fan-out 을 수행하지 않는다(진단 관찰만).

### §22.8 `fallbackModel` — 모델 과부하·미가용 시 폴백 체인 (v2.1.166+)

멀티 소비자 환경에서 장기 자율 위임을 동시 다발로 수행하면, primary 모델이 일시적으로
**과부하(overloaded)·미가용(unavailable)·non-retryable 5xx** 응답을 반환해 세션이 실패할
수 있다. `fallbackModel` 은 이때 지정한 폴백 모델을 **순서대로** 시도해 세션을 지속시킨다.

> ⚠️ **적용 범위 — 모델 *가용성* 한정, quota/rate-limit 은 비대상.**
> fallbackModel 은 과부하/미가용/non-retryable 5xx 에만 발동한다. 다음에는 **발동하지
> 않는다** — 인증 오류, billing/요금제 오류, **rate-limit(429)**, request-size 오류, 전송
> 오류(이들은 일반 retry 로직을 탄다). 즉 "usage limit 소진"(plan quota 도달) 같은 요금제
> 한도는 fallbackModel 이 복구하지 못한다. 그 실패 모드는 §22.9(SessionEnd flush) + cross-worker
> 인계 + `/usage` 모니터링(§11.3)의 영역이다. 두 메커니즘을 혼동하지 않는다.

**`.claude/settings.json` 등록 예 (primary=Opus 4.8 → Sonnet 4.6 → Haiku 4.5):**

```json
{
  "fallbackModel": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
}
```

- 값은 **폴백 목록만** 담는다(현재 primary 는 제외). 별칭(`sonnet`·`haiku`)·`"default"`(기본 모델로 전개)도 허용.
- **순서대로** 시도하며 전환 시 notice 를 표시한다. 중복 제거 후 **최대 3개**까지(초과분 무시).
- 전환은 **현재 턴 한정** — 다음 메시지는 다시 primary 부터 시도한다.
- 도달 불가 모델(예: 은퇴 모델)은 건너뛰고 다음 항목으로 진행.
- CLI 플래그 `--fallback-model sonnet,haiku` 가 설정값보다 우선.
- **subagent 에는 자동 적용되지 않는다** — subagent 는 자체 model 설정을 따른다(§22.3.2 의
  subagent 비재개성과 별개 사안 — 대규모 fan-out 에서 폴백이 필요하면 subagent model 을 별도 지정).
- **실 폴백 depth 는 `availableModels` 와의 교집합**: `enforceAvailableModels` 가 켜지고 allowlist 에
  체인 항목 일부가 빠지면, 문서상 3-deep 체인이 실제로는 1~2-deep 로 **조용히 축소**된다(아래 read
  시점 drop). 설정한 체인 = 실효 체인이 아닐 수 있음을 전제로 둔다.

**`availableModels` / `enforceAvailableModels` — 모델 allowlist (cost·consistency 제어, v2.1.175+):**

폴백 체인이 의도치 않은 모델로 확대되지 않도록 선택 가능 모델을 allowlist 로 제한한다.

> ⚠️ **보안 경계가 아니다.** 이는 비용·일관성(어느 tier 를 쓰는가) 제어이지 capability/권한
> 경계가 아니다 — 로컬 `settings.json` 을 편집할 수 있는 주체는 이 목록도 편집할 수 있다. 실효
> 강제가 필요하면 상위 scope(managed/policy settings)로 배포해야 한다.

```json
{
  "availableModels": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  "enforceAvailableModels": true
}
```

- `availableModels`: 선택 가능 모델 allowlist. `/model`·`--model`·`ANTHROPIC_MODEL`·subagent
  `model`·**fallbackModel 체인**에 모두 적용. 체인 중 allowlist 밖 항목은 read 시점에 **drop 되어
  시도되지 않는다**.
- `enforceAvailableModels: true`(v2.1.175+): allowlist 를 Default 옵션까지 확장(tier 기본이
  allowlist 밖이면 첫 허용 항목으로 resolve). `availableModels: []` 이면 enforcement 미발동.
- managed/policy settings 의 값은 하위 scope 를 **대체**(merge 아님) — 조직 차원 강제의 유일한 실효 lever.

모델 id 는 본 환경 정본을 사용한다 — Opus 4.8 `claude-opus-4-8`, Sonnet 4.6 `claude-sonnet-4-6`,
Haiku 4.5 `claude-haiku-4-5-20251001`(별칭 `opus`/`sonnet`/`haiku` 는 최신 tier 로 resolve).
자세한 설정 의미는 Claude Code `model-config` 문서를 따른다.

### §22.9 `SessionEnd` lifecycle hook — 종료 시 결정적 finalize + worktree 정리 (v2.1.169+)

Claude Code v2.1.169+ 의 **`SessionEnd`** hook(changelog 의 "post-session" hook 의 실제 event
이름)은 세션이 종료된 **후·workspace(worktree) 삭제 직전**에 스크립트를 실행한다. 장기 위임
세션이 quota 소진·사용자 종료·rollover 등으로 끝날 때 in-progress 상태를 **결정적으로** 보존하고
잔재를 회수하는 종료 게이트로 쓴다. §22.1 PreCompact(압축 직전)와 bookend 이며 `SessionStart`
(세션 시작)와 짝을 이룬다.

**`.claude/settings.json` 등록 예:**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "clear|logout|prompt_input_exit|other",
        "hooks": [
          { "type": "command", "command": "bash repo/bin/hooks/session-end.sh" }
        ]
      }
    ]
  }
}
```

- `matcher` 는 종료 사유로 필터(`clear`·`resume`·`logout`·`prompt_input_exit`·`bypass_permissions_disabled`·`other`). 생략 시 전체.
- **exit code 는 무시된다 — hook 은 종료를 차단할 수 없다**(PreCompact 의 *차단형*과 다른 점). 관찰·기록·정리 전용.
- stdin JSON 으로 `session_id`·`transcript_path`·`cwd`·`reason`·`hook_event_name` 수신. `additionalContext` 문자열을 반환해 로깅 가능.

**용도 1 — 결정적 인계 flush (§11.1·§22.3.2 보완):**
장기 위임 세션이 끝날 때 TASK.md/REPORT.md 최종 상태와 cross-worker 인계 노트(worktree/branch/
base SHA/verify 명령/적용 메모리/re-cycle 계획)를 종료 시점에 자동 flush 한다. §22.3.2 가 다루는
"subagent/세션 비재개성" 의 보완책 — 문서 누적(§11.1)을 후속 작업자가 의존할 수 있도록 종료 시점에
deterministic 하게 확정한다. quota 소진으로 수동 인계가 강제되던 마찰(§22.8 의 비대상 실패 모드)을
이 hook 이 자동화로 완화한다.

**용도 2 — worktree 잔재 cleanup (§22.5 F0/F1 존중):**
in-flight 임시 산출물(예: `scenario.*.json`, `*.worktree-tmp` 등 프로젝트가 정한 비밀-아닌 잔재
패턴)이 누적되는 것을 종료 시 회수한다. 단 §22.5 의 F0/F1 isolation 정책을 존중한다 — cleanup 은
**자신의 worktree/세션 잔재에 한정**하고 consumer main checkout(`./repo`)의 추적 파일이나 타
worktree 를 건드리지 않는다.

> ⚠️ **두 가지 안전 제약 (작성자 책임):**
> - **secret 파일을 열거·출력하지 않는다.** `.env*`·`*.secret*` 등 비밀-보유 파일은 이 hook 에서
>   `find`/`cat`/`echo` 대상에 넣지 않는다 — 파일명만으로도 비밀 존재가 노출되고, SessionEnd 출력은
>   transcript 에 남아 teardown 후에도 영속한다. 비밀 잔재 정리가 꼭 필요하면 명시 경로만 처리하고
>   출력은 `>/dev/null` 로 버린다.
> - **삭제 스코프는 script 가 직접 보장한다.** SessionEnd 는 exit code 를 무시하므로 harness 도
>   non-zero exit 도 잘못된 `rm` 으로부터 main checkout 을 보호하지 못한다(§22.5 F0). `rm`/`-delete`
>   전에 대상 경로가 **본 세션 worktree 내부인지 단언**한 뒤에만 삭제한다.

```bash
#!/usr/bin/env bash
# session-end.sh — 종료 시 인계 노트 flush + 본 세션 worktree 잔재 정리 (예시)
payload=$(cat)   # stdin JSON: session_id / transcript_path / cwd / reason
wt=$(printf '%s' "$payload" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
# 1) TASK/REPORT 최종 상태가 미flush 면 인계 노트 append (프로젝트별 구현)
# 2) 삭제 전 대상이 본 세션 worktree(격리 경로) 내부인지 단언 후, 비밀-아닌 임시 잔재만 정리
case "$wt" in
  */worktrees/*|*/.ai/*) find "$wt" -maxdepth 2 -name 'scenario.*.json' -delete 2>/dev/null ;;
  *) : ;;  # main checkout 등 격리 밖 경로면 아무것도 삭제하지 않음 (F0 보호)
esac
exit 0   # exit code 는 어차피 무시됨 — 차단 불가
```

> 참고: `SessionEnd` 는 종료를 막지 못하므로, "압축/종료를 *차단*해 컨텍스트를 지키는" 용도는
> 여전히 §22.1 PreCompact(`{"decision":"block"}`+exit 2)가 담당한다. SessionEnd 는 "막을 수
> 없는 종료를 *깔끔하게 마무리*" 하는 보완재다.

### §22.10 Skill hot-reload — 세션 재시작 없이 스킬 변경 반영 (v2.1.176+)

Claude Code v2.1.176+ 는 **skill hot-reload** 를 지원한다 — 디스크의 스킬 `.md` 가 바뀌면 변경된
스킬만 세션에 재announce 되고, `/reload-skills` 명령은 스킬 디렉토리를 mid-session 으로 재스캔한다.
세션을 끝내고 다시 띄우지 않아도 편집이 즉시 반영된다.

본 템플릿은 maintainer 가 다수 스킬(`.claude/commands/_template/*`, `.claude/commands/_local/*`,
`.claude/commands/_maintainer/improve`)을 **반복 편집**하는 구조라, 이 hot-reload 가 개발 iteration 을
직접 단축한다.

- 스킬 `.md` 를 수정한 직후 `/reload-skills` 로 디렉토리를 재스캔하면 새 정의가 같은 세션에서 호출
  가능해진다 — `/_maintainer:improve`·`/_local:inbox` 같은 스킬을 고치며 dogfood 할 때 세션 재시작
  왕복이 사라진다.
- 신규 스킬 파일을 추가한 경우에도 `/reload-skills` 가 discovery 를 갱신한다 (자동완성 listing 포함).
- 주의: hot-reload 는 **스킬 정의(프롬프트)** 를 갱신하는 것이지, 이미 진행 중인 스킬 실행의 거동을
  소급 변경하지 않는다 — 편집 후 새로 호출해야 반영된다.

### §22.11 Nested `.claude/` 디렉토리 해석 — closest-to-cwd 우선순위 (v2.1.178+)

Claude Code v2.1.178+ 는 `.claude/skills`(및 `.claude/` 하위 agent·workflow·output-style)를
**작업 디렉토리(cwd)에 가장 가까운 것 우선**으로 로드한다 — 동일 이름이 복수 `.claude/` 에 존재하면
**cwd 최근접 정의가 충돌 시 이긴다**. 이름 충돌은 `<dir>:<name>` 으로 표기돼 진단 가능하고,
project-scope workflow 저장은 가장 가까운 기존 `.claude/workflows/` 를 타깃한다.

본 템플릿은 **wrapper-layout**(cwd=wrapper, git-root=`repo/`) + **worktree-first**(`.worktrees/<branch>/`,
§13.2/§22.5) 구조라 이 규칙이 직접 영향을 준다 — 동일 이름의 skill/agent/workflow 가 wrapper·`repo/`·
`.worktrees/<branch>/` 의 여러 `.claude/` 에 존재하면, v2.1.178+ 부터 호출 위치(cwd)에 따라 다른 정의로
resolve 될 수 있다. worktree cwd 에서 호출한 스킬이 의도와 다른 디렉토리의 정의로 풀릴 위험이다.

**정합성 규칙:**

- 템플릿 스킬(`_template`/`_local`/`_maintainer`)·agent 의 **정본 배치 위치를 한 곳으로 고정**하고
  복수 `.claude/` 에 중복 정의를 두지 않는다 — wrapper·`repo/`·worktree 어느 cwd 에서 호출해도 동일
  정의로 resolve 되게 한다.
- 의도된 cwd-별 분기(예: machine-local `_local/*` 가 repo cwd 에서만 노출, §`/_local:inbox` SENTINEL)는
  유지하되, 그 외 이름 충돌은 회피한다.
- **보안 경계 (MUST)**: "closest-to-cwd wins" 는 worktree-local 또는 소비자 `.claude/` 가 maintainer-only·
  machine-local 명령(`_maintainer/*`, `_local/*`)을 **shadow 하거나 의도치 않게 surface** 시키는 형태가
  될 수 있다. machine-local 격리(`/_local:inbox` 의 hostname+cwd+인프라 3-layer SENTINEL)는 디렉토리
  resolution 이 아니라 **명령 본문의 런타임 가드로 강제**되므로, 다른 cwd 에서 이름이 resolve 되더라도
  SENTINEL 이 실행을 차단한다 — nested resolution 우선순위에 격리를 의존하지 않는다. 신규 `.claude/`
  배치 시 maintainer-only 명령명과 충돌하지 않는지 확인한다.
- 충돌이 의심되면 listing 의 `<dir>:<name>` 표기로 어떤 디렉토리 정의가 우선됐는지 확인한다.

### §22.12 headless / cron 자기위임 recipe (v3.35.0)

본 템플릿의 핵심 use case 는 **AI 위임 개발**이며, 소비자가 자체 스케줄(cron)로 스킬을 자기위임
실행하는 것(이 인프라의 `scheduled-inspection/run.sh` 와 동형)은 일급 패턴이다. headless/cron 호출의
보편 제약을 매번 경험적으로 재발견하지 않도록 아래를 정본으로 둔다.

**1. `--dangerously-skip-permissions` 는 root/sudo 로 실행 거부 (하드 제약)**

`claude --dangerously-skip-permissions` 는 **root 또는 sudo 권한으로는 실행을 거부**한다
(verbatim: `--dangerously-skip-permissions cannot be used with root/sudo privileges for security
reasons`). 따라서 cron 에서 `sudo claude …` (claude 프로세스를 root 로) 형태는 불가하다. 대안:

- claude 프로세스는 **비-root 소유자**로 실행한다 (cron 라인을 해당 user 의 crontab 에 둔다).
- 권한이 필요한 작업(예: root-소유 디렉토리 정리)은 claude 프로세스 *내부*에서 **scoped NOPASSWD
  sudo** 로 한정 호출한다 — 프로세스 전체를 root 로 올리지 않는다. sudoers 는 **특정 바이너리/래퍼
  스크립트로 좁혀** 등재한다 (예: `NOPASSWD: /path/to/cleanup-worktrees`). `NOPASSWD: ALL` 이나
  무제한 `rm` 은 비-root 프로세스를 사실상 root-동등으로 만들어 격리를 무력화한다 — 금지.
- 권한 우회가 꼭 필요 없으면 `--dangerously-skip-permissions` 대신 **`--allowed-tools` 화이트
  리스트**로 최소 권한을 부여한다 (reference 구현: `scheduled-inspection/run.sh` — skip-permissions
  미사용 + `--allowed-tools Bash Edit Write Read …`).

**2. headless invocation — `--print --effort <tier>`**

비대화 실행은 `claude --print`(non-interactive) 로 한다. 입력은 stdin 파이프 또는 프롬프트 파일.
reasoning 깊이는 `--effort <low|medium|high|max>` 로 전달한다.

```bash
cat prompt.md | claude --print --effort max --allowed-tools Bash Edit Read >out.log 2>err.log
```

**3. cron clean-env hygiene**

cron 은 로그인 셸이 아니라 최소 환경에서 돈다. 자기위임 실행 전 다음을 주입/확인한다:

- **git identity**: `git config user.name/user.email` (commit 산출 시) — clean env 엔 없을 수 있다.
- **TZ**: 타임존 (예: `TZ=Asia/Seoul`) — 리포트/로그 timestamp 정합.
- **per-user credentials**: claude 인증(`~/.claude` / credentials.json)이 실행 user 소유로 존재하고
  **소유자 전용 권한(`chmod 600`)** 이어야 한다 — world-readable 이면 토큰이 누출된다. cron job 은 그
  자격증명의 **소유 user 로 실행**한다; 읽기 실패를 권한 완화(world-read)로 우회하지 않는다.
- **flock**: 중복 실행 방지 (`flock -n <lockfile> -c '<cmd>'`) — cron 간격보다 작업이 길어질 때.

**4. `.worktrees/` root-소유 orphan 정리**

worktree 디렉토리가 root 소유로 생성되면(예: root 컨텍스트에서 cycle-init), 비-root 세션이
`git worktree remove` 시 물리 디렉토리 삭제가 `Permission denied` 로 실패한다. 권장:

- worktree 는 **실행 세션 소유자**로 생성·정리한다 (소유자 일관).
- 이미 root-소유 orphan 이 생겼으면 **우선 `cycle-finalize.sh --target-worktree <path>` 로 대상을
  명시해 main 에서 정리**한다 (§16.3 Step 6 참조). sudo 가 불가피하면 위 §1 의 scoped NOPASSWD
  (특정 정리 래퍼 한정)로만 호출한다.

**범위 밖 (비-actionable)**: 모델-tier 강제(예: ultracode 기본화)는 harness/모델 설정이지 코드
템플릿이 강제할 수 있는 대상이 아니다. 본 recipe 는 **CLI/env 보편 사실의 문서화**에 한정하고,
어떤 effort/모델로 돌릴지는 소비자 정책에 위임한다.

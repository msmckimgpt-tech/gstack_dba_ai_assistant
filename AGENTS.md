---
template_version: v3.6.1
domain: [governance, workflow, context, safety]
ai_read_priority: 1
---

# mysql_ai 템플릿 작업 지침서

> **주의:** 이 문서가 포함된 폴더 구조가 템플릿에서 복사된 직후라면,
> `FIRST_REQUEST.md`의 **시나리오 0 (템플릿 초기화)**를 먼저 수행해야 한다.
> 템플릿의 예시 콘텐츠(`feature-0001-example`, 템플릿 ADR 등)가 남아 있으면
> 이를 실제 프로젝트 요구사항으로 오해할 수 있다.

---

# Part A — 기본 원칙

## §1. 목적

현재 디렉토리(`.`)에 템플릿 실행 루트로 재구성된 MySQL 기반 `agent_cli` 환경을 운영한다.
최우선 목적은 **요청 의도에 맞는 실제 데이터 결과를 빠르게 반환**하는 것이다.
- 이 문서는 원본 루트 `AGENTS.md`의 의미를 유지한 채 템플릿 구조에 맞게 옮긴 정본이다.
- 템플릿 사본은 **단독 실행**을 전제로 하며, 원본 프로젝트와의 동시 기동은 지원하지 않는다.

이 저장소에서 AI는 사용자의 요구를 바탕으로 기능을 설계, 구현, 테스트, 문서화한다.
모든 작업은 코드와 문서가 함께 갱신되어야 하며, 여러 AI와 사람이 함께 접근해도 충돌과 모호성을 최소화해야 한다.

### §1.1 연구 기반 방향 전환 (강제)
- 목표 상태는 "LLM 파라미터에 DB를 암기"가 아니라, **외부 지식베이스를 완전 구축**하고 LLM이 매 요청 시 해당 지식을 참조해 SQL을 작성하는 구조다.
- 따라서 지식 품질의 1순위는 `DB -> Memory KB` 동기화 완전성이고, 2순위는 LLM 입력 패키징 정확도다.
- 요청 텍스트를 코드가 임의 가공/축약/휴리스틱 분기하는 방식은 금지한다.
- LLM에는 가능한 한 **요청 원문 + 근거 지식 + 실행 결과 피드백**을 전달한다.
- 사용자 질의 경로에서 SQL은 **오직 LLM이 작성**한다. 코드 템플릿 SQL(`COUNT(*)`, 메타 점검 SQL, fast-aggregate SQL) 생성/주입은 금지한다.

### §1.2 웹 기준 업계 표준 반영 (강제)
- 대화 상태는 단순 문자열 누적이 아니라 **안정적인 상태 관리**로 유지한다.
  - 메타 점검 발화(예: "문맥 이해하니?")는 `origin_request`를 덮어쓰지 않는다.
  - 주제 전환은 명시 전환 신호(새 도메인/새 객체/명시 SQL)일 때만 반영한다.
- 메모리는 `short-term(thread)` + `long-term(global)`를 분리해 사용하고, 실행마다 근거 패키지를 재구성한다.
- RAG 라우팅은 `retrieve -> rerank -> grounded plan` 순서를 지키고, 근거 부족일 때만 메타탐색으로 폴백한다.
- 근거가 없는 객체 강제 집계(`random table count`)를 금지한다.
- 참고 표준:
  - OpenAI Conversation State: https://platform.openai.com/docs/guides/conversation-state
  - LangGraph Memory: https://docs.langchain.com/oss/python/langgraph/add-memory
  - Anthropic Tool Use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
  - Azure RAG Architecture: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-architecture

### §1.3 최우선 과제 (우선순위 고정)
- `1)` 정확도: 메타데이터 나열이 아닌 실제 결과/결론 반환
- `2)` 맥락: follow-up(`다시/이어서/아까 그거`)에서도 의도 유지
- `3)` 지식 재사용: 기존 검증 근거 재활용으로 재탐색 최소화
- `4)` 성능: 90초 초과 비율 감소, 루프/중복 탐색 제거

### §1.4 비전문가 사용자 가정
- 사용자는 모호한 요청을 한다.
- 객체명/컬럼명을 틀릴 수 있다.
- "다시/이어서/알아서" 같은 follow-up이 많다.
- 오류 원인 분석을 agent에 위임한다.

#### 대응 원칙
- 최소 검증 후 실행 가능한 결과를 우선 반환.
- 불확실성은 1회만 질문하고, 가능하면 실행 우선.
- 오류 시 동일 쿼리 반복 금지, 오류 유형별 복구 경로 전환.

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

### §2.2 핵심 제약
- `_ai_delegated_dev_template` 외부 디렉토리 수정 금지.
- 런타임 산출물은 `../artifacts/`에만 저장한다.
- `.env.example` 기본값에는 실제 키를 넣지 않는다.
- 단, 기존 `OPENAI_API_KEY` 값이 이미 있으면 `.env`에서 삭제/덮어쓰기 금지.
- 컨테이너 내부 경로는 Linux 경로만 사용한다.
- 호스트 파일시스템 경로는 상대경로만 사용한다.
- 도커 제어는 반드시 `make` 타깃 사용(직접 docker/compose 명령 금지).
- DB 테스트/제어는 기본적으로 `make ask` 사용.
- 예외: 메모리 DB(`AGENT_MEMORY_DB`, `AgentMemory*`) 점검은 mysql client 직접 사용 허용.
- 메모리 DB 점검 시 `make ask`, `make mysql` 사용 금지.

### §2.3 절대 금지 (충돌 항목 제거)
- 문자열 패턴 기반 의도 분기/강제 SQL 경로 금지 (`_is_aggregate_like_request` 류 금지).
- 요청 토큰 매칭 기반 객체 점수화/선택 금지(테이블 선택은 LLM resolver + 근거 패키지 기준).
- 요청 토큰 매칭 기반 KB 검색 필터링 금지(근거 로딩은 전체/스키마/객체 exact 기준으로 수행).
- `planner_constraints.*` 같은 임의 제약 변수로 LLM 행동을 강제하는 방식 금지.
- `AGENT_KB_FACT_LIMIT`, `AGENT_GLOBAL_KB_FACT_LIMIT`, `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES` 등 **고정 상한 기반 샘플링 설계 금지**.
- "요약만 주입하고 원문 근거는 버리는 구조" 금지.
- 사용자의 요청과 무관한 스키마/테이블 탐색을 먼저 수행하는 행동 금지.
- 명시 근거 없이 객체를 임의 선택해 `COUNT(*)`로 즉시 응답하는 동작 금지.
- 객체 선택 실패 시 `schema_top`/`fallback_top_candidate`/가중치 상위 1개 같은 임의 폴백 금지.

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
8. `/repo/playbooks/*.md`
9. 기능 폴더의 `/docs/AGENTS.md`
10. 기능 폴더의 `/docs/FUNCTION.md`
11. 기능 폴더의 `/docs/TASK.md`
12. 기능 폴더의 `/docs/REPORT.md`
13. 기능 폴더의 `/docs/MODIFY.md`, `/docs/REVIEW.md`, `/docs/TEST.md`, `/docs/DECISIONS.md`

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

### §4.2 기본 구조

- `./unit/feature-0001-platform-runtime/src`
- `./unit/feature-0002-agent-core/src`
- `./unit/feature-0003-agent-web-ui/src`
- `./unit/feature-0004-browser-automation/src`
- `./unit/feature-0005-qa-mcp/src`
- `./unit/feature-0006-lan-proxy-access/src`
- `./unit/<feature-id>/docs`
- `./shared`
- `./docs`
- `./.env`
- `./docker-compose.yml`
- `./Makefile`
- `./MCP_DESIGN.md`

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

## §6. 추적성 규칙

가능하면 아래 식별자를 사용한다.

| 식별자 | 용도 | 형식 |
|--------|------|------|
| `REQ-XXXX` | 요구사항 | 순번 |
| `AC-XXXX` | 수용 기준 | 순번 |
| `CHG-YYYYMMDD-XXXX` | 변경 | 날짜+순번 |
| `REV-YYYYMMDD-XXXX` | 리뷰 | 날짜+순번 |
| `ADR-XXXX` | 결정 | 순번 |
| `TEST-XXXX` | 테스트 | 순번 |
| `LRN-YYYYMMDD-XXXX` | 학습 | 날짜+순번 |

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
- 영향받는 파일 목록
- 접근 방법 요약 (3~5줄)
- 위험도 평가 (§12.3 기준: Minor / Major / Critical)

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
| `.env`, `.env.example` | `docs/SECURITY.md`, `docs/DECISIONS.md ADR-0014` | 원본 `mysql_ai/.env`의 운영 의미 보존. 비밀값 커밋 금지 |
| `docker-compose.yml`, `Dockerfile*` | `docs/CONVENTIONS.md`, `docs/DECISIONS.md ADR-0012` | 서비스(`mysql`, `agent`, `memory-init`, `insight-worker`, `mcp`) 경계·포트 규칙 확인 |
| `unit/**/src/**/*.py` | 해당 feature `docs/AGENTS.md` + `docs/FUNCTION.md` | 기능별 경계·외부 의존성 규칙 확인 |
| `unit/**/tests/**/*.py` | 해당 feature `docs/TEST.md` | 테스트 케이스 정의는 rewrite, 결과는 append-only |
| `Makefile` | `docs/ARCHITECTURE.md` | 실행 진입점 — 타깃 추가/제거는 ADR 경유 |
| `../../artifacts/**` | `docs/DECISIONS.md ADR-0011`, `ADR-0013` | Git 외부 — 코드에서 경로만 참조하고 커밋하지 않는다 |

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

### §11.3 인사이트/근거 참조 운영 규정
- 관련 질문에서 먼저 `AgentMemoryFactEntries` 근거를 조회한다.
- 근거 충족 시 `search_objects` 같은 메타탐색을 건너뛴다.
- 근거 부족일 때만 메타탐색을 수행하고, 부족 이유를 로그에 남긴다.
- 동일 요청 도메인에서 이미 검증된 객체가 있으면 해당 객체를 우선 사용한다.
- `AGENT_LLM_REQUEST_PASSTHROUGH=1`일 때는 모호 요청의 객체 short-circuit를 기본 비활성으로 둔다.
- 선택 객체 SQL은 실행 전 grounding review를 통과해야 하며, 실패 시 재작성 또는 차단한다.

### §11.4 맥락 품질 재발 방지 (P0/P1/P2)

#### P0 (즉시 적용/회귀 불가)
- `origin_request`는 주제 전환 시 갱신한다.
- 요청/의도 판단에 문자열 휴리스틱을 사용하지 않는다.
- 코드에서 LLM 행동을 제약하는 강제 분기 변수 주입을 금지한다.
- 요청 원문을 임의 가공하지 않는다.
- 이미 답한 질문 반복 금지.
- 사용자 교정사항은 최우선 제약으로 즉시 반영.

#### P1 (우선 적용)
- 연속 `ask` 구간에서도 요약/맥락 갱신.
- 검증된 결과를 전역 지식에 반영.
- 지식 충돌 시 최신/고신뢰 근거 우선.

#### P2 (차후 적용)
- 스키마 메타는 요청 관련 객체 중심으로 전달.
- Fact 모델은 다중 근거/출처/신뢰도 보존을 확장.

---

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

### §12.3 위험도 등급 분류

| 등급 | 대상 | 대응 |
|------|------|------|
| **Critical** | 인증/인가, 파괴적 데이터, 개인정보 | 반드시 사람 승인 |
| **Major** | 외부 비용, 롤백 어려운 마이그레이션, 보안 저하 | 사전 승인 없으면 사람 승인 |
| **Minor** | 비파괴적 스키마 추가, 내부 API 변경 | AI 자율 진행 + `REVIEW.md` 기록 |

## §13. 다중 AI 협업

### §13.1 충돌 방지 규칙

- 한 문서에 현재 상태와 변경 이력을 섞지 않는다.
- append-only 문서는 기존 항목을 의미 변경 수준으로 덮어쓰지 않는다.
- 기능 단위로 작업 범위를 쪼개고, 동시에 같은 파일을 수정해야 할 때는 상위 지침을 먼저 따르며 충돌 사실을 기록한다.
- 문서 상단 메타데이터의 `edit_policy`를 따른다.
- **프로젝트 수준 rewrite 문서**(ARCHITECTURE.md, CONVENTIONS.md 등)는 동시에 하나의 AI만 수정할 수 있다. 구조 변경이 필요하면 프로젝트 수준 `DECISIONS.md`에 제안을 기록하고 사람이 반영한다.
- **append-only 문서 동시 추가 시** 각 항목에 타임스탬프와 작업자 ID(AI 세션 또는 기능 ID)를 포함하여 자동 병합이 가능하도록 한다.
- 아래 마커를 지원한다.

```md
<!-- HUMAN-LOCKED:START -->
이 구간은 사람 명시 지시 없이는 수정 금지
<!-- HUMAN-LOCKED:END -->

<!-- AI-EDITABLE:START -->
AI가 자유롭게 갱신 가능한 영역
<!-- AI-EDITABLE:END -->
```

#### §13.1.1 다중 AI 작업 충돌 방지 (프로젝트 특화)
- `SESSION_TAG` 또는 `SESSION`을 고유값으로 분리한다.
- 확인: `make session-info`
- 단일 테스터 병렬 lane 규칙:
- `SESSION_TAG=<ai>_<lane>`
- lane 간 동일 태그 재사용 금지
- `WEB_PARALLEL_LIMIT` 초과 금지

### §13.2 작업 격리 정책

#### 단일 AI 작업 (기본)
단일 AI가 순차적으로 작업하는 경우 별도 격리 없이 §13.1의 충돌 방지 규칙을 따른다.

#### 병렬 AI 작업 (권장: Git Worktree + 2계층 브랜치)
두 개 이상의 AI가 동시에 서로 다른 기능을 작업하는 경우:

1. **내부 작업 브랜치 (로컬 전용)**: 각 AI는 별도 내부 브랜치에서 작업한다.
   - 브랜치 명명: `ai/<agent-id>/<issue-number>/<slice>`
   - 이 브랜치는 **로컬/worktree 전용**이며, GitHub PR head로 직접 사용하지 않는다.

2. **공개 PR 브랜치 (이슈당 1개)**: 외부로 push하고 PR을 여는 브랜치는 항상 `issue/<issue-number>-<short-slug>` 하나만 사용한다.
   - 내부 `ai/*` 브랜치에서 작업한 결과는 로컬에서 `issue/*` 브랜치로 통합한 뒤 push한다.

3. **Worktree 격리 (권장)**: Git worktree를 활용하여 물리적으로 작업 디렉토리를 분리한다.
   ```bash
   git worktree add ../worktrees/issue-12 -b ai/claude/12/browser-cleanup
   ```
   - 각 AI는 자신의 worktree 내에서만 파일을 수정한다.
   - 내부 브랜치 작업 완료 후 공개 `issue/*` 브랜치에 통합하고 worktree를 제거한다.

4. **공유 파일 수정 프로토콜**:
   - 프로젝트 수준 문서(STATUS.md, ARCHITECTURE.md 등)는 병합 시에만 갱신한다.
   - shared/ 코드 변경이 필요하면 REPORT.md에 기록하고 공개 `issue/*` 브랜치 통합 단계에서 합친다.
   - 동일 shared 모듈을 두 AI가 동시 수정하는 것은 금지한다.

#### 샌드박스 실행
AI가 코드를 실행(테스트, 빌드 등)할 때는 다음을 준수한다:
- 프로덕션 데이터에 접근하지 않는다.
- 네트워크 호출은 테스트 대상 또는 명시적으로 허용된 엔드포인트에만 수행한다.
- 파일 시스템 변경은 작업 디렉토리 내로 제한한다.
- 구체적 범위는 §15.2 도메인 절대 금지사항에서 프로젝트별로 정의한다.

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

- 프로젝트 루트에 `.env.example`을 두고, 모든 환경변수의 키와 설명을 유지한다.
- `.env`(실제 값)는 `.gitignore`에 포함하고 저장소에 커밋하지 않는다.
- 설정은 아래 계층 구조를 따른다 (후순위가 전순위를 오버라이드):
  1. 코드 내 기본값
  2. 공통 설정 파일 (예: `config/default.env`)
  3. 프로필별 설정 (예: `config/profiles/<profile>.env`)
  4. 환경변수 (`.env` 또는 시스템 환경)
  5. CLI 인자 / 사용자 직접 지시
- AI가 새 환경변수를 추가하면 `.env.example`에 키와 설명을 동시에 갱신한다.
- 환경변수 변경은 `MODIFY.md`에 기록하고, 의미 변경(이름 유지 + 동작 변경)은 `REVIEW.md`에 근거를 남긴다.

### §14.1 .env 정책 (프로젝트 특화)

#### 유지/필수
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `AGENT_MEMORY_DB`
- `AGENT_MODE`
- `AGENT_INSIGHT_WORKER_ENABLED`
- `AGENT_INSIGHT_WORKER_TICK_SEC`
- `AGENT_SCHEMA_INSTANCE_SCAN`
- `AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC`
- `AGENT_LLM_REQUEST_PASSTHROUGH=1`
- `AGENT_INSIGHT_ROUTE_LOG=1`

#### 제거/비권장 (충돌 항목)
- 고정 개수 기반 지식 주입/후보 제한 변수는 제거 또는 사용 중단한다.
- 예: `AGENT_KB_FACT_LIMIT`, `AGENT_GLOBAL_KB_FACT_LIMIT`, `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES`
- `planner_constraints` 계열 제약 주입 플래그는 제거한다.

#### 신규 권장 (향후 구현용)
- `AGENT_KB_COVERAGE_MODE=complete`
- `AGENT_KB_PREFETCH_ON_ASK=1`
- `AGENT_KB_PREFETCH_ON_START=1`
- `AGENT_KB_INCREMENTAL_SYNC_SEC=5`
- `AGENT_KB_REQUIRE_EVIDENCE=1`
- `AGENT_METADATA_FALLBACK_ONLY_WHEN_MISSING=1`
- `AGENT_INSIGHT_OBJECT_FASTPATH=1` (인사이트 객체 즉시 참조 활성)
- `AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH=1` (`AGENT_LLM_REQUEST_PASSTHROUGH=1`이어도 근거 기반 fast-path 허용)
- `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES=0` (고정 샘플링 제한 비활성, coverage 기반)
- `AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT=120` (한 턴에서 과도한 후보 확장 방지용 기본 상한)
- `AGENT_OBJECT_PICK_MIN_CONFIDENCE=0.55` (근거 기반 객체 선택 최소 신뢰도)
- `AGENT_OBJECT_RESOLVE_BATCH_SIZE=40` (대규모 후보군 LLM 선택 배치 크기)
- `AGENT_OBJECT_RESOLVE_MAX_BATCHES=6` (배치 선택 최대 반복 수)
- `AGENT_GENERIC_ASK_GUARD=1` (generic ask 반복 시 자동 재계획)
- `AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC=20` (선택 객체 기반 SQL 작성 LLM 타임아웃, timeout 완화)
- `AGENT_OBJECT_RESOLVE_MODEL=gpt-5-mini` (객체 선택 전용 모델 분리)
- `AGENT_SQL_COMPOSE_MODEL=gpt-5-mini` (SQL 작성 전용 모델 분리)
- `AGENT_SQL_REVIEW_MODEL=gpt-5-mini` (SQL grounding review 전용 모델 분리)
- `AGENT_SQL_GROUNDED_REVIEW=1` (선택 객체 SQL 실행 전 grounding reviewer 수행)
- `AGENT_SQL_GROUNDED_REWRITE_ON_FAIL=1` (review 실패 시 LLM 재작성 허용)
- `AGENT_SQL_GROUNDED_BLOCK_ON_FAIL=1` (review 실패 SQL 실행 차단)
- `AGENT_KNOWLEDGE_SQL_FALLBACK=1` (plan이 `ask`/메타로 수렴할 때 knowledge 근거 기반 SQL 1회 강제 생성)
- `AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC=20` (fallback LLM SQL compose 타임아웃)
- `AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES=2` (fallback에서 객체 후보 재시도 최대 횟수)
- `AGENT_AUTO_FIX_SQL=1` (syntax/not-found 오류에 대한 LLM 기반 SQL 보정 활성)
- `AGENT_DISABLE_AUTO_RETRY=0` (오류 후 자동 재시도 비활성화 금지)
- `AGENT_ERROR_AUTO_RECOVERY=1` (SCHEMA/TABLE/COLUMN not-found 자동 복구 활성)
- `AGENT_AUTO_CONTINUE_AFTER_STEP=0` (정상 결과 1회 반환 후 불필요한 자동 `continue` 루프 방지)
- `AGENT_RAG_DOC_OBJECT_SCORE_BOOST=24` (RAG 문서 FT 점수를 객체 랭킹에 반영하는 가중치)
- `AGENT_SCHEMA_USAGE_RECORD_STRICT=1` (모호 요청 결과의 `table_pref` 오염 방지)
- `AGENT_PLAN_TIMEOUT_SEC=35` (기본 플래너 타임아웃)
- `AGENT_PLAN_TIMEOUT_RECOVERY_SEC=20` (복구/재시도 단계 플래너 타임아웃)
- `AGENT_PLAN_TIMEOUT_MIN_SEC=8` (플래너 최소 타임아웃)
- `AGENT_RAG_PRIORITY_TIMEOUT_SEC=12` (RAG 우선 재플랜 타임아웃)
- `AGENT_RAG_PRIORITY_FIRST=1` (지식 근거가 있으면 기본 플래너 전에 RAG 우선 플랜 단축 경로 시도)
- `AGENT_RAG_PRIORITY_SHORT_CIRCUIT=0` (모호 follow-up에서 임의 객체 short-circuit 비활성)
- `AGENT_AUX_SKIP_NEAR_DEADLINE_MS=15000` (마감 임계치에서 summary/validation 생략)
- `AGENT_OPENAI_MAX_RETRIES=0` (플래너/요약 호출의 SDK 재시도 비활성화로 상한 시간 준수)

## §15. 도메인 커스터마이징 가이드

이 섹션은 프로젝트가 실제 도메인에 적용될 때 커스터마이징해야 할 영역을 안내한다.

### §15.1 실행 환경 고정 (WSL 강제)
- 모든 실행은 WSL(Ubuntu)에서만 수행.
- 작업 경로: 현재 디렉토리(`.`) 또는 저장소 상대경로 `./_ai_delegated_dev_template/repo`
- 시작 체크:
- `pwd`가 템플릿 실행 루트(또는 하위)
- `uname -s`가 `Linux`
- 불만족 시 즉시 WSL 전환 후 재시작.

#### WSL 전환 표준 명령
- WSL 진입 후 저장소 루트에서 `cd ./_ai_delegated_dev_template/repo && make session-info`

#### 금지 규칙
- `C:\...` 기준 실행 금지.
- Windows 인터프리터(`py.exe`, `python.exe`, `node.exe`) 실행 금지.

### §15.2 도메인 절대 금지사항

§2.3의 절대 금지 항목 참조.

### §15.3 운영 명령 (Make)
- `make start`
- `make stop`
- `make status`
- `make convo-clear`
- `make web`
- `make web-down`
- `make insight-up`
- `make insight-down`
- `make insight-status`
- `make insight-logs`
- `make mysql sql="SELECT 1;"` (사용자 명시 요청 시만)
- `make browser-up`
- `make browser-down`
- `make browser-session`
- `make browser-goto url="https://example.com"`
- `make browser-click selector="..."`
- `make browser-type selector="..." text="..."`
- `make browser-press selector="..." key="Enter"`
- `make browser-wait selector="..."`
- `make browser-text selector="..."`
- `make browser-html selector="..."`
- `make browser-shot`
- `make browser-close`

### §15.4 Docker Compose 기준
- 서비스: `mysql`, `agent`, `memory-init`, `insight-worker`, `mcp`(선택)
- MySQL: `mysql:8.0`
- 볼륨:
- `../artifacts/shared:/shared`
- `../artifacts/mysql-data:/var/lib/mysql`
- `../artifacts/mysql-backup:/shared/mysql-backup`
- `../artifacts/certs:/certs`

### §15.5 메모리/로그 운영
- `AgentMemoryFacts`, `AgentMemoryFactEntries`는 복수 근거를 보존한다.
- Fact에는 최소 `SourceRunId`, `SourceType`, `Weight/Confidence`를 보존한다.
- 지식 참조 경로 로그:
- `/shared/logs/YYYY-MM-DD/insight_route.log`
- 필수 기록: 실제 참조한 스키마/테이블/컬럼, action, reason, result, error
- `insight-worker` 는 `artifact_missing -> repair_from_fact/generate_insight -> verify_persist` 흐름을 그대로 남긴다.
- `insight_worker.log` 는 cycle 시작/종료/오류 요약만 남기고, idle heartbeat 는 남기지 않는다.
- 타이밍 로그:
- `/shared/logs/YYYY-MM-DD/timing.log`
- `/shared/logs/YYYY-MM-DD/timing_breakdown_<run_id>.json`
- 실행 SQL 로그:
- `/shared/logs/YYYY-MM-DD/*_executed_sql.log`
- 오래된 로그 보관:
- `7일` 초과 날짜 디렉토리는 `/shared/logs/archive/YYYY-MM-DD.tar.gz` 로 압축 보관한다.

### §15.6 지식 아키텍처 목표 (신규 기준)

#### 1) 완전 구축 레이어
- `AgentMemoryFactEntries`는 DB 전역 구조 지식을 누락 없이 누적한다.
- 최소 저장 단위:
- 스키마
- 테이블
- 컬럼/타입
- PK/FK/인덱스
- 대표 조인 경로
- 검증된 지표 정의(메트릭 정의)

#### 2) 요청별 근거 패키지 레이어
- `make ask` 실행마다 LLM 호출 전에 근거 패키지를 재구성한다.
- 패키지는 고정 top-k가 아니라 **coverage 기반**으로 생성한다.
- 기준:
- 요청에서 언급된 객체/동의어 포함
- 최근 성공 실행에서 사용된 객체 포함
- 도메인 앵커와 충돌하는 후보 배제 근거 포함

#### 3) 실행 피드백 레이어
- 성공 SQL/실패 SQL/복구 경로를 지식에 반영한다.
- 같은 실패 시그니처는 즉시 우회 경로를 제시한다.

#### 4) 카테고리 + Depth 라우팅 레이어 (신규)
- 인사이트 객체(`table_insight/schema_insight`)는 아래 카테고리를 구조화해 저장한다.
- `domain`, `entity_type`, `metric_family`, `event_type`, `time_grain`, `join_hints`, `confidence`
- 요청 실행 시 근거 선택은 고정 top-k가 아니라 `D0 -> D1 -> D2 -> D3` 단계로 확장한다.
- `D0`: 명시 객체/직전 확정 객체 우선
- `D1`: 스키마 앵커 범위
- `D2`: 스키마 + 도메인 카테고리 확장
- `D3`: 전체 근거 풀(최종 폴백)
- 단계 승급 사유(`ask_loop`, 재시도, 오류)는 로그에 남기고, 무관 스키마 점프를 금지한다.

### §15.7 구현 로드맵 (이후 작업계획 명시)

#### P0 (즉시)
- `agent_cli` 플래닝 경로에서 강제 분기용 `planner_constraints` 주입 제거.
- LLM 입력 `knowledge`를 요약 중심에서 근거 중심으로 전환.
- 요청 원문 보존: follow-up 재작성/임의 문자열 덧붙이기 제거.
- 메타탐색은 "근거 부족"일 때만 허용하고 사유를 로그에 강제 기록.
- `origin_request`/`domain_anchor` 보호: 메타 점검 발화는 상태를 오염시키지 않도록 차단.
- RAG fallback 게이트: 명시 객체/앵커가 없는 경우 강제 객체 집계로 점프하지 않는다.

#### P1 (우선)
- `AgentMemoryFactEntries`를 중심으로 전수 인덱싱 워커 구현.
- 인덱싱은 배치/페이지 방식으로 수행하되 최종 coverage는 100%를 목표로 한다.
- 고정 상한 대신 `incomplete_queue` 기반으로 미완료 객체 우선 처리.
- 질문 실행 전 preflight로 "요청 관련 근거 존재 여부"를 검사하고 부족 시 선동기화.

#### P2 (구조 개선)
- `reg_*` FactKey는 행수/컬럼명 나열형 텍스트 저장을 중단하고, 아래 구조화 정보로 대체:
- metric 정의(분자/분모/기간/필터)
- 조인 경로(테이블/키)
- 검증 상태(confirmed/estimated)
- 근거 SQL 시그니처
- ScopeKey는 요청 문장 기반이 아니라 `domain/schema/object/metric` 구조화 키를 우선 사용.

#### P3 (운영 안정화)
- 지식 참조 경로 추적 로그를 요청 단위로 필수화한다.
- "왜 그 객체를 선택했는지"를 점수 대신 근거 목록으로 남긴다.

### §15.8 도메인별 환경변수 정책
`.env.example`에서 관리하는 변수의 카테고리와 변경 규칙은 §14.1을 참조한다.

### §15.9 도메인별 품질 게이트
기능 완료 시 도메인 특화 검증 항목이 있으면 여기에 추가한다.

---

# Part G — 완료 및 동기화

## §16. 완료 기준 및 검증 절차

### §16.1 완료 기준

작업은 아래를 만족해야 완료로 본다.
- `make start`로 MySQL + 웹 + 브라우저 + 인사이트 워커 정상 기동.
- `make ask` 정상 동작.
- 브라우저 제어 기능 정상.
- MCP 사용 시 `make mcp-test` 통과.
- C/E/F/G 회귀 없음.
- `FUNCTION.md`가 현재 동작과 일치한다.
- `TASK.md`, `MODIFY.md`, `REVIEW.md`, `REPORT.md`, `TEST.md`가 필요한 수준으로 갱신되었다.
- `ANCHOR.md` §1~§3이 작성되었다 (24h bootstrap grace 이후).
- `ANCHOR.md` §4 human 검증 로그는 일반 TASK cycle 완료 조건이 아니며, release/milestone 검토 또는 방향 전환 검증이 필요할 때만 요구된다 (§18 참조).
- 남은 리스크와 후속 작업이 `REPORT.md`에 정리되었다.
- `/repo/docs/STATUS.md`에 기능 상태가 반영되었다.
- `/repo/docs/CODEBASE_MAP.md`에 새 파일/모듈이 반영되었다 (해당 시).

### §16.2 작업자 준수 체크 (시작 전/종료 전)
- 시작 전: "이번 변경이 정확도/맥락/지식 중 무엇을 개선하는지" 1줄로 남긴다.
- 종료 전: "실제 데이터 결과가 출력되는지" 확인한다.
- 종료 전: "동일 도메인 재요청에서 불필요한 메타탐색이 줄었는지" 확인한다.

### §16.3 테스트 조건
- 기존 테스트와 약간 다른 노이즈를 포함한다.
- 단순/일반/복잡 조건을 모두 포함한다.

### §16.4 완료 선언 (Completion Checklist)

AI가 작업 완료를 선언할 때는 `TASK.md`의 Completion Checklist를 명시적으로 체크한다:

```md
## 7. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 자동 테스트가 통과한다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] ANCHOR.md §1~§3이 채워져 있다 (또는 24h bootstrap grace 범위 내이다) (§18)
- [ ] `bin/verify-completion.sh --pre-commit <feature-id>`가 PASS한다 (§16.5)
- [ ] Git 커밋이 완료되었다 (§16.5)
- [ ] Git 원격 동기화가 완료되었다 또는 동기화 불가 사유가 기록되었다 (§16.5)
```

### §16.5 Git 동기화 절차 (verify-completion 기반)

작업 완료 선언 전에 AI는 반드시 `bin/verify-completion.sh`를 호출한다.
이 스크립트가 완료 체크리스트 검증 + ANCHOR.md 게이트 + unstaged 잔여 검사를 흡수한다.
AGENTS.md §1 AI 전권 위임 원칙에 부합한다 — 스크립트는 **AI가 호출하는 도구**이지
인간 개입이 아니다.

**기본 원칙: AI 작업자는 완료 가능한 cycle을 사용자 확인 대기로 멈추지 않는다.**
pre-commit 검증이 PASS하고 BLOCKED/Critical/Major 승인 대기 항목이 없으면 AI가
직접 commit한다. 원격 저장소가 설정되어 있고 공개 브랜치 push가 가능하면 AI가
직접 push/PR 갱신까지 수행한다. `commit/push 결정은 사용자에게 위임` 같은 응답은
정책 위반이다.

커밋 메시지 형식은 `CONTRIBUTING.md`의 커밋 규칙 섹션을 따른다.

#### Step 0: 완료 선언 정의

"완료 선언"이란 AI가 사용자에게 "작업 완료" 메시지를 전달하기 직전의 지점이다.
이 시점 이전에 working tree는 정리된 상태여야 한다.

#### Step 1: 사전 검증 (pre-commit)

```
1. 코드 + docs 변경 (working tree)
2. ANCHOR.md §1~§3 확인 — §4 human 검증 로그는 release/milestone 또는 방향 전환 검증 시에만 확인 (§18 참조)
3. git add <변경된 모든 파일> (prefer named add, never -A)
4. bash bin/verify-completion.sh --pre-commit <feature-id>
   → FAIL: stderr의 누락 항목 해결 후 step 1로 복귀
   → PASS: step 2로 진행
```

#### Step 2: 커밋

필수 trailer:

```
<type>(<scope>): <summary>

<body>

Task-Cycle: <feature-id>
```

`Task-Cycle` trailer는 이 커밋이 어느 TASK cycle에 속하는지 명시한다
(§18 Cycle Boundary). 이 trailer가 없는 commit은 post-commit hook의 verify 대상이 아니다.

```bash
1. `git status`로 변경 파일을 확인한다.
2. `.gitignore` 대상(`.env`, 자격증명 등)이 포함되지 않았는지 검증한다.
3. 코드와 문서를 같은 커밋에 포함한다.
4. 커밋 메시지 규칙에 따라 커밋한다 (Task-Cycle trailer 필수).
```

#### Step 3: 사후 검증 (post-commit)

`.git/hooks/post-commit`이 자동으로 `verify-completion.sh --post-commit <feature-id>`
를 호출한다 (`bin/install-hooks.sh`가 설치). FAIL 시:
- hook은 commit을 차단하지 않는다 (이미 발생). 경고만 출력.
- AI는 출력을 읽고 **새 commit**으로 누락 항목을 수정한다. `git commit --amend` **금지**.

#### Step 4: 원격 동기화 판정

원격 저장소(`origin`)가 설정되어 있는 경우, 아래 조건표에 따라 동기화 범위를 판정한다.

| 조건 | 동작 |
|------|------|
| BLOCKED 항목 없음 + Critical/Major 승인 대기 없음 | **AI가 commit 후 공개 브랜치 동기화** (Step 5 진행) |
| BLOCKED 항목 있음 또는 Critical/Major 승인 대기 | **AI가 commit만** 수행, push/PR 보류 사유를 `REPORT.md`에 기록 |
| 원격 저장소 미설정 | **커밋만** 수행, 원격 설정은 사람에게 위임 |

#### Step 5: 공개 브랜치 동기화 (조건 충족 시)

Step 4에서 공개 브랜치 동기화로 판정된 경우:

1. **공개 브랜치 규칙 확인**:
   - 외부로 push하는 브랜치는 반드시 `issue/<issue-number>-<short-slug>` 형식을 따라야 한다.
   - 현재 브랜치가 내부 `ai/<agent-id>/<issue-number>/<slice>` 브랜치라면, 로컬에서 공개 `issue/*` 브랜치에 먼저 통합한다.

2. **Push**: 현재 공개 브랜치를 원격에 push한다.
   ```bash
   git push origin <current-branch>
   ```

3. **PR 생성 또는 갱신**:
   - 공개 브랜치에 대한 PR이 없으면 생성한다.
   - 이미 있으면 동일 PR을 갱신한다.
   - PR 제목은 `#<issue-number> <summary>` 형식을 사용하고, 본문에는 반드시 `closes #<issue-number>`를 포함한다.

4. **병합**:
   - 병합은 GitHub PR 흐름으로 진행한다 (사람 검토 + `gh pr merge`).
   - `main` 직접 push 또는 로컬 `main` 병합은 금지한다.
   - 브랜치 동기화 중 충돌이 발생하면 §16.6 정책에 따라 처리한다.

#### Step 6: 결과 기록

Git 동기화 결과를 `REPORT.md`에 기록한다.

```md
### Git 동기화 결과
- 커밋: <commit-hash> (<branch>)
- verify-completion: PASS / FAIL (재시도 N회)
- Push: 완료 / 보류 (사유: ...)
- PR: 생성 / 갱신 / 보류 (사유: ...)
- 병합 상태: 머지 완료 / 수동 검토 / 보류
- 충돌 해결: 없음 / AI 자율 해결 (건수, 요약) / 사람 위임 (사유)
```

#### SPOF 대응 (bypass 금지)

`verify-completion.sh`는 모든 commit의 gate이며 bypass 경로를 제공하지 않는다
(SPOF 복구는 §18.4 "운영 vs 메타 층위" 참조).

#### 완료 응답 금지 패턴

AI 작업자는 완료 가능한 cycle에서 아래 응답으로 작업을 멈추면 안 된다.

- `자동 commit/push는 하지 않았습니다`
- `commit 결정은 사용자에게 위임합니다`
- `push 여부를 확인해 주세요`

허용되는 예외는 다음뿐이다:

- `verify-completion` FAIL 또는 테스트 FAIL이 남아 있고 AI가 같은 cycle 안에서 복구할 수 없음
- `BLOCKED` 항목 또는 Critical/Major 승인 대기가 `REPORT.md`에 기록됨
- 원격 저장소가 없거나 인증/권한 문제로 push가 기술적으로 불가능함
- 사용자가 명시적으로 "commit/push 하지 말라"고 지시함

예외가 아니면 AI는 §16.5에 따라 commit하고, 가능한 경우 push/PR 갱신까지 완료한 뒤
결과를 `REPORT.md`와 최종 응답에 기록한다.

### §16.6 병합 충돌 해결 정책

공개 `issue/*` 브랜치를 `origin/main`에 맞춰 동기화하거나, 내부 `ai/*` 브랜치를 공개 `issue/*` 브랜치에 통합하는 과정에서 충돌이 발생할 수 있다.
충돌 발생 시 AI는 아래 분류 기준에 따라 자율 해결 또는 사람 위임을 판정한다.
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
  │    └─ 공개 issue/* 브랜치 동기화 계속 (push / PR 갱신)
  │
  ├─ 하나라도 모호 포함 → 부분 해결 + 사람 위임
  │    ├─ git merge --abort 또는 rebase --abort (통합 중단)
  │    ├─ REPORT.md에 BLOCKED: merge-conflict-needs-review 기록
  │    │    ├─ AI 해결 가능 항목 목록
  │    │    ├─ 사람 판단 필요 항목 + 양쪽 내용 요약
  │    │    └─ AI의 권장 해결 방향 (참고용)
  │    └─ 사람 검토 후 재시도
  │
  └─ 판단 불가 → 전체 사람 위임
       ├─ git merge --abort 또는 rebase --abort
       └─ REPORT.md에 BLOCKED: merge-conflict 기록
```

#### 자율 해결 시 커밋 메시지

```
refactor(project): 공개 브랜치 동기화 충돌 해결 (#<issue-number>)

- <파일1>: <충돌 유형> — <해결 방법>
- <파일2>: <충돌 유형> — <해결 방법>
```

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
- `.github/**` (CI/CD 워크플로 + 자동화 스크립트 + 정책 contract — 운영 코드와 분리된 인프라)

#### META 작업 워크플로

META 작업도 일반 feature와 동일한 8-doc + ANCHOR.md 구조에 편입된다.
형식: `unit/META-NNNN-<name>/`.
**`[META]` commit prefix는 지원하지 않는다** — path convention만 유효 게이트.

#### Pure-meta commit의 verify skip

변경 파일이 **전부** META 경로면 `verify-completion.sh`가 "META mode" 진입하여
모든 검사를 skip한다. 템플릿 자체 유지 작업에 필수 경로.

**Mixed commit (META + operational)**은 operational로 취급되어 full gate를 거친다.
이로써 AI가 operational 작업에 META 경로를 끼워 우회하는 패턴이 차단된다.

#### SPOF 복구

`verify-completion.sh` 자체에 버그가 발생해 모든 feature 작업이 차단되면,
AI는 META mode로 자동 진입하여 스크립트를 수정한다. bypass env var는 존재하지 않는다.

### §18.5 TASK Cycle 정의 (§4 엔트리 경계)

"TASK cycle"은 하나의 TASK 수명 기간이다. cycle 시작은 아래 중 **나중의** commit:

- `Task-Cycle: <feature-id>` trailer를 가진 가장 이른 commit (이 feature에 대해)
- 해당 TASK의 첫 TASK.md 수정 commit
- (migration day 이후라면) `anchor-migrate.sh`가 생성한 seed commit

§4 엔트리가 이 범위 내에 ≥ 1개 있어야 `verify-completion.sh` check #7이 PASS한다.
단, 24h bootstrap grace 적용 시 check #7은 skip된다.

### §18.6 §4 엔트리 품질 gate

각 엔트리 필수 필드:

- `source: human:<name>` — 유일 허용 형식
- `timestamp:` — ISO8601
- `body:` — 실제 내용 ≥ 200자 (non-whitespace)
- `challenge:` — 한 줄, 이 검증이 무엇을 반박하거나 확인했는지

단순 confirmation(`"pass"`, `"looks good"` 등 단독)은 FAIL로 처리한다.

### §18.7 Bootstrap grace (24h)

새로 생성된 `ANCHOR.md`는 `created_at` 기준 24시간 이내면 §1~§3 빈칸 검사와
§4 엔트리 수 검사가 skip된다. 이 유예 시간 안에 작성자가 §1~§3를 채우고
최초 §4 엔트리를 추가한다.

`created_at`은 frontmatter 값과 git log first-add timestamp 중 **더 이른 쪽**을
canonical로 사용한다 (frontmatter 조작 방지).

### Codex command compatibility

- Codex command 원본은 repo-local `.codex/commands/_template/*.md` 이다.
- Codex skill wrapper 는 `.codex/skills/_template-*/SKILL.md` 에 둔다.
- Repo-local marketplace/plugin 원본은 `.agents/plugins/marketplace.json` 과
  `plugins/ai-delegated-dev-template/` 이다.
- `~/.codex` 와 Codex plugin cache 는 설치/링크 대상일 뿐 source of truth 가 아니다.
- Exact intent 는 계속 `/_template:<skill>` 로 기록하고, Codex surface 가 이를 거부하면
  `_template-<skill>` fallback prompt alias 를 사용한다.

### Codex copy-base skill discovery

- 현재 확인된 Codex skill 호출 표면은 `$<skill-name>` 이다.
- `_template` skill 자동완성은 Codex 가 시작된 workspace 에서 `.codex/skills` 를
  발견할 수 있어야 동작한다.
- copy-base 를 파일 복사로 전달하면 symlink 가 누락될 수 있다. 첫 AI 작업자는
  skill 이 없다고 판단하기 전에 wrapper 위치에서 다음을 먼저 실행한다:

  ```bash
  bash repo/bin/codex-template-install.sh --check
  bash repo/bin/codex-template-install.sh --link
  bash repo/bin/codex-template-install.sh --check
  ```

- 이미 `/repo` 안에서 작업 중이면 `bash bin/codex-template-install.sh --check` 를
  사용한다. `--link` 가 플랫폼 정책상 실패하면 Codex 를 `/repo` 에서 시작하고,
  wrapper-level 자동완성 제한을 작업 로그에 명시한다.

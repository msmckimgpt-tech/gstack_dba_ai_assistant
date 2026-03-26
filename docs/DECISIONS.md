---
doc_type: PROJECT_DECISIONS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
---

# Project Decisions

## ADR-0001
- Status: accepted
- Date: 2026-03-25
- Context: 여러 AI와 사람이 동시에 작업할 때 현재 상태와 이력 문서가 섞여 혼란이 발생하기 쉬움
- Decision: 현재 상태 문서와 변경 이력 문서를 분리한다
- Consequences:
  - `FUNCTION.md`, `TASK.md`, `REPORT.md`는 현재 상태를 유지한다
  - `MODIFY.md`, `REVIEW.md`, `DECISIONS.md`는 append-only를 기본으로 한다

## ADR-0002
- Status: accepted
- Date: 2026-03-25
- Context: 에이전트별 정책 파일이 중복되면 지침 충돌이 발생할 수 있음
- Decision: `AGENTS.md`를 정본으로 하고 `CLAUDE.md`는 참조용으로 유지한다
- Consequences:
  - 저장소 수준 정책의 단일 기준점이 생긴다
  - 호환성은 유지하되 정책 중복을 줄인다

## ADR-0003
- Status: accepted
- Date: 2026-03-26
- Context: FIRST_REQUEST.md가 AGENTS.md 내용을 거의 그대로 재서술하여 "중복된 source of truth" 위반 발생
- Decision: FIRST_REQUEST.md를 부트스트랩 진입점 전용으로 축소하고, 신규 기능 시작 / 기존 작업 이어받기 두 시나리오를 분리한다
- Consequences:
  - 정책 내용은 AGENTS.md에만 존재
  - 새 AI는 시나리오에 따라 명확한 온보딩 경로를 가짐

## ADR-0004
- Status: accepted
- Date: 2026-03-26
- Context: "전권 위임" 목표와 §11 승인 필요 항목 간 구조적 모순이 존재
- Decision: 비동기 블로킹 흐름(BLOCKED 상태) + 사전 승인 범위(Pre-approved Scope) + 위험도 등급 분류(Critical/Major/Minor)를 도입한다
- Consequences:
  - AI가 승인 필요 항목에 도달해도 다른 태스크를 계속 진행 가능
  - 사전 승인 범위를 FUNCTION.md에서 기능별로 선언 가능
  - Minor 등급은 AI 자율 진행, Critical은 반드시 사람 승인

## ADR-0005
- Status: accepted
- Date: 2026-03-26
- Context: TASK.md가 source_of_truth: false로 되어 있어 작업 진행 상태의 정본이 모호
- Decision: TASK.md를 작업 진행 상태의 source of truth로 격상한다 (source_of_truth: true)
- Consequences:
  - 새 AI가 현재 진행 상황을 TASK.md에서 확인할 수 있음
  - 완료 체크리스트 섹션을 추가하여 완료 선언 절차를 명확화

## ADR-0006
- Status: accepted
- Date: 2026-03-26
- Context: TEST.md의 edit_policy가 rewrite여서 이전 테스트 실행 결과가 매번 덮어씌워짐
- Decision: TEST.md를 혼합 정책으로 변경 — 케이스 정의(§1, §2)는 rewrite, 실행 결과 이력(§3)은 append-only
- Consequences:
  - 회귀 발생 여부를 과거 테스트 결과와 비교하여 판별 가능
  - 테스트 결과 이력이 보존됨

## ADR-0007
- Status: accepted
- Date: 2026-03-26
- Context: §4 충돌 해석 원칙에서 "상위 문서 우선"과 "구체적 문서 우선"이 병존하여 AI 해석 오류 가능성
- Decision: "상위 문서 우선"을 주 규칙으로 확정하고, "구체적 문서 우선"은 같은 계층 내에서만 적용
- Consequences:
  - AGENTS.md(상위)와 기능 AGENTS.md(하위) 충돌 시 상위 우선이 명확
  - 같은 우선순위 수준에서만 구체성 원칙 적용

## ADR-0008
- Status: accepted
- Date: 2026-03-26
- Context: append-only 문서가 무한 증가하면 AI 컨텍스트 윈도우 소진 위험
- Decision: 20건 초과 시 아카이빙 정책을 도입한다 (_archive/ 디렉토리 사용)
- Consequences:
  - 현행 파일에는 최근 항목만 유지
  - 아카이브 참조 링크로 전체 이력 접근 가능

## ADR-0009
- Status: accepted
- Date: 2026-03-26
- Context: shared/ 디렉토리의 소유권, 변경 절차, 문서 구조가 없어 다중 AI 충돌 위험
- Decision: shared/에 README.md(거버넌스)와 MODIFY.md(변경 이력)를 두고, 변경 시 교차 참조 규칙을 적용한다
- Consequences:
  - shared 변경의 영향 범위를 역참조로 파악 가능
  - 대규모 변경은 별도 unit으로 관리

## ADR-0010
- Status: accepted
- Date: 2026-03-26
- Context: 프로젝트 전체 현황을 한눈에 볼 수 있는 문서가 부재하여 신규 AI의 전체 파악이 어려움
- Decision: `docs/STATUS.md`를 추가하여 기능별 상태, 의존성, 블로킹 항목, 전체 진행률을 관리한다
- Consequences:
  - 신규 AI가 하나의 문서로 프로젝트 전체 상황 파악 가능
  - 각 기능의 REPORT.md로부터 파생하여 갱신

## ADR-0011
- Status: accepted
- Date: 2026-03-26
- Context: `.gitignore`에 `../../artifacts/*` 같은 상위 디렉토리 패턴을 둘 수 없었음
- Decision: artifacts가 repo 외부에 있으므로 .gitignore에서 artifacts 관련 규칙을 제거한다
- Consequences:
  - .gitignore가 실제로 동작하는 규칙만 포함
  - artifacts는 repo 외부이므로 git 추적 대상이 아님

## ADR-0012
- Status: accepted
- Date: 2026-03-26
- Context: 기존 `mysql_ai`는 루트 중심 구조였고, 템플릿은 기능 단위 구조를 요구함
- Decision: 루트는 실행 진입점만 유지하고, 실제 구현은 `unit/<feature-id>/src`로 재배치한다
- Consequences:
  - 기능별 소유권이 명확해진다
  - compose/Makefile/Dockerfile은 새 경로만 참조해야 한다

## ADR-0013
- Status: accepted
- Date: 2026-03-26
- Context: 원본 프로젝트의 `shared/`는 런타임 데이터와 버전관리 자산이 섞여 있었음
- Decision: 런타임 데이터는 `../../artifacts`로 분리하고, `../shared/`는 공용 코드 예약 영역으로 제한한다
- Consequences:
  - 코드 저장소와 런타임 산출물 경계가 분리된다
  - 로그/세션/데이터 파일이 버전관리 대상에서 제외된다

## ADR-0014
- Status: accepted
- Date: 2026-03-26
- Context: 템플릿 이관 과정에서 `repo/.env` 값과 `repo/AGENTS.md` 의미가 원본 루트 프로젝트와 어긋나 포트, 모델, 운영 규칙 정합성이 깨졌음
- Decision: `repo/.env`는 원본 루트 `.env`의 운영 의미를 최대한 보존하고, `repo/AGENTS.md`는 원본 루트 지침을 템플릿 실행 루트 기준으로만 최소 변환한 정본으로 유지한다
- Consequences:
  - 템플릿 사본은 구조만 분리되고 운영 의미는 원본과 일치한다
  - `repo/.env.example`는 대체 기본값이 아니라 민감값 제거 샘플로 취급한다
  - 템플릿 사본은 원본과 동시 기동하지 않는 단독 실행 전제를 문서로 고정한다

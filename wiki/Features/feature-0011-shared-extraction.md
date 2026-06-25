---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: stub
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
feature_id: feature-0011-shared-extraction
linked_unit: unit/feature-0011-shared-extraction
created: 2026-06-24
sources:
  - ../../unit/feature-0011-shared-extraction/docs/FUNCTION.md
---

# Feature — 공통 코드 `shared/` 추출

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0011-shared-extraction/docs/FUNCTION|unit/feature-0011-shared-extraction/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0002(agent-core)·feature-0003(web-ui)·격리 컨테이너가 공유하는 저결합 공통 코드를 repo 루트 `shared/` Python 패키지로 **점진 추출**하는 라이브 제품 구조 리팩터 (P5).

## 2. 상태

- **단계**: stub / in-progress — P5a Step 1~3 완료(`model_catalog`·`config`·`db`), Step 4~6 후속.
- **마지막 갱신**: 2026-06-24
- **AI 작업자**: claude / Human (TASK-0011, PLAN-APPROVED 2026-06-24)

## 3. 책임 경계

- **입력**: 기존 `modules/` 공통 모듈 + import 사이트(agent_core·app.py·modules/llm·테스트) + Dockerfile/Makefile PYTHONPATH.
- **출력**: repo 루트 `shared/` 패키지(`__init__.py` + 이동된 모듈) + `modules/X` → `shared/X` **모듈 alias shim**(비파괴 재노출).
- **side-effect**: 없음(동작 무변경 리팩터). 모든 심볼·monkeypatch·wildcard·재노출 체인을 동일 객체로 보존, `make test` 회귀 0 게이트.

## 4. 관련 정본

- [[../../unit/feature-0011-shared-extraction/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0011-shared-extraction/docs/TASK|TASK.md]] — 작업 큐 (active)
- [[../../unit/feature-0011-shared-extraction/docs/REPORT|REPORT.md]] — 진행 요약
- [[../../unit/feature-0011-shared-extraction/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference

## 5. 관련 노트

- [[feature-0002-agent-core]] — 공통 모듈 출발지(import 재배선 대상)
- [[feature-0003-agent-web-ui]] — 공통 모듈 소비처(app.py import 재배선 대상)
- [[../../docs/DOC_REGISTRY|DOC_REGISTRY.md]] — `shared/` = 공통 코드 정본(경계 = 디렉토리)

## 6. Open questions / 미해결

- P5a Step 4: L1 cross-feature 공통(`conn_health`·`datasources`) 이동 + `db` lazy back-dep 정리.
- Step 5: import 점진 마이그레이션 + alias shim 제거.
- Step 6: feature 단위 Dockerfile 분리 + 브라우저 QA. (app.py router 분할은 P5b 별도 cycle.)

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0011-shared-extraction/docs/MODIFY.md` 에.

- 2026-06-24: 초안 작성 (feature 신규 생성 동반 — P5a Step 1~3 머지 반영).

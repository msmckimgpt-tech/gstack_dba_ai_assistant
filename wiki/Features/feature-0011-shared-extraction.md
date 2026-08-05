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
maturity: substantial
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

feature-0002(agent-core)·feature-0003(web-ui)·격리 컨테이너가 공유하는 저결합 공통 코드를 repo 루트 `shared/` Python 패키지로 **점진 추출**한 라이브 제품 구조 리팩터 (ssot-consolidation ROADMAP **ITEM-P5a done** — 2026-08-05 종결).

## 2. 상태

- **단계**: substantial / **완결** — Step 1~5 완료(`shared/` 5모듈 `model_catalog`·`config`·`db`·
  `conn_health`·`datasources` 추출 + 소비처 429 ref 마이그레이션 + alias shim 4개 전부 제거,
  make test 회귀 0) · Step 6(feature 단위 Dockerfile 분리)은 **불채택 종결**.
- **마지막 갱신**: 2026-08-05
- **AI 작업자**: claude / Human (TASK-0011, PLAN-APPROVED 2026-06-24 · 종결 결정 ADR-20260805T153000)

## 3. 책임 경계

- **입력**: 기존 `modules/` 공통 모듈 + import 사이트(agent_core·app.py·modules/llm·테스트) + Dockerfile/Makefile PYTHONPATH.
- **출력**: repo 루트 `shared/` 패키지(`__init__.py` + 이동된 5모듈 `model_catalog`·`config`·`db`·`conn_health`·`datasources`). 이동 중 비파괴 재노출에 쓰인 `modules/X` → `shared/X` **모듈 alias shim 4개는 Step 5 에서 전부 제거**됐고, 이제 소비처는 `shared.*` 정본 경로만 쓴다.
- **side-effect**: 없음(동작 무변경 리팩터). 모든 심볼·monkeypatch·wildcard·재노출 체인을 동일 객체로 보존, `make test` 회귀 0 게이트.

## 4. 관련 정본

- [[../../unit/feature-0011-shared-extraction/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0011-shared-extraction/docs/TASK|TASK.md]] — 작업 큐 (active)
- [[../../unit/feature-0011-shared-extraction/docs/REPORT|REPORT.md]] — 진행 요약
- [[../../unit/feature-0011-shared-extraction/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference
- [[../../docs/DECISIONS|docs/DECISIONS.md]] — `ADR-20260805T153000-p5a-closeout` (Step 6 불채택 · 미결정 #4 보존 · env 키 정본)

## 5. 관련 노트

- [[feature-0002-agent-core]] — 공통 모듈 출발지(import 재배선 대상)
- [[feature-0003-agent-web-ui]] — 공통 모듈 소비처(app.py import 재배선 대상)
- [[../../docs/DOC_REGISTRY|DOC_REGISTRY.md]] — `shared/` = 공통 코드 정본(경계 = 디렉토리)

## 6. Open questions / 미해결

- (해소) Step 4 L1 공통(`conn_health`·`datasources`) 이동 · Step 5 import 마이그레이션 + alias shim 제거 — 2026-06-25 완료.
- (종결) Step 6 feature 단위 Dockerfile 분리 — **불채택**(단일 이미지 유지): 분리 전제였던 import 얽힘·경계 불명은 `shared/` 추출 + CODEBASE_MAP §7 로 해소됐고, 이후 배포 스파인(0014/0020/0039)이 단일 이미지 전제로 안정화됐다(ADR-20260805T153000). **재개 조건**: 이미지 크기·보안 요구가 실측으로 등장할 때 별도 initiative.
- (보존 확정) `attachment_reconciliation` 0002판은 GDPR 용도 **미배선 보존**(dedup·합치기 금지, 파일 헤더 라벨 + CODEBASE_MAP §7) · 주기 env 키 정본은 `ATTACHMENT_RECON_INTERVAL_SEC`.
- 잔여 미해결: 없음 (P5a 전 단계 종결 — TASK §7).

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0011-shared-extraction/docs/MODIFY.md` 에.

- 2026-06-24: 초안 작성 (feature 신규 생성 동반 — P5a Step 1~3 머지 반영).
- 2026-08-06 (doc_sync): 08-05 P5a 종결 반영 — Step 6 Dockerfile 분리 불채택 · 미결정 #4(GDPR 미배선 보존) 확정 · env 키 정본(ADR-20260805T153000-p5a-closeout) + P3-제외 로드맵 100% 검증 실증(wiki sources 백필 기완료 · skeleton 라벨 기해소 · pb0008 통합 불채택). §2 'Step 4~6 후속' · §3 'alias shim' · §6 미해결 3건 stale 정정. 요지+포인터만(SSOT) — 정본 TASK §1/§3/§7 · REPORT §1/§2 · REVIEW REV-20260805T153000/T160500 · MODIFY CHG-20260805T153000/T160500.

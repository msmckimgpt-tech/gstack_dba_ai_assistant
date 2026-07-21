---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.39.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0022-agent-scratch-workspace
linked_unit: unit/feature-0022-agent-scratch-workspace
sources:
  - ../../unit/feature-0022-agent-scratch-workspace/docs/FUNCTION.md
---

# Feature — Agent PG Scratch Workspace

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0022-agent-scratch-workspace/docs/FUNCTION|FUNCTION.md]].

## 1. 한 줄 요약

assistant 가 PG 전용 낙서장 DB(`agent_scratch`)에서 대화별로 격리된 테이블을 자율적으로 만들고,
여러 외부 데이터소스 데이터를 반입해 PG 안에서 cross-source JOIN 을 수행하며, 설정된 TTL(기본
24h) 주기로 임시데이터를 자동 정리하는 기능.

## 2. 상태

- **단계**: substantial (백엔드 코어 완료·테스트 통과·회귀 0, 기본 OFF)
- **마지막 갱신**: 2026-07-21
- **AI 작업자**: claude / feature-0022 cycle

## 3. 책임 경계

- 입력: `scratch_import(sql, dest_table[, datasource])`, `scratch_sql(sql)`, `scratch_list`,
  `scratch_reset` (assistant 도구) + 활성 대화 id.
- 출력: `agent_scratch` DB 안 대화별 스키마 `s_<hash>` 의 반입/파생 테이블 + 도구 결과 텍스트.
- side-effect: 전용 role 로 PG DDL/DML(sandbox 한정); TTL reaper 의 `DROP SCHEMA CASCADE`.

## 4. 관련 정본

- [[../../unit/feature-0022-agent-scratch-workspace/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0022-agent-scratch-workspace/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0022-agent-scratch-workspace/docs/DECISIONS|DECISIONS.md]] — ADR-SCRATCH-0001~0004
- [[../../unit/feature-0022-agent-scratch-workspace/docs/ANCHOR|ANCHOR.md]] — 방향성 앵커

## 5. 관련 노트

- 코드 거주: feature-0002(코어·도구·워커·bootstrap), shared(config·db·runtime_settings).
- 선례 재사용: feature-0021 agent-notes TTL reaper, ADR-0021/0024 PG 분리·별 DB.

## 6. Open questions / 미해결

- 활성화(bootstrap+enable)는 운영자 결정. 라이브 e2e·격리 실증은 deferred.
- 관리 콘솔 작업공간 관측 UI 후속.

## 7. 변경 이력 (이 카드)

- 2026-07-21 — 신규 (feature-0022 초기 구현).

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

- **단계**: substantial (백엔드 코어 완료·테스트 통과·회귀 0, 기본 OFF · 2026-08-14 대화 분기 이월 + 매-턴 작업공간 상태 주입 라이브 실증)
- **마지막 갱신**: 2026-08-14
- **AI 작업자**: claude / feature-0022 cycle

## 3. 책임 경계

- 입력: `scratch_import(sql, dest_table[, datasource])`, `scratch_sql(sql)`, `scratch_list`,
  `scratch_reset` (assistant 도구) + 활성 대화 id.
- 출력: `agent_scratch` DB 안 대화별 스키마 `s_<hash>` 의 반입/파생 테이블 + 도구 결과 텍스트.
- side-effect: 전용 role 로 PG DDL/DML(sandbox 한정); TTL reaper 의 `DROP SCHEMA CASCADE`.

## 4. 관련 정본

- [[../../unit/feature-0022-agent-scratch-workspace/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0022-agent-scratch-workspace/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0022-agent-scratch-workspace/docs/DECISIONS|DECISIONS.md]] — ADR-SCRATCH-0001~0005
- [[../../unit/feature-0022-agent-scratch-workspace/docs/ANCHOR|ANCHOR.md]] — 방향성 앵커

## 5. 관련 노트

- 코드 거주: feature-0002(코어·도구·워커·bootstrap·`modules/scratch.py`), feature-0003
  (`routers/_conv_store.py` 분기 훅 · `routers/share.py` 감사, 2026-08-14 추가),
  shared(config·db·runtime_settings).
- 선례 재사용: feature-0021 agent-notes TTL reaper, ADR-0021/0024 PG 분리·별 DB.

## 6. Open questions / 미해결

- 활성화(bootstrap+enable)는 운영자 결정. 라이브 e2e·격리 실증은 deferred.
- 관리 콘솔 작업공간 관측 UI 후속.

## 7. 변경 이력 (이 카드)

- 2026-07-21 — 신규 (feature-0022 초기 구현).
- 2026-08-17 (doc_sync): **대화 분기 시 작업공간 이월 + 매 턴 작업공간 상태 주입**(2026-08-14,
  `3c37bf52` → 라이브 실증 `456b83d9`) 반영. 대화 분기 3 경로(사본 만들기·앵커 분기·**공유 링크
  복제**)가 문맥은 복사하면서 작업공간은 이월하지 않아 assistant 가 **문맥에만 남은 유령 테이블**을
  참조해 답변 품질이 떨어졌다. `modules/scratch.py::clone_workspace()` 신설 — 원본 대화 스키마
  테이블을 분기본 스키마로 **CTAS 독립 복사**, 캡 3종(테이블 수·총 행수·시간 예산) + 부분 성공
  보고 + fail-soft(예외 미전파), 원본이 비면 분기본 스키마를 만들지 않는다(전역 캡 미소모).
  `routers/_conv_store.py::_fork_conversation_impl` 에 3 경로 공통 이월 훅을 두고 응답에
  `scratch_cloned`/`scratch_truncated` 를 노출한다. 같은 cycle 이 `agent_core.
  _scratch_workspace_state_note()` 로 **매 턴 실재 테이블 목록을 문맥보다 우선하는 사실로 주입**해
  (빈 작업공간은 EMPTY + 재반입 유도 · 조회 실패는 침묵) **TTL 만료로 작업공간만 사라진 대화 재개**
  경로까지 같은 축으로 동시에 차단했다. 이월 범위는 **전 분기 경로(교차계정·부분 구간 포함)** 로
  확정 — 사용자 결정: "공유 링크 생성 자체가 권한의 수동적 상승이며 링크를 만든 대화 소유자의
  책임". 추적성은 `routers/share.py` 의 `share.fork` 감사에 `scratch_tables_copied`(건수만)를
  실어 교차계정 이월 forensics 로 보완한다. `AGENT_SCRATCH_FORK_CARRYOVER`/`MAX_CLONE_ROWS`/
  `FORK_BUDGET_MS` 스펙 · **ADR-SCRATCH-0005** · 단위 38 PASS(이월·상태 주입 13건 추가) ·
  라이브 실증(배포 `db5d469b`: PG 실권한 이월 7행 CTAS · 실 사용자 duplicate API
  `scratch_cloned=1` · 분기본에서 이월 테이블 조회 성공 · 상태 주입 문구 2분기(실재 목록 / EMPTY) ·
  검증 잔재 전량 정리). 정본 `docs/DECISIONS.md` ADR-SCRATCH-0005 · `docs/TEST.md §5.4`.

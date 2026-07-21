---
doc_type: REPORT
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 현재 상태 (2026-07-21)
백엔드 코어 구현 완료 + 단위 테스트 통과 + 회귀 0. **기본 OFF**(운영자 bootstrap+enable 전엔
런타임 동작 불변). 라이브 활성화·e2e 는 deferred(TASK-0009~0011).

## 구현 요약
- **PG 격리 경계**: `bin/scratch-pg-bootstrap.sh` + `agent_scratch_schema.sql` 이 별도 DB
  `agent_scratch` + 전용 role `agent_scratch_rw`(NOSUPERUSER 등) 생성. CONNECT 는 이 DB 로만,
  다른 DB 무-grant → KB/runtime/web/datasource 물리 격리(ADR-SCRATCH-0001).
- **대화별 스키마**: `scratch.schema_for()`=`s_<sha1[:24]>`. `_scratch_admin.schema_registry`
  가 last_used_at 로 TTL 추적(ADR-SCRATCH-0002).
- **도구 4종**(feature-0002 tools.py): `scratch_import`(execute_sql 신뢰경계 재사용→materialize),
  `scratch_sql`(scratch guard + search_path pin + statement_timeout), `scratch_list`,
  `scratch_reset`. agent_core 가 활성 시에만 노출(with_scratch_tools) + 대화 ContextVar set/reset.
- **TTL reaper**: ask-worker 주기 훅이 `scratch.sweep_expired_schemas()` 호출(feature-0021
  agent-notes 선례 재사용).
- **런타임 설정**: `AGENT_SCRATCH_*` 7종(shared/runtime_settings.py).

## 검증
- 단위 테스트 `test_scratch.py` 15건 PASS(guard 보안·타입추론·스키마명·enabled 게이트).
- 회귀: feature-0002 전체 RC=0, feature-0003 전체 RC=0(기존 agent 이미지 마운트 pytest).
- 적대적 보안 리뷰(§18.8): REVIEW.md 참조.

## 잔여 / 다음
- 운영자: bootstrap 실행 + `.env` 자격 + 콘솔에서 `AGENT_SCRATCH_ENABLED=1`.
- 라이브 e2e(반입→JOIN→TTL DROP·대화 격리) + (후속) 관리 콘솔 관측 UI.

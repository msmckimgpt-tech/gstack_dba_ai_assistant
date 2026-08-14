---
doc_type: REPORT
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 현재 상태 (2026-08-14)
라이브 활성 운영 중. 이번 cycle 에서 **대화 분기 시 작업공간 유실**(사용자 보고) 을 구조적으로
해소했다 — 분기 시 이월(독립 복사) + 작업공간 실제 상태의 매-턴 프롬프트 주입.

### 이번 cycle: 분기 이월 (ADR-SCRATCH-0005)
- **결함**: 분기 3 경로가 표시 메시지·LLM 문맥·첨부는 이월하면서 작업공간만 빠뜨렸다. 스키마 키가
  `s_<sha1(conversation_id)>` 라 새 대화 id = 빈 작업공간인데, 문맥은 복사되므로 assistant 가
  "테이블 a·b 를 만들었다"는 자기 기록을 믿고 없는 테이블을 참조하다 실패했다.
- **수정**: (1) `clone_workspace` 로 원본 테이블을 분기본 스키마에 CTAS 독립 복사(캡·시간 예산·
  부분 성공 보고·fail-soft). (2) 분기 3 경로 공통 훅(`_fork_conversation_impl`). (3) 교차계정 fork
  이월 건수를 `share.fork` 감사에 기록. (4) **매 턴 실재 테이블 목록 주입** — 이월 상한 초과분·
  이월 실패·**TTL 만료**까지 포함해 "문맥엔 있는데 실물은 없는" 어긋남 일반을 차단.
- **이월 범위 = 전 경로 (사용자 결정)**: 교차계정(공유 링크 fork)·부분 구간 분기도 이월. AI 초안은
  동일계정+전체분기로 제한하는 fail-closed 안이었으나, 사용자가 "공유 링크 생성 자체가 권한의
  수동적 상승이며 링크를 만든 소유자의 책임" 으로 판단. 추적성은 감사 기록으로 보완, 운영자
  차단 스위치(`AGENT_SCRATCH_FORK_CARRYOVER=0`) 보존.
- **검증**: 단위 13건 신규(전건 PASS, 총 38) + 전체 회귀 + **라이브 실증 완료**(배포 db5d469b) —
  PG 실권한 이월(7행 CTAS) · 실 사용자 `duplicate` API `scratch_cloned=1` · 분기본에서 이월 테이블
  조회 성공 · 상태 주입 문구 2분기(실재 목록 / EMPTY) 확인 · 검증 잔재 전량 정리. TEST.md §5.4.

## 이전 상태 (2026-07-21)
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

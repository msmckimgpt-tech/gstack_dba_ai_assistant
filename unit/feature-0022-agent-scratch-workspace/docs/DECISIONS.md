---
doc_type: DECISIONS
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Decisions

## ADR-SCRATCH-0001 — 전용 DB `agent_scratch` + 전용 role 로 "완전 자율"을 격리 (2026-07-21)
- **결정**: assistant 의 PG 자율 작업공간을 기존 `agent_kb` 안 스키마가 아니라 **별도 database
  `agent_scratch` + 전용 login role `agent_scratch_rw`** 로 둔다.
- **근거**: 사용자가 "이 구조에 대한 접근 권한은 완전 자율"을 명시. 완전 자율 DDL/DML 을 안전하게
  담으려면 PG 의 **database-level 격리**가 가장 강한 경계다. 별 DB + CONNECT 를 그 DB 로만 부여 +
  다른 DB 에 무-grant → role grant 누출·search_path 사고에도 KB/runtime/web 에 도달 불가.
  ADR-0021/0024(KB 분리·별 DB) 패턴과 정합.
- **role 속성**: NOSUPERUSER·NOCREATEDB·NOCREATEROLE·NOREPLICATION·NOBYPASSRLS. `agent_scratch`
  안에서는 스키마/테이블 CREATE·DROP·CRUD 자유(완전 자율). `dblink`/`postgres_fdw`/파일 함수는
  superuser 부재로 자연 실패 + scratch guard 가 앱-레이어에서도 차단(defense-in-depth).
- **결과**: `agent_scratch` 는 alembic(agent_kb 대상) 밖 → 전용 `bin/scratch-pg-bootstrap.sh` 로 관리.

## ADR-SCRATCH-0002 — 대화별 스키마 격리 (2026-07-21)
- **결정**: 반입/생성 데이터는 대화별 스키마 `s_<sha1(conversation_id)[:24]>` 아래 둔다.
- **근거**: 반입은 datasource 의 read-only 게이트(allowlist·DB-단위·공유 [from,to] window RBAC)를
  통과한 데이터를 PG 로 옮긴다. 전역 공유 작업공간이면 대화 A 가 볼 수 없어야 할 데이터를 대화 B 가
  같은 테이블에서 읽어 **가시성 격리가 깨진다**. 대화별 스키마 + search_path pin + scratch guard 의
  cross-schema 차단으로 격리를 materialization 후에도 보존.
- **대안**: 전역 공유(단순하나 다중 사용자·공유 대화에서 누출) — 기각.
- **잔여 위험(적대 리뷰 반영, accepted with mitigation)**: 모든 `s_*` 스키마는 동일 role
  `agent_scratch_rw` 가 소유 → **PG 레벨 대화 격리는 없음**. 격리는 `scratch_guard`(allowlist)
  + search_path pin 이 강제한다. 초기 구현의 denylist guard 는 (a) `CREATE FUNCTION` 문자열
  본문에 cross-schema 참조 은닉 (b) `pg_catalog` 무자격 참조로 타 대화 메타데이터 열거 두 우회가
  발견돼(feature-0021 적대 리뷰 BLOCK/HIGH), guard 를 **allowlist 로 반전**(허용 root 명시 +
  CREATE/DROP 은 TABLE/INDEX kind 만 + 테이블명 `pg_` 접두·함수 `pg_` 접두 차단)해 봉인했다.
- **후속(권장)**: 대화별 전용 PG role + `s_*` 스키마 USAGE 를 그 role 에만 부여해 **PG 레벨**
  대화 격리로 승격(소프트웨어 guard 에 격리를 의존하지 않도록). TASK-0013 로 이월.

## ADR-SCRATCH-0003 — governed 반입(execute_sql 신뢰경계 재사용) (2026-07-21)
- **결정**: `scratch_import` 는 새 데이터 접근 경로를 만들지 않는다. 반입 SELECT 는 `execute_sql`
  과 **동일한** sql_guard(단일 SELECT/CTE·금지스키마·금지함수) + `_freeform_sql_access_error`
  (제품 allowlist·무자격·cross-DB) 게이트를 통과한 뒤에만 실행·적재된다.
- **근거**: "이미 SELECT 가능하던 데이터"만 반입 가능 → 데이터 유출 표면 증가 0. 반입 데이터는
  기존 execute_sql 결과와 동일하게 untrusted(프롬프트 인젝션 datamarking 계층 적용).

## ADR-SCRATCH-0004 — 시간기반 TTL reaper(기본 24h·기본 OFF 활성 게이트) (2026-07-21)
- **결정**: 삭제 주기는 `_scratch_admin.schema_registry.last_used_at` 기준 시간 TTL(런타임
  `AGENT_SCRATCH_TTL_HOURS`, 기본 24h)로, ask-worker 주기 reaper 가 `DROP SCHEMA CASCADE`.
  기능 자체는 `AGENT_SCRATCH_ENABLED` 기본 0(OFF) — bootstrap+enable 전엔 도구 미노출.
- **근거**: 사용자가 "설정된 임시데이터 삭제 주기에 따라 비워지도록"을 명시 → 런타임 조정 가능한
  TTL. feature-0021 agent-notes TTL reaper 선례 재사용(동일 ask-worker 훅). 기본 OFF 는 Critical
  쓰기 경로가 병합·배포만으로 활성화되지 않도록 하는 안전 기본값(feature-0010 scaffold 패턴).
- **대안**: 대화 종료 감지 시 즉시 삭제(감지 로직 추가 필요·idle 정의 모호) — 시간 TTL 우선, 필요 시
  후속으로 종료-트리거 추가.

## ADR-SCRATCH-0005 — 대화 분기(fork) 시 작업공간 이월 + 실제 상태 프롬프트 주입 (2026-08-14)
- **문제**: 대화 분기 3 경로(사본 만들기 `POST /api/conversations/{cid}/duplicate` · 앵커 분기
  `POST /api/fork_conversation` · 공유 링크 복제 `share.fork`)는 모두 `_fork_conversation_impl`
  을 타며 표시 메시지·**LLM 문맥(core_messages)**·첨부(blob 독립 복사 + sandbox 재적재)까지
  이월했으나 **scratch 작업공간만 이월 대상이 아니었다**. 스키마 키가 `s_<sha1(conversation_id)>`
  라 새 대화 id 를 받는 순간 작업공간이 빈다. 그런데 문맥은 복사되므로 assistant 는 "테이블
  a·b 를 반입해 JOIN 했다"는 **자기 기록을 그대로 읽고 없는 테이블을 참조**하다 실패 →
  재작업·답변 품질 저하(사용자 보고, 2026-08-14).
- **결정 (1) 이월 = 독립 복사**: `scratch.clone_workspace(src_cid, dst_cid)` 가 원본 스키마의
  테이블을 분기본 스키마로 `CREATE TABLE ... AS SELECT ... LIMIT n` 복사한다. 조상 스키마를
  **공유하지 않는다** — 첨부 fork 가 이미 채택한 "조상 sandbox 공유 금지" 원칙과 동형이며,
  공유 시 원본의 이후 변경·TTL DROP 이 분기본을 깨뜨린다. 인덱스·제약은 옮기지 않는다(작업공간
  테이블은 분석용 중간 산출물이고, 제약 재현 실패가 이월 전체를 깨는 편이 더 나쁘다).
- **결정 (2) 전 분기 경로 이월 (사용자 결정)**: 교차계정(공유 링크 fork)·부분 구간 분기도
  이월한다. AI 초안은 "동일계정 + 전체 분기" 로 제한(교차계정은 원본 소유자 datasource 권한으로
  반입된 데이터라 권한 상승 소지)하는 fail-closed 안이었으나, 사용자가 **"공유 링크 기능 자체가
  사실상 권한의 수동적 상승과 유사하며 이는 링크를 생성한 대화 소유자의 책임"** 으로 판단해
  전 경로 이월로 결정했다. 추적성 보완: 교차계정 fork 의 이월 **건수**를 `share.fork` 감사
  기록(`scratch_tables_copied`)에 남긴다(기존 `attachments_copied`·`core_messages_copied` 와
  동일한 forensics 원칙 — 건수만, 내용 비노출). 운영자 전역 차단 스위치
  `AGENT_SCRATCH_FORK_CARRYOVER=0` 을 남겨 정책 변경 여지를 보존한다.
- **결정 (3) 실제 상태 주입이 근본 해소**: 이월만으로는 부족하다 — 이월 상한 초과분, 이월 실패,
  그리고 **TTL 만료**(24h 뒤 같은 대화 재개 시 작업공간만 사라짐)에서 같은 "문맥엔 있는데 실물은
  없는" 어긋남이 재현되기 때문이다. 그래서 scratch 활성 대화의 매 턴 시스템 프롬프트에
  `_scratch_workspace_state_note(cid)` 로 **실재하는 테이블 목록**을 "문맥 기록보다 우선하는
  사실" 로 주입한다. 비었으면 "EMPTY + 재반입하라" 를 명시한다. 조회 실패 시에는 아무 말도 하지
  않는다(빈 문자열) — 조회 실패를 "비어 있음" 으로 오도하면 assistant 가 멀쩡한 테이블을 버리고
  다시 반입한다.
- **캡·fail-soft**: 이월은 테이블 수(`MAX_TABLES_PER_CONV`)·총 행수(`MAX_CLONE_ROWS`, 기본 20만)·
  문당 timeout·전체 wall-clock 예산(`FORK_BUDGET_MS`, 기본 10s)으로 제한하고, 초과·실패는
  `truncated`/`skipped_detail` 로 드러낸다(조용한 절단 금지). 이월 실패는 **예외를 올리지 않는다**
  — 작업공간은 보조물이라 이월 실패가 분기 자체(대화·문맥·첨부)를 막아선 안 된다(첨부 복사의
  fail-open 정책과 동일).
- **대안**: (a) 조상 스키마 read 공유 — 격리가 `scratch_guard` allowlist 에 의존하는 현 구조에서
  cross-schema 참조를 열어야 해 ADR-SCRATCH-0001 격리 경계를 훼손. 불채택. (b) 이월 없이 신호만 —
  "맥락 보존" 요구를 절반만 충족(직전 작업 결과가 사라짐). 불채택. (c) lazy clone-on-first-use —
  비용은 낮으나 분기 시점의 권한 컨텍스트를 agent 측에 넘길 마커 인프라(스키마 변경)가 필요해
  복잡도 대비 이득이 적다. 불채택.

---
doc_type: WIKI_HOT_CACHE
scope: project
status: active
edit_policy: rewrite
source_of_truth: false
template_version: v3.13.2
domain: [wiki, session-context]
ai_read_priority: 9
wiki_role: hot_cache
wiki_name: project
confidence: high
maturity: active
ai_generated: true
---

# Hot Cache

> `/_template:entry` 가 세션 시작 시 **가장 먼저** 읽는 파일 (Phase 2 §2.6 Tier 1).
> 직전 세션의 컨텍스트를 ≤500자로 압축해 저장한다.
> 매 세션 종료 시 (Phase 6.5) AI 가 자동 갱신. 사람이 직접 편집 가능.

## 목차

- [Last Updated](#last-updated)
- [Key Recent Facts](#key-recent-facts)
- [Recent Changes](#recent-changes)
- [Active Threads](#active-threads)

## Last Updated

`2026-05-28T15:50:00Z` — T1~T5 로드맵 + PgBouncer/Replica 전체 활성화 완료

## Key Recent Facts

- T1~T5 + 후속 활성화 **전체 완수**: DISTINCT ON/ANY/MV/JSONB/PgBouncer/replica/advisory-lock/kb_invalidations
- `AGENT_KB_PG_HOST=pgbouncer` 활성화 (transaction-mode pool, md5 auth via pg_hba.conf 172.18.0.10/32)
- `postgres-replica` 기동: streaming async 복제 중 (sent_lsn = replay_lsn)
- `AGENT_KB_PG_HOST_RO=postgres-replica` + `AGENT_KB_PG_USER_RO=agent_kb_ro` 활성화 — RO 읽기 replica 라우팅
- `agent_kb_rw` 비밀번호 md5 형식으로 재설정 (pgbouncer md5 ↔ pg_authid 정합)
- docker-compose.yml 수정: `postgres-replica` max_connections=100, `postgres-replica-init` entrypoint list 형식 수정

## Recent Changes

- `.env`: `AGENT_KB_PG_HOST=pgbouncer` + RO 환경변수 블록 추가
- `docker-compose.yml`: replica max_connections 50→100, entrypoint YAML list 형식 수정
- `pg_hba.conf`: `host all all 172.18.0.10/32 md5` 추가 (pgbouncer 전용)
- `pg_hba.conf`: `host replication all all scram-sha-256` 추가 (replica 초기화용)
- `agent_kb_rw` 비밀번호: scram→md5 형식 변환 (pgbouncer userlist 정합)

## Active Threads

- HNSW 전환 (ADR-0024 후보) — 100K+ row 이후 ivfflat → hnsw ALTER 검토
- `REFRESH MATERIALIZED VIEW CONCURRENTLY agent_memory_facts` 주기적 실행 연동 미완 (cron 또는 fact write hook 추가 필요)
- pg_hba.conf 변경사항은 컨테이너 재생성 시 초기화됨 — schema SQL에 반영 필요

---

`#wiki/hot-cache` · `#status/active`

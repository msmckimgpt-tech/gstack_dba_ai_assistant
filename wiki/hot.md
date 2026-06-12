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

`2026-06-12` — wiki 정합 갱신 (2026-05-28 → 2026-06-12 drift 해소)

## Key Recent Facts

- **멀티 데이터소스 시대 (2026-06)**: 단일 MySQL → MySQL·MSSQL N개. dialect 추상화 + envelope 암호화 registry(KEK/DEK) + DB-단위 접근 (TASK-0187/0205/0206/0219, 배포·라이브검증).
- storage Postgres 단일화 완료 (KB Phase 1 + runtime Phase 2, 2026-05-27).
- 관리 콘솔 성숙: 대시보드 위젯/CloudWatch(0210/0218), LLM 사용량(0163~0202), insight 완료율(0223/0242).
- ask-worker out-of-process 큐 cutover (TASK-0169). 요청 중단·재요청(0241).

## Recent Changes

- wiki: ADR-0027~0030 mirror 신규, concept 6종(multi-datasource·datasource-registry·db-level-access·datasource-aware-rag·insight-worker·ask-worker-queue), entities/mssql 신규.
- feature-0002/0003 카드·Architecture 3종·overview·Index 멀티 데이터소스 반영. feature 7→8(feature-0008).

## Active Threads

- 멀티 데이터소스 Stage 2 MSSQL 전면 / P2 UI.
- 메인 loop tier 라우팅 부재(edge/auto, claude만).
- Phase 3 web* 18 테이블 Postgres 이관 미진행.

---

`#wiki/hot-cache` · `#status/active`

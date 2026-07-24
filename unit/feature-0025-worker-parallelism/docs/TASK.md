---
doc_type: TASK
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (구현 완료·검증 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-24

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** shared/runtime_settings.py · unit/feature-0002-agent-core/src/modules/{ask,node_analysis,semantic_cluster,insight}.py · docker-compose.yml · unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html} · unit/feature-0002-agent-core/tests/test_worker_parallelism.py
- **접근 방법:** feature-0018 runtime-settings 레지스트리에 `performance` 그룹(10 knob) 추가 →
  워커 루프의 직렬 지점을 concurrency 분기(기본 1=byte-동치, LLM 만 스레드 병렬·DB 직렬)로 배선 →
  페이싱/배치 knob 을 get_int live 소비로 전환 → 인프라 여력(pgbouncer/PG 상향) → admin '성능·병렬' 서브탭.
- **위험도:** Major (additive·기본 현행동치·admin RBAC·clamp 방어; 운영자가 값 상향 시 pgbouncer/LLM 부하 실증 필요)

<!-- PLAN-APPROVED by mckim on 2026-07-24 (AskUserQuestion: "전체 + 인프라 여력" 선택) -->

## 3. Task Queue
- [x] TASK-0001 워커 동시성 아키텍처 조사(insight/ask, 병렬화 여지·자원 제약)
- [x] TASK-0002 runtime_settings performance 그룹 + serialize_registry 버킷 + accessor
- [x] TASK-0003 node_analysis process_pending 병렬화(LLM 병렬·DB 직렬, conc==1 byte-동치)
- [x] TASK-0004 semantic_cluster cluster_label 배치 LLM 병렬화
- [x] TASK-0005 ask-worker N executor 스레드(전용 conn) + coordinator 유지보수
- [x] TASK-0006 페이싱/배치 knob live 배선(insight tick·cluster interval·sig_batch·embedding·idle-poll)
- [x] TASK-0007 인프라 여력: pgbouncer 풀·PG max_connections 상향 + anchor env baseline
- [x] TASK-0008 admin UI '성능·병렬 처리' 서브탭(admin.html nav/panel + admin.js render/dirty)
- [x] TASK-0009 단위 테스트(test_worker_parallelism) + 기존 스위트 회귀 검증
- [ ] TASK-0010 §18.8 적대 리뷰 패널 반영(REVIEW.md)
- [ ] TASK-0011 verify-completion PASS + commit
- [ ] TASK-0012 배포 후 PB-0008 라이브 검증(설정 UI 렌더·override 반영·워커 재시작 동시성)

## 4. In Progress
- §18.8 리뷰 반영 + verify-completion.

## 5. Blocked
- 없음

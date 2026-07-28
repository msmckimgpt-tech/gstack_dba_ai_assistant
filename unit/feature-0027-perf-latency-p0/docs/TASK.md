---
doc_type: TASK
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-28
feature_status_note: P0 성능 개선 1차 — post-answer 큐레이션(topic/용어/ENUM LLM 3건) terminal 후 이동(체감 -25~35s)·grounding RO 단일연결·MySQL 버퍼풀 128MB→1G·Caddy gzip+immutable static (feature-0026 측정 근거, 품질 무영향 축만)
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude, 사용자 자율 위임 2026-07-28)
- Priority: high
- Last Updated: 2026-07-28

## 2. Implementation Plan

### 2.1 Plan (§7.1)
- **영향 파일/symbol:** `agent_core.py`(_run_agent_core 패키지 조립·done 후 호출·
  `run_post_answer_curation` 신설·`_build_knowledge_context` 공유 RO conn),
  `modules/ask.py`(_execute_job finalize 후 호출), `feature-0001 .../99-mysql-ai-server.cnf`
  (buffer pool 1G), `feature-0006 .../Caddyfile`(encode+header), `bin/perf-snapshot.sh`(§3c 캡션),
  테스트 `test_post_answer_curation.py`(신규 3).
- **접근:** 실행 내용 불변·시점만 이동(A — worker 한정, §18.8 패널 흡수) / 연결 공유(D) / 설정 상향(C) / 엣지 압축·캐시(E).
  전부 가역적(설정 revert·순서 revert). 품질 영향 축(레드팀·thinking)은 배제.
- **완료 판정:** AC-1~4 + 라이브 검증(terminal 후 큐레이션 로그 순서·버퍼풀 1G·gzip 응답 헤더·
  immutable 헤더) + before/after 실측 기록.
- **위험도:** Minor~Major 경계 (비파괴·가역·인가/스키마 무변경; 핫패스 순서 변경이라 §18.8
  패널 backend+qa 2렌즈 필수). 사용자 명시 자율 위임 하 진행.

## 3. Task Queue
- [x] TASK-20260728T010001-p0-a post-answer 큐레이션 이연 — worker=job terminal 후 / in-process=종전 순서 유지 (§18.8 backend B2 반영)
- [x] TASK-20260728T010002-p0-d grounding 공유 RO 연결
- [x] TASK-20260728T010003-p0-c MySQL 버퍼풀 1G (cnf; 라이브 SET GLOBAL 은 배포 단계)
- [x] TASK-20260728T010004-p0-e Caddy encode(SSE 제외 allowlist)+immutable(stamp 쿼리 매처) — adapt PASS
- [ ] TASK-20260728T010005-p0-verify 테스트·패널·verify-completion·머지·배포·전/후 실측

## 7. Completion Checklist
- [ ] 모든 REQ 의 AC 구현 + 라이브 검증
- [ ] 자동 테스트 통과 (make test, COMPOSE_PROJECT_NAME=repo)
- [x] UI 표면 없음 — PB-0008 비대상 (정적/템플릿/HTML 변경 0 — Caddy 헤더/압축은 전송 계층)
- [ ] MODIFY/REVIEW/REPORT/TEST 갱신 + verify-completion PASS + 머지/배포

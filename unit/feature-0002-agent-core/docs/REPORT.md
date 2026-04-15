---
doc_type: REPORT
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
agent 코어를 feature 구조로 이관했고, 새 Dockerfile과 루트 실행 파일이 이 경로를 참조하도록 바꿨다.

## 2. Progress
- Planned: 0
- In Progress: 테스트 데이터 로드, 엄격한 질의 검증 기준 정리
- Done: 소스 이관, Docker 경로 재구성, LLM 게이트웨이 연결 검증 완료

## 3. Recent Changes
- 코어 Python 소스를 `unit/feature-0002-agent-core/src`로 이동
- agent 이미지 Dockerfile 추가
- 2026-04-06: LLM 게이트웨이(local-llm-gateway) 연결 성공, `make ask` 동작 확인
- 2026-04-15: 외부 `llm-shared` 계약을 유지한 채 Ollama 기반 `local-llm-gateway`와 alias 모델(`auto`, `edge`, `core`, `code`) 기동 경로 복구
- 총 변경 횟수: 3

## 4. Open Issues
- 테스트 DB(gunzgame, account_db 등)가 아직 로드되지 않음 — TestDataDB.sql 복사 필요
- 구조/기동 외의 질의 정확도 검증은 아직 미완료다.

## 5. Test Status
- 자동 테스트: `tests/test_llm_api.py` 이관 완료, 실행 미기록
- 수동 테스트: `make ask q="현재 데이터베이스 목록을 보여줘"` 성공 (2026-04-15, local-llm-gateway 연결 상태)
- 미검증 항목: 엄격한 도메인 시나리오 (테스트 데이터 로드 후 진행 예정)

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 질의 정확도 평가 기준 확정

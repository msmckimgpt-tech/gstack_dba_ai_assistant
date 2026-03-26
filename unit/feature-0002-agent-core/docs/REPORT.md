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
- In Progress: 엄격한 질의 검증 기준 정리
- Done: 소스 이관, Docker 경로 재구성

## 3. Recent Changes
- 코어 Python 소스를 `unit/feature-0002-agent-core/src`로 이동
- agent 이미지 Dockerfile 추가
- 총 변경 횟수: 1

## 4. Open Issues
- 구조/기동 외의 질의 정확도 검증은 아직 미완료다.

## 5. Test Status
- 자동 테스트: `tests/test_llm_api.py` 이관 완료, 실행 미기록
- 수동 테스트: `make ask` 구조 검증 예정
- 미검증 항목: 엄격한 도메인 시나리오

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 질의 정확도 평가 기준 확정

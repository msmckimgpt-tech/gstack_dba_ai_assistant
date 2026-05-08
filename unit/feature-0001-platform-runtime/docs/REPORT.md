---
doc_type: REPORT
feature_id: feature-0001-platform-runtime
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
운영 자산을 기능 단위 구조로 이관했고, 런타임 산출물은 `../../../../artifacts`로 분리했다.

## 2. Progress
- Planned: 0
- In Progress: 엄격한 검증 시나리오 정의
- Done: 설정 파일/SQL 유틸리티 이관, 루트 경로 반영, 내장 Local LLM bootstrap 제거

## 3. Recent Changes
- MySQL/DAB 설정을 feature 경로로 이동
- SQL 유틸리티를 버전관리 대상 자산으로 정리
- 2026-04-15: 현재 repo가 소유하던 `src/local-llm/init_ollama_models.sh`를 제거해 MySQL runtime 경계를 복구
- 총 변경 횟수: 2

## 4. Open Issues
- 운영 검증 기준이 아직 구조/기동 수준에 머물러 있다.

## 5. Test Status
- 자동 테스트: 미구성
- 수동 테스트: 루트 기동 검증 예정
- 미검증 항목: 엄격한 운영 시나리오

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 추후 운영 검증 시나리오 기준 확정

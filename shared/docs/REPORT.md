---
doc_type: SHARED_REPORT
scope: shared
status: active
edit_policy: rewrite
source_of_truth: true
---

# shared/ Report

<!--
shared 모듈의 현재 상태 스냅샷.
기능별 REPORT.md와는 다른 관심사: cross-feature 영향, 의존성 그래프, 최근 변경 요약.

rewrite 정책: 최신 상태만 유지. 변경 이력은 shared/docs/MODIFY.md에서 관리.
-->

## 1. 현재 상태
- 활성 모듈: (목록 — shared 하위 디렉토리별)
- 최근 변경: (가장 최근 CHG-ID from MODIFY.md)
- 영향 받는 기능: (의존 feature-id 목록)

## 2. 의존성 맵
- `shared/<module-name>/`:
  - 의존하는 기능: feature-xxxx, feature-yyyy
  - 외부 의존성: (라이브러리, 서비스)

## 3. 알려진 이슈 / 리스크
- (현재 알려진 buf, 레이스 컨디션, 성능 이슈)

## 4. Cross-feature 참조
- 변경 시 알림 필요: (feature별 REPORT.md 경로)

## CHG-20260907T181510-kb-external-search
- Date: 2026-09-07
- Changed By: feature-0002-agent-core (Codex), 단일 mutator.
- Files: shared/config.py
- Summary: normalize_kb_embedding_model로 철거된 titan-embed/bge-m3/ollama 별칭을 빈 값으로
  정규화하여 제거된 제공자로의 쿼리/백필 호출을 차단한다. 명시적인 기타 제공자 값은 재지정하지
  않는다. 새 외부 API를 추가하지 않으며 기존 Claude/Codex가 문자 검색 후보의 의미를 판단한다.
- Affected Features: feature-0002-agent-core, feature-0003-agent-web-ui.
- Verification: core의 retired-model LLM/worker-DB tripwire 포함 최종203 PASS.
- Cross-ref: unit/feature-0002-agent-core/docs/REPORT.md REPORT-20260907T181510-kb-external-search.

---
doc_type: TEST
feature_id: feature-0019-message-editing
status: active
edit_policy: mixed
source_of_truth: true
---

# Test — 메시지 편집

## 1. 테스트 전략
- 단위: 코어 로더/쓰기 primitive 브랜치 라우팅(DB 없이 fake cursor) — 최고 blast-radius 가드.
- 통합(남은 pass): 편집 authz IDOR·@assistant 잠금·브랜치 전환·window 합성(라이브 DB).
- 시각검증(남은 pass): PB-0008 실 Windows 브라우저 — 편집·재답변·`< n/m >` 페이징
  (visual_verification_scope: always).

## 2. Run 기록

### Run 2026-07-13 — 단위테스트 (checkpoint 1)
- Command: `PYTHONPATH=<wt>:<wt>/unit/feature-0002-agent-core/src python3 -m pytest
  tests/test_message_branching.py -q`
- Environment: 로컬(agent 이미지 미기동 — fake cursor, DB 불요)
- Result: **11 passed**
- 커버:
  - AC-ME-2 비분기 항등성: `load_core_messages`(active_leaf 없음)=`_PG_LOAD_CORE_MESSAGES`,
    windowed=`_PG_LOAD_CORE_MESSAGES_WINDOWED`; `save_core_message`(브랜치 인자 없음)=
    `_PG_INSERT_CORE_MESSAGE` (byte-identical 경로).
  - 브랜치: use_branch → active-path CTE(`_PG_LOAD_CORE_MESSAGES_BRANCH`); window 술어 합성;
    null-leaf(첫 메시지 편집 전이) → CTE empty-anchor.
  - 게이트 상태 파싱; pre-migration(42703) fail-safe 기본값.

## 3. 남은 테스트 (Phase 1)
- [ ] 통합: reanswer → 새 sibling + 재답변 + 옛 브랜치 보존; 브랜치 전환 후 recall/history 정합.
- [ ] IDOR: 타인 메시지 편집 4xx; 그룹 @assistant 메시지 편집 4xx.
- [ ] window 합성: windowed 멤버 + 브랜치 동시 — 가려진 구간 미노출(fail-closed).
- [ ] PB-0008 라이브 시각검증.

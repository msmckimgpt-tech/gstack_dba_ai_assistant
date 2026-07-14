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

### Run 2026-07-14 — 엔드포인트+프론트 (checkpoint 3)
- Command: `make test` (agent 컨테이너, --no-deps) + 컨테이너 route-parity 재실행.
- Result: **브랜치 15 PASS + route_parity PASS**(golden 207 routes 갱신 후). app import OK
  (신규 엔드포인트·브랜치 헬퍼·app.py import 배선 성공). ruff PASS.
- 정적 게이트: `gen-routemap.py --check` up-to-date(신규 2 route 등재) · `codenav-lint.sh` OK.
- **잔여 4 실패 = pre-existing local-env**(routine_dbanalysis·runtime_settings·item11_batch8·
  runtime_settings_api): backend-only cycle(feature-0003 무변경)에서도 동일 실패 → 본 변경 무관.
  CI 는 이들 통과(PR #766 backend cycle 에서 CI green 실증) — local 컨테이너 env 특이.
- §18.8 적대적 보안 리뷰: REVIEW.md 참조.

## 3. 남은 테스트 (Phase 1)
- [ ] PB-0008 라이브 시각검증(편집·재답변·`< n/m >` 페이징 — 배포 후).
- [x] IDOR/authz: 서버 게이트(본인 소유·user 메시지·그룹 차단·conversation_id 스코프) — 보안 리뷰.
- [x] 비분기 항등성·active-path·window 합성 — 백엔드 단위 15 PASS.

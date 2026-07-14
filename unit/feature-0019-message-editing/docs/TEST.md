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

### Run 2026-07-14 — PB-0008 실 Windows 브라우저 라이브 시각검증 (Phase 1 완료 게이트)
- Environment: **Windows-browser** (`bin/win-browser.py` relay @ Chrome 150, https://localhost/).
- 배포: web-a/web-b + ask-worker/insight-worker = 브랜치 백엔드(마이그 0041 적용) + hotfix(파라미터 캐스팅).
- 검증 시나리오 (bootstrap_admin, 1:1 대화 "SQL 파일 변경점 비교"):
  1. **편집 버튼**: user 말풍선에 '수정' 버튼 3개 렌더 확인(`.message-edit-trigger`). ✅
  2. **인라인 편집 UI**: 수정 클릭 → 편집 박스 + 원본 프리필 + [요청사항 수정(재답변) / 단순 수정 /
     취소] 3버튼 렌더. 스크린샷 `/tmp/pb0008-edit-ui2.png`. ✅
  3. **reanswer 브랜치**: 텍스트 수정 → 요청사항 수정 → 새 답변 생성 + 버전 페이저 `‹ 2 / 2 ›`.
     DB: 1069(원본)+1070(원답변)=옛 브랜치 / 1121(편집,parent=1068)+1122(새 답변)=새 브랜치, 형제
     parent 공유. 스크린샷 `/tmp/pb0008-pager-2of2.png`. ✅
  4. **페이징 정합**: `‹` 클릭 → `1 / 2` 전환 + 마지막 답변이 원본으로 정합 복원(하위 출력 정합). ✅
- **POST-DEPLOY 결함 적발 + 수정**: 첫 reanswer 무응답 → ask-worker 로그 진단 → `_PG_LOAD_CORE_
  MESSAGES_BRANCH` 비-windowed 타입추론 실패(`could not determine data type of parameter $3`) →
  명시 캐스팅 hotfix(PR #774) → 워커 재배포 → 재검증 PASS. (단위테스트 mock cursor 가 못 잡는
  SQL 유효성 결함 — visual_verification_scope: always 정책 가치 실증.)
- Result: **Phase 1 PB-0008 PASS** (편집·재답변·페이징 라이브 정상).

## 3. 남은 테스트 (Phase 2 — 그룹/공유)
- [ ] PB-0008 라이브: 그룹 대화에서 본인 메시지 단순 수정('편집됨' 배지) + @assistant 호출 메시지
  편집 버튼 미노출 + 타 멤버 메시지 편집 버튼 미노출.
- [x] 서수 매핑 그룹 이벤트 제외(__event__) — REV #5 수정.
- [ ] 그룹 sender IDOR·@assistant 잠금·window 정합 — §18.8 Phase 2 보안 리뷰(REVIEW.md).

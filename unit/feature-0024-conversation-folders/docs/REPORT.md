---
doc_type: REPORT
feature_id: feature-xxxx-template
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
현재 기능 상태를 한눈에 파악할 수 있도록 짧게 정리한다.

## 2. Progress
- Planned:
- In Progress:
- Done:

## 3. Recent Changes
- 최근 반영된 변경사항 요약
- 총 변경 횟수: 0

## 4. Open Issues
- 남아 있는 문제
- 확인이 필요한 항목

## 5. Test Status
- 자동 테스트:
- 수동 테스트:
- 미검증 항목:

## 6. Blocked Items
<!-- 승인 대기 또는 불명확성으로 차단된 항목 -->
- 없음

## 7. Human Attention Needed
- 사람 판단 또는 승인이 필요한 항목

## 8. Suggested Improvements
<!-- AI가 작업 중 발견한 개선 기회를 기록한다 (§8.1 개선 제안 정책) -->
<!-- 제안은 기록만 하며, 사용자 지시 없이 실행하지 않는다 -->
- 없음

## 2026-08-13 — 공유받은 그룹 대화 폴더 DnD 개방 (folder-dnd-shared-group)

사용자 요청으로 **다른 계정이 공유한 그룹 대화(내가 멤버)도 사이드바 drag&drop 으로 폴더별 이동**이
된다. 원인은 프론트 draggable 게이트만 소유자로 좁혀져 있던 것(폴더 파티션·'···' 메뉴 '이동'·백엔드는
이미 멤버 허용) — `isFolderScopedConversation`(owner || is_member) 하나로 파티션과 게이트를 통일했다.
백엔드·스키마·권한 변경 0, 배정은 기존 계정별 row 그대로라 소유자·타 멤버 뷰 불변.

- 코드/테스트 거주: feature-0003-agent-web-ui (`src/static/app/sidebar.js`,
  `tests/verify_folder_dnd_shared_group.mjs` 31 PASS). 상세 = 동 feature TASK/MODIFY/REVIEW/REPORT
  `20260813T1812`, Run fragment `docs/test-runs.d/REV-20260813T181200-folder-dnd-shared.md`.
- 라이브(PB-0008): 배포 후 수행 — 실 마우스 드래그 배정·빼기 + 크로스-계정 격리 실측.
- 후속(기록만): 관리자 `.any` 열람 "타 계정 대화" 의 '···' 메뉴 '이동' 무음 실패(폴더 하위 미렌더) —
  숨김 또는 파티션 확대 중 사용자 결정 필요.

**POST-DEPLOY 종결(2026-08-13, main `763ad65d`)**: 제품 경로로 구성한 라이브 시나리오(admin 대화 공유
링크 → 테스트 계정 가입·`operator` 부여 → join)에서 **공유받은 그룹 대화 `draggable="true"` · 드래그
폴더 배정/해제 서버 왕복 · 크로스-계정 격리(admin 뷰 폴더 미노출·`folder_id` null) · `pageerror` 0**
전 항목 PASS. AC-20260813T181200-folder-dnd-shared-group-1/-2/-3 충족. 상세 =
`unit/feature-0003-agent-web-ui/docs/test-runs.d/REV-20260813T181200-folder-dnd-shared.md`.
테스트 데이터(폴더·공유 링크·테스트 계정) 전량 정리 완료.

---
run_at: 2026-08-14T06:40:00+09:00
session: ai/claude/feature-0003-attach-version-tree-ui
scope: [attach-version-tree-ui, diff-axis-toggle, cross-lineage-diff]
verdict: PRE-COMMIT PASS (jsdom 24 + pytest 14 + 전체 스위트 회귀) · POST-DEPLOY PB-0008 라이브 실측 예정
---

### Run (2026-08-14) — attach-version-tree-ui: 버전 비교 축 토글 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정 — 토글의 좁은 폭 접힘·축 전환 시 표 안정성은 레이아웃 산물이라 jsdom 으로 정본 대체 불가, visual_verification_scope: always)**

- 대상 변경: `src/static/app/attach-diff.js`(축 토글·`_fillSelects`·`_diffParams`·캐시 키) ·
  `messages.js`/`composer.js`(계보 전달·진입 조건) · `css/chat.css`(토글 스타일 공유) ·
  `src/routers/attachments.py`(계보 간 diff 축).

- **PRE-COMMIT ① 동작 — `tests/verify_attach_version_tree_ui.mjs` 24 PASS**
  (Node18 + jsdom@22, 정본 모듈을 그대로 실행 — 로직 재구현 0):
  - **A 노출 조건(4)**: 계보 2개면 토글 · 버튼 2개 · 기본축 '이 계보 안' · 계보 1개면 토글 숨김.
  - **B 축 전환(6)**: 옵션 값 의미 전환(version_number ↔ attachment_id) · 과거→최신 정렬 ·
    소유자 라벨 · '현재' 표시 · 활성 상태 추종.
  - **C 요청(2)**: 시간순은 `from_attachment_id`/`to_attachment_id`, version 파라미터 미혼입.
  - **D 배선/구조(6)**: 양 경로 계보 전달 · `_diffParams` 단일 결정점 · 캐시 무효화 · CSS 공유.
  - **E 적대리뷰 반영(6)**: AI v1 칩 진입점 · 동일선택 축 인지 · 캐시 키 축 포함 · 응답 축 재확인 ·
    파일명 폴백 · 계보만으로 모달 개시.
- **PRE-COMMIT ② 인가 — `tests/test_attach_version_branching.py` 14 PASS**(계보 간 diff 는 양쪽을
  각각 인가 · 같은 대화·같은 파일명 스코프 · 동일 첨부 거부 · 기존 version 축 무회귀).

- **POST-DEPLOY 에서 확인할 것**: 토글이 좁은 패널에서 접히는지 · 축 전환 시 표가 튀지 않는지 ·
  실제 사용자 v1 ↔ AI v1 비교가 화면에서 끝까지 되는지(적대 리뷰가 지적한 진입점 결함의 실물 확인).

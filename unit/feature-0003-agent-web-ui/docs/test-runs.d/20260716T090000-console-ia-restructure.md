---
run_at: 2026-07-16T09:00:00+09:00
session: console-ia (ai/claude/feature-0021-console-ia)
scope: 관리 콘솔 IA 재구성 — '설정 > AI 추론' 단일 탭을 '감사 > AI 추론'(리뷰 활동·메모리 노트) + '설정 > 프롬프트'[전역 시스템 프롬프트/작동 지침/스킬]로 분리 (feature-0021 후속, 사용자 요청)
verdict: PENDING-POST-DEPLOY (코드/문법/단위 회귀 PASS — Windows-browser 는 배포 직후 수행)
---

### Run (2026-07-16) — console-ia 재구성 — **Environment: CLI (node --check ES module + 컨테이너 pytest)**

- **node --check** (ES module): admin.js OK (권한 맵 감사 재배치 · renderReasoning 지침/스킬 섹션
  제거 · 설정 mountGuidanceRegistryPanel · showGuidanceDetail detailId 파라미터화 후).
- **컨테이너 pytest** (62건 PASS): `test_admin_reasoning.py`(권한 분리 — guidance=system_prompt.global.read /
  redteam·notes=console.reasoning.read, 교차 거부, ?kind 필터, system-prompt-base 제외, 부분 degrade) +
  `test_permission_dependency_map.py`(M5 정합 — console.reasoning.read 를 감사 카테고리로 재배치한 FE↔카탈로그
  일치) + `test_route_parity_p5b.py`(경로 불변, 권한만 변경) + `test_redteam.py`/`test_agent_notes.py`(회귀 0).
- **make test 잔여 FAILED 4건**: 전부 pre-existing 환경 의존(PG 부재 2 · env AGENT_TIMEOUT_SEC=300 단정 2) —
  본 diff 무관(main 동일 실패, feature-0021 최초 cycle TEST.md §3 에 기 확인).
- **Windows-browser 미수행 사유**: IA 재배치(nav 그룹 이동·설정 항목 신설)는 배포된 web 에서만 조회 가능.
  visual_verification_scope=always 준수를 위해 **배포 직후 PB-0008 로 (1) '감사 > AI 추론' 탭이 감사 그룹에
  노출·리뷰 활동+노트 2섹션 렌더, (2) '설정 > 프롬프트' 그룹에 [전역 시스템 프롬프트/작동 지침/스킬] 3항목,
  (3) 작동 지침/스킬 progressive disclosure 본문 로드, (4) 시스템 그룹에 'AI 추론' 탭 부재**를 검증하고
  본 fragment 를 POST-DEPLOY Run 으로 갱신한다.

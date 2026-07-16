---
run_at: 2026-07-16T09:00:00+09:00
session: console-ia (ai/claude/feature-0021-console-ia)
scope: 관리 콘솔 IA 재구성 — '설정 > AI 추론' 단일 탭을 '감사 > AI 추론'(리뷰 활동·메모리 노트) + '설정 > 프롬프트'[전역 시스템 프롬프트/작동 지침/스킬]로 분리 (feature-0021 후속, 사용자 요청)
verdict: PASS (코드/문법/단위 62 + §18.8 적대검증 CLEAN + POST-DEPLOY Windows-browser 라이브 — 감사>AI추론 위치·2섹션·설정>프롬프트 3항목·progressive disclosure·fallback 제외 실증)
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

### Run (2026-07-16) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay, 배포 a8d9d05f)**

- **배포 전달 확인 (PASS)**: 서빙 web-a `GIT_COMMIT=a8d9d05f`, soak 통과.
- **(1) '감사 > AI 추론' 탭 위치·노출 (PASS)**: nav DOM 순회 결과 reasoning 탭의 소속 그룹 = **감사**
  (`감사:reasoning`), 노출됨(admin 은 감사 접근권+console.reasoning.read 보유). 시스템 그룹에는 부재.
- **(2) 감사>AI추론 pane 2섹션 (PASS)**: 섹션 = ["자가 적대 리뷰 활동", "메모리 노트 (임시 파일)"] 만
  (통계 타일 6). 지침/스킬 목록 UI(`.reasoning-guidance-row`) 없음 — 설정으로 분리 완료. pageError 0.
- **(3) 설정 > 프롬프트 그룹 3항목 (PASS)**: `data-settings-group="프롬프트"` 항목 = [global-prompt,
  guidance, skills]. 작동 지침 패널 8행(방언·능동해석·mermaid·인젝션·redteam·노트 등), 스킬 패널 12행
  (execute_sql·describe_table·describe_routine·search_tables …). pageError 0.
- **(4) fallback 중복 제거 (PASS)**: 작동 지침 패널에 "부트스트랩 fallback"(system-prompt-base) 항목
  부재 — 전역 시스템 프롬프트가 편집 정본으로 단일화.
- **(5) progressive disclosure (PASS)**: 작동 지침 첫 행(MySQL 방언 지침) 클릭 → `guidancePanelMountDetail`
  본문 2145자 lazy 로드.
- **판정: PASS** — 증거 스크린샷 `scratchpad/console-ia-settings-prompt.png`(감사 nav 그룹에 'AI 추론' +
  설정 프롬프트 3항목 + 스킬 도구 스키마 렌더). 회귀 0.

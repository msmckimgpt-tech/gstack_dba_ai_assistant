---
run_at: 2026-07-16T14:00:00+09:00
session: console-subtabs (ai/claude/feature-0021-console-subtabs)
scope: 관리 콘솔 유사 항목 서브탭 통합 — 감사 [LLM 사용량/AI 운영 현황/AI 추론] → 'AI 운영 현황' 단일 탭+서브탭, 설정 프롬프트 3항목 → 단일 '프롬프트' 항목+서브탭 (사용자 요청)
verdict: PASS (코드/문법/단위 33 + §18.8 적대검증 MAJOR2+MINOR2 반영 + POST-DEPLOY Windows-browser 라이브 — 감사 단일 'AI 운영 현황' 탭·서브탭 전환·lazy load·대시보드 딥링크 ops 착지·설정 프롬프트 서브탭 실증)
---

### Run (2026-07-16) — console-subtabs 통합 — **Environment: CLI (node --check + 컨테이너 pytest)**

- **node --check** (ES module): admin.js OK (bindPaneSubtabs·initAiConsoleSubtabs·activateAiConsoleSubtab·
  mountPromptsPanel·switchTab 레거시키 별칭 매핑 후).
- **컨테이너 pytest** (33건 PASS): `test_permission_dependency_map.py`(권한 코드·종속 불변 — 탭 키만 통합) +
  `test_admin_reasoning.py`(엔드포인트 무변경) + `test_route_parity_p5b.py`(경로 불변). ruff PASS.
- **§18.8 적대검증(REV-0005)**: 기능 CLEAN, key-drift 회귀 MAJOR 2(대시보드 딥링크 빈 pane·통합 pane
  스크롤 유실) + MINOR 2(usage 레이아웃 가드·firstKey 방어) 전건 반영. 서버 위젯 tab 계약
  (admin_console.py:562=usage·594=ai-ops) ↔ switchTab 별칭(usage→usage·ai-ops→ops) 정합 실측.
- **make test 잔여 FAILED 4건**: pre-existing 환경 의존(PG 부재·env) — 본 diff(프론트 전용) 무관.
- **Windows-browser 미수행 사유**: 서브탭 통합은 배포된 web 에서만 조회 가능. 배포 직후 PB-0008 로
  (1) 감사 그룹에 'AI 운영 현황' 단일 탭 + 서브탭[LLM 사용량/운영 현황/추론] 전환·lazy load,
  (2) 대시보드 위젯 '열기 →' 딥링크가 해당 서브탭 착지(빈 pane 아님), (3) 통합 pane 하단 스크롤 도달,
  (4) 설정 '프롬프트' 단일 항목 + 서브탭[전역/지침/스킬] 전환을 검증하고 POST-DEPLOY Run 으로 갱신한다.


### Run (2026-07-16) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay, 배포 b7e60f67)**

- **배포 전달 (PASS)**: 서빙 web-a `GIT_COMMIT=b7e60f67`, soak 통과.
- **(1) 감사 그룹 단일 탭 (PASS)**: 감사 그룹 = [감사 로그, 보관 대화, **AI 운영 현황(ai-console)**].
  옛 usage/ai-ops/reasoning 개별 탭 전부 부재(oldTabsPresent=[false,false,false]). ai-console 노출.
- **(2) 서브탭 전환·lazy load (PASS)**: ai-console pane 서브탭 [usage*|ops|reasoning], 기본 usage 활성·
  visibleSubpane=[usage]. 운영 현황 서브탭 클릭 → visibleSubpane=[ops]·aiOpsBody 렌더(err 0).
- **(3) 대시보드 딥링크 착지 (PASS — MAJOR#1 수정 확증)**: 'AI 상태 관리 화면 열기' 위젯(서버 tab:"ai-ops")
  클릭 → ai-console pane 활성 + **ops 서브탭 착지**·내용 렌더(notBlank=true). 빈 pane 회귀 해소.
- **(4) 통합 pane 스크롤 (PASS — MAJOR#2 수정 확증)**: usage 서브탭에서 요약 카드·일별 토큰 차트·
  모델별 비중까지 우측 스크롤로 하단 도달(스크린샷). 하단 잘림 없음.
- **(5) 설정 프롬프트 통합 (PASS)**: 설정 list 프롬프트 그룹 = 단일 [prompts] 항목, detail 서브탭
  [global|guidance|skills] 3개. pageError 0.
- **판정: PASS** — 증거 스크린샷 `scratchpad/console-subtabs-aiconsole.png`. 회귀 0.

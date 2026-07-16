---
run_at: 2026-07-16T14:00:00+09:00
session: console-subtabs (ai/claude/feature-0021-console-subtabs)
scope: 관리 콘솔 유사 항목 서브탭 통합 — 감사 [LLM 사용량/AI 운영 현황/AI 추론] → 'AI 운영 현황' 단일 탭+서브탭, 설정 프롬프트 3항목 → 단일 '프롬프트' 항목+서브탭 (사용자 요청)
verdict: PENDING-POST-DEPLOY (코드/문법/단위 33 + §18.8 적대검증 MAJOR2+MINOR2 반영 — Windows-browser 는 배포 직후)
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

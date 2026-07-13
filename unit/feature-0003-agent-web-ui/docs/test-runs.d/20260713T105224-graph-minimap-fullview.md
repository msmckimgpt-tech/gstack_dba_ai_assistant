---
run_at: 2026-07-13T11:52:00+09:00
session: ai/root/feature-0016-minimap-fullview
scope: graph/graph-core.js §77 graph-minimap-fullview (PRE-LANDING live)
verdict: PASS
---

### Run (2026-07-13) — §77 미니맵 전역 개요 유지 PRE-LANDING 라이브 — Environment: Windows-browser

- 방법: PB-0008 — bin/win-browser.py(실 Windows Chrome 150, CDP relay), https://localhost/admin.
  변경 `graph/graph-core.js` 스탬프 정합 치환 후 web-a/b docker cp 주입(+주입 사본 한정 디버그
  핸들 — repo 미포함), 자산 스탬프 재범프로 모듈 캐시 우회, error/unhandledrejection 수집기.
- 결과 **PASS**: mssql-qa-idc 1,249 노드(스키마 2개 펼침·fit-클램프 케이스) — ① 컬링-유예 시딩
  수렴(전체 이미지 서명=현재 기하) ② **극단 줌인 2.0 컬링 rebuild(방출 1,573→153)에 미니맵
  toDataURL 해시 완전 불변**(전역 개요·카메라 유지 — 사용자 리포트 직접 해소 실증) ③ 팬+rebuild
  불변 ④ 스코프 전환(gz-dev) 재렌더(동결 없음) ⑤ 전 과정 pageerror 0. 스크린샷 2매 육안 동일.
- headless: `tests/headless/test_g6build_minimap_reuse.js` **65 PASS**(Section E/F — 라이브 적발
  3건 재현·잠금) + 그래프 11 스위트 **279 PASS / 0 FAIL**(graph-split 후 7모듈 sed 연결 번들
  레시피). 상세 원장: unit/feature-0016-metadata-graph/docs/test-runs.d/20260713T105224-minimap-fullview.md

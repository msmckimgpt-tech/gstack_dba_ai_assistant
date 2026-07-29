---
run_at: 2026-07-29T18:20:00+09:00
session: ai/root/ui-copy-budget-adopt
scope: UI 카피 예산 게이트 채택 + 설정 패널 hint 4건 축약 (feature-0021 CHG-20260729-0008)
verdict: PASS
---

### Run — 설정 화면 안내 축약 시각검증 (Environment: **Windows-browser**, PB-0008)

기능 정본은 feature-0021, 웹 자산(`src/static/admin.html`)이 여기 거주한다. 상세 Run 은
`unit/feature-0021-redteam-review/docs/TEST.md` §3 "Run 2026-07-29 (7)".

- Environment: **Windows-browser** (PB-0008) + 격리 컨테이너 `http://localhost:18099`
  (라이브 web 이미지 + 본 branch src 마운트)
- Runner: AI · Bridge: relay @ `http://172.26.144.1:9223` (Chrome/150.0.7871.115)
- Evidence: `/tmp/win-browser-shots/rr-15-settings-trimmed.png`
- 확인: 설정 화면의 표시 중인 안내 길이 전수 `[49,40,77,78,97,57,80]` 로 예산(180자) 이내.
  탭 전환·패널 렌더 정상. 축약으로 버린 것은 조작법·타 화면 경로·내부 계약이고, 오설정 비용
  경고(타임아웃 초과·커넥션 풀/LLM 한도 소모)는 유지했다.
- Pass/Fail: **PASS**

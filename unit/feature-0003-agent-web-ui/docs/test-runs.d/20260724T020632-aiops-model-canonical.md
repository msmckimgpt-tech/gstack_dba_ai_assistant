---
run_at: 2026-07-24
session: ai/claude-corp/aiops-model-canonical
scope: '운영 현황' 서브탭(ai_ops) 모델 표기 canonical 정합 + 활동 상세 라우팅 M1 수정 (usage-model-canonical 후속)
verdict: PASS (pre-merge Windows-browser 로직 eval; 라이브 admin PB-0008 = 배포 후 후속)
---

### Run — admin.js 활동 상세 modelDetail 렌더 로직 (Environment: Windows-browser, PB-0008 relay)
- 방법: 실 Windows Chrome(win-browser.py CDP relay, https://localhost/admin 세션)에서 수정본 `modelDetail`
  로직(`srvM = r.resolved_model || r.req_model`, canonical `r.model` 미참조)을 대표 4시나리오 데이터에 직접 eval.
- 결과 (전부 기대 일치):
  - 정상 변형(req=claude-haiku-4, resolved=claude-haiku-4-chat) → `claude-haiku-4 → claude-haiku-4-chat` (실 라우팅 표시) PASS
  - gemma 폴백(req=claude-haiku-4, resolved=gemma4:e2b) → `claude-haiku-4 → gemma4:e2b` (실 폴백 라우팅 표시) PASS
  - **M1 트리거(req=auto, resolved=NULL)** → `auto` (날조 화살표 `auto → edge` 없음 — 적대리뷰 M1 수정 확증) PASS
  - NULL+haiku(req=claude-haiku-4, resolved=NULL) → `claude-haiku-4` (단일 모델, 화살표 없음) PASS
- 주 배지(`r.model`=canonical)는 백엔드 `_query_activity` 가 canonical 화 — 전체 pytest 로 별도 가드
  (test_query_activity_no_cursor_has_more/…preserves_routing/…null_resolved_badge_canonical_raw_preserved).

### Run — 백엔드 + 문법 (Environment: agent-image / node)
- `node --check` admin.js PASS · py ast admin ok · 전체 pytest **2287 passed / 2 skipped**(기존 baseline).

### Run — 라이브 admin '운영 현황' 실데이터 (Environment: Windows-browser) — 배포 후 후속
- 배포(web-only) 후 https://localhost/admin > 감사 > AI 운영 현황 > 운영 현황: '최근 활동' 피드 모델 배지가
  canonical 실 모델명(claude-haiku-4/edge/claude-sonnet-4)으로 표시 + 행 펼침 상세의 '요청 → 서빙' 라우팅이
  실제 값(폴백행 `… → gemma4:e2b` 등)만 표시(날조 화살표 0) + categories 카테고리 롤업 정합 + pageerror 0.

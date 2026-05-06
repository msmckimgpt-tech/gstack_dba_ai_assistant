---
doc_type: BRIEFING
feature_id: feature-0003-agent-web-ui
status: open
edit_policy: append-only
source_of_truth: false
created_at: 2026-04-29
related_task: TASK-0047
---

# Briefing — Product Selector + Auto Mode (v1)

> 본 브리핑은 TASK-0047 (제품 선택자 / auto 모드 진입 UX) 의 **검토 없이 진행된 합의 결과**에 대한
> 후속 검증 항목을 정리한다. AGENTS.md §9.2 (불명확성 사람 확인 필요 범위) 와 §12 (승인 필요 항목)
> 에 따라 사람 확인 후 처리해야 할 내용을 모은 단일 진입점이다.
>
> 본 turn 에는 사용자 검토 없이 4인 agent team(UX / Frontend Architect / Backend Engineer / QA-Flow Validator)
> + Codex CLI 교차검증 결과를 합의해 핵심 인프라만 구현했다. 사용자가 사용 즉시 가시화되는
> "사이드바 제품 칩" 과 "auto 모드 진입" 동작은 검증 가능하지만, 운영 가드/회귀/UX 학습
> 항목은 본 문서로 별도 추적한다.

---

## 0. 본 turn 에서 구현된 범위 (요약)

- DB
  - `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` 신설.
  - `WebAccounts.ProductPrefMode` / `WebAccounts.ProductPrefPinnedId` 신설.
- API
  - `/api/session` 응답에 `product_pref` / `conversation_product` 추가.
  - `/api/new_conversation` body 에 `mode='auto'|'pinned'` 수용.
  - `PATCH /api/conversations/{cid}/product` 신규 (race 가드: `last_status='processing'` 일 때 409).
- Agent core
  - `compose_system_prompt(... , product_mode='pinned'|'auto')` 분기 추가.
  - auto 모드는 `[AUTO MODE]` 한 줄만 inject 하고 PRODUCT/role/account 의 product 한정 prompt 를 건너뛴다.
  - `run_agent` / `_run_agent_core` 시그니처에 `product_mode` 파라미터 전달.
- Web 진입 흐름
  - auto 모드에서 `allowed_schemas=[]` (메타 4 스키마만 접근, cross-product leak 차단).
- Frontend
  - 사이드바 헤더에 `productChip` (auto + 활성 제품 select) + caption "이 대화의 제품".
  - `state.productMode` / `state.pinnedProductId` / `state.activeProductId` 분리.
  - `setActiveProduct(...)` optimistic + PATCH + localStorage 미러.
  - 진행 중 ask 동안 select disabled + tooltip.
  - `/api/session` hydrate 결과를 우선 적용, localStorage 는 깜빡임 방지용 미러.
- 용어
  - 사용자 가시 한글 라벨 "상품" → "제품" 일괄 치환 (`app.py`, `index.html`, `app.js`, `admin.html`, `admin.js`).
  - 코드 식별자(`Product`, `product_id`, `WebProducts`, `ProductKey`) 는 보존.

---

## 1. 차후 검증이 필요한 위험 항목 (Codex 교차검증 + agent team QA 합의)

| # | 항목 | 사유 / 영향 | 권고 검증 방법 |
|---|---|---|---|
| **R-01** | `auto` 라벨 / 기대치 정합 | "auto" 라는 이름은 자동 추론을 기대하게 하지만, 본 MVP 는 LLM resolver 가 없어 product context 미주입 + `[AUTO MODE]` 안내만 제공한다. 사용자가 제품 데이터를 묻는 일반 대화에서 답이 일반화되거나 "제품을 골라 달라" 로 끝날 수 있음. | (1) 베타 사용자 30명 1주 사용률 / 수동 전환률 측정 (2) 라벨 카피 A/B: "auto · 자동 (제품 미선택)" vs "(제품 미선택)" |
| **R-02** | LLM resolver 도입 | auto 의 본래 약속(맥락 포커싱) 은 resolver 없이 완전하지 않다. spec v1 §3 에 후속 설계가 있다 (입력: `{user_message, recent_turns≤3, products[]}` → JSON `{product_id|null, confidence, rationale}`, threshold ≥0.6, conversation row 갱신은 X, hint cache 만). | 별도 task — 평가 셋 50건 라벨링 + threshold 튜닝 + audit log 의무화. AGENTS.md §1.1 (휴리스틱 분기 금지) 준수 위해 분기는 LLM 결과 + confidence 기반만 허용. |
| **R-03** | PATCH race 강화 | 현재는 `AgentMemoryKv.last_status='processing'` 동안 PATCH 거부(409). 그러나 (a) ask 시작 직후 PATCH 가 race 로 통과 가능, (b) PATCH 직후 ask 가 구 설정을 읽을 수 있다 (Codex 지적). | conversation row 단위 row-level lock 또는 `version` 컬럼 추가로 ask/PATCH 직렬화. 회귀 테스트: 동시 PATCH+POST ask 100회 시 product_mode 변경이 turn 단위 immutability 를 깨지 않는지 확인. |
| **R-04** | pinned product 가 비활성/삭제될 때의 강등 정책 | 현재 1차 가드: `_load_account_product_pref` 가 active products 에 없으면 자동 auto 강등 + 토스트. 단, 이미 진행 중인 대화의 pinned 가 inactive 로 바뀌면 ask 결과가 끊길 수 있다. | admin 의 product 비활성화 액션이 영향받는 대화를 탐색해 운영자 알림 / migration 권고. 회귀 테스트: pinned 대화 진행 중 product 비활성화 → ask 가 명시적 에러 메시지를 반환하는지. |
| **R-05** | localStorage hydrate vs 서버 권한 race | localStorage `mad.productPref.v1` 가 즉시 반영되어 깜빡임을 줄이지만, 서버에서 권한이 회수된 경우 잠깐 잘못된 선택이 보일 수 있다 (Codex 지적). | 권한 체크는 서버에서 PATCH 시 강제. UI 는 hydrate 후 `pref.fallback_reason='pinned_inactive'` 가 오면 토스트로 강등 안내. |
| **R-06** | UI 위치의 멘탈 모델 | 사이드바 로고 아래는 "전역 계정 설정" 처럼 보일 수 있다. 본 turn 에는 caption "이 대화의 제품" 으로 보강. | 사용자 30명 인터뷰 또는 thinking-aloud 5명 — "이 칩이 무엇을 바꾼다고 생각하나요?" 검증. |
| **R-07** | 모바일 ≤720px UX | CSS 에 `max-width:16ch` ellipsis 만 적용. 칩이 좁은 화면에서 스크롤 영역과 충돌할 수 있다. | iPhone SE (375px) / iPad Mini (768px) 에서 칩 + 새 대화 + 대화 목록의 hit area 검증. bottomsheet 도입은 후속. |
| **R-08** | 키보드 접근성 | `<select>` native 사용으로 기본 keyboard 지원은 있다. 단, focus 시 chip 배경색 강조 / disabled 시 tooltip 의 키보드 노출은 별도 검증 필요. | a11y audit (axe-core) 자동 + 수동 Tab 흐름 점검. |
| **R-09** | 기존 default product 자동 채움 회귀 | ~~기존 NULL product_id 행이 자동 backfill 되는지~~ → **CLOSED 2026-04-30**: `_runtime_tables_available` probe 에 신규 컬럼 검사 + errno 1054 분기 추가로 기존 배포에서도 신규 컬럼 마이그레이션이 자동 트리거됨이 Playwright 28-check 로 확인됨 (CHG-20260430-0019, REV-20260430-0009). | ✅ closed |
| **R-10** | Playwright 자동 검증 specs | **PARTIAL 2026-04-30**: `repo/.gstack/qa-reports/qa-product-selector.cjs` (28-check, healthScore=100) 가 productSelector / persistence / hydrate / PATCH race-guard 를 자동 검증. autoFocusChip 은 LLM resolver(R-02) 도입 시 보강. | ✅ partial — autoFocusChip 만 R-02 와 함께 후속 |
| **R-11** | BroadcastChannel 다중 탭 동기화 | 두 탭에서 같은 사용자가 다른 product 를 고르면 마지막 PATCH 가 우선. UX 상 토스트 안내가 없다. | `BroadcastChannel("mad-product")` 도입 + 충돌 시 last-write-wins + 토스트. |
| **R-12** | 다국어 / 일본어/영어 뷰 | "제품" 한글 통일은 한국어 사용자 가정. ja/en 사용자 placeholder/chip/error 카피 자연스러움 미검증. | i18n 전환 지점에 "제품" 토큰 catalog 화. |
| **R-13** | 로그 적합성 | `product_id`, `product_mode`, (후속 resolver) `auto_focus_reason` 모든 turn 에 남기는지 운영 검증. | `/shared/logs/YYYY-MM-DD/insight_route.log` schema 확장 + grep 점검. |
| **R-14** | 보안 격리(cross-product leak) | auto 모드에서 `allowed_schemas=[]` 으로 차단. 단, resolver 가 들어가면 잘못된 product 로 resolve 됐을 때 다른 product 의 데이터에 닿을 수 있다. | resolver 도입 시 grounding review 1단계를 product 일치 검증으로 강화. |
| **R-15** | "auto → 제품" inline chip 응답 메시지 | UX 의견: auto resolved 시 응답 상단에 "auto → 제품명" chip 으로 사용자에게 시스템 선택 노출. 본 MVP 는 미구현. | resolver 도입과 함께. `assistant 메타 → 응답 헤더 chip` 렌더 1줄. |
| **R-16** | products 100+ 시 검색 가능 listbox | 현재 native select 만 사용. 50+ 부터 UX 저하. | `role="combobox"` + 검색 가능 listbox 패턴, 또는 fuzzysort filter. |

---

## 2. 사람 확인 권장 결정 사항

- **D-01** auto 라벨 한국어 카피: "auto · 자동 (제품 미선택)" / "(제품 미선택)" / "자동 (제품 미정)" 중 운영 결정.
- **D-02** LLM resolver 도입 일정 / 평가 셋 책임자.
- **D-03** PATCH race 강화 방식: row-level lock vs version 컬럼.
- **D-04** pinned product 비활성화 시 영향 대화 강제 마이그레이션 정책.
- **D-05** Playwright spec 4개를 본 feature 의 `tests/` 또는 `repo/.gstack/qa-reports/` 중 어디에 둘지.

---

## 3. 회귀 가드 (이미 본 turn 에 적용된 항목)

- 기존 `_get_default_product_id` 자동 채움 경로는 `mode='pinned'` 흐름에서만 유지.
- `compose_system_prompt(product_id=None, product_mode='pinned')` 호출의 의미 변경 없음 (기존 None 경로 보존).
- `tools.py` 의 `allowed_schemas=None` bypass 는 변경하지 않음. auto 모드에서 web 레이어가 `[]` 빈 리스트를 명시 전달.
- ALTER TABLE 은 `IF NOT EXISTS` / `try/except` 로 idempotent. MySQL 8.0 의 column add 는 metadata-only.
- "상품" → "제품" 치환은 사용자 가시 텍스트만. `WebProducts`/`ProductKey`/`product_id` 등 식별자는 그대로.

---

## 4. 4인 agent team + Codex 교차검증 원본

본 합의는 다음 입력을 반영했다 (요약, 자세한 본문은 세션 transcript 에 보존):

- **UX Designer**: 사이드바 헤더 칩 + caption "이 대화의 제품", `Auto · 자동 포커싱` 라벨, ChatGPT/Claude 모델/프로젝트 칩 패턴 참조.
- **Frontend Architect**: `productMode`/`pinnedProductId`/`activeProductId` 3-필드 분리, optimistic + PATCH + preference upsert, BroadcastChannel 후속.
- **Backend Engineer**: `product_mode` 컬럼 신설(NULL=auto sentinel 회피), `PATCH /api/conversations/{cid}/product` 신규, auto 시 `[AUTO MODE]` 한 줄 + `allowed_schemas=[]`, MySQL 8 INSTANT/INPLACE 마이그레이션.
- **QA-Flow Validator**: 6 사용자 여정, 8 edge-case, 4 Playwright specs, 5 차후 검증 항목.
- **Codex CLI**: auto 라벨 기대 불일치(R-01), PATCH race(R-03), pinned 비활성 fallback(R-04), localStorage hydrate race(R-05), 사이드바 의미 모호성(R-06) 5건을 추가 지적.

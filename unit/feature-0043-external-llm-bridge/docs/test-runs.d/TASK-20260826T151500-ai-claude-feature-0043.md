---
run_at: 2026-08-26T16:00:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: codex 리뷰 P1 5건 · P2 3건 조치 + 프론트 폴링 + 배선 회귀
verdict: PASS (단위·배선) / 잔여 — PB-0008 시각검증 · 도달성 probe
---

# Run — codex 리뷰 조치 검증

Environment: container (`make test` 하네스) + 로컬 pytest

## 결과

| 스위트 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **54 passed** (게이트 24 · 러너 5 · **배선 25**) |
| 편집 Python 5파일 AST | 통과 |
| `static/app/composer.js` (ESM `node --check`) | 통과 |
| route golden 재생성 | 253 routes / 252 api (`/api/ai/bridge_status` 신규 반영) |
| `bin/gen-routemap.py` | 250 routes / 29 modules |

## 배선 회귀 25건이 잠그는 것

리뷰가 잡은 P1 5건 중 **4건이 배선 결함**이었으므로, 헬퍼 correctness 가 아니라 **"그 함수가
실제로 그 자리에 배선돼 있는가"** 를 AST·소스 층에서 단정한다.

- 어댑터 등록(HTTP·stdio 양쪽 + `_register` 호출 + catch-all 앞 순서)
- 쿼터 게이트의 조건부화 · 브리지 분기가 dispatch 앞
- 반환 계약 3필드 + `_http_status`
- user 메시지 저장 · 대화 문맥 각인
- 원장 실패 시 점유 롤백 · `Status='open'` 한정
- 제출 소유권(`ClaimedBy`) · CREATE TABLE 컬럼 · 복합 인덱스 · online DDL 절
- 프론트 `bridge_pending` 소비 · 상태 API 의 세션 인증·계정 스코프·본문 미포함

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — 이번 cycle 에서 `static/app/composer.js` 를
  수정했으므로 `visual_verification_scope: always` 의 hard gate 대상이다. 대기 말풍선 →
  폴링 → 답변 렌더 전 구간을 실 브라우저로 확인해야 한다.
- **도달성 1-probe** (`reachability_scope: included`) — 웹 질문 → 개인 AI 처리 → 답변 렌더
  end-to-end. 컴포넌트 health 로 갈음하지 않는다.

---
run_at: 2026-08-27T09:30:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: codex 2차 리뷰 P1 6건 · P2 3건 조치 + 상태/장애/권한 회귀 17건
verdict: PASS (단위) / 잔여 — PB-0008 시각검증 · 도달성 probe
---

# Run — codex 2차 조치 검증

Environment: container (`make test` 하네스) + 로컬 pytest

## 결과

| 스위트 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **71 passed** (게이트 24 · 러너 5 · 배선 25 · **상태/장애/권한 17**) |
| 편집 Python 4파일 AST | 통과 |
| `static/app/composer.js` ESM `node --check` | 통과 |
| 컨테이너 `make test` (전체) | 통과 |

## 2차 조치가 닫은 것

1차 조치 뒤 재리뷰가 **절반만 닫힌 것들**을 드러냈다.

- **P1-A (기능 사망)** — `selectConversation()` 은 이미 활성인 대화면 즉시 return 한다(읽음처리만).
  폴링은 성공하고 토스트까지 뜨는데 답변은 화면에 나타나지 않았다. `loadHistory()` 로 교체하고,
  테스트가 **주석이 아닌 실제 호출**만 검사하도록 작성해 재발을 막았다.
- **P1-E (권한)** — 질문 후 그룹에서 퇴출된 계정이 `claim_request` 로 최신 문맥을 읽고
  `submit_answer` 로 그 대화에 쓸 수 있었다. 양 시점 fail-closed 재검증.
- **P1-B/C (상태 신뢰성)** — `submitted` 와 "대화에 실렸다" 를 분리(`Delivered` 컬럼),
  전달을 원장보다 먼저, `save_memory_message` 의 삼킨 실패(0 반환) 확인.
- **P1-D (고착)** — lease 30분. 목록·점유가 같은 술어를 공유.
- **P1-F / P2** — 러너 문맥 전달 · 세션 소유권 · INSERT→저장 순서 · 폴러 4xx 중단.

## 테스트 축을 넓힌 이유

codex 가 1차 조치의 회귀 테스트를 두고 *"대부분 AST/문자열 배선 검사라 상태 전이·장애·권한
결함을 검출하지 못한다"* 고 지적했다. 정확한 지적이라 **검사 대상이 배선이 아니라 조건·순서·
실패 경로**인 17건을 추가했다(권한 판정의 fail-closed, 전달↔원장 순서, lease 술어 공유,
save 반환값 확인, 취소의 스코프, 폴러의 4xx 분기).

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — 웹 자산(`composer.js`) 변경 cycle 이므로 필수.
- **도달성 1-probe** (`reachability_scope: included`).

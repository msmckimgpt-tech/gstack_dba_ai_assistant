---
run_at: 2026-08-28T11:40:00+09:00
session: ai/claude/feature-0043-connect-page-handoff
scope: `/ai/connect` 지시문 도달성 (TASK-20260828T120000)
verdict: **결함 발견 → 수정 → 재확인 PASS** — 새 문안이 화면에 도달함을 실측 확인
---

# Run — `/ai/connect` 지시문 도달성 (PB-0008)

Environment: **Windows-browser** (`bin/win-browser.py` relay @ `172.26.144.1:9223`,
Chrome/151.0.7922.170 · 격리 프로필 세션 `bootstrap_admin`)

## 이 Run 이 이 cycle 을 만들었다

직전 cycle(TASK-20260828T100000)이 지시문을 전면 개정하고 배포까지 정상 완료한 **직후** 수행한
검증이다. 목적은 "새 문안이 화면에 잘 나오는지" 확인이었는데, 결과는 그 반대였다.

## 절차와 관측

| # | 한 일 | 관측 |
|---|---|---|
| 1 | 배포 판정 — 서비스별 이미지 태그 | `web-a`·`web-b`·`ask-worker`·`insight-worker` 전부 `54e84874` (= main HEAD). 정상 |
| 2 | 컨테이너에서 무결성 값 실측 | `/srv/trust` 마운트 정상 · CA 지문 `F5:B9:C5:…:3C:1C` · 러너 체크섬 `9442bbaa…` — **서버는 값을 제대로 계산한다** |
| 3 | `goto https://localhost/ai/connect` | 200 · title `내 AI 연결하기` |
| 4 | `session-check` | `authenticated: true` · `bootstrap_admin` · admin |
| 5 | [연결 정보 만들기] 클릭 → `#handoffText` 판독 | **785자 · 옛 문안** |

### 5번에서 실제로 나온 것 (앞부분)

```
DB 질의 어시스턴트에 연결해줘. 아래 정보로 인증까지 끝낼 수 있으니 나한테 더 묻지 않아도 돼.
네가 지원하는 방식으로 A → B → C 순서로 시도해.

인증 (이것만 있으면 통과. 별도 로그인·승인 없음)
  Authorization: Bearer mat_…

A. MCP 설정에 추가
```

**없는 것**: 검증 값 블록(CA 지문·러너 체크섬) · TLS 신뢰 범위 · 상주 러너 5단계 · 토큰 성질 ·
운영자 시스템 지침 고지 · 발급자 표시. **있는 것**: 거절 사유였던 `"나한테 더 묻지 않아도 돼"`.

## 진단

`ai-connect.js` 가 서버 응답의 `body.handoff` 를 **버리고 자체 조립**하고 있었다
(`function handoff(token)`). 서버 문안이 여러 차례 개정되는 동안 이 사본은 갱신되지 않았다.

계약은 처음부터 있었다 — `compose_connect_handoff` docstring 이 "표시하는 곳이 둘이라 각자
조립하면 문안이 갈린다" 고 적었고 테스트도 있었다. 다만 `test_modal_uses_server_composed_handoff`
라는 이름 그대로 **모달에만** 걸려 있었고, 단독 페이지는 검사 대상 목록에 없었다.

소스 테스트는 전부 green 이었다. **검사 범위가 좁다는 사실은 green 으로 보이지 않는다.**

## 수정

- `ai-connect.js`: 자체 조립 제거 → `body.handoff` 사용(표시·복사). dead code 정리.
- 계약을 표시 화면 **전부**로 parametrize(`test_every_surface_uses_the_server_composed_handoff`).
- 회귀 역검증: 단독 페이지를 자체 조립으로 되돌리는 뮤턴트 → **KILL** 확인.

## 재배포 후 재확인 (2026-08-28 23:47) — PASS

배포 `369b40b1` 후 같은 절차(`goto` → `#makeHandoff` 클릭 → `#handoffText` 판독).

| 판독 항목 | 1차(결함) | 2차 |
|---|---|---|
| 문안 길이 | 785자 | **5,664자** |
| CA 지문 | 없음 | ✓ 실값 렌더 |
| 러너 체크섬 | 없음 | ✓ 실값 렌더 |
| 평문 CA 우선 | 없음 | ✓ |
| 발급자 표시 | 없음 | ✓ `bootstrap_admin 계정으로` |
| 운영자 지침 고지 | 없음 | ✓ |
| 5단계 러너 | 없음 | ✓ |
| "나한테 더 묻지 않아도 돼" | **있음** | ✓ 없음 |

**레이아웃**: `clientHeight 340` / `scrollHeight 4157` · `overflow-y:auto` · `white-space:pre-wrap`
→ 스크롤 정상, **잘림 없음**. [복사]는 DOM 전문을 넘기므로 스크롤 위치와 무관하게 전체 복사된다.

증적: `evidence/TASK-20260828T120000-connect-after.png`

---
run_at: 2026-09-01T13:30:00+09:00
session: ai/claude-corp/feature-0003-remove-query-result-details
scope: 말풍선 「▼ 쿼리 결과」 여닫이 제거 — PRE-DEPLOY 기준선 실측 (제거 대상이 실제로 거기 있는가)
verdict: PASS(기준선) — 제거 대상 4요소를 라이브에서 직접 관측. 부재 확인은 POST-DEPLOY fragment 로 이월
---

# Run — 말풍선 여닫이 제거 PRE-DEPLOY 기준선 (Environment: **Windows-browser**)

제거 작업의 시각검증은 **두 번**이라야 성립한다. 「없다」만 보면 애초에 없던 것과 구별되지
않으므로, 배포 **전에** 그것이 거기 있었다는 사실을 먼저 못 박는다. 이 fragment 가 그 절반이다.

실 Windows Chrome(격리 프로필, `bootstrap_admin` 세션), 배포본 `9ad72849` 기준.

## 1. 대상 화면

`https://localhost/` → 대화 `20260901030637-95dc8844`
(「쿼리 리뷰를 진행해주세요…」, 메시지 6, SQL 17건 실행된 답변).

152개 대화를 순회해 `summary.textContent === "쿼리 결과"` 인 말풍선을 가진 대화를 찾았다 —
`▼ 쿼리 결과` 는 답변에 `execute_sql` 단계가 있을 때만 그 문구가 되므로(없으면 「실행 단계」),
사용자가 지목한 그 화면을 정확히 재현한 것이다.

## 2. 제거 대상 — 4요소 관측 (기준선)

| # | 항목 | 관측값 | 판정 |
|---|---|---|---|
| B1 | 말풍선 여닫이 `.message-details` | 존재, `summary` = **"쿼리 결과"** | **관측됨** |
| B2 | 두 범위 블록 `.message-detail-block > strong` | `["단계", "쿼리 결과"]` | **관측됨** |
| B3 | 단계 스크롤 목록 `.step-detail-list` | 1개 | **관측됨** |
| B4 | 결과 네비게이터 `.sql-nav-indicator` | **"쿼리 1/17"** · 결과 표 14개 | **관측됨** |

같은 말풍선 아래 「단계 보기 (77)」 버튼도 함께 관측됐다 — **제거 후 남는 유일한 표시면의
입구**이며, 사용자가 "더 정확하고 의미있는 데이터를 조회 가능" 하다고 지목한 그 경로다.
같은 답변에서 여닫이는 77단계 중 SQL 17건 + 비-SQL 일부만 보이고, 패널은 77단계 전부를
소요시간과 함께 보여준다 — 중복이면서 **덜 보여주는** 쪽이 여닫이였다.

증적: `docs/evidence/remove-query-result-details/before-bubble-details.png`

## 3. 이 fragment 가 **검증하지 않은** 것

- 제거 후의 화면(여닫이 부재 · 「단계 보기」 정상 동작 · 레이아웃 붕괴 없음).
  → JS 변경은 `?v=` 스탬프 주입과 모듈 캐시 때문에 배포 전 컨테이너 `docker cp` 로 검증할 수
    없다(기존 학습). **POST-DEPLOY fragment 로 이월**하며, 그때 아래 4항목을 측정한다:
  1. `.message-details` **0개** (같은 대화 `20260901030637-95dc8844`)
  2. `.bubble-steps-btn` 존재 + 클릭 시 사이드 패널이 77단계로 열림
  3. 패널 카드의 SQL·결과셋 토글(`.sql-toggle-btn`)이 그대로 동작
  4. 말풍선 하단 레이아웃(간격·경계) 붕괴 없음 — 스크린샷 대조
- 브리지 진행 중 화면에서 「단계 보기 (N)」 입구가 새로 생성되는 경로.
  → 개인 AI 러너 미연결(`내 AI가 실행 중이 아닙니다` 배너 실측)로 진행 중 run 을 만들 수 없다.
    구조 단언(`test_bubble_always_offers_an_entrance_to_the_panel`)으로만 잠근 상태이며,
    이 미측정 사실을 숨기지 않고 남긴다.

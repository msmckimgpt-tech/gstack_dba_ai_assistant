---
run_at: 2026-09-01T14:30:00+09:00
session: ai/claude-corp/feature-0003-rqrd-postdeploy
scope: 말풍선 「▼ 쿼리 결과」 여닫이 제거 — POST-DEPLOY 부재 확인 (사전 열거 4항목)
verdict: PASS — 4/4. 배포본 786815f2 · 자산 ?v=cd84170acd28 · 엣지 blip 0
---

# Run — 말풍선 여닫이 제거 POST-DEPLOY 부재 확인 (Environment: **Windows-browser**)

선행 fragment(`TASK-20260901T1330-remove-query-result-details.md`)가 §3 에 **사전 열거**한
4항목의 이행. 그 fragment 는 제거 대상이 거기 있었다는 사실을 못 박았고(기준선), 이 fragment 가
없어졌다는 사실을 못 박는다. **둘이 함께라야 「제거했다」가 「원래 없었다」와 구별된다.**

실 Windows Chrome(격리 프로필, `bootstrap_admin` 세션), 배포본 `786815f2`
(web-a·web-b 동일 SHA 실측), 서빙 자산 스탬프 `?v=cd84170acd28`,
엣지 `no upstreams available` **0건**.

## 0. 도달 — 서빙 사본에 조립 경로가 없다

브라우저가 실제로 받는 바이트를 직접 fetch 해 확인했다(소스 트리가 아니다).

| # | 대상 | 확인 | 결과 |
|---|---|---|---|
| D1 | `GET /static/app/messages.js?v=cd84170acd28` (23,668 bytes) | `function renderMessageDetails(` **부재** | **PASS** |
| D2 | 〃 | `function buildSqlNavigator(` **부재** | **PASS** |
| D3 | 〃 | `function buildStepBlocks(` **부재** | **PASS** |

⚠ 이 확인이 필요한 이유: Chrome 모듈 캐시는 서버 파일이 신버전이어도 구버전을 실행할 수
있다(기지 함정). `location.reload(true)` 후 스탬프가 붙은 실 서빙 사본을 읽어 갈라냈다.

## 1. 부재 확인 4항목 — 4/4 PASS

대상은 **기준선과 같은 대화** `20260901030637-95dc8844` 다(다른 화면을 보면 대조가 성립하지 않는다).

| # | 항목 | 기준선(배포 전) | 배포 후 | 판정 |
|---|---|---|---|---|
| PD1 | `.message-details` | **1** (summary=「쿼리 결과」) | **0** | **PASS** |
| 〃 | `.message-detail-block` | 2 (`["단계","쿼리 결과"]`) | **0** | **PASS** |
| 〃 | `.step-detail-list` | 1 | **0** | **PASS** |
| 〃 | `.sql-navigator` | 1 (「쿼리 1/17」) | **0** | **PASS** |
| PD2 | 「단계 보기」 입구 | `[77, 2, 2]` | **`[77, 2, 2]` 동일** — 클릭 시 패널 `hidden:false`, 배지 **「77단계」**, 카드 37 + 내부 동작 행 40 (= 77) | **PASS** |
| PD3 | 패널 카드 결과셋 토글 | — | `.sql-toggle-btn` 37개, 클릭 시 `.step-result-wrap` `hidden true → false` + 라벨 「결과 보기」→「결과 닫기」. `.step-sql` 17블록 렌더 | **PASS** |
| PD4 | 말풍선 하단 레이아웃 | 여닫이 + 버튼 | 버튼만, 경계·간격 붕괴 없음 | **PASS** |

증적: `docs/evidence/remove-query-result-details/before-bubble-details.png` ↔
`after-bubble-no-details.png` (같은 대화·같은 위치 대조).

**PD2 의 «77» 이 이 cycle 의 요지다.** 여닫이는 같은 답변에서 SQL 17건 + 비-SQL 일부만
보였고, 패널은 **77단계 전부**를 소요시간·근거와 함께 보여준다. 사용자가 "더 정확하고
의미있는 데이터" 라고 지목한 것이 이 차이이며, 제거 후에도 그 경로는 **수치까지 그대로**다.

## 2. 여전히 **미검증**인 것

숨기지 않는다 — 통과한 축이 통과하지 못한 축을 대신하지 않는다.

| 축 | 상태 | 근거 |
|---|---|---|
| 완료된 답변의 여닫이 부재 | **검증됨** | PD1 (기준선 대조) |
| 「단계 보기」 패널이 유일 표시면으로 동작 | **검증됨** | PD2·PD3 (실 클릭) |
| **브리지 진행 중** 화면의 입구 «없으면 생성» | **미검증** | 개인 AI 러너 미연결 — 진행 중 run 을 만들 수 없다. 구조 단언(`test_bubble_always_offers_an_entrance_to_the_panel`)까지만 잠김 |
| 구형 메시지(`steps` 없음)의 표시면 소실 실측 | **미검증** | 해당 형식 메시지를 라이브에서 찾지 못했다. 소실 자체는 코드상 확정이며 TASK/REPORT 에 기록 |

마지막 두 줄이 이 표의 존재 이유다. 앞의 두 줄이 통과했다는 사실이 그것들을 대신하지 않는다.

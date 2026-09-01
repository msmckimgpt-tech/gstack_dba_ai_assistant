---
run_at: 2026-09-01T11:05:00+09:00
session: ai/claude/feature-0043-split-evidence
scope: 단계/결과셋 범위 분리 · 스크롤 대상 단계 한정 · POST-DEPLOY 실측
verdict: PASS
---

# Run — TASK-20260901T104500-steps-result-split · **POST-DEPLOY** (배포본 `65641296`)

- **Environment**: **Windows-browser** (PB-0008) — Windows Chrome/151, 라이브 `https://localhost`.
- **배포**: web ×2 `mysql-ai-web:65641296` · 워커 `mysql-ai-agent:65641296` · 대화 스모크 PASS ·
  surge 0 · `no upstreams available` **0건** · 서빙 stamp `9586c7d56d51`.

## evidence identity 대조 (§16.6 (c))

```
GET /static/app/messages.js?v=9586c7d56d51 → is-result-range      1 hit
GET /static/css/chat.css?v=9586c7d56d51    → min(38vh, 300px)     1 hit
```

렌더는 페이지가 로드한 모듈 URL 로 `import()` 해 **같은 인스턴스**로 수행했다.

## 측정 — 미리 열거한 6항목

시나리오: 비-SQL 단계 10건 + SQL 단계 4건(각 26줄 SQL + 60행 결과표).

### ① 단계 목록만 스크롤하는가

```
.step-detail-list   clientHeight 300   scrollHeight 631   scrolls: true
                    overflow-y auto    max-height 300px (= min(38vh,300px))
```

### ② 상세 본문은 스크롤하지 않는가

```
.message-details-body  clientHeight 1256  scrollHeight 1256  scrolls: **false**
                       overflow-y visible   max-height none
```

**스크롤 대상은 단계 목록 하나** — 요구 그대로.

### ③ 결과 표가 전역 상한을 되찾았는가

```
.result-table-wrap  max-height 460px   (상세 전용 380px 축소 규칙 제거됨)
```

### ④ 페이징이 어떤 스크롤도 움직이지 않는가

단계 목록을 120px 내려 둔 상태에서 ▶ · `ArrowRight`:

```
before  listTop 120  logTop 0  docTop 0   쿼리 1/4     navTop 424
after   listTop 120  logTop 0  docTop 0   쿼리 2/4     navTop 424
kbd     listTop 120  logTop 0             쿼리 3/4
```

`nothingScrolled: true` · `resultStaysPut: true` — 결과 범위가 **고정 위치**라는 주장의 실측.
2026-08-31 의 「페이징 시 스크롤 이동」 요구를 **구조가** 만족시킨다(그래서 그 코드를 지웠다).

### ⑤ 두 범위 제목이 렌더되는가

```
.message-detail-block > strong  →  ["단계", "쿼리 결과"]
.sql-result-group.is-result-range  존재
```

### ⑥ 페이지 높이가 부분 상한의 합 안에 드는가

```
상세 전체        1295px
├ 단계 블록        323  (목록 300 = 캡 + 제목)
└ 쿼리 결과 블록   921  (헤더 28 + 패널 844: SQL 블록 320 캡 + 결과표 ≤460 + 여백)
```

**정직한 수치**: 종전(2026-08-31)의 바깥 캡은 680px 였으므로 이 배치에서 상세는 그보다 높다.
그것이 이번 요구의 대가다 — 결과셋을 스크롤에서 빼면 그만큼 자리를 차지한다. 다만 **유계**다:
무한히 자라던 단계 목록이 300px 에서 멈췄고(같은 시나리오에서 캡이 없었다면 631px, 단계가
늘수록 계속 증가), 결과 범위는 SQL 블록 320 + 결과표 460 이 상한이다. 이 세 상한 중 하나라도
사라지면 회귀 테스트가 FAIL 한다.

## 캡처

`artifacts/pb0008-steps-result-split/split.png` · `split-crop.png` —
「단계」 블록에 **자기 스크롤바**가 붙어 있고, 그 아래 「쿼리 결과」 블록은 바깥 스크롤 없이
온전한 높이로 놓인 모습.

## 잔류물

없음. 검증용 DOM·핸들 제거 확인(`cleaned: true`), 대화·첨부·DB 미변경.

## 남은 판단 (사용자 결정 대기 아님 — 정보 제공)

상세 전체 1295px 가 과하다고 느껴지면 조정 지점은 셋이다: 단계 목록 캡(300) · SQL 블록
캡(320) · 결과표 캡(460). 셋 다 CSS 한 줄이며, 어느 것도 구조를 바꾸지 않는다.

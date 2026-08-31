---
run_at: 2026-08-31T19:40:00+09:00
session: ai/claude/feature-0043-scrollpanel-evidence
scope: 말풍선 상세 자기 스크롤 패널 + 페이징 시 패널 내부 이동 · POST-DEPLOY 실측
verdict: PASS
---

# Run — TASK-20260831T175800-details-scroll-panel · **POST-DEPLOY** (배포본 `47299f6a`)

- **Environment**: **Windows-browser** (PB-0008) — Windows Chrome/151, 라이브 `https://localhost`,
  세션 `bootstrap_admin`. 뷰포트 높이에서 `70vh = 622px`.
- **배포**: web ×2 `mysql-ai-web:47299f6a` · 워커 `mysql-ai-agent:47299f6a` · 스모크 PASS ·
  surge 0 · `no upstreams available` **0건** · 서빙 stamp `44ca06dfecd1`.

## evidence identity 대조 (§16.6 (c))

```
GET /static/app/messages.js?v=44ca06dfecd1  → revealInPanel·pageTo            9 hits
GET /static/css/chat.css?v=44ca06dfecd1     → min(70vh,680px)·min(46vh,380px) 2 hits
```

렌더는 페이지가 로드한 모듈 URL 로 `import()` 해 **같은 인스턴스**로 수행했다.

## 측정 — TEST fragment 에 미리 열거한 6개

### ① 패널이 자기 스크롤을 갖는가

```
clientHeight 622   scrollHeight 782   → scrollable: true
overflow-y   auto        overscroll-behavior-y  contain
max-height   622.3px (= min(70vh,680px))       min-height  0px
```

`min-height: 0px` — 요구대로 **최소 높이 제한 없음**.

### ② 페이지가 밀리지 않는가

패널이 넘치는 동안(scrollHeight 1199 vs clientHeight 622) 페이징을 해도
`messageLog.scrollTop`·`document.documentElement.scrollTop` **불변**(아래 ④).
종전에는 이 1199px 가 전부 페이지 높이로 나갔다 — 그것이 제보의 "과도한 페이지 스크롤" 이다.

### ③ 안쪽 표가 패널보다 작은가 (중첩 함정 부재)

```
result-table-wrap  clientHeight 378   max-height 380px  (= min(46vh,380px))
패널               clientHeight 622   → 378 < 622  ✔
```

### ④ 페이징이 **패널만** 움직이는가

네비게이터가 스크롤 아래에 가려진 상태에서 ▶:

```
before  panelTop   0   navOffset 381   logTop 0   docTop 0
after   panelTop 375   navOffset   6   logTop 0   docTop 0
```

패널 scrollTop 만 375 로 이동, **대화 로그·문서 스크롤은 0 그대로**.

### ⑤ 결과셋이 패널 상단에 오는가

`navOffset 6px` — 코드의 `_NAV_REVEAL_MARGIN_PX = 6` 과 정확히 일치.
최대 스크롤(577)이 아니라 **375** 에 멈췄으므로 clamp 가 아니라 계산된 위치다.

> 참고(정직 표기): 결과셋 아래 콘텐츠가 패널 높이보다 짧은 배치에서는 스크롤 여유가 없어
> `navOffset` 이 6px 까지 못 내려간다(측정 사례: 48px, `panelTop` 이 max 449 에서 clamp).
> 그때도 "가능한 만큼 올린다" 가 맞는 동작이며 결과셋은 화면 안에 들어온다.

### ⑥ 키보드 경로도 같은가

`ArrowRight` 로 `쿼리 2/5 → 3/5` 전환 시 같은 이동(`pageTo` 단일 경로).

### ⑦ 짧은 상세는 짧은 대로인가

```
단계 1건 상세  clientHeight 81px   scrollable false   min-height 0px
```

## 캡처

`artifacts/pb0008-details-scroll-panel/panel-scroll.png` ·
`panel-scroll-crop.png` — 패널 자체 스크롤바, 페이징 후 상단에 온 `쿼리 2/4` 헤더,
그보다 작은 안쪽 스크롤(SQL 블록·결과 표), 그리고 **밀려나지 않은 하단 컴포저**가 함께 보인다.

## 잔류물

없음. 검증용 DOM(`position:fixed` 호스트)과 임시 핸들은 제거했고(`cleaned: true` 확인),
대화·첨부·DB 는 변경하지 않았다. 캡처는 git 밖 `artifacts/` (§2).

## 남은 판단

상한 수치(`70vh/680px`, `46vh/380px`)는 실측상 자연스러웠다(패널 622 · 표 378). 다만 이는
**판단**이며, 더 크거나 작은 화면에서 사용자 취향과 어긋나면 CSS 두 값만 조정하면 된다.

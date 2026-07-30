---
run_at: 2026-07-30T19:40:00+09:00
session: ai/claude/feature-0016-gb-highlight-lit
scope: 접힌 컨텐츠 카테고리 집계 관계선이 하이라이트 상태에서 사라지던 결함(gb-highlight-lit)
verdict: PARTIAL — 로직 결함/수정은 **수정 전·후 차분으로 확증**, 픽셀 육안 캡처는 **미확보(사유 명시)**
---

# Test Run — gb-highlight-lit

- **Environment: Windows-browser** (실 Windows Chrome/150.0.7871.115, 전용 인스턴스
  `WIN_BROWSER_CDP_PORT=9242` · `WIN_BROWSER_PROFILE=C:\temp\win-browser-r3` — 타 세션 탭 무접촉)
- **Runner: AI** · **Bridge:** relay @ `http://172.26.144.1:9243`
- **대상:** §13.2.9 격리 경로 — worktree `src` 트리를 `/app/web` 에 volume 마운트한 격리 컨테이너
  `gb-verify`(:18099). 라이브 web-a/web-b·공유 트리 무접촉. 신 코드 서빙 확인: 서빙 자산에
  `gbMembersLit` 3회.

## 1. 라이브에서 확인된 것 (PASS)
- 격리 인스턴스에서 `cc_pyron` 펼침 성공 — 상태줄 `cc_pyron: 테이블·함수 854개 펼침`,
  `groupInfo=147`(밴드), `nodes=991`. 컨텐츠 밴드 레이어가 정상 구성된다.
- 모듈 싱글턴 접근(서빙 스탬프로 barrel 동적 import)으로 `_metaGraph` 상태 판독 가능:
  `groupOf`·`groupCollapsed`·`groupInfo` 및 렌더 산출 `graph._built` 확인.
- 배포본(라이브 `https://localhost/admin`)에서도 동일 경로로 밴드 우클릭 → `컨텐츠 카테고리`
  배지 + `길드 멤버 관리 · 테이블 37` 판독, `▾ 접기(묶음)` 동작 확인.

## 2. 결함·수정의 확증 — **수정 전/후 차분**(본 Run 의 핵심 근거)
브라우저 합성 이벤트로는 rebuild 를 신뢰성 있게 트리거하지 못해(아래 §3) 라이브 카운트를 근거로
쓰지 않고, **동일 계약 테스트를 수정 전 코드에 돌린 차분**으로 확증했다 — `origin/main` 의
`graph-core.js` 만 갈아끼운 번들과 수정본 번들을 같은 테스트로 비교:

| 계약 | 수정 전 | 수정 후 |
|---|---|---|
| 무선택 시 밴드 집계선 존재(기준선) | PASS | PASS |
| **하이라이트 상태에서도 밴드 집계선 보존** | **FAIL** (`total:0, gb:0`) | **PASS** |
| 보존된 선은 여전히 집계(`aggregated:true`) | FAIL | PASS |
| **무관 노드 선택 시엔 제거**(§67 의미 유지) | PASS | PASS |
| 스위트 합계 | 26 passed / **2 failed** | **28 passed / 0 failed** |

수정 전에는 하이라이트 상태에서 밴드 관련 엣지가 **통째로 0** 이었다(→ 사용자는 노드를 클릭해
탐색하므로 집계 관계선이 사실상 보이지 않았다). 대조군이 양쪽 PASS 라 **과잉 보존이 아님**도 확인된다.

## 3. 미확보 — 픽셀 육안 캡처 (정직 표기, §16.6 다운그레이드 금지)
접힌 밴드 헤더에 **종단하는 선**을 판독 가능한 크기로 캡처하지 못했다. 사유:
- 이 화면의 rebuild 는 `admin.js` 의 `_metaG6Apply` 가 구동하는데 barrel 이 그것을 export 하지 않아
  모듈 경로로 직접 호출할 수 없다. 렌더러 `zoomTo` 로는 rebuild 가 걸리지 않아(`_built.edges` 가
  전 측정에서 26 고정) **접기 상태가 씬에 반영되지 않았다** — 즉 라이브에서 관측한 `gbEdges:0` 은
  결함의 증거가 아니라 **rebuild 미발생의 산물**이다(이 점을 오독하지 않도록 명시한다).
- 캔버스가 1,426 노드로 가득 차 선택 해제용 빈 지점이 없고, 합성 클릭은 매번 다른 노드를 선택했다.
- 따라서 §16.6 의 "캡처 실패 시 escalate, 다운그레이드 금지" 에 따라 **시각 PASS 를 선언하지 않는다.**
- 남은 경로: 배포 후 사람 조작(밴드 접기)으로 1회 확인하거나, `_metaG6Apply` 를 barrel 에 export 해
  QA 핸들을 여는 별 cycle. 후자는 프로덕션 표면 확장이라 사용자 판단 대상으로 남긴다.

## 4. 정리
격리 컨테이너 `gb-verify` 제거 · 전용 브라우저 인스턴스 유지(타 세션 무접촉). 공유 트리·라이브
replica·DB 무변경, 라이브 데이터 쓰기 0.

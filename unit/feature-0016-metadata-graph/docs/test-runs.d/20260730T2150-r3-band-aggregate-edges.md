---
run_at: 2026-07-30T21:50:00+09:00
session: ai/claude/feature-0016-cluster-outcome
scope: R3 — 접힌 컨텐츠 클러스터 밴드의 집계 관계선(GB/GX 엔드포인트 승격) 라이브 픽셀 검증
verdict: PASS
---

# Run — PB-0008 R3 밴드 집계선 픽셀 검증 (Environment: Windows-browser)

- 대상: main `dcf4f845` 배포본(라이브 Caddy 경유 `https://localhost/admin`), 자산 스탬프
  `admin.js?v=b75da99e12c9`. Runner: AI (`bin/win-browser.py` relay, Chrome/150.0.7871.115,
  `WIN_BROWSER_CDP_PORT=9222` / relay `9223`).
- **왜 다시 보는가**: 직전 cycle 에서 `lit`/`litSelf` 의 `GB:` 미해소를 고쳤고(28/0 헤드리스 통과),
  집계선이 실제 픽셀로 그려지는지는 §16.6 상 **미검증(PARTIAL)** 으로 남겨 두었다. 그 잔여를 닫는다.
- 대상 데이터: 데이터소스 `mssql-qa-idc`(`mssql-06656002eda6`) · 스키마 `cc_data_main` ·
  컨텐츠 클러스터 **`메일 배송 기록 · 테이블 5`**(멤버: `UT_Mail`, `UT_Mail_Send`,
  `UT_MailAddItem`, `UT_MailAddItem_S…`, `DT_Letter`).

| # | 시나리오 | 관측 | 결과 |
|---|---|---|---|
| 1 | 밴드 우클릭 | `.admin-meta-graph-ctxmenu` 헤드 = `컨텐츠 카테고리 / 메일 배송 기록 · 테이블 5` | **PASS** |
| 2 | `▾ 접기 (묶음)` | 씬 객체 **1478 → 1466**(`made:10`) = 실제 리빌드 + 멤버 미방출 | **PASS** |
| 3 | 접힘 렌더 | 멤버 5개 소멸 · **헤더 pill 만 잔존** · 토글 `⊟`→`⊞` | **PASS** |
| 4 | **집계 관계선** | 펼침 시 개별 멤버(`UT_Mail`/`UT_Mail_Send`)에 각각 꽂히던 관계선들이, 접힘 시 **밴드 좌측 단일 엔드포인트(다이아몬드 마커)로 수렴** | **PASS** |
| 5 | 픽셀 차분 | 밴드 영역 diff bbox `(40,0,400,119)` — 변화가 밴드 영역에 실재 | **PASS** |
| 6 | 원복 | `▸ 펼치기 (묶음)` → 객체 **1466 → 1478** 복귀 | **PASS** |
| 7 | 콘솔 | `pageerror` / `console.error` **0건** | **PASS** |

## 첫 시도는 무효였다 — 검증 설계 오류 (기록)

처음에는 `UT_Mail` 을 **검색**해 그 결과 행을 클릭해 진입한 뒤 같은 밴드를 접었다. 메뉴 라벨은
`접기`↔`펼치기` 로 뒤집히는데 **캔버스는 픽셀 단위로 불변**이었고(`made:0`), 강제 리빌드를 걸어도
접힘이 반영되지 않았다. 결함으로 보고할 뻔했으나 코드를 먼저 확인했다:

```js
// graph-core.js:306-308
const smt = (_metaGraph.mode === "search") ? _metaGraph.searchMatchTables : null;
const isCollapsed = (sg) => _metaGraph.groupCollapsed.has(sg.key)
  && !(smt && sg.tables.some((t) => smt.has(t.key)));
```

**검색 매칭 멤버가 있는 그룹은 접힘 상태여도 강제 펼침**이 설계다(결과 가시성 보장). 검색으로 진입한
탓에 대상 밴드가 정확히 그 예외에 걸려 있었다 — 즉 **제품 결함이 아니라 내 검증 설계 오류**였다.
검색을 비운 뒤 동일 조작을 하자 위 표대로 정상 동작했다.

> **검증 제약(재사용)**: 컨텐츠 클러스터 접기/펼치기를 검증할 때는 **검색 모드를 반드시 해제**한다.
> 검색 상태에서의 "접기 무반응" 은 정상 동작이며 결함이 아니다.

- Evidence(4매): `artifacts/shared/win-browser-shots-r3-band-agg-edges/`
  (`01_bands_expanded.png` · `02_band_expanded_zoom.png` · `03_band_collapsed.png` ·
  `04_band_collapsed_zoom.png` — 02/04 가 집계선 수렴을 보여주는 확대본)
- 정리: 라이브 조작은 **읽기·뷰 상태 전용**(접기/펼치기는 세션 로컬, 서버 mutation 0) · 검증 후
  밴드를 펼침으로 원복 · `win-browser.py down` 으로 드라이버 인스턴스만 종료.

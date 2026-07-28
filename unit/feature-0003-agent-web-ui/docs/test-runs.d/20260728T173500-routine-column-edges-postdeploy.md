---
run_at: 2026-07-28T17:35:00+09:00
session: ai/claude/feature-0016-routine-coledges-postverify
scope: 함수/프로시저 사용 관계선 → 실제 참조 컬럼 연결 — POST-DEPLOY 실데이터 backfill + 라이브 재확인 (routine-column-edges)
verdict: PASS
---

# Run — PB-0008 POST-DEPLOY 라이브 재확인 (Environment: Windows-browser)

- 대상: PR #1014 머지(main `96dfdbdd`) + 무중단 전체 롤아웃 이후의 **main 기반 서빙본**.
  web `b36493a9`(이후 PR #1015·#1016 머지분 포함) · ask/insight 워커 `96dfdbdd`.
- **왜 다시 보는가**: 사전 검증(`20260728T161940-routine-column-edges.md`)은 §13.2.9 격리 harness 에서
  **주입한 fixture** 로 수행했다. 본 cycle 의 핵심 결함 클래스는 "코드·테스트·시각검증은 모두 통과하는데
  라이브에서만 죽는" 경로(`routine_refs_signature` 에 `cols` 미포함 → ROUTINE_USES 재작성 생략)였으므로,
  **실 데이터소스에서 파서가 컬럼을 뽑고 그것이 AGE 로 투영돼 화면에 도달하는지**는 배포 후에만 확인
  가능한 별개 사실이다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).

## 0. 실데이터 채움 (routine 재-introspect + graph sync)

`bash bin/routine-backfill.sh` — 등록 전 datasource(27개) 즉시 재-introspect + scope 별 `sync_graph`
투영. AGE 그래프 락은 `metadata-graph-sync.sh` 와 동일 flock 으로 직렬화(§82).

| 지표 | backfill 전 | backfill 후 |
|---|---|---|
| `routine_objects` 중 `referenced_tables[].cols` 보유 | 19 | **5,807** |
| AGE `ROUTINE_USES` 엣지 중 `ref_columns` 속성 보유 | 29 | **2,725** (전체 28,126 중) |

- backfill 전 19건은 배포 직후 insight-worker cadence 가 자연 전파한 분량 — 즉 **워커 경로도 실제로
  동작**하고 있었고, backfill 은 그 전파를 기다리지 않는 결정론 수단으로 쓰였다.
- 도달 불가 datasource(사내 VPN 경로 밖 원격 다수)는 per-(ds,DB,schema) 오류로 리포트되고 비차단 계속 —
  본 검증의 대상 datasource(`mysql-local`·`mssql-dk-dev`)는 정상 처리됐다.

## 1. 서빙 baked 확인 (라이브 Caddy 경유)

`https://localhost/static/graph/graph-core.js?v=3772f0cfa0c5` — 신규 심볼 `resolveColId` 2 ·
`ref_columns` 2 · `colEdge` 2 · `::c::` 1 · `::t::` 1. `graph-ctxmenu.js` — `ref_columns` 2 · `✎` 3.
`repo-web-a-1`/`repo-web-b-1` `GIT_COMMIT=b36493a9`, 워커 `96dfdbdd`.

## 2. 시나리오

Runner: AI (`bin/win-browser.py` relay) · Chrome/150.0.7871.115 · `https://localhost/admin` (라이브 서빙본).
좌표는 `getElementPosition`→`getViewportByCanvas` 환산 후 canvas 에 합성 PointerEvent 를 발생시켜 조작.

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | **접힘 = 기존대로** (`mysql-local` / `gunzlogin`, 테이블 미펼침) | `SessionKeyInsert→websessionkey`(write, ref_columns 5) · `LOGIN_*_GUNZ→websessionkey`(read, ref 없음) · `LOGIN_*_GUNZ→logsessionkey`(write, ref 3) 렌더 엣지 **전건 `colEdge:false`·테이블 끝점** — 모델에 `ref_columns` 가 있어도 분해되지 않음 **PASS** |
| 2 | **펼침 = 컬럼별 연결 (쓰기)** `websessionkey` 펼침 | `…::c::SessionKey` 엣지 1건 — `colEdge:true`·`ref_column:SessionKey`·`relation_type:write`, 끝점 model **(2142,449)** = 컬럼 정점 **PASS** |
| 3 | **부분 매칭 폴백 혼재** 같은 테이블 | 미렌더 참조 컬럼(AccountName·BirthDay·ClientIP·Time) 몫이 `…::t::write` 1선으로 테이블 끝점 model **(2195,415)** 로 승격 — 한 테이블에 컬럼선과 테이블선 **공존** **PASS** |
| 4 | **ref_columns 부재 무회귀** 같은 테이블 | `LOGIN_STEAM_GUNZ`·`LOGIN_MASANG_GUNZ` 의 read 선 2건은 분해 없이 테이블 끝점 유지 **PASS** |
| 5 | **펼침 = 컬럼별 연결 (읽기)** `mysql-local` / `global_db.serverinfo` 펼침 | `SP_SRVGRP_GETCOUNT`·`SP_SRVGRP_GETSERVERLIST` → `serverinfo.si_sid` 각 `colEdge:true`·`relation_type:read` · 미렌더 `si_type` 몫은 `::t::read` 로 테이블 승격 · `SP_SRVGRP_GETMAX`(ref 없음)는 테이블선 유지 **PASS** |
| 6 | **읽기/쓰기 한 컬럼 공존** `mssql-dk-dev` / `dk_game_release_231.CharacterSanction` 펼침 | 같은 컬럼 정점 `CharacterSanction.CharacterID` 에 `spGetAccountCharacterGlobalSanction`(**read**) · `spInsertCharacterSanction`(**write**) 컬럼선이 각각 연결 + 후자는 `::t::write` 폴백 동반 · ref 없는 다른 9개 루틴은 테이블선 유지 **PASS** |
| 7 | **상세 패널 (쓰기)** 루틴 `SessionKeyInsert` 선택 | `사용 테이블 (1) · 읽기 0 · 쓰기 1` → `gunzlogin.websessionkey ✎AccountName, ✎BirthDay, ✎ClientIP, ✎SessionKey, ✎Time` — 쓰기 마커 `✎` 5건 **PASS** |
| 8 | **상세 패널 (읽기, 테이블측)** 테이블 `serverinfo` 선택 | `사용하는 함수·프로시저 (4) · 읽기 4 · 쓰기 0` → `SP_SRVGRP_GETCOUNT si_sid, si_type` · `SP_SRVGRP_GETSERVERLIST si_sid, si_type` (읽기라 `✎` 없음) · `SP_SRVGRP_GETMAX`·`SP_LG_GET_OWNER` 는 컬럼 병기 없음 **PASS** |
| 9 | 콘솔 | `error` / `unhandledrejection` 리스너 **0건** |

## 3. Evidence

`artifacts/shared/win-browser-shots-routine-coledges-postdeploy/`
- `01_collapsed_table_only.png` — 접힘: 3개 루틴 → `logsessionkey`/`websessionkey` 테이블 수렴
- `02_expanded_overview.png` — 펼침 전경: `websessionkey` + `SessionKey` 컬럼 노드
- `03_write_col_terminus_and_table_fallback.png` — **결정 증거**: 한 선은 `SessionKey` 컬럼 점에 종결,
  나머지 선들은 `websessionkey` 테이블 박스에 종결 (컬럼선·테이블선 공존이 한 화면에)
- `04_detail_panel_write_refcols.png` — 상세 패널 `✎` 5컬럼 병기
- `05_read_col_and_table_detail.png` — 읽기 컬럼선 근접 + 테이블측 상세(`si_sid, si_type`)
- `06_read_span_routines_to_column.png` — 읽기 전경: 루틴 3개 → `serverinfo`/`si_sid`

## 4. 한계 (정직 표기)

- **컬럼 정점 커버리지가 상한**: 그래프의 Column 정점은 `column_descriptions` SSOT 에서 오므로, 참조
  컬럼이 파싱돼도 그 컬럼이 아직 introspect/기술되지 않았으면 렌더 대상이 아니고 테이블 폴백으로 남는다.
  라이브 관측치(`websessionkey` 5개 참조 중 1개만 컬럼 정점 존재)가 그 상태를 그대로 보여준다 — 설계된
  동작이며, 커버리지는 컬럼 introspect 진행에 따라 자연 증가한다.
- **파싱 상한은 불변**: 동적 SQL·MSSQL 4000자 절단·`SELECT *`·비수식 컬럼은 채택하지 않는다(보수적
  기준, 사용자 결정). 따라서 한 테이블 안에서 일부 선은 컬럼에, 일부는 헤더에 붙는 혼재가 **정상**이다.
- **미도달 datasource**: 사내 VPN 경로 밖 원격 다수가 backfill 시점에 연결 불가(비차단 리포트). 그
  datasource 의 컬럼 채움은 도달 가능한 시점의 backfill 또는 insight-worker cadence 로 넘어간다.
- 라이브 조작은 **읽기·카메라·펼침 전용**(펼침은 세션 로컬 상태, 서버 mutation 0). 자산 주입 없음 —
  서빙본 그대로 관측. 드라이버 전용 프로필 탭만 사용.
- **범위 외 라이브 발견(§8.1 기록만)**: backfill 의 `sync_graph` 리포트에
  `routine_prefetch: SyntaxError syntax error at or near ":"` 6건. `metadata_graph.py:1054` 의 cyvol
  선조회(feature-0030)가 `WHERE` 절을 노드 패턴과 관계 패턴 **사이에** 보간해 스코프 지정 sync 에서 항상
  실패한다(로컬 재현 확인). 실패는 fail-safe(빈 `_deg_by_key` → 전량 재작성 = 최적화 이전 동작)라 본
  POST-DEPLOY 의 `ref_columns` 채움에는 영향이 없었고, 손실은 최적화 무효화에 한정된다. 본 cycle 범위
  밖이라 수정하지 않고 feature-0016 `REPORT.md` 에 기록했다.
- `bin/win-browser.py screenshot`(playwright `page.screenshot`)이 본 세션 중반부터 fonts-loaded 직후
  30s 타임아웃으로 실패 — CDP `Page.captureScreenshot` 직접 호출로 캡처했다(동일 실 브라우저 화면).
  05·06 은 그 경로로 얻은 것이며 렌더 결과의 성질은 동일하다.

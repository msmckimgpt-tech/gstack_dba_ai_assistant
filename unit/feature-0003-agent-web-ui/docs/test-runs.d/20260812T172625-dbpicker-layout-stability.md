---
run_at: 2026-08-12T17:26:25+09:00
session: ai/claude-corp/db-picker-layout-stability
scope: 관리 콘솔 > 제품 > '+ 데이터베이스 추가' 목록 위치 안정성 (체크박스 토글 시 밀림 0) + '+ 데이터소스 추가' 동일 결함 클래스
verdict: PASS (Environment: Windows-browser, 실 Chrome 150.0.7871.128 relay)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

**환경**: `bin/win-browser.py` relay(`http://172.26.144.1:9223`) → **실 Windows Chrome 150.0.7871.128**.
검증 대상이 미머지 브랜치 코드라, 라이브 web 이미지(`mysql-ai-web:7c2918a8`)에 변경 2파일
(`static/admin/products.js` · `static/css/admin.css`)만 bind-mount 한 **격리 컨테이너**
(`web-dbpicker-verify`, `http://localhost:18099`, `repo_dbnet`, 평문)로 실측했다 — §13.2.9.
라이브 `web-a`/`web-b`·Caddy 는 **무접촉**. 검증 종료 후 컨테이너 제거.

**대상 데이터**: 제품 `CC_QA` (id 113) × datasource `mssql-qa-idc`(healthy) — 후보 DB **130개**,
등록 DB 16개. 사용자가 실제로 겪는 "후보가 많은" 케이스다.

**모든 토글은 클라이언트 pending 스테이징**이며 `모두 적용` 은 한 번도 누르지 않았다.
종료 후 서버 정본 재확인 — `webproductdatabases(ProductId=113)` = `mssql-qa-idc:16`,
`mssql-web-qa:1`, `webproductdatasources` = 2행 → **라이브 데이터 변경 0**.

## 1. '+ 데이터베이스 추가' — 체크 시 목록이 밀리지 않는다 (AC-…-1)

- 드롭다운을 열고 항목 `Account` 의 화면 좌표(1235, 328)를 기록 → `document.elementFromPoint`
  가 `Account` 를 반환.
- 그 체크박스를 **실 트러스티드 클릭**(Playwright CDP) → 등록 목록 16 → 17행, 카운트
  `선택됨 17개`.
- **앵커 이동 `0px`**, 같은 좌표의 `elementFromPoint` 는 여전히 `Account`.
- 통제 측정(단일 토글, 자동 스크롤 개입 없음): `dAnchor = 0`, 위쪽 `cov-detail` 높이 변화 `0`.

### 1-b. 역검증 — 수정 전 구조를 되돌리면 재현된다

- 같은 화면에서 DOM 순서만 수정 전으로 되돌리고(`cov-db-wrap` 을 picker 앞으로) 동일한 실
  클릭 반복 → 앵커 **+38px 이동**(드롭다운 내부 스크롤 불변 = 자동화 아티팩트 아님).
- 즉 이 화면은 **수정 전이었다면 반드시 달랐다**. 38px 은 행 높이(29px)보다 커서 다음 클릭이
  다른 DB 에 떨어진다 — 사용자가 보고한 "번거로움" 의 정체.

## 2. '+ 데이터소스 추가' — 동일 결함 클래스 (AC-…-2)

- 드롭다운의 첫 항목(`mssql-dk-dev`) 좌표 기록 → 미바인딩 datasource 를 **실 클릭**으로 체크
  → accordion 2 → 3행(바인딩 스테이징), 카운트 `1건 pending`.
- **앵커 이동 `0px`** (재구성으로 항목 노드가 새로 만들어졌음에도 같은 자리).
- 역검증: `ds-acc-add-row` 를 accordion 뒤로 되돌리면 같은 클릭이 앵커를 **+74px** 밀었다.

## 3. 드롭다운 가시 행 수 (AC-…-4)

- 종전 `max-height:220px` 에서 sticky toolbar(검색+정규식+선택 카운트, 실측 112px)가 절반을
  먹어 **가시 후보 3~4행 / 130** 이었다.
- `min(50vh, 420px)` 적용 후 실측 `listH=420px`, **가시 10행** (뷰포트 1904×945).
- ⚠ 이 축은 처음 측정에서 `220px` 로 나왔다 — 배포 스탬프가 같은 URL 이라 엣지/브라우저가
  구 CSS 를 `immutable` 로 붙들고 있었다(알려진 함정). 고유 쿼리의 stylesheet 를 새로 붙여
  **실제 서빙 파일**로 재측정해 420px/10행을 확인했다. (배포 후 POST-DEPLOY 재확인 대상.)

## 4. 회귀 축

- 편집기 자식 순서 실측 `[admin-db-picker-wrap, cov-db-wrap, cov-db-rule]`, 연결 degraded
  datasource 에서는 `[picker, admin-db-degraded-note, cov-db-wrap, cov-db-rule]` — 배너가
  picker 아래(목록 위)에 정상 배치.
- 검색·정규식 입력, `일치 선택`, 시스템 DB 고정칩, 등록 목록의 분석 진척/초기화/× 제거,
  하단 커밋 바(`1건 pending` → 새로고침 후 `0건 pending`)는 모두 종전대로 동작.
- 페이지 예외 0.

**증거**: `docs/evidence/pb0008-dbpicker-layout-stability-20260812.png` (수정본 — picker 상단 +
10행 드롭다운 + `AccountDB` 체크가 제자리, 아래로 등록 목록) ·
`docs/evidence/pb0008-dbpicker-layout-stability-before-height-20260812.png` (높이 확대 전 상태 —
같은 화면에서 가시 4행).

**Runner**: AI · **Bridge**: relay @ `http://172.26.144.1:9223` · **Pass/Fail**: PASS

**후속(POST-DEPLOY)**: 배포본에서 §3 의 가시 행 수를 캐시 무효화 없이 재확인한다.

---

# Run 2 — POST-DEPLOY 라이브 실측 (Environment: Windows-browser)

**run_at**: 2026-08-12T18:10:00+09:00 · **verdict**: PASS

PR #1221 머지(main `d619259d`) → `make deploy-web-only` 롤링 완료. web-a/web-b 양쪽
`mysql-ai-web:d619259d` · `/healthz git_commit=d619259d` · 엣지 `no upstreams available`
**0건**(무중단 실측) · 자산 스탬프 `c1426a14086f`.

라이브 서빙 자산에 수정 반영 확인 — `css/admin.css` 에 `min(50vh, 420px)` 1 hit ·
`admin/products.js` 에 `dbEditorWrap.appendChild(pickerWrap)` → `(chipWrap)` 순서 ·
`dbSection.insertBefore(addRow, dsAccordion)` 1 hit.

실 Chrome/150 `https://localhost/admin` 제품 `CC_QA` × `mssql-qa-idc`(후보 130개):

- 편집기 자식 순서 `[admin-db-picker-wrap, cov-db-wrap, cov-db-rule]` · 섹션 순서
  `[…, cov-detail, ds-acc-add-row, ds-acc]` — 배포본에서도 동일.
- **드롭다운 `listH=420px` · 가시 10행** — Run 1 에서 프리뷰 캐시(`immutable`)로 이월했던
  축을 **캐시 우회 없이** 배포본에서 확인. 이월 종결.
- 실 트러스티드 클릭 → 앵커 이동 **0px**, 같은 좌표 `elementFromPoint` 가 동일 DB
  (`atum2_db_7`) 유지, 16→17행, `선택됨 17개`, `1건 pending`.
- **역검증**: 같은 화면에서 DOM 순서만 수정 전으로 되돌리고 같은 클릭 → **+38px** 재현.
- 새로고침 후 `0건 pending`, 서버 정본 `webproductdatabases(113)` = 16/1 — **라이브 데이터
  변경 0**(`모두 적용` 미클릭).

**증거**: `docs/evidence/pb0008-dbpicker-layout-stability-postdeploy-20260812.png`

**배포 전 프리뷰 결과와 차이 0** (가시 행 수 축 포함).

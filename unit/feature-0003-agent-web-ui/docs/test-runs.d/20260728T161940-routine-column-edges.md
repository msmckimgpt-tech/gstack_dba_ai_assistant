---
run_at: 2026-07-28T16:19:40+09:00
session: ai/claude/feature-0016-routine-column-edges
scope: unit/feature-0002-agent-core/src/modules(routines·metadata_graph) · unit/feature-0003-agent-web-ui/src/static/graph(graph-core·graph-ctxmenu)
verdict: PASS
---

### Run (2026-07-28) — routine-column-edges: 함수/프로시저 사용 관계선을 실제 참조 컬럼에 연결 — **Environment: Windows-browser**

#### 1. 사용자 요청

> 그래프 뷰에서, 함수 및 프로시저가 테이블[로 부터/을 향해] 관계선을 표현할 때 연관된 컬럼이 아니라
> 테이블에만 연결되고 있는 것으로 확인되었습니다. 테이블 노드가 접힌 상태에서는 기존대로 작동하되,
> 펼쳐진 상태에서 각 컬럼이 드러났을 경우에는 실제 [읽기/쓰기] 참조하는 컬럼에 관계선을 구성하도록
> 개선해주세요.

#### 2. 근본 원인

FK 관계(`REFERENCES`)는 AGE 엣지의 **양끝이 Column 키**라 `graph-core.js` 의 `renderEndpoint` 가
"컬럼 렌더 시 컬럼 / 미렌더 시 테이블 / 스키마 접힘 시 SC: 카드" 3단 승격을 자동 수행한다. 반면
`ROUTINE_USES` 는 SSOT(`routine_objects.referenced_tables = [{fqn, kind}]`)부터 **테이블 단위**라
승격할 컬럼 끝점이 존재하지 않았다. 정의 파싱에 컬럼 추출을 더하는 것이 유일한 경로.

#### 3. 검증 환경 — 격리 harness (라이브 무영향)

**라이브 주입 QA 를 중단하고 격리 harness 로 전환했다.** 사유(정직 기록):
- 본 검증 시점에 **병렬 세션 6+ 가 활성**이고 브라우저·라이브 web(web-a/web-b)을 공유한다.
  주입본을 올린 상태에서 `win-browser.py` 의 `eval` 이 다른 세션 탭(`localhost:18099`)을 잡는 것을
  실측했다(`contexts[0].pages[0]` 고정). 주입 QA 를 지속하면 타 세션 검증을 오염시킨다.
- 라이브 주입은 **즉시 원복**했다 — web-a/web-b 양쪽 `graph-core.js`/`graph-ctxmenu.js` md5 가
  주입 전 원본과 일치함을 확인(`5a1ecca4…` / `d9c5410c…`), `/livez` 200.
- 대신 `pixi-migration/poc/integration-harness.html` 계보의 **격리 harness**(실 admin.html 그래프
  마크업 + Pixi UMD + graph 8모듈 번들 + mock apiFetch)를 만들고, **CDP relay 에 직접 붙어 새 탭**을
  열어 구동했다(playwright `connect_over_cdp` → `context.new_page()`) — 타 세션 탭 불간섭.
- 브라우저: **실 Windows Chrome 150.0.7871.115** (WSL → `172.26.144.1:9223` relay). 뷰포트 1680×1020.
- harness·번들은 검증 후 삭제(커밋 제외). 재현 레시피는 아래 §7.

#### 4. 대조 실증 — 접힘 vs 펼침

동일 mock 데이터(같은 엣지 3개)를 **컬럼 노드 유무만 바꿔** 두 번 로드했다.

| 케이스 | 사용선 | 끝점 | 컬럼 표식 |
|---|---|---|---|
| **접힘**(`?nocols=1`, 컬럼 미렌더) | 3 | `T_User`·`T_Order`·`T_User` (전부 테이블) | 없음(`colEdge:false`) |
| **펼침**(컬럼 렌더) | 6 | `T_User.UserID`(읽기)·`T_User.Point`(쓰기)·`T_User.Name`(쓰기)·`T_Order.Amount`(읽기) + `T_Order`(쓰기 승격) + `T_User`(대조군) | 컬럼 4건 `colEdge:true` |

- **(a) 접힘 = 기존 동작 완전 불변** — `ref_columns` 를 가진 엣지도 컬럼이 렌더되지 않으면 종전과
  같은 단일 테이블선 1개, 엣지 id 도 모델 원본 그대로. 스크린샷 `rce-COLLAPSED.png`: 각 루틴에서
  테이블 헤더로 선 하나씩.
- **(b) 펼침 = 컬럼별 분해** — `sp_UpdateUser` 가 `T_User` 의 **UserID/Name/Point 세 컬럼에 각각**
  선을 뻗는다. 스크린샷 `rce-EXPANDED.png` 육안 확인.
- **(c) 읽기/쓰기가 컬럼 단위로 갈린다** — 엣지 레벨 kind 는 `write`(UPDATE)지만 `UserID` 는 조건절
  참조라 `read` 로 유지되고, 화살표 방향도 반대(`startArrow` vs `endArrow`).
- **(d) 미렌더 컬럼은 테이블로 승격** — `T_Order` 의 `NoSuchCol`(컬럼 노드 없음)은 `T_Order` 본체로
  relation_type 별 1선 병합(FK 승격 규약 동형). 컬럼선과 공존.
- **(e) `ref_columns` 없는 관계는 무회귀** — 대조군 `sp_ReadOrder → T_User` 는 컬럼이 전부 펼쳐진
  상태에서도 테이블 연결·원본 id 유지.
- **(f) 상세 패널 병기** — `T_User` 상세 "사용하는 함수·프로시저 (2) · 읽기 1 · 쓰기 1" 에서
  쓰기 행 `⚙ sp_UpdateUser` 뒤에 **`UserID, ✎Point, ✎Name`**(✎ = 쓰기) 표기. `ref_columns` 없는
  읽기 행 `⚙ sp_ReadOrder` 는 표기 없음.
- **(g) pageerror 0** — 콘솔 error 는 `ResizeObserver loop completed…`(브라우저 양성) 외 0건.

스크린샷: `artifacts/rce-qa/rce-COLLAPSED.png` · `rce-EXPANDED.png` · `rce-DETAIL.png`.

#### 5. 자동 검증

- **헤드리스 신규** `tests/headless/test_graph_routine_colref.js` **30 PASS / 0 FAIL** — 접힘 무회귀·
  컬럼 분해·컬럼별 read/write·부분 매칭 승격·케이스 불일치 해소·`ref_columns` 부재/빈 배열 폴백·
  SC 카드 승격 경로 제외·테이블 경계 격리·정적 회귀(구현 우회 방지).
  - **이 스위트가 실제 결함 1건을 잡았다**: 초판 구현은 접힘 상태에서도 `ref_columns` 의 read/write
    별로 테이블선을 2개 만들어 "접힌 상태 = 기존대로" 계약을 깼다. 렌더된 컬럼이 0이면 분해 자체를
    포기하도록 수정.
- **그래프 헤드리스 전 스위트 18개 0 FAIL**(신규 포함 총 722 PASS) — 기존 `test_graph_edge_flow.js`
  73 PASS 등 회귀 없음.
- **pytest 신규** `tests/test_routine_column_refs.py` **27건** — 파서 채택 규칙(alias 수식/INSERT
  컬럼리스트/UPDATE SET 좌변)·비수식 미추정·미실재 폐기·모호 alias 폐기·스키마 qualifier 오인
  방지·주석 무시·크로스-DB 제외·cap 결정성 / 컬럼 인벤토리 조회(대상 한정·빈 입력 no-op·실패
  비차단) / 그래프 투영(`ref_columns` 속성·부재 시 생략·화이트리스트 등재·응답 정제·garbage 방어).
  - **이 스위트도 실제 결함 1건을 잡았다**: `_fetch_columns` 의 `cursor()` 획득이 try 밖이라 실패 시
    예외가 상위로 전파돼 **그 스키마의 routine upsert 전체가 죽을 수 있었다**. try 내부로 이동.
- **컨테이너 전체 회귀** `make test`: **2740 passed / 15 failed** · ruff PASS.
  15건은 **전부 baseline** — 동일 커맨드를 **main worktree(본 변경 없음)** 에서 돌려 **정확히 같은
  15건**이 실패함을 실측 대조했다(attachment_idor 4 · attach_inline_honesty 4 ·
  attachment_user_version_context 5 · runtime_settings 1 · runtime_settings_api 1). 본 cycle 신규 실패 0.

#### 6. 알려진 한계 (정직)

- **정의 파싱은 원리상 불완전**하다 — 동적 SQL(`EXEC(@s)`), MSSQL 4000자 절단 정의, `SELECT *` 는
  컬럼을 확정할 수 없다. 확정 실패분은 **테이블 연결로 남으므로**(폴백) 손실이 아니라 종전 동작이다.
- **비수식(unqualified) 컬럼은 추정하지 않는다**(사용자 결정 = 보수적). 다중 테이블 구문에서
  오귀속하면 "없는 관계를 사실처럼" 보여주게 되기 때문. 커버리지보다 정확성 우선.
- **크로스-DB 참조는 컬럼 승격 제외** — 현재 연결로 타 DB 컬럼 실재를 검증할 수 없다.
- **실데이터 e2e 는 POST-DEPLOY 잔여** — 라이브에서 컬럼선이 뜨려면 배포 후 ① routine 재-introspect
  (`referenced_tables.cols` 채움) ② graph sync(AGE `ref_columns` 투영)가 선행되어야 한다. 본 Run 은
  **렌더·상세 계약**을 실 브라우저에서 실증한 것이고, 실데이터 반영은 배포 후 재확인 대상이다.

#### 7. 재현 레시피

```bash
# 1) graph 8모듈 번들(어댑터 포함) — poc/graph-bundle.js
for f in graph-state graph-roleviz graph-util graph-rellayout graph-simgroups \
         graph-renderer-pixi graph-core graph-ctxmenu; do
  sed -e '/^import /d' -e '/^const G6 = window.G6;/d' \
      -e 's/^export const /const /' -e 's/^export let /let /' \
      -e 's/^export function /function /' -e 's/^export class /class /' -e '/^export {/d' \
      unit/feature-0003-agent-web-ui/src/static/graph/$f.js
done > unit/feature-0016-metadata-graph/pixi-migration/poc/graph-bundle.js
# 2) integration-harness.html 을 복제해 mock apiFetch 를 Routine/ROUTINE_USES(ref_columns)로 교체
#    — 노드 key 는 반드시 `scope:fqn`(예: ds_demo:schema_0.T_User). scope 접두가 없으면
#      _metaGraphExpandSchema 의 scope 가드가 "blocked" 로 조기 반환한다(실측 함정).
# 3) 정적 서버: (cd unit && python3 -m http.server 8899)
# 4) 실 Chrome: playwright connect_over_cdp("http://172.26.144.1:9223") → contexts[0].new_page()
#    (win-browser.py 의 eval/goto 는 pages[0] 고정이라 병렬 세션 탭을 잡는다)
```

#### 8. 헤드리스 스위트 실행

```bash
node unit/feature-0003-agent-web-ui/tests/headless/test_graph_routine_colref.js <graph-bundle.js>
```

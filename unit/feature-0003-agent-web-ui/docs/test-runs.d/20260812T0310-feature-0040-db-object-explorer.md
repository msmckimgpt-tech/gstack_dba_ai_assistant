---
run_at: 2026-08-12T12:10:00+09:00
session: ai/claude-corp/feature-0040-db-object-explorer
scope: feature-0003-agent-web-ui (graph 뷰 자산) · 정본 feature-0040-db-object-explorer
verdict: PASS
---

# Run (2026-08-12) — feature-0040 역할 기반 DB 객체 그래프 뷰 (Major §12.3) — **Environment: Windows-browser**

정본 feature 는 `feature-0040-db-object-explorer` 이고, 본 fragment 는 **파일 소유 feature**
(feature-0003 web/UI 자산: `static/admin.html` · `static/graph/{graph-core,graph-roleviz,
graph-state,graph-ctxmenu}.js` · `static/graph/graph.css`) 쪽 기록이다(§16.3 check #13 규약).

## 검증 경로 — 라이브 배포 없이 **실 Windows Chrome**

라이브 `/admin` 은 (a) 정적 자산이 이미지에 baked 라 재배포 전에는 새 코드가 없고,
(b) `db_objects` SSOT 가 alembic 0054 + insight cadence 이후에 채워져 빈 상태 확인에
그친다. **그러나 §16.3 「검증 사전-descope 금지」 에 따라 먼저 실측 경로를 consult 했고**,
`bin/win-browser.py doctor` 가 브리지 가용(relay @ 172.26.144.1:9223 · Chrome/150.0.7871.128)을
확인해 **integration-harness 경로**(선례: `20260728T161940-routine-column-edges.md` §7)로
실 브라우저 검증을 수행했다 — headless 가 아니라 **실 Windows Chrome + 실 WebGL**.

- 하네스: `integration-harness.html`(실 그래프 마크업 + Pixi UMD + graph 8모듈 번들 +
  mock apiFetch)에 feature-0040 역할 토글 5종 마크업과 DbObject fixture 5종을 주입.
- 렌더러 실측: `PixiGraphAdapter` · `renderer=webgl` · `PIXI 8.19.0`.
- 하네스·번들은 **검증 후 삭제**(커밋 제외). 재현 레시피는 아래 §재현.

## 결과

**① 렌더 (스크린샷 `evidence/feature-0040-db-object-explorer/01-graph-dbobjects-render.png`)**
- 역할 객체 5종 전부 방출: `⚡ trg_order_ai` · `▤ v_daily_sales` · `⏱ ev_purge_old` ·
  `↪ syn_legacy_user` · `# seq_order_no` — **역할 아이콘이 라벨 접두**로 붙음.
- 칩 색 전부 `#b0592a`(구리) — 테이블 teal · 루틴 보라와 **3색 분리** 육안 확인.
- combo 전부 `ds_demo:schema_0` — **스키마 클러스터 소속**(용어·기타 강등 아님).
- 엣지: `OBJECT_ON` 2건 **전부 파선** · `OBJECT_USES` 5건 **전부 실선**.
  스크린샷에서 `t_order —(파선)— trg_order_ai` 소유선과 `t_log` 로 모이는 실선 사용선이
  육안으로 구분됨(픽셀 확인 — element 상태 아님).

**② 인터랙션 — 역할 토글 (실 trusted click)**
`[data-kind="dbobj:trigger"]` 버튼을 실제 클릭:

| | dbobj 노드 | OBJECT_ON | OBJECT_USES | ROUTINE_USES | 테이블 |
|---|---|---|---|---|---|
| 클릭 전 | 5 | 2 | 5 | 1 | 3 |
| 트리거 숨김 | **4** | **1** | **4** | 1 (불변) | 3 (불변) |
| 재클릭 복원 | 5 | 2 | 5 | 1 | 3 |

- 노드뿐 아니라 **그 노드의 엣지 2종이 함께** 제거됨(끊긴 선 잔존 없음).
- 루틴 사용선·테이블은 불변 — **격리 확인**(과잉 제거 아님).
- `aria-pressed="false"` + `is-active` 해제 — a11y 상태 정합.

**③ 상세 패널 (스크린샷 `02-detail-panel-trigger.png`)**
```
트리거 / trg_order_ai / ⚡ 트리거 / 종류 TRIGGER / 대상 테이블 t_order
/ 시점 AFTER / 이벤트 INSERT / 활성 활성 / AI 능동 분석 ✨
```
- 역할별 속성 표제(시점·이벤트·활성)가 **서버가 붙인 표제 그대로** 표시.
- `대상 테이블` 라벨이 역할(trigger)에 맞게 선택됨.
- **AI 능동 분석 진입점이 역할 객체 상세에도 존재** — 사용자 축2 결정(전 엔드포인트 분석)이
  UI 에서 도달 가능함을 확인.

**④ 부수 수정 (본 검증이 잡음)**: 상세 배지가 내부 라벨 `DbObject` 를 그대로 노출하고
있었다 → 역할 한글명(`트리거`)으로 교체(`_metaDetailBadgeKo`). Table/Column/Routine 등
기존 라벨은 **미변경**(범위 밖 UI 변경 금지). 재검증에서 `트리거` 표시 확인.

## 회귀

- headless 그래프 스위트 24 파일 **1179 PASS 단언 · 실패 0**(수정 후 재실행).
- 신규 `test_g6build_dbobjects.js` **21 PASS**.

## 한계 (정직 표기)

본 검증은 **렌더·인터랙션 계약**을 실 브라우저에서 실증한 것이고, **라이브 실데이터 반영은
배포 후 재확인 대상**이다. 배포 후 POST-DEPLOY 체크리스트는
`unit/feature-0040-db-object-explorer/docs/TEST.md §3` 에 있다(마이그레이션 0054 적용 +
insight cadence 경과 후 `db_objects` 행 존재 → 실 스키마에서 위 ①~③ 재확인).

## 재현

```bash
# 1) graph 8모듈 번들
for f in graph-state graph-roleviz graph-util graph-rellayout graph-simgroups \
         graph-renderer-pixi graph-core graph-ctxmenu; do
  sed -e '/^import /d' -e '/^const G6 = window.G6;/d' \
      -e 's/^export const /const /' -e 's/^export let /let /' \
      -e 's/^export function /function /' -e 's/^export class /class /' -e '/^export {/d' \
      unit/feature-0003-agent-web-ui/src/static/graph/$f.js
done > unit/feature-0016-metadata-graph/pixi-migration/poc/graph-bundle.js
# 2) integration-harness.html 에 역할 토글 5종 + DbObject fixture 주입
# 3) (cd unit && python3 -m http.server 8907)
# 4) python3 bin/win-browser.py launch --url http://<WSL_IP>:8907/feature-0016-metadata-graph/pixi-migration/poc/integration-harness.html
#    ⚠ 하네스 schema key 는 scope 접두 필요(`ds_demo:schema_0`) — 없으면 _metaGraphExpandSchema 가 조기 반환
```

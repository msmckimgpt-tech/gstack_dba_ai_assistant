---
run_at: 2026-07-15T22:37:44+09:00
session: ai/claude/feature-0003-graph-cluster-detail-fulllist
scope: 스키마 클러스터 상세 컨텐츠 카테고리 목록을 전체 출력하도록 캡 사실상 해제(그룹당 캡 제거 + 전역 500→5000) + 행 상호작용 이벤트 위임 (20260715T2237-graph-cluster-detail-fulllist)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED
---

### Run 1 — 문법 검증 (Environment: node --check, ESM)
- `graph-ctxmenu.js` ESM 문법 OK. 단일 파일(28 insert / 15 delete).

### Run 2 — 정적·로직 검증 (Environment: 코드 리뷰 + 이벤트 위임 동등성 추적)
- **캡 해제**: `shown = Math.min(sg.tables.length, Math.max(0, 5000-emitted))` — 그룹당 캡 제거로 각 컨텐츠 카테고리가 전체 멤버 렌더, 전역 5000 은 극단 가드. 멤버 총합 <5000 스키마는 전체 표시(`(shown/n)` 절단 없음). 헤딩 항상 방출 유지. flat 폴백 `slice(0,5000)`.
- **이벤트 위임 누적 없음**: 위임 리스너를 영속 `el`(#metadataGraphDetailBody)이 아닌 **매 렌더 innerHTML 로 재생성되는 `ul.amgr-cluster-tables`** 에 부착 → 직전 ul 이 리스너와 함께 GC, 렌더마다 새 ul 에 1회씩 부착(누적 0). collapse/analyze 버튼은 여전히 getElementById 개별 바인딩(간섭 없음).
- **hover 의미 보존**: 원본 per-row `mouseenter/leave/focus/blur`(비버블) ↔ 위임 `mouseover/out/focusin/out`(버블). ① 행 자식(칩↔code) 이동: `mouseout` 의 `!b.contains(relatedTarget)` 검사가 같은 행 내부 이동 시 취소 억제. ② 인접 행 직접 이동: 행A `mouseout`(relatedTarget=행B, 행A 밖)→취소 + 행B `mouseover`→pan = 원본 leave+enter 순서와 동등. ③ `_hoverKey`로 같은 행 재-pan 방지. ④ window 이탈(relatedTarget=null)→취소.
- **클릭 동등성**: `e.target.closest(".amgr-ct-row[data-node-key]")` 로 행 자식 클릭도 행 승격, 그룹 헤딩(data-node-key 없음)→null→no-op. 클릭 후 `_metaGraphShowDetail` 재렌더(ul 교체)는 이벤트 처리 완료 후라 무해.
- **회귀**: 소형 스키마는 캡 미도달 → 전체 표시(기존과 동일, 단 직전 cap cycle 의 그룹당 25 절단이 사라져 25 초과 그룹도 전량). XSS: rowHTML `esc()` 무변경.
- 결과 **PASS(정적)** — §18.8 적대 리뷰 결과는 REVIEW.md 참조.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **DEFERRED(배포 후 수행)**
- 대상: 재배포 후 컨텐츠 카테고리 멤버 총합 500 초과 스키마(사용자 스크린샷의 gemstone/battlefield/transform-job DB) 클러스터 상세 재진입 → (1) 모든 컨텐츠 카테고리가 전체 멤버 렌더(`(0/N)`·`(3/5)` 소거), (2) hover 시 카메라 pan 정상, (3) 행 클릭 → 노드 상세 조회, (4) pageerror 0, (5) 다수 행 렌더 시 체감 지연 없음.
- visual_verification_scope: always — 배포 후 충족 예정. 미수행 사유: 정적 자산 baked 라 web 재배포 후에만 서빙 반영.

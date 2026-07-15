---
run_at: 2026-07-15T21:52:41+09:00
session: ai/claude/feature-0003-graph-cluster-detail-cap
scope: 스키마 클러스터 상세 목록의 전역 80행 캡이 대형 스키마(gunzgame 409항목)에서 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 — 헤딩 항상 방출 + 그룹당/전역 이중 캡으로 개정 (20260715T2152-graph-cluster-detail-cap)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED
---

### Run 1 — 문법 검증 (Environment: node --check, ESM)
- `graph-ctxmenu.js` ESM 문법 OK. 단일 파일(10 insert / 4 delete).

### Run 2 — 라이브 근본원인 확정 (Environment: Windows-browser, PB-0008 relay — 선행 cluster-detail-routines 배포본 1b370dfd)
- win-browser.py 실 Windows Chrome 150 relay, https://localhost/admin > 그래프 뷰 > 데이터소스 mysql-gz-dev 진입 > gunzgame 스키마 카드 클릭 → 상세 패널(`_metaGraphShowClusterDetailLocal`).
- 실측: 섹션 제목 "테이블·함수·프로시저 (409)", 설명 "테이블 115개 · 함수·프로시저 294개" — **집계는 정확**(cluster-detail-routines 작동 확인). 그러나 렌더된 컨텐츠 카테고리 그룹 = 10개(캐릭터 정보 및 랭킹 32·사용자 환경 설정 15·캐시 상점 상품 3·캐시 상점 6·메달 상점 6·메일 및 메시지 4·길드 관리 5·서바이벌 시나리오 4·웹 랭킹 조회 3·전체 순위 2/3), **전부 테이블(rtn=0)**. 함수·프로시저 컨텐츠 카테고리 0개 노출. aside overflow-y:auto·scrollH 2620>clientH 575, 마지막 그룹 `(2/3)` 절단 = 80행 전역 캡 도달.
- 결론: 80행 전역 캡이 be:(테이블) 우선 순서로 소진돼 뒤쪽 routine 컨텐츠 카테고리 전체가 렌더 자체에서 누락. → 본 cycle 의 캡 규약 개정 필요.

### Run 3 — 정적 로직 검증 (Environment: 코드 리뷰)
- 개정 후 `shown = Math.min(sg.tables.length, PER_GROUP=25, Math.max(0, ROW_CAP=500 - emitted))`. 헤딩은 조기 return 없이 **항상 방출** → 모든 컨텐츠 카테고리 가시. 캡 도달(emitted≥500) 시 shown=0 → 헤딩+0행+`(0/n)`. 그룹 멤버 ≤25·예산 충분 시 전량. gunzgame(409<500): 그룹 멤버 >25 인 그룹(32)만 25 표시, 나머지 전량 → **함수·프로시저 컨텐츠 카테고리 전부 헤딩+멤버 노출**. 개수 정합: 헤딩 `sg.n` 불변 + `(shown/n)` 표식.
- 결과 **PASS(정적)**.

### Run 4 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **DEFERRED(배포 후 수행)**
- 대상: 재배포 후 gunzgame 클러스터 상세 재진입 → (1) 함수·프로시저 컨텐츠 카테고리(예 "상점 아이템 명칭" 류 routine 그룹)가 헤딩 + ƒ/⚙ 보라 칩 멤버 행으로 실제 렌더, (2) routine 행 클릭 → 노드 상세(파라미터) 조회, (3) 테이블 그룹은 25 초과 시 `(25/n)` 표식·나머지 정상, (4) pageerror 0.
- visual_verification_scope: always — 배포 후 충족 예정. 미수행 사유: 정적 자산 baked 라 web 재배포 후에만 서빙 반영.

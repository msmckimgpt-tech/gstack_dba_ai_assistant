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

### Run 4 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **PASS**
- 배포: PR #828 → main cdee785e + `sudo -E bin/deploy-web.sh` 무중단 롤링(web-a/web-b·워커 recreate·soak 통과). 서빙 자산 `/app/web/static/graph/graph-ctxmenu.js` `ROW_CAP = 500` grep=1(web-a/web-b baked).
- 방법: win-browser.py 실 Windows Chrome 150 relay, https://localhost/admin(로그인 세션) 하드 리프레시 → 그래프 뷰 > 데이터소스 mysql-gz-dev 진입(합성 좌클릭) > gunzgame 스키마 카드 클릭 → 상세 패널.
- 결과 **PASS**:
  1. **함수·프로시저 컨텐츠 카테고리 노출**: 렌더된 컨텐츠 카테고리 그룹 = **72개**(cap 수정 전 10개), 그중 **함수·프로시저-only 그룹 51개**(수정 전 0개). 실측 예: "계정 조회"(24 routine)·"캐릭터 인벤토리"(25)·"아이템 구매"(15)·"아이템 정보"(13)·"재화 변환"(5)·"스팀 캐시 관리"(3)·"로그인 보상"(2) 등. 총 렌더 행 400(ROW_CAP=500 내), mixed 그룹 0.
  2. **routine 행 ƒ/⚙ 칩 + 클릭 조회**: "계정 조회" 그룹의 `⚙ Game_AllItemGet`(key `mysql-6e07e3baa968:gunzgame.Game_AllItemGet()`) 클릭 → 상세 패널 "ROUTINE / Game_AllItemGet / ⚙ 프로시저 · 이웃 2개" 정상 조회. 스크린샷 육안: "계정 조회 24" 헤딩 아래 `⚙ Game_AccountItemBringBack`·`ƒ Func_IsAccountBoundCustomizeItem`·`⚙ Game_AccountGet` 등 ƒ/⚙ 보라 칩 멤버, 그 위 `⚙ Game_CashSetItem`·`⚙ Game_MedalItemList` 등. 캔버스 sim-group("아이템 구매 기록·7"·"퀘스트 플레이 기록·5")과 일치.
  3. **섹션 제목/개수 정합**: "테이블·함수·프로시저 (409)", 설명 "테이블 115개 · 함수·프로시저 294개".
  4. **pageerror 0**: window 에러 배열 빈값·docReady complete.
- visual_verification_scope: always (§10.5 web/UI 완료 게이트) — 충족. evidence: gz_routine_groups.png(계정 조회 그룹 ⚙/ƒ 멤버).

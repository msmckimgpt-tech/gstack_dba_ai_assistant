---
run_at: 2026-07-13
session: ai/root/feature-0016-graph-pixi
scope: §78 POST-DEPLOY 라이브 admin 그래프 뷰 PixiJS 실데이터 검증 (T78.4)
verdict: PASS
---

### Run — 라이브 admin 그래프 뷰 실데이터 (Environment: Windows-browser, PB-0008 relay)
- 배포: PR #752 → main d776f57b + `bin/deploy-web.sh` 무중단 롤링(web-a/web-b recreate·soak 90s PASS). 서빙 자산: pixi.min.js 200(797KB)·graph-core.js seam 심볼 7·cache-buster b9c4582d47b7.
- 방법: win-browser.py 실 Windows Chrome 150, https://localhost/admin 로그인 → 지식베이스 > 그래프 뷰, 데이터소스 mysql-gz-dev(건즈 개발, 3 DB·173 테이블).
- 결과 **PASS**:
  1. **seam**: 그래프 인스턴스 = PixiGraphAdapter(renderer=webgl, pixi 8.19.0). g6→pixi 전환 라이브 확인.
  2. **roots 렌더**: 카테고리 밴드(🎮 건즈-개발·3 DB·173 테이블) + 3 스키마 카드(gunzgame/gunzlog/gunzlogin) + 집계 관계선(SCHEMA_REF 47) + 미니맵(우하단) + 범례. pageerror 0.
  3. **스키마 펼침**: gunzgame 카드 클릭 → **테이블 115 + 함수/프로시저 = 409 객체** 펼침. 테이블 역할색 칩·보라 루틴 칩(f/⚙)·ROUTINE_USES 보라 점선 관계선 다수·**미니맵 전역 개요 표시(§18.8 M3 수정 실증 — 컬링 비활성로 부분집합 아님)**.
  4. **상세 패널**: combo(스키마 클러스터 gunzgame) 클릭 → 우측 상세(테이블 115 목록·DB 전체 AI 능동분석 버튼).
  5. **툴바**: 줌 +/−/전체맞춤, 검색('item' → 스키마 2개 매칭·badge), 초기화 — 전부 동작.
  6. **★ 핵심 성능**: 대형 스키마(409 객체) 상태 팬 **60fps vsync-perfect(frames 180·p50 16.7·p95 16.8·max 33.4ms)**. 사용자 리포트 "노드 다수 카메라 이동 버벅임" **근본 해소**(G6 Canvas per-frame CPU 재래스터 → GPU 상주 world transform).
  7. **pageerror 0** 전 과정.
- 부기: win-browser CDP `click` 은 마우스 이벤트만 발생시켜 어댑터 pointer 리스너 미트리거 → PointerEvent dispatch 로 상호작용 구동(실 사용자 마우스는 브라우저가 pointer 이벤트 생성이라 무관, 도구 한계). 스크린샷 evidence: live_graph_roots·live_expanded·live_final.
- 폴백 실증: `window.__META_RENDERER='g6'` + 재로드로 G6 복귀 경로 코드 확인(라이브 토글 미실행 — pixi 정상이라 불필요).

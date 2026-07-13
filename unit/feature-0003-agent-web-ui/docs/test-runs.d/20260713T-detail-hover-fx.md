---
run_at: 2026-07-13T18:00:00+09:00
session: ai/claude/feature-0016-detail-hover-fx
scope: §81 상세 패널 하위 항목 hover 시각 효과 (배포 전 정적/적대 검증)
verdict: PASS (라이브 admin PB-0008 = 배포 후 후속)
---

### Run — 정적 + 적대 검증 (Environment: node vm)
- `node --check` 3개 모듈(graph-renderer-pixi.js·graph-core.js·graph-ctxmenu.js) PASS. 신규 심볼 export/import 정합(_metaGraphHoverPan/HoverPanCancel/SetHoverHighlight/ClearHoverHighlight), 어댑터 메서드(setHoverHighlight/clearHoverHighlight/_hoverLayer) 존재. staged diff 스코프 = graph 4파일 + feature-0016 docs.
- §18.8 적대 검증 패널(subagent): PASS-WITH-FIXES → MAJOR(연속 hover-pan 충돌) 세대토큰으로 수정 · MINOR 3건 수정. XSS/G6폴백/draw스래싱/리스너누수/hit-test/클릭라우팅 = 결함 없음 확인(REV-...-detail-hover-fx-panel).
- 비커밋 설계: hover 효과는 world-space `_hoverLayer` 오버레이 + intent-지연 팬 — 커밋 선택(setSelected)·전체 rebuild(setData/draw) 상태 무접촉이라 기존 그래프 동작 회귀면 없음.

### Run — 라이브 admin PB-0008 (Environment: Windows-browser) — 배포 후 후속(T81.6)
- deploy_scope=included(사전승인) 배포 후 `bin/win-browser.py` 로 5개 상세 뷰 hover 실측 예정:
  ① 카테고리 상세 스키마 클러스터 행 hover→해당 클러스터로 부드러운 카메라 이동 ② 클러스터 상세 테이블 행 hover→테이블 이동
  ③ 테이블 상세 컬럼 행 hover→컬럼 노드 강조 링 ④ 참조 행(.amgr-trace)/⑤ 함수·프로시저(ROUTINE_USES) 행 hover→연결선 강조
  + 연속 hover 시 카메라 비요동(세대토큰)·pageerror 0·팬 부드러움. visual_verification_scope=always 하드 게이트.

### Run — 라이브 admin PB-0008 (Environment: Windows-browser) — 배포 후 실측 (2026-07-13, T81.6 완료)
- 배포: PR #764 → main 84f66608, deploy-web.sh 무중단 롤링(web-a/web-b soak PASS), 서빙 자산 setHoverHighlight 배선 확인·cache-buster ?v=04a485d52d0a.
- 라이브 admin(mysql-gz-dev / gunzgame 409 객체, win-browser.py relay Chrome 150):
  · **카메라 이동**: 클러스터 상세 테이블 행(mailreserve) hover → 카메라가 '출석 관리' 영역에서 mailreserve 로 부드럽게 팬(pan-01→pan-02 스크린샷).
  · **연결선 강조**: 함수·프로시저 행(Game_BuyCashItem_Steam) hover → 굵은 파란 연결선 + 양끝 노드 강조 링(hl-03). mouseleave → 즉시 해제(hl-04).
  · **노드 강조**: 동일 setHoverHighlight nodeKeys 경로(연결선 끝점 링으로 실증) — 컬럼 행 hover 는 미펼침 컬럼→소속 테이블 조상 승격 강조(뷰포트 밖이라 스크린샷 무징표, 경로 동일).
  · pageerror 0(benign ResizeObserver loop warning 만). 신규 ES 모듈 라이브 로드·실행 정상.
- verdict: PASS (라이브 실측).

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

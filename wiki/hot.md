---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-17
---

# Hot Cache

## Last Updated
2026-06-17

## Key Recent Facts
- 서비스 소개 프레젠테이션: `docs/presentation/index.html`(자기완결 HTML 덱, 15슬라이드/7섹션) + `SCENARIO.md`(발표 스크립트).
- 공격적 질문 대응은 발표자 전용 `docs/presentation/OBJECTION-HANDLING.md` 로 분리(덱에는 미노출 — 청중 불편 방지).

## Recent Changes
- 덱 상호작용 발견성: **Ctrl 키 누르면 클릭 가능 항목 주위 glow 가 천천히 fade-in/out**(outline 제거, `@keyframes findglow` `filter:drop-shadow` alpha 0↔.55, prefers-reduced-motion 정적 폴백). **keyup/blur 해제는 snap 아닌 fade-out**(현재 glow 값 inline 고정→애니메이션 중단→reflow→`filter:none` base `transition:filter .5s`로 점진 감소, 재누름 시 타이머 clear+inline reset). + **팝업 열린 채 다른 항목 클릭 시 교체**(`.pop{pointer-events:none}`/`.pop-card{auto}` 오버레이 통과, 빈 곳 클릭=팝업만 닫힘·페이지 유지).
- 덱 정합/표현 보완: mock UI 실제 라벨·"예시 화면" 표기·과장 절제·scale-to-fit(scroll=0)·모든 항목 클릭 상세 팝업(data-explain)·우측 말풍선(딤 없음).
- wiki overview/feature-0002·0003/datasource-registry 2026-06-16 동작 정합화 유지.

## Active Threads
- 정식 배포 불필요(웹 비-서빙 정적 산출물) · 보안 Phase 1~3 로드맵.

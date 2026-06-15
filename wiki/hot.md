---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-15
---

# Hot Cache

## Last Updated
2026-06-15

## Key Recent Facts
- TASK-0256: assistant 가 첨부/쿼리 리뷰·편집 시 변경을 markdown ```diff 블록으로 제시 + 웹 UI 가 라인별 +/- 색 렌더.
- 라이브 base prompt 의 truth = WebSystemPrompts global row(상수=seed/fallback); 프롬프트 변경은 라이브 row 갱신 필수.

## Recent Changes
- agent_core.SYSTEM_PROMPT(diff 지침) + app.js/share.js enhanceDiffBlocks + styles.css/share.css 팔레트.
- 배포: web+ask-worker 재빌드 + 라이브 global row append(백업). PR#209 main 2befd37.

## Active Threads
- 잔여: PB-0008 Windows-browser 시각검증(diff 색 구분, WARN-only).

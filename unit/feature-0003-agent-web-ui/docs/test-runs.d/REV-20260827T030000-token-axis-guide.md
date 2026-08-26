---
run_at: 2026-08-27T12:00:00+09:00
session: ai/claude/feature-0043-mat-token-unify
scope: 인증 축 통일 — static/ai-api-guide.md 문구 변경
verdict: N/A — 화면 렌더 아님(정적 마크다운 문서)
---

# Run — 토큰 축 통일의 웹 자산 변경

Environment: **Windows-browser 미수행 — 검증 대상이 화면이 아니다**

## 사유

이번 cycle 이 건드린 `static/` 자산은 **`ai-api-guide.md` 하나**이고, 그것은 렌더링되는 화면이
아니라 **외부 AI·개발자가 읽는 마크다운 문서**다(`/api/ai/guide` 로 텍스트 그대로 서빙).
버튼·레이아웃·상호작용이 없으므로 브라우저 시각검증이 확인할 대상이 존재하지 않는다.

문서 내용의 정합은 **회귀 테스트로 고정**했다(`test_token_axis_unified.py` — 토큰 형식 힌트,
self-serve 안내, 폐기 표시, 발급 명령이 폐기 맥락 밖에 남지 않을 것).

## 별건: 브리지 UI 시각검증은 여전히 미수행

`static/app/composer.js` 의 대기/폴링 UI 는 이전 cycle 의 대상이며, `win-browser` 브리지
불가로 미수행 상태다 — 사유·해소조건은
`REV-20260827T000500-bridge-poll-ui.md` 를 참조한다. 이번 cycle 이 그 상태를 바꾸지 않았다.

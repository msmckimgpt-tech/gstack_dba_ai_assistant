---
run_at: 2026-08-05T19:24:00+09:00
session: ai/claude/feature-0002-agent-core
scope: 단계 결과 패널 "표시용 발췌" 주석(.step-result-preview-note) 신설 — FR-read-attachment-preview-looks-partial
verdict: PASS (실 Windows Chrome 렌더 확인)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

- 변경 소유: 정본은 `unit/feature-0002-agent-core/docs/`(TASK-20260805T1900,
  CHG-20260805T190000-read-attach-completeness). 본 fragment 는 UI 자산 소유 feature(0003) 측 check #13 기록.
- **대상**: `static/app.js` `_buildStepPreviewNote()` 산출 마크업 + `static/css/profile.css`
  `.step-result-preview-note`.

## 방법 (라이브 무접촉)

1. 브랜치 static 자산만 bind-mount 한 **일회용 web 인스턴스**를 별도 포트로 기동 —
   라이브 web-a/web-b 및 caddy 무접촉:
   `docker compose run -d --rm --no-deps --name pb0008-web-preview -p 18443:8000 \`
   `  -v <worktree>/unit/feature-0003-agent-web-ui/src/static:/app/web/static:ro web-a`
2. **Host 함정**: `TrustedHostMiddleware`(app.py:327 `WEB_ALLOWED_HOSTS`)가 IP Host 를 400 으로
   거부한다. 라이브 도메인을 Windows hosts 로 가로채면 사용자 브라우징을 오염시키므로 쓰지 않고,
   허용 목록에 있는 **`localhost`** 를 WSL2 localhost 포워딩으로 사용했다
   (`https://localhost:18443/...`).
3. `bin/win-browser.py`(relay, Chrome/150.0.7871.128) 로 실 Windows Chrome 구동 → 하네스 페이지
   렌더 → full-page 스크린샷.
4. 하네스는 실 CSS(`base.css`+`profile.css`)를 그대로 로드하고 `_buildStepPreviewNote()` 가 만드는
   마크업(`div.step-result-preview-note`)을 `pre.step-result-preview` 아래에 배치해, **CSS cascade 를
   통과한 실제 렌더**를 검증한다. 인증이 필요한 대화 화면은 자격증명 미보유로 열지 않았다(아래 한정).

## 결과 — PASS

| 케이스 | 확인 |
|---|---|
| A. 발췌 주석(문자수 있음) | 본문 `pre` 아래에 muted 톤으로 렌더, `※ … (결과 1,485자 중 발췌).` 가독 |
| B. 발췌 + 모델측 절단 경고 | 긴 문장이 **자연 줄바꿈**(2줄), 가로 overflow 없음, 컨테이너 폭 유지 |
| C. 잘리지 않은 결과 | 주석 **미표시** — 회귀 확인 |

- 증거: `evidence/20260805T192400-step-preview-note.png`
- 대비 확인: 주석이 본문 `pre`(고정폭·회색 배경)와 시각적으로 구분되고 위계가 낮다(muted).

## 한정 (정직)

- 하네스는 **주석 마크업 + CSS cascade** 를 검증한다. **실 대화 화면의 단계 보기 패널 안에서의
  배치**(토글 펼침 후 표/텍스트 분기 뒤 위치)는 인증 세션이 필요해 이 Run 에서 확인하지 않았다 —
  그 축은 headless `tests/headless/test_step_preview_note.js` ⑦(호출부가 표/텍스트 분기 **바깥**)로
  소스 수준에서 고정했고, **배포 후 라이브 화면에서 최종 확인**한다.
- 다크 테마 대비는 미확인(주석은 `var(--muted, #6b7280)` 사용 — 형제 요소와 동일 토큰 체계).

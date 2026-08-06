---
run_at: 2026-08-06T18:53:00+09:00
session: ai/claude/feature-0003-attach-diff-syntax
scope: 첨부 버전 diff 파일 유형별 구문 하이라이트 (frontend-only)
verdict: PASS
---

# Run — attach-diff 구문 하이라이트

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_diff_syntax_highlight.mjs` — **77 PASS / 0 FAIL**
  - A 유형 판정 14 · B 언어별 토큰 28 · C 원문 무손실 2(표본 13 + fuzz 1,200) ·
    D XSS 7 · E 렌더 통합 19 · F CSS·정본 배선 7
- `tests/verify_attach_version_diff.mjs` — **85 PASS / 0 FAIL** (하이라이트 primitive 실물 주입 후)
- mjs 전수 — **46 suite / 0 failed**
- 뮤테이션 역검증 — **5/5 KILLED** (lang 무시 · JSON key 판정 제거 · CSV catch-all 제거 ·
  미지원도 토글 노출 · innerHTML 조립)

## Environment: Windows-browser (PB-0008) — POST-DEPLOY 실측

- Bridge: relay @ `http://172.26.144.1:9223` · Chrome/150.0.7871.128 · Runner: AI
- 대상: `https://localhost/?conversation=20260806100447-8db00b81` → 첨부 패널 → "버전 3개 ▾" →
  `⇄ 버전 비교` (`.sql` 3버전 체인). 배포본 `6a3b1a97`(hotfix 포함).
- **토큰 색 computed style 실측 PASS** — `code-tok-keyword` `rgb(124,58,237)`(=`#7c3aed`)·weight **600** /
  `code-tok-number` `rgb(15,118,110)`(=`#0f766e`) / `code-tok-comment` `rgb(90,88,82)`(=`#5a5852`).
  ※ 첫 Run(배포본 `6cd4afd2`)에서 keyword 가 `rgb(38,37,30)`/400 이던 결함을 적발 →
  `20260807T0640-attach-diff-syntax-css-fix` 로 해소 후 재실측.
- **토글 PASS** — 라벨 `SQL 구문 색` · 기본 checked · 2열 토큰 12개
- **끔 PASS** — span **12 → 0**, 셀 텍스트 **완전 동일**(원문 무손실 라이브 확인)
- **재켬 PASS** — span 0 → 12, 텍스트 동일
- **단일열 PASS** — 토큰 11개 · `code-tok-keyword` 존재(두 뷰 parity)
- **2버전 체인 PASS** — 다른 첨부(`버전 2개`)에서도 토글 노출 + 토큰 11 · stats `+2 / -8`
- Evidence: `/tmp/win-browser-shots/pb0008-attach-diff-syntax-{01-split-on,02-fixed-split-on,03-unified}.png`

## 미수행 (정직 표기)

- `tests/headless/verify_attach_diff_geometry.py` — 이 환경에 playwright 브라우저 바이너리 부재로
  **미실행**. span 은 inline 이라 열 폭 기하에 영향이 없다는 것이 근거이나 측정하지 않았다.
- **비교 불가 유형의 토글 미노출** — 라이브에 `Kind ∉ (text,csv)` 인 **v2+ 체인이 존재하지 않아**
  실화면 실측이 불가능했다(DB 조회 0건). 하네스 H9(4종: comparable=false·조회실패·동일·행0)·
  H10(에러)·H11(from===to)이 응답 합성으로 커버한다.
- **6,000행 체감** — 그 규모의 라이브 첨부가 없어 미측정. 코드 상한(`MAX_LINE_LEN`)과 하네스 I1/I2
  (최악 0.609ms/line·성장률 1.92×)가 대리 지표다.

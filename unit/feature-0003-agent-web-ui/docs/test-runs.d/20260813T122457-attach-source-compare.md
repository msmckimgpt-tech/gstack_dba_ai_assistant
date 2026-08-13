---
run_at: 2026-08-13T12:24:57+09:00
session: ai/claude-corp/feature-0003-attach-source-compare
scope: attach-source-compare (REQ-20260813-attach-source-compare)
verdict: PASS
---

# Run 1 — 프리뷰 컨테이너 라이브 실측 (PB-0008)

- **Environment: Windows-browser** — 실 Chrome/150, §13.2.9 격리 프리뷰
  (`web-attach-src-cmp-preview` · worktree `src` 마운트 · `http://localhost:18099`).
- 데이터: 라이브 대화 `20260807035225-9cb592cb` / `probe_a.sql` 7버전 체인(id 929…1063).
- 결과: 5단계 전 축 PASS — ① 원문+선택기(126행·옵션 7·기본 `v7 · 이 버전`·diff 컨트롤 0×0)
  ② v1 기준 비교(`v1 → v7` · `+5 / -0` · 2열 · gap 114줄) ③ 같은 버전 복귀 **fetch 0회**
  ④ 목록 버튼 최초→최신(기준 v1 / 비교 v7) ⑤ 비교 모달 같은 버전 → 원문 121행 + 사유 배너.
- 신원 대조: 서빙 `attach-diff.js` 에 `_bodyState`/`_renderSourceBody`/`attach-source-cmp` 존재.
- 세션 격리: 공유 CDP 의 `pages[0]` 이 병렬 세션 탭으로 바뀐 것을 관측 → 자기 생성 탭에서만 수행.
- 증거: `../evidence/pb0008-attach-source-compare-{1..5}*.png`.
- 이월: 배포 후 baked 자산에서 POST-DEPLOY 재실측(Run 2).

# Run 2 — POST-DEPLOY 라이브 실측 (baked 자산)

- **Environment: Windows-browser** — 실 Chrome/150, `https://localhost/`(Caddy → web-a/web-b).
- 배포: PR #1243 → main `c5a27e0d` → `sudo make deploy-web-only`. 양 replica
  `mysql-ai-web:c5a27e0d` · soak 통과 · 엣지 `no upstreams available` **0건** · `/healthz` 200.
- 파리티: 서빙 `attach-diff.js` `_bodyState`(8)·`_renderSourceBody`(5)·`attach-source-cmp`(4) ·
  `composer.js` `oldestNum`(4)·`vnums`(2).
- 결과: 5단계 전 축 PASS — **Run 1(프리뷰)과 차이 0**. 캡처 5매가 Run 1 캡처와 **byte-identical**
  (git dirty 0) = 픽셀 단위 동일 + main mutation 0.
- 라이브 데이터 변경 0(열람 경로만 사용).
- 이월: 없음 — 본 Run 으로 시각검증 축 종결.

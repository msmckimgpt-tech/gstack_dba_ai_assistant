---
run_at: 2026-07-28T12:50:00+09:00
session: ai/claude/feature-0014-asset-stamp-cache-integrity
scope: feature-0003-agent-web-ui 의 변경분 — `src/static_cache.py`(신설, 렌더 표면 없음) · `src/app.py`(mount 래핑) · `src/static/release-notes-data.js`(릴리즈노트 콘텐츠)
verdict: PASS
---

# Run — asset-stamp-cache-integrity 의 feature-0003 변경분

- Date: 2026-07-28
- Environment: `Windows-browser` (`bin/win-browser.py`, 실 Windows Chrome/150 CDP) + `CLI`
- Runner: AI (claude)
- Bridge: `relay` @ `http://172.26.144.1:9223`
- 소유 feature: **feature-0014-zero-downtime-deploy** (본 cycle 의 정본 — 상세 근거·설계 판단은
  [feature-0014 fragment](../../feature-0014-zero-downtime-deploy/docs/test-runs.d/20260728T123000-asset-stamp-cache-integrity.md))

## 변경 표면 분류

| 파일 | 성격 | 렌더 표면 |
|---|---|---|
| `src/static_cache.py` | HTTP 응답 헤더 결정(ASGI 래퍼) | 없음 — DOM·CSS 무변경 |
| `src/app.py` | `/static` mount 를 래퍼로 감쌈 | 없음 |
| `src/static/release-notes-data.js` | 릴리즈노트 **콘텐츠 데이터** (렌더러 `release-notes.js` 는 무변경) | **있음** — 관리 콘솔 > 릴리즈 노트 |

앞의 둘은 픽셀이 없다. 셋째만 PB-0008 대상이며 아래에서 실 화면으로 확인했다.

## PB-0008 — 릴리즈 노트 렌더 (라이브)

`release-notes-data.js` 1개만 라이브 컨테이너에 스테이징(콘텐츠 데이터라 import 그래프 무관 =
blast radius 최소)한 뒤 관리 콘솔 > 릴리즈 노트에서 실 화면 확인:

- 최상단 블록이 **2026년 7월 28일** 로 갱신, 요약문 정상 렌더
- 항목 **3건** — `수정/공통` "업데이트 후에도 예전 화면이 계속 보이던 문제를 고쳤습니다" ·
  `개선/관리 콘솔` 관계도 설명 문구 정리 · `개선/관리 콘솔` 저장할 변경 없을 때 '적용' 바 숨김
- 기존 2026-07-27 이하 블록 무손상(회귀 0), 필터 칩(전체/작업 화면/관리 콘솔/공통)·접기 동작 정상
- 콘솔 에러 0
- 증적: `artifacts/pb0008/feature-0014-asset-stamp-cache-integrity/pb0008-release-notes-0728-20260728.png`

검증 종료 후 스테이징을 **즉시 원복**(이미지 baked 파일로 되돌림, `curl` 로 0728 블록 잔존 0 확인)
— 라이브에 잔재 없음.

## 부수 관측 — 고치려는 버그가 검증 중에 그대로 재현됐다

스테이징 직후 첫 확인에서 화면은 여전히 **2026-07-27** 블록을 보여줬다. 서버는 새 파일을 서빙
(`curl` 로 0728 블록 2건 확인)하는데 브라우저가 `release-notes-data.js?v=<현 스탬프>` 를
`immutable` 로 붙들고 있었기 때문이다. CDP `Network.clearBrowserCache` 로 비운 뒤 즉시 정상 렌더.

이것이 본 cycle 이 없애려는 실패 모드 그 자체이며(같은 URL·다른 내용이 `immutable` 로 굳음),
수정 후에는 스탬프가 불일치하는 응답이 `no-store` 로 나가 이 상태가 **캐시에 들어가지 못한다**.

## 후속 (POST-DEPLOY)

배포 후 결정론 헤더 프로브로 불변식을 라이브 확정한다 — 현 스탬프→`immutable` /
구 스탬프→`no-store`+`x-asset-stamp: mismatch` / vendor pin→`immutable` / 무-`?v=`→미설정.

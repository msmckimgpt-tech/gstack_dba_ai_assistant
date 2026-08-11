---
run_at: 2026-08-07T19:30:00+09:00
session: ai/claude/attach-source-view
scope: 첨부 목록 행 클릭 = 문서 원문 보기 (버전 없는 첨부 포함)
verdict: PASS
---

# Run — attach-source-view (첨부 원문 보기)

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_source_view.mjs` **77 PASS / 0 FAIL**
  (A 원문 무손실 · B 강등·절단·503 도달성·sha · C 하이라이트 parity · D 배선·접근성·press-pair ·
  E 계약·보안 헤더·ranged read·rate limit)
- **뮤테이션 2/2 red** — ① 행 클릭의 버튼 가드 제거 → D6 red ② 서버 D21 pending 게이트 제거 → E10 red
- 선행 하네스 회귀 — `verify_attach_diff_identical_source.mjs` **61** ·
  `verify_attach_version_diff.mjs` **91** · `verify_attach_diff_syntax_highlight.mjs` **113** ·
  `verify_diff_lineno_leak.mjs` **30** 전부 PASS

## Environment: container pytest (`make test`)

- `tests/test_attachment_source_view.py` S1~S6 · E1~E13 신규. 결과는 REPORT.md "Git 동기화 결과" 참조.
- 첫 전량 실행에서 자기 결함 2건 적발(내 E7 단언 자기-red · route 골든 drift) → 수정 후 재실행.

## Environment: Windows-browser (PB-0008) — 격리 컨테이너, 라이브 무접촉

- Bridge: relay @ `http://172.26.144.1:9253` · Chrome/150.0.7871.128 · **전용 인스턴스**
  (`CDP_PORT=9252` / `RELAY_PORT=9253` / `PROFILE=C:\temp\win-browser-attachsrc`) · Runner: AI
- 대상: 라이브 web 이미지 `mysql-ai-web:ca801d46` + **worktree `src` 를 `/app/web` 에 마운트**한 별
  컨테이너(`:18098`). 라이브 web-a/web-b 무접촉.

### 서버 계약

| 축 | 실측 |
|---|---|
| 단일 버전 텍스트 | `viewable=true` · `rows=5` · `stats.lines=5` · `lines_partial=false` · `truncated={source:false,rows:false}` |
| 저장 정책 헤더 | `cache-control: private, no-store` · `x-content-type-options: nosniff` |
| 바이너리(xlsx) | `viewable=false` · `reason=binary` · `rows` 키 **부재**(빈 본문 흉내 없음) |
| 라이브(구코드) 대조 | 같은 첨부에 `GET /api/attachments/1050/source` → **404**(엔드포인트 자체가 없음) |

### 화면 실측

1. **단일 버전 원문** (`pb0008-attachsrc-01-source.png`) — **PASS** (이번 요청의 주 대상)
   - 파일명 클릭 → `문서 원문 — solo_check.sql` · 5행 렌더 · 렌더 텍스트 == 원본 · SQL 토큰 7개
   - `aria-labelledby` 로 제목이 모달 이름 · 원문 표 `aria-label="문서 원문 5행"` ·
     열릴 때 포커스가 닫기 버튼(`share-mgr-close`)
2. **접근성 구조** — **PASS**
   - 행 `role`: `null`(중첩 버튼 회피) · `is-openable`: true(마우스 편의 히트영역)
   - 파일명 버튼: `role=button` · `tabIndex=0` · `aria-label="solo_check.sql 원문 보기"`
3. **키보드 경로 + 포커스 복귀** — **PASS**
   - 파일명 버튼 focus → `Enter` → 모달 열림(5행). 열린 동안 포커스 = `share-mgr-close`.
   - `Escape` → 닫힘 + 포커스가 **`attach-list-item-name-text` (`solo_check.sql`)** 로 복귀.
4. **kind 별 어포던스 문구** — **PASS**
   - `.sql` 행 title `클릭하면 문서 원문을 봅니다` / `.xlsx` 행 title
     `이 형식은 원문 보기를 지원하지 않습니다 — 메타 정보와 다운로드`
5. **바이너리 강등** (`pb0008-attachsrc-02-binary.png`) — **PASS**
   - 안내 + 메타 표(작성 주체·크기·시각·sha) · 원문 표 없음 · **컨트롤 바 `hidden=true`**
     (통계도 토글도 없을 때 빈 띠가 남지 않는다)
6. **행 안 버튼 격리** — **PASS**: ⬇ 클릭 후 `attach-source-backdrop` 미생성
7. **다중 버전 — 버전 이력 👁 진입점** (`pb0008-attachsrc-03-oldversion.png`) — **PASS**
   - `probe_b.sql` 버전 박스에 👁 2개(`aria-label`: "버전 2 원문 보기" / "버전 1 원문 보기")
   - v1 클릭 → 제목 `문서 원문 — probe_b.sql (v1)` · 121행 · 통계 `121줄 · 7KB`
   - docstring 이 주장하던 "구버전은 그 버전의 id 로 연다" 경로가 화면에 실재함을 확인
8. **스크롤 보존** — **PASS**: scrollTop 900(전체 2250) → 구문 색 토글 → **899** (토큰 span 0)

### 정리

- 검증용 대화 `20260807102431-6078cf13` **삭제 완료**(잔존 0) · 격리 컨테이너 제거 ·
  전용 Chrome 인스턴스만 `down`(marker `win-browser-attachsrc` — 공용 Chrome 무접촉).

### 미수행 축 (정직 표기)

- **6,000행 원문의 렌더 체감 미측정** — 최대 표본이 121행이었다. 하이라이트 토글마다 전량 재렌더
  (`paintCodeInto` 동기)이므로 대용량에서의 체감은 추정치일 뿐이다(REPORT §8 후속 등재).
- **원본 1MB cap 절단의 라이브 표본 없음** — 절단 경로는 pytest E5/E10 과 하네스 B5/B6 로만 확인.
  `lines_partial` 이 붙은 화면(제목 "문서 앞부분")은 실 브라우저에서 보지 못했다.
- **스크린리더 실기기 미검증** — `role`/`aria-label`/포커스 이동은 DOM·`document.activeElement` 로만
  확인했다. ux 패널이 지적한 낭독 결과(중첩 버튼 회피의 실효)는 NVDA/VoiceOver 가 정본이다.
- **hover 대비 육안 미판정** — design 패널이 `--bg`→`--surface-2` ΔL ≈ 2% 로 "사실상 안 보인다" 고
  지적했고 어포던스가 border 색과 **파일명 밑줄**에 걸려 있다. 스크린샷으로 밑줄·커서는 확인했으나
  hover 배경 대비 자체는 정량 측정하지 않았다.

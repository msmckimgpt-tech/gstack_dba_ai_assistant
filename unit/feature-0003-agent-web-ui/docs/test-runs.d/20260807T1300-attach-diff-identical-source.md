---
run_at: 2026-08-07T13:40:00+09:00
session: ai/claude/attach-diff-identical-source
scope: 첨부 버전 비교 — 내용이 동일하면 문서 원문 출력
verdict: PASS
---

# Run — attach-diff 내용 동일 시 문서 원문 출력

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_diff_identical_source.mjs` **61 PASS / 0 FAIL**
  (A 원문 무손실 · B 본문 분기·절단 문구·sha 불일치 · C 하이라이트 parity · D **모달 실구동**
  4상태 컨트롤 · E 서버 계약)
- 선행 하네스 회귀 — `verify_attach_version_diff.mjs` **89 PASS** ·
  `verify_attach_diff_syntax_highlight.mjs` **113 PASS**(E8 렌더러 3종으로 개정) ·
  `verify_diff_lineno_leak.mjs` **30 PASS**
- **뮤테이션 3/3 red** — ① 판정면을 초판(`identical` 만)으로 되돌림 → D4·D6 red
  ② 절단 게이트(`clipped`) 무력화 → B8d·B8e·B8f red ③ sha 판정 무력화 → B9·B9b red

## Environment: container pytest (`make test`)

- `tests/test_attachment_version_diff.py` B7·B7b·B7c·E15 신규 포함 전량 — 결과는 REPORT.md
  "Git 동기화 결과" 참조.

## Environment: Windows-browser (PB-0008) — 격리 컨테이너, 라이브 무접촉

- Bridge: relay @ `http://172.26.144.1:9243` · Chrome/150.0.7871.128 · **전용 인스턴스**
  (`WIN_BROWSER_CDP_PORT=9242` / `RELAY_PORT=9243` / `PROFILE=C:\temp\win-browser-attachdiff`
  — 병렬 세션 탭 하이재킹 회피) · Runner: AI
- 대상: 라이브 web 이미지 `mysql-ai-web:f81c5bcb` + **worktree `src` 를 `/app/web` 에 마운트**한
  별 컨테이너(`-p 18099:8000`, `repo_dbnet`+`llm-shared`+`replica-net`). 라이브 web-a/web-b 무접촉.
  자산 스탬프 `?v=dev` 로 서빙 — HTML·JS·CSS 가 한 트리라 모듈 그래프 일관.

### 서버 계약 A/B — 같은 DB·같은 첨부(id 943), 신·구 코드 대조

| 코드 | 응답 |
|---|---|
| **구(라이브 `https://localhost`)** | `identical=true` · `rows=1` · `types=['gap']` — **본문 0줄** |
| **신(격리 `:18099`)** | `identical=true` · `rows=5` · `types=['equal']` · gap 0 · `truncated.rows=false` |

신 응답의 5행을 이어붙인 텍스트가 업로드 원본과 일치(줄 내용 5줄 전량).

### 화면 실측

준비: 새 대화에 같은 줄 내용을 **LF 판**(108B, sha `f0145f9e…`)과 **CRLF 판**(113B, sha
`8fa460cf…`)으로 2회 업로드 → v1/v2 체인. `splitlines()` 비교라 `identical=true` 인데 파일은 다르다
(실서비스에서 가장 흔한 identical 케이스 — 해시가 같으면 업로드가 dedup 하므로 두 버전이 생기지 않는다).

1. **sha 불일치 identical** (`pb0008-attachdiff-03-source.png`) — **PASS**
   - 배너(is-warn): "줄 내용은 같지만 두 파일이 완전히 동일하지는 않습니다(줄바꿈 방식·마지막 줄
     개행 등). 아래는 v2 원문(5줄)입니다."
   - 배지: `줄 차이 없음 · 파일은 다름`
   - 원문 표 `table.is-source` 5행 · SQL 구문 색 토큰 7개 · 하이라이트 토글 노출(`SQL 구문 색`)
   - 2열/단일열 `disabled=true` + `title="비교할 차이가 없는 화면이라 표시 방식을 바꿀 대상이
     없습니다."` · "동일한 줄도 모두 보기" `disabled=true` — **컨트롤이 사라지지 않아 바가 안 흔들린다**
   - 모달 높이가 내용에 맞춰 축소(짧은 문서에 빈 영역 없음 — `max-height: 94vh` 상한 계약 유지)
2. **순수 identical (sha 일치)** (`pb0008-attachdiff-04-same.png`) — **PASS**
   - 배너(is-same): "두 버전의 내용이 동일합니다 — 아래는 문서 원문(5줄)입니다." / 배지:
     `차이 없음 — 원문 표시`
   - ⚠️ **클라이언트 렌더 검증**: 해시가 같은 두 버전은 업로드 dedup 때문에 라이브에서 만들 수
     없어 `fetch` 를 감싸 `to.sha256 = from.sha256` 으로만 바꿔 렌더 경로를 실증했다(서버·DB 무변경).
     서버 계약은 위 A/B 와 pytest B7 이 담당.
   - **§18.8 design F8(초록 어휘 충돌) 판정**: 실화면에서 초록 배너는 전폭·라운드·테두리로 흰
     배경 코드 표와 명확히 분리돼 "추가된 줄" 로 읽히지 않았다 — is-same 유지.
3. **절단 상태** (`pb0008-attachdiff-05-clipped.png`) — **PASS** (같은 방식의 클라이언트 렌더 검증)
   - 배너 2개 모두 is-warn: "문서가 길어 앞쪽 6000행만 표시했습니다." + "비교한 범위에서 두 버전의
     내용이 동일합니다 — 아래는 문서 앞부분 5줄입니다(전체는 더 길 수 있습니다)."
   - 배지: `차이 없음(부분 비교)` · 화면 전체에 **"문서 원문" 0회 · "차이가 많아" 0회**
     (초판이 한 화면에서 서로 반박하던 세 문구가 해소됨)
   - 검증 후 `fetch` 스텁 해제 확인(`window.__origFetch` 부재) + 실데이터 화면 복귀 재확인
4. **정상 diff 회귀** (`pb0008-attachdiff-06-regression-split.png`) — **PASS**
   - 다른 대화의 `probe_b.sql` v1↔v2: 배지 `+1 / -0` · `table.is-split` 6행 · gap "동일한 117줄
     생략 — 펼치기" 버튼 · 2열/단일열·맥락 토글 **전부 활성** · 하이라이트 토글 노출

### 정리

- 테스트 대화 `20260807043438-768ebf89` **삭제 완료**(잔존 0), 격리 컨테이너 제거,
  전용 Chrome 인스턴스만 `down`(marker `win-browser-attachdiff` — 공용 Chrome 무접촉).

### 미수행 축 (정직 표기)

- **6,000행 원문의 실제 체감·렌더 비용 미측정** — 표본이 5줄이었다. identical 이면 `rows` 가 각
  줄을 `left`/`right` 두 벌로 싣는 구조라 대용량에서의 payload·토큰화 비용은 추정치일 뿐이다
  (REPORT.md §8 후속 제안 등재).
- **원본 1MB cap 절단의 라이브 표본 없음** — `truncated.rows` 만 스텁으로 재현했고
  `from_source/to_source` 경로는 하네스 B8f(jsdom)로만 확인.
- 스크린리더 실기기 검증 미수행 — `aria-label`/`aria-hidden` 은 DOM 속성으로만 확인.

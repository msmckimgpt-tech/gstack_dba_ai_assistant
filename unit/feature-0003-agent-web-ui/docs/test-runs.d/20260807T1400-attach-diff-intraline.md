---
run_at: 2026-08-07T14:00:00+09:00
session: ai/claude/attach-diff-intraline
scope: 첨부 버전 diff — 줄 안(글자 단위) 변경 구간 표시
verdict: PARTIAL
---

# Run — attach-diff intra-line 변경 구간

사용자 요청: "여전히 line 단위 차이만 나타나고 있는 상태이며 **각 글자 단위의 차이점은 출력되지
않는** 형태라 작업 완수가 필요합니다" (2026-08-07).

`verdict: PARTIAL` 인 이유는 **PB-0008 라이브 시각검증이 배포 후 잔여**이기 때문이다
(`visual_verification_scope: always`). 아래 축은 모두 PASS.

## Environment: CLI (pytest, 컨테이너 오프라인 이미지)

외부 DNS 단절로 `make test` 의 `dc-build` 가 registry 토큰을 못 받아 실패 → 이미 빌드된
`repo-unittest-agent:pytest-offline` 이미지에 `--network none` 으로 직접 실행(같은 격리 env).

- 전체: **4,018 passed / 0 failed** · `ruff check` clean.
- `tests/test_attachment_version_diff.py` **47 PASS** (신규 B20~B36 17건 — 형제 cycle 이 B7 을 선점해 재번호).
  - B20 왕복 바이트 동치 — 세그먼트를 이으면 원문과 같다(프론트 덧칠의 전제).
  - B21 CJK 글자 단위 — `수정합니다`→`삭제합니다` 에서 `수정`/`삭제` 만 잡힌다(어절 통짜 아님).
  - B22 ASCII 단어 유지 — `beta`→`delta` 가 통 토큰(글자 단위로 쪼개면 색종이).
  - B23 무관 쌍 폴백 — 변경비율 컷에서 **키 자체가 없다**(빈 배열이면 프론트 분기가 갈린다).
  - B24 insert/delete 무세그먼트 · B25 길이 컷에도 줄 단위 diff 유지 · B26 행 상한 통과 행만 계산.
  - B27 자소 묶음 — ZWJ 가족 이모지·결합 악센트·VS·피부톤이 토큰 경계에 갈리지 않는다.
  - B28 예산 초과 → `truncated.intraline=True` + `replace` 40행 전부 생존.
  - B29 정상 diff 는 절단을 주장하지 않는다(배너 늑대소년 방지).
  - E1 절단 **4종 전열거**로 갱신(키 증감이 여기서 먼저 깨지도록).

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_version_diff.mjs` **124 PASS / 0 FAIL** (신규 D1~D8) · mjs 전수 **49 suite OK**.
  D1 2열 마크·텍스트 무손실 / D2 단일열 동일 구간 / D3·D3b 구문 하이라이트 공존 + 토큰 **내부**
  부분 구간 / D4 세그먼트 없으면 종전 경로 / D5·D5b 계약 위반 마킹 거부 / D6 스타일 계약(배경
  금지·skip-ink·쪽별 색·저대비 `-bd` 금지) / D7 서버 단독 산출 / D8 정밀도 절단 배너.
- `tests/verify_attach_diff_syntax_highlight.mjs` **113 PASS / 0 FAIL** — 구문 토큰 대비(G2)
  무회귀 확인. 마크가 배경을 칠하지 않으므로 텍스트 배경면이 3면 그대로다.

## Environment: WSL-headless chromium (playwright) — 실 레이아웃

⚠️ **선행 파손 수리 후** 실행. `tests/headless/verify_attach_diff_geometry.py` 는 구문 하이라이트
cycle 이후 `ReferenceError: detectCodeLanguage is not defined` 로 **전 케이스 미실행**이었다
(main 에서도 동일 재현 — 즉 이 게이트는 그동안 죽어 있었다). 정본 `code-highlight.js` 를 같은
페이지에 인라인해 부활시켰다.

- **53 PASS / 0 FAIL** (부활 46 + 신규 M1~M5 7단언).
  - M1/M1b 좌우 변경 구간이 실제로 마크되고 셀 텍스트 무손실.
  - M2 `inset box-shadow` · `box-decoration-break: clone` 렌더 확인.
  - M2b 좌 `rgb(127,29,29)` / 우 `rgb(21,128,61)` — 쪽별 색(이색형 명도 분리).
  - **M3b 탭 문자 위 192px 도포** — `text-decoration` 밑줄이 0px 였던 결함의 회귀 잠금.
  - M3 마크 배경 `rgba(0,0,0,0)` — **렌더 실측**으로 배경 미칠 확인(규칙이 바뀌어도 잡힌다).
  - M4 행 높이 세그먼트有 19px = 無 19px — 마크가 레이아웃을 바꾸지 않는다(스크롤 앵커 계약 보호).
  - M5 단일열도 같은 구간·같은 쪽 색.
  - 기존 T1~T12 · S1~S6 · B1~B9b 전부 PASS(무회귀).

## Environment: CLI (성능 실측)

`_build_version_diff_view` 를 격리 실행해 계측. **§18.8 backend 패널이 든 최악 입력**을 그대로
재현하고, 상한 통화를 "토큰쌍 예산" 에서 "문자쌍 컷 + 경과시간 + 응답 바이트" 로 바꾼 뒤 재측정:

| 입력 | 패널 실측(수정 전) | 현재 |
|---|---|---|
| 폭 1000 `a,b;c.` 1047행 | 2,997 ms | **5.3 ms** |
| 폭 700 1495행 | 2,367 ms | **4.1 ms** |
| 0채움 CSV 500열 1048행 | 1,079 ms | **2.7 ms** |
| 폭 2000 전량 초과 524행 | 1,039 ms | **2.1 ms** |
| 현실 CSV 142자 6000행 | 547 ms | 510 ms · 1,204행 마크 + 배너 |
| 정밀화 게이트 탈출(1토큰×2000자) | 266 ms | **0.00 ms** |

(수정 전 기준선: intra-line 패스 없이 3~8 ms. 초기 구현은 행 수 상한만 두어 폭 2000자 ×
1500행에서 **411초**까지 갔다 — 상한이 행 수가 아니라 비용이어야 하는 이유.)

시간 예산 보정 — 현실 CSV 142자 6,000행:

| 예산 | 총 소요 | 마크된 행 |
|---|---|---|
| 0.25s | 259 ms | 606 |
| **0.50s (채택)** | **510 ms** | **1,204** |
| 1.0s | 818 ms | 1,860 (여기서 페이로드 상한이 먼저 걸린다) |

모달 한 화면이 ≈40행이므로 1,204행이면 30화면 분량이다.

## Environment: CLI (WCAG 계산)

배경 칠 방식을 **채택하지 않은 정량 근거**. 구문 토큰 9색 × 추가/삭제 행 배경에 마크 tint 를
합성해 재계산:

| 마크 알파 | 최저 대비 | 최저 조합 |
|---|---|---|
| 0.34 | 2.75 | danger/number |
| 0.28 | 3.02 | danger/number |
| 0.20 | **3.40** | danger/number |

어떤 사용 가능한 알파에서도 AA 4.5:1 을 못 넘긴다. 밑줄은 텍스트 배경을 안 바꿔 3면 대비가
그대로이고, 비-텍스트 대비(1.4.11, 3:1)는 `--tag-ok-fg` **4.39** · `--tag-danger-fg` **5.37** 로
충족한다(`--tag-*-bd` 는 1.51 / 1.81 로 미달 — 그래서 `-fg` 를 쓴다).

## Environment: 실 chromium (마크 표현 후보 비교)

`text-decoration` / `inset box-shadow` / `linear-gradient` 3종을 같은 페이지에서 계측:

| 후보 | 탭 `\t\t` | 공백 8개 | 줄바꿈 | `background-color` |
|---|---|---|---|---|
| `text-decoration` (초판) | **0 px** | 48 px | 2조각 OK | transparent |
| **`inset box-shadow` (채택)** | **156 px** | 96 px | 2조각 OK | transparent |
| `linear-gradient` | 156 px | 96 px | 2조각 OK | transparent |

gradient 도 동수치지만 `background-image` 를 쓰므로 "배경을 칠하지 않는다" 는 진술이 흐려진다 —
같은 결과라면 진술이 정확한 쪽을 고른다.

## Environment: Windows-browser (PB-0008) — **미수행 (배포 후 수행)**

**미수행 사유**: 이 변경은 `static/app/attach-diff.js`·`css/{base,chat}.css` 정적 자산이며,
정적 자산은 **web 이미지에 baked** 된다(무번들 ESM + content-hash 스탬프). 따라서 라이브에
반영되기 전에는 실 Windows 브라우저에서 이 코드를 열 수 없다 — 배포 전 PB-0008 은 원리적으로
직전 배포본을 검증하게 되어 이번 변경의 검증이 되지 못한다.

**따라서 이 Run 은 배포 직후 수행하고 본 fragment 에 append 한다** (AC-ADI-9,
`visual_verification_scope: always`). 그때 확인할 축:

- 좌/우 마크가 실제로 보이는가 · 1글자 변경이 200열 CSV 행에서 눈에 걸리는가
- **탭 들여쓰기 변경**에 마크가 그려지는가(이번 cycle 이 고친 P1 — 헤드리스 M3b 는 192px 를
  쟀지만 실 Windows 렌더는 별 축)
- 한글 글자 단위 마크가 자연스러운가 · ZWJ 이모지·국기가 깨지지 않는가
- 구문 하이라이트 on/off 왕복에서 마크가 유지·소멸하는가
- `is-note` 배너가 내용 절단 배너와 시각적으로 구분되는가
- 2열↔단일열 토글에서 같은 구간이 같은 색으로 나오는가

배포 전 근거는 위 WSL-headless chromium Run(54 PASS)이며, §15.4.1 표상 그것은 UI 완료 검증으로
**인정되지 않는다** — 이 fragment 의 `verdict: PARTIAL` 이 그 사실을 담고 있다.

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저** — 위 절대로 배포 후 잔여(AC-ADI-9).
- **라이브 데이터 표본** — 실제 첨부 체인에서의 마크 밀도·가독성은 배포 후 확인.
- **응답 페이로드 증가**(+1.2MB, 6000행 CSV) — 512KB 세그먼트 상한으로 완화했을 뿐 원인은 남음.

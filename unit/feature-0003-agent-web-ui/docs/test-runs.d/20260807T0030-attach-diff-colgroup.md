---
run_at: 2026-08-07T00:30:00+09:00
session: ai/claude-corp/feature-0003-attach-diff-colgroup
scope: unit/feature-0003-agent-web-ui/src/static (app/attach-diff.js · css/chat.css)
verdict: PASS (headless 기하 + 구조 가드) / PENDING (Windows-browser 재검증 — 배포 후)
---

### Run (2026-08-07) — attach-diff-colgroup: diff 표 열 폭 계약을 colgroup 으로

#### 1. 선행 cycle 의 POST-DEPLOY 적발 (이 cycle 의 출발점)

`20260806T2320-attach-version-diff` 배포본(`d46a6b04`)에서 **Environment: Windows-browser** 로
diff 모달을 열어 캡처를 판독한 결과, 좌우 열이 표 폭을 채우지 못하고 가운데로 몰려 양옆에 큰
여백이 생겼다. **자동 게이트는 전부 통과했다**(pytest 22 · mjs 57 · verify-completion PASS) —
레이아웃은 산출물이라 jsdom·정적 스캔·pytest 에 눈이 없다.

라이브 실측(추측 아님):

| 항목 | 값 |
|---|---|
| 표 폭 | 1136px |
| 네 열 폭 | **284 / 284 / 284 / 284** (= 1136/4 균등 분할) |
| 계약상 기대 | 48 / 520 / 48 / 520 |
| 첫 행 | `gap`(`colspan=4`) |

원인: `table-layout: fixed` 는 열 폭을 **첫 행의 셀**에서 가져온다. 첫 행이 colspan 하나면 개별
열 폭이 정의되지 않아 브라우저가 균등 분할하고, CSS 의 `td` width 는 무시된다. 파일 앞부분에
동일 줄이 4줄 이상이면 gap 이 맨 위에 오므로 **거의 항상** 발현한다.

#### 2. 헤드리스 기하 실측 — **Environment: WSL-headless (chromium)**

`tests/headless/verify_attach_diff_geometry.py`(신설) — 실 `attach-diff.js` 렌더 함수 + 실
`css/{base,chat}.css` 를 chromium 에 올려 첫 행이 gap 인 조건에서 열 폭을 측정.

| # | 항목 | 결과 |
|---|---|---|
| 전제 | 첫 행이 gap(결함 발현 조건) | PASS |
| T1 | 줄번호 열 48px 고정 | PASS `[48, 48]` |
| T2 | 좌우 code 열 동폭 + 줄번호 3배 이상 | PASS `[520, 520]` |
| T3 | 열 폭 합 == 표 폭(≤2px) | PASS `합=1136 표=1136` |
| T4 | 단일열 = 48 / 18 / 잔여 | PASS `[48, 18, 1070]` |
| T5 | 같은 행 좌/우 셀 세로 정렬 일치 | PASS |
| T6 | 문서 폭 불변(scroller 안에서만 넘침) | PASS |
| T7 | **colgroup 제거 시 계약 붕괴** | PASS `제거 후 폭=[284,284,284,284]` |

**T7 이 이 하네스의 핵심**이다 — 제거 시 측정값이 **라이브에서 관측된 284×4 와 정확히 일치**한다.
즉 "지금 통과한다" 가 아니라 "그 결함이 들어오면 반드시 red 가 된다" 를 증명한다(vacuous 아님).

#### 3. 구조 가드 — **Environment: CLI (jsdom)**

`verify_attach_version_diff.mjs` A1b 7건: colgroup 유무 · 2열 4 col / 단일열 3 col 클래스 ·
colgroup 이 첫 자식 · CSS 가 `col` 로 폭 선언 · **`td` width 잔존 0**(정본 이중화 금지) ·
결함 조건(첫 행 gap)이 테스트 데이터에 실재. 하네스 **65 PASS**(선행 57 + 8).
전수 mjs **44 suite OK / 0 fail**.

#### 4. pytest — **Environment: CLI**

본 cycle 은 **제품 Python 변경 0**(`git diff --name-only` 에 `src/**/*.py` 없음, 신규 파일은
헤드리스 검증 스크립트 1개로 pytest 수집 대상 아님)이므로 pytest 결과는 선행 cycle 배포본
(`d46a6b04`)과 동일하다. 그 기준선은 정본 러너 `make test` 로 확인한다.

> **정직 기록 — 임시 러너의 함정**: 본 세션의 임시 pytest 러너(격리 컨테이너 + worktree 마운트)는
> `PYTHONPATH` 를 `/work/**` 로 **덮어써** 이미지에 baked 된 `/app`(= `web` 패키지)을 떨어뜨린다.
> 그 탓에 `test_share_redaction_invariant.py` 7건이 `ModuleNotFoundError: No module named 'web'`
> 로 실패했다. **손대지 않은 main 체크아웃에서 동일 재현**되어 코드 회귀가 아님을 확인했고,
> 판정은 정본 `make test` 로 갈음한다. (임시 러너로 얻은 수치를 게이트 근거로 쓰지 않는다.)

#### 5. **Environment: Windows-browser** — 배포 후 재검증 (미수행 사유)

신규/수정 JS 는 스탬프 미주입 + 모듈 캐시 이중 인스턴스로 배포 전 `docker cp` QA 가 불가하다.
배포 후 선행 cycle 의 31항목 + **기하 실측 4항목**(G1 colgroup · G2 줄번호 48px · G3 code 동폭 ·
G4 열 폭 합 == 표 폭)을 재실행한다 — 이번엔 육안이 아니라 **숫자로** 판정한다.

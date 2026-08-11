---
run_at: 2026-08-11T15:00:00+09:00
session: ai/claude/attach-diff-mark-underscore
scope: 줄 안 변경 마크가 `_` 등 밑선 글자를 가리는 문제 수정
verdict: PARTIAL
---

# Run — intra-line 마크 ↔ `_` 충돌 해소

사용자 지적: "변경을 강조하는 하이라이트 밑줄이 특정 문자의 가독성을 떨어뜨리는 이슈가
확인되었습니다. (`'_'` 문자 등)"

`verdict: PARTIAL` — PB-0008 실 Windows 브라우저는 **배포 후 수행**(정적 자산이 web 이미지에
baked 되어 배포 전에는 이 CSS 를 라이브에서 열 수 없다). 아래 축은 모두 PASS.

## Environment: WSL-headless chromium (playwright) — 재현과 판정

**재현(수정 전)**: 실제 `base.css`+`chat.css` 를 그대로 올리고 마크 규칙만 `inset 0 -2px` 로
되돌려 렌더 — `legacy_gy_pay` 가 **`legacygypay` + 밑줄 하나**로, `my_flag, __init__` 의
`__init__` 이 **`init`** 으로 읽혔다. `inset` 은 바를 content box 안쪽 맨 아래에 놓는데,
그 자리가 `_` 글자가 놓이는 자리와 같다.

**후보 4종 비교** (같은 표 맥락 · 같은 폰트/행간, 3× 렌더로 육안 판독):

| 후보 | `_` 가독 | 판정 |
|---|---|---|
| A `inset 0 -2px` (수정 전) | ✗ 바에 흡수 | — |
| E `padding-bottom:2px` + `inset` | ✓ | 인라인 박스 기하를 바꿈 → 탈락 |
| **F `0 2px` 바깥 그림자 (채택)** | **✓** | 기하 불변 · 대비 논거 유지 |
| G 배경색 1px 간격 + 바 | ✓ | 행 배경색(추가/삭제 상이)을 하드코딩해야 함 → 탈락 |
| D `inset 0 2px` (윗줄) | ✓ | 바가 **위쪽 줄에 붙어 보여** 귀속이 흐려짐 → 탈락 |

**채택안 정밀 실측** (device_scale_factor 6):

| 축 | 결과 |
|---|---|
| 글자 영역 마크색 픽셀 | **0** — 바깥 그림자는 border box 안쪽에 그려지지 않는다(대비 논거 유지) |
| span `background-color` | `rgba(0,0,0,0)` |
| 탭 구간 도포 | 있음(밑줄 방식이 0px 였던 원 결함 무회귀) |
| 행 높이 | 마크 有/無 모두 19px |
| 줄바꿈 | `box-decoration-break: clone` 유지 |

## Environment: WSL-headless chromium — 회귀 하네스

`tests/headless/verify_attach_diff_geometry.py` **55 PASS / 0 FAIL**

- **M6 신설** — 마크 구간에 `legacy_gy_pay` 를 넣고 캡처해 **글자 잉크 최하단과 바 최상단 사이
  빈 픽셀 행**을 직접 센다. 실측 **1행** 확보. computed style 로는 잡히지 않고 렌더된 픽셀로만
  드러나는 축이다(§16.6).
- **M2 갱신** — `inset` 이 아니라 `0px 2px 0px 0px` 임을 단언.
- **M3b 클립 보정** — 바가 박스 바깥으로 나가면서, 박스 안쪽만 캡처하던 기존 클립이 마크를
  **0px 로 세어 거짓 FAIL** 을 냈다(하네스 아티팩트). 아래 4px 까지 캡처하도록 고쳐 192px 재확인.
- 기존 T/S/B/M 축 전건 무회귀.

## Environment: node18 + jsdom@22

- `tests/verify_attach_version_diff.mjs` **125 PASS / 0 FAIL** — **D6a2 신설**(`inset` 재도입을
  소스에서 금지). mjs 전수 **50 suite OK**.

## Environment: CLI (pytest)

- `make test` 전 스위트 — 결과는 아래 "검증 결과" 절 참조. CSS·테스트만 변경이라 백엔드 무영향.

## Environment: Windows-browser (PB-0008) — **미수행 (배포 후 수행)**

**미수행 사유**: 변경 대상이 `css/chat.css` 정적 자산이고, 정적 자산은 **web 이미지에 baked**
된다. 배포 전에는 실 Windows 브라우저가 이 CSS 를 열 수 없어, 지금 PB-0008 을 돌리면 직전
배포본(= `inset` 판)을 검증하게 되어 이번 수정의 검증이 되지 못한다. 배포 직후 수행해 본
fragment 에 append 한다.

배포 전 근거는 위 WSL-headless chromium 실측(재현·후보 비교·픽셀 간격·회귀 하네스 55 PASS)이며,
§15.4.1 표상 그것만으로는 UI 완료 검증이 성립하지 않는다.

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저** — 위 절대로 배포 후 수행. 확인할 축: 실제 SQL 첨부 diff 에서 `_` 가
  포함된 식별자(`v_CreatorAuthNo`·`p_SponsorEndTime` 등)의 밑줄 분리 · 탭 들여쓰기 마크 ·
  좌/우 색 · 구문 색 공존.
- **다른 밑선 글자**(예: 결합 밑줄 `U+0332`, 일부 폰트의 `,`·`;` 하강부)는 `_` 만큼 붙지 않아
  별도로 재지 않았다 — 같은 1행 간격이 동일하게 적용된다.

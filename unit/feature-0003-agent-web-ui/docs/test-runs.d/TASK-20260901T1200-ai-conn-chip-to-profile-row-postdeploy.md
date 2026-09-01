---
run_at: 2026-09-01T12:45:00+09:00
session: ai/claude/ai-conn-chip-postdeploy
scope: "연결 칩 프로필 행 이동 — 배포본 자산(주입 없음) POST-DEPLOY 재실측"
verdict: PASS
---

# Run — TASK-20260901T1200-ai-conn-chip-to-profile-row (POST-DEPLOY)

- **Environment**: **Windows-browser**(PB-0008, Chrome/151.0.7922.170 · relay) — `https://localhost/`
- **배포본**: `git_commit = 40340f53` (`/healthz`). PR #1465(`6fac965e`)이 그 조상.
- **선행 Run 과의 차이**: 배포 전 실측은 라이브 페이지에 변경본 CSS 를 **주입**한 상태였다.
  본 Run 은 **주입 없이 서버가 서빙하는 자산 그대로** 측정한다.

## 1. 서빙 자산이 실제로 바뀌었는가

| 확인 | 결과 |
|---|---|
| `css/profile.css` 의 `.sidebar-profile > .ai-conn` 규칙 | 1건 (존재) |
| `css/profile.css` 의 `flex-wrap: wrap` | 5건 |
| `css/chat.css` footer 접힘 규칙에 `.ai-conn` 잔여 | **0건** |
| `index.html` 칩 위치 | `.sidebar-profile`(127행) 안 **144행** — `.composer-footer`(406행)보다 앞 |
| `app/connect-modal.js` 라벨 | `연결 안 됨` · `대기 안 함` · `업데이트 필요` · `대기 중` (접두 없음) |

칩의 런타임 부모가 `.sidebar-profile` 이 아니면 측정 자체를 중단하도록 스크립트에 가드를 뒀다
(`chip not in sidebar-profile` 반환) — 통과했으므로 배포본 마크업이 실제로 그 자리다.

## 2. 4상태 × 계정 4종 16조합 (배포본 자산)

| 계정 | 같은 줄 | 행 높이 | 화살표→칩 | 이름 잘림 | 가로 넘침 | 칩 글꼴 | composer-footer |
|---|:---:|---:|---:|:---:|---:|---:|---|
| `admin` (5자) | ✅ 4상태 전부 | 65px 고정 | 18px 일정 | 없음 | 0 | 10.88px | `none` |
| `mckim` (5자) | ✅ 4상태 전부 | 65px 고정 | 18px 일정 | 없음 | 0 | 10.88px | `none` |
| `bootstrap_admin` (15자) | ⤵ 4상태 전부 | 90px 고정 | — | 없음 | 0 | 10.88px | `none` |
| `verylongaccountname_x` (21자) | ⤵ 4상태 전부 | 90px 고정 | — | ellipsis | 0 | 10.88px | `none` |

칩 폭: 연결 안 됨 76 / 대기 안 함 63 / 업데이트 필요 81 / 대기 중 60 (px).

**배포 전 실측치와 16조합 전부 일치.** 주입 실측이 배포본을 정확히 예측했음이 확인됐다.

## 3. 사용자 제보 해소

- `.composer-footer` 가 **전 16조합에서 `display: none`** — 입력창 아래에 상시 남던 26px 한 줄이
  사라졌다(제보의 "불필요한 여백").
- 칩은 프로필 버튼이 쓰고 남은 여백에 선다(`admin` 기준 화살표에서 18px 오른쪽).
- 증적: `docs/evidence/ai-conn-badge-sidebar/postdeploy-admin-waiting.png`

## 4. 미수행 (정직 표기)

- 실 러너를 띄운 상태 전이(off→idle→on) end-to-end 는 미수행. 본 변경은 칩의 자리와 라벨
  길이에 한정되며 상태 판정 분기(`_paintConn` 조건)는 손대지 않았다. 네 상태의 렌더는 위 표대로
  각각 확인했다.
- 계정명 변형(`mckim`·`verylongaccountname_x`)은 실제 로그인이 아니라 DOM 텍스트 치환으로
  재현했다 — **CSS·마크업은 배포본 그대로**이며 레이아웃 계약(이름 길이 → 줄 배치)을 겨냥한
  측정이다. 서버 상태·대화 데이터 변경 0.

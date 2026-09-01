---
run_at: 2026-09-01T12:00:00+09:00
session: ai/claude/ai-conn-badge-sidebar
scope: "연결 칩을 컴포저 하단 → 사이드바 프로필 행 여백으로 이동 (입력창 아래 상시 여백 해소)"
verdict: PASS
---

# Run — TASK-20260901T1200-ai-conn-chip-to-profile-row

- **Environment**: **Windows-browser**(PB-0008, `bin/win-browser.py` relay → Chrome/151.0.7922.170)
  + 컨테이너 `make test` + node 하네스
- **대상**: `https://localhost/` (repo-web-a/b healthy, Caddy :443)
- **배포 전 실측 방식(정직 표기)**: 정적 자산은 web 이미지에 baked 되므로, 라이브 페이지에
  **변경본 CSS 를 주입하고 칩 노드를 프로필 행으로 옮긴 상태**에서 측정했다. 서버는 건드리지
  않았다(클라이언트 DOM/CSSOM 한정). 배포본 자산으로의 재확인은 POST-DEPLOY fragment 로 남긴다.

## 1. 사용자가 지적한 여백이 실재하는지 — 배포본 실측

| 항목 | 값 |
|---|---|
| `--sidebar-w` | 252px |
| 칩의 부모 | `composer-footer` |
| `.composer-footer` computed display | **`flex`** (= 입력창 아래 26px 한 줄 상시 점유) |
| 프로필 행 여백(`profile-info` 끝 → 화살표) | **10px** (계정 `bootstrap_admin`, 이름이 149px 을 다 씀) |

접힘 규칙 `:has(.ai-conn.hidden)` 이 칩을 예외로 두고 있었고 칩은 늘 보이므로, 규칙은 한 번도
매칭되지 않았다. 제보하신 "불필요한 여백" 이 정확히 그 줄이다.

## 2. 변경본 적용 후 — 4상태 × 계정 4종 16조합

사이드바 252px(기본). 칩 폭은 라벨 길이에 따라 60~81px.

| 계정 | 같은 줄 | 프로필 행 높이 | 화살표→칩 | 이름 잘림 | 가로 넘침 | composer-footer |
|---|:---:|---:|---:|:---:|---:|---|
| `admin` (5자) | ✅ 4상태 전부 | 65px 고정 | 18px 일정 | 없음 | 0 | `none` |
| `mckim` (5자) | ✅ 4상태 전부 | 65px 고정 | 18px 일정 | 없음 | 0 | `none` |
| `bootstrap_admin` (15자) | ⤵ 4상태 전부 아래 줄 | 90px 고정 | — | 없음 | 0 | `none` |
| `verylongaccountname_x` (21자) | ⤵ 4상태 전부 아래 줄 | 90px 고정 | — | ellipsis | 0 | `none` |

- **상태 전환에 따른 튐 0** — 계정마다 네 상태(연결 안 됨 76px / 대기 안 함 63px / 업데이트 필요
  81px / 대기 중 60px)가 **같은 줄·같은 행 높이**를 유지한다. 접두를 남겼을 때는
  «대기 중»(85px)만 들어가고 «연결 안 됨»(101px)·«업데이트 필요»(106px)는 아래 줄로 내려가
  행 높이가 65↔90 을 오갔다.
- **긴 계정명은 우아하게 강등** — 15자·21자 계정은 네 상태 모두 아래 줄로 **일관**되며 가로
  넘침이 0 이다(`flex-shrink: 0` + `flex-wrap` + 이름 ellipsis). 폭 임계값 추정이 아니라 실제
  이름 길이가 판단한다.
- **여백 해소** — 전 16조합에서 `.composer-footer` 가 `display: none`.

### 2.1 화살표 절대배치 시도와 되돌림 (중간 실패 기록)

스크린샷이 지목한 자리가 화살표 *앞* 이라 `.profile-arrow` 를 행 오른쪽 끝에 절대배치 +
`pointer-events: none` 으로 시도했다. 실측에서 두 문제가 드러나 되돌렸다:

1. 칩이 아래 줄인 조합에서 `.profile-trigger` 가 전폭이 되며 **21자 계정명이 화살표 밑으로**
   들어갔다(이름 영역 끝 233px vs 화살표 시작 221px).
2. 화살표 자리를 트리거 `padding-right` 로 비우면 같은 줄 임계가 16px 빡빡해져 `admin` +
   최장 라벨(«업데이트 필요»)이 아래 줄로 밀렸다(247 > 235).

화살표를 흐름에 두면 두 문제가 함께 사라지고, 칩이 프로필 버튼 **밖의 별개 클릭 대상**(연결
모달)이라는 사실도 경계로 드러난다.

## 3. 시각 증적

- `docs/evidence/ai-conn-badge-sidebar/after-admin-waiting.png` — 최종 형태.
  `[아바타] admin / Admin  ›  [● 대기 중]` 이 한 줄, 입력창 아래 여백 없음.

## 4. 자동 검증

- 컨테이너 `make test` — pytest 전건 PASS(rc=0, skip 3), ruff PASS
- `verify_connect_modal_autoclose.mjs` **25/0** · `verify_llm_restriction_surface.mjs` **35/0**
- `test_connect_gate.py` / `test_session_revoke_parity.py` — 계약 방향 전환 후 전건 PASS

## 5. 미수행 (정직 표기)

- **배포본 자산으로의 재확인** — 정적 자산은 web 이미지에 baked 되므로 본 Run 은 주입 실측이다.
  배포 후 `?v=<hash>` 자산으로 같은 16조합을 재측정해 POST-DEPLOY fragment 로 남긴다.
- 실 러너를 띄운 end-to-end 상태 전이(off→idle→on)는 미수행 — 본 변경은 칩의 **자리**와 라벨
  길이에 한정되며, 상태 판정 로직(`_paintConn` 분기 조건)은 손대지 않았다.

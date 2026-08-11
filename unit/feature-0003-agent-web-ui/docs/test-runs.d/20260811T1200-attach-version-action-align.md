---
run_at: 2026-08-11T12:00:00+09:00
session: ai/claude/attach-version-action-align
scope: 버전 이력 행 액션 열 정렬 (비교 버튼 유무에 따른 아이콘 위치 뒤틀림)
verdict: PASS
---

# Run — attach-version-action-align

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_version_action_align.mjs` **34 PASS / 0 FAIL**
  (A 슬롯 수 불변 · B 열별 기능 단일성·순서 · C 불필요 예약 금지 · D 접근성·폭 규칙 ·
  E 형제 목록 — 휴지통은 **실행 테스트**, 활성 목록은 async 라 구조 단언 + PB-0008 좌표)
  — `_renderAttachmentVersionsBox` 를 중괄호 밸런스로 떼어 **실제 실행**하고 행별 슬롯 배열을
  대조한다. 정적 문자열 검사로는 행마다 슬롯이 몇 개 붙는지 알 수 없다.
- **뮤테이션 7/7 red**:
  - **M1 `⇄` 예약 제거** → 슬롯 수 `[3,4,4]` — **사용자 보고 상태를 정확히 재현**(A2·B1·B3·A3·C1 red)
  - **M2 `🗑` 예약 제거** → `can_manage` 가 갈리는 체인에서 `[4,3,4]`(A3·B5 red)
  - **M3 예약 무조건화** → 아무도 삭제 못 하는 체인에 쓰이지 않는 빈 여백 발생(C1 red)
  - **M4 활성 목록 예약 제거** → E8·E9 red
  - **M5 휴지통 예약 제거** → 슬롯 배열 `[2,1,1]`(E4·E5·E6·E9 red)
  - **M6 슬롯을 `↩` 앞에 삽입**(열 순서 파괴) → E6 red — §18.8 ux 가 지목한 "오배치 통과" 구멍
  - **M7 CSS 를 `min-width` 바닥으로 되돌림** → D5·D5b·D5d red
- 선행 하네스 회귀 — `verify_attach_version_diff.mjs` **124** · `verify_attach_source_view.mjs` **77** ·
  `verify_attach_diff_identical_source.mjs` **61** · `verify_attach_diff_syntax_highlight.mjs` **113** ·
  `verify_diff_lineno_leak.mjs` **30** 전부 PASS

## Environment: Windows-browser (PB-0008) — 격리 컨테이너, 라이브 무접촉

- Bridge: relay @ `http://172.26.144.1:9263` · Chrome/150.0.7871.128 · **전용 인스턴스**
  (`CDP_PORT=9262` / `RELAY_PORT=9263` / `PROFILE=C:\temp\win-browser-attachalign`) · Runner: AI
- 대상: 라이브 web 이미지 `mysql-ai-web:bc8d0597` + **worktree `src` 를 `/app/web` 에 마운트**한 별
  컨테이너(`:18097`). 라이브 web-a/web-b 무접촉.

### 좌표 실측 — 이 결함의 정본은 픽셀이다

**2버전 체인** (`probe_b.sql`, `pb0008-align-01-after.png`):

| 행 | 슬롯 | `👁` x | `⬇` x |
|---|---|---|---|
| v2(최신) | `src, slot, dl, del` | **1135** | **1183** |
| v1 | `src, cmp, dl, del` | **1135** | **1183** |

**negative control** — 브라우저 안에서 예약 슬롯(`.attach-list-version-slot`)만 제거
(`pb0008-align-02-negctl.png`):

| 행 | 슬롯 수 | `👁` x | `⬇` x |
|---|---|---|---|
| v2(최신) | 3 | **1159** | 1183 |
| v1 | 4 | **1135** | 1183 |

→ 최신 행의 `👁` 만 **24px 우측으로 밀린다**. 사용자가 보고한 "뒤틀림" 이 정확히 재현되며,
수정본에서는 사라진다.

**4버전 체인** (`probe_a.sql`, `pb0008-align-03-4versions.png`) — 열마다 x 좌표가 **단일값**:

| 열 | x |
|---|---|
| `👁` 원문 | 1135 |
| `⇄` 비교 | 1159 (최신 행은 빈 슬롯) |
| `⬇` 다운로드 | 1183 |
| `🗑` 삭제 | 1207 |

4행 모두 슬롯 수 4. 최신 행만 `cmp: null`(빈 슬롯이 그 자리를 차지).

### 정리

- 검증에 기존 대화의 첨부만 **읽었다**(신규 데이터 생성 0, 삭제 대상 없음) · 격리 컨테이너 제거 ·
  전용 Chrome 인스턴스만 `down`(marker `win-browser-attachalign` — 공용 Chrome 무접촉).

### 폭 규칙 A/B — `min-width`(바닥) vs `flex-basis`(고정)

§18.8 ux 지적 검증. 한 버튼의 글꼴을 16px 로 키운 뒤 같은 열(`👁`)의 x 좌표를 비교:

| 규칙 | 확대된 버튼 실폭 | `👁` 열 좌표 | 정렬 |
|---|---|---|---|
| `flex: 0 0 auto; min-width: 22px` (초판) | **24px** | `[1135, **1133**, 1135, 1135]` | **깨짐** |
| `flex: 0 0 22px; min-width: 0` (채택) | **22px** | `[1135, 1135, 1135, 1135]` | 유지 |

→ `min-width` 는 바닥이라 글리프가 넘으면 그 버튼만 넓어지고, 오른쪽 정렬이라 그 행의 좌측
아이콘이 밀린다. 브라우저 "최소 글꼴 크기" 설정으로 11px 이 승격되는 접근성 경로에서 원증상이
복귀할 수 있었다. **정렬이 폭보다 우선**하므로 `flex-basis` 로 못을 박는다.

**버튼 실폭 실측**(초판 규칙 하): 버전 이력 `👁·⇄·⬇·🗑` 전부 22.00px(11px/4px padding) ·
활성 목록 `⬇·🗑` 전부 22.00px(12px/5px padding) — 리뷰어의 "활성 목록은 24-25px 라 미바인딩"
추정은 **기각**됐으나, 위 A/B 로 구조적 지적 자체는 **확증**됐다.

### 형제 목록(활성 첨부) 좌표 — DOM-level control

라이브에 `can_manage` 가 갈리는 표본이 없어(전 행 true), 브라우저 안에서 한 행의 `🗑` 만 제거해
그 상황을 만들었다(서버·DB 무변경):

| 상태 | `⬇` x (4행) |
|---|---|
| 원본(전 행 🗑 있음) | `[1180, 1180, 1180, 1180]` |
| 🗑 제거 · 예약 없음 | `[**1204**, 1180, 1180, 1180]` — **24px 드리프트** |
| 🗑 제거 · 예약 슬롯 삽입 | `[1180, 1180, 1180, 1180]` — 복귀 |

→ 형제 목록에도 같은 결함이 **실재**하고 같은 예약으로 해소됨을 픽셀로 확인. 검증 후 원복.

### 미수행 축 (정직 표기)

- **`can_manage` 가 행마다 갈리는 라이브 표본 없음** — 그 조합(그룹 대화에서 업로더가 섞인 체인)은
  jsdom 하네스(A3·B5)와 뮤테이션 M2 로만 확인했다. 라이브에서는 전 행 `can_manage=true` 였다.
- **다른 폰트·플랫폼에서의 슬롯 폭 미검증** — `min-width: 22px` 규칙이 글리프 advance 편차를
  흡수하는지는 이 환경(Chrome/Windows)에서만 확인했다.
- **휴지통의 좌표 미실측** — 라이브 휴지통이 비어 있어 실행 테스트(E2~E7)와 뮤테이션 M5/M6 으로만
  확인했다. 활성 목록은 위 DOM-level control 로 좌표를 확보했다.
- **라이브에 `can_manage` 가 갈리는 표본 없음** — 그 조합(그룹 대화에서 업로더 혼재)은 하네스와
  DOM-level control 로 재현했다. 실제 그룹 데이터로는 확인하지 못했다.
- **jsdom 은 레이아웃을 계산하지 않는다** — 하네스의 "슬롯 수가 같다" 는 픽셀 정렬의 **필요조건**
  일 뿐이다. 이 Run 의 좌표 표가 그 간극을 메우는 정본이다.

## Environment: Windows-browser (PB-0008) — POST-DEPLOY 라이브 실측 (배포본 `04f2ecf5`)

- Bridge: relay @ `http://172.26.144.1:9263` · Chrome/150.0.7871.128 · 전용 인스턴스
  (프로필 `C:\temp\win-browser-attachalign`) · Runner: AI
- 대상: `https://localhost/` (라이브) · `web-a`/`web-b` 둘 다 `GIT_COMMIT=04f2ecf5`

### 좌표 — 사용자가 보고한 그 화면

`probe_b.sql` 2버전 체인(v2 최신 = `⇄` 없음, v1 = `⇄` 있음):

| 행 | 슬롯 수 | `👁` x | `⬇` x | `🗑` x | 버튼 실폭 |
|---|---|---|---|---|---|
| v2(최신) | **4** | 1135 | 1183 | 1207 | 22.00px |
| v1 | **4** | 1135 | 1183 | 1207 | 22.00px |

열별 x 좌표가 **단일값**(`👁`1135 · `⇄`1159 · `⬇`1183 · `🗑`1207)이고 두 행의 슬롯 수가 같다.
스크린샷(`pb0008-align-live.png`)에서도 v2 행의 비교 자리가 비어 있고 나머지 아이콘이 세로로
정렬된다 — **사용자가 보고한 뒤틀림이 라이브에서 해소됨**을 확인.

### 정리

- 라이브 데이터 **읽기만**(신규 생성·삭제 0) · 전용 Chrome 인스턴스만 `down`
  (marker `win-browser-attachalign` — 공용 Chrome 무접촉).

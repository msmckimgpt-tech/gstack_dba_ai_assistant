---
run_at: 2026-08-12T18:30:00+09:00
session: ai/root/metadata-pane-refresh
scope: 관리 콘솔 > 지식베이스 > 메타데이터 pane 전체 시각 재구성 (골격 그리드 통합 표 · 공용 폼 프리미티브 · 상태 dot · sticky 열 헤더 · 마감 결함 4종)
verdict: PASS (Environment: Windows-browser, 실 Chrome 150.0.7871.128 relay) — 사전 검증 1건 적발·수정 후 재실측
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

**환경**: `bin/win-browser.py` relay(`http://172.26.144.1:9223`) → **실 Windows Chrome 150.0.7871.128**.

검증 대상이 미머지 브랜치 코드이므로 §13.2.9 격리 경로를 썼다 — 라이브 web 이미지
(`mysql-ai-web:d619259d`)에 **worktree 의 `src/static/` 디렉토리 전체**를 bind-mount 한 격리
컨테이너(`web-metaui-verify`, `http://localhost:18099`, `repo_dbnet`, 평문)로 실측. 라이브
`web-a`/`web-b`·Caddy 는 **무접촉**(검증 중 두 replica 는 다른 세션 배포본
`mysql-ai-web:a68fbbac` 로 healthy 유지). 검증 종료 후 컨테이너 제거.

> ⚠️ **함정 기록** — 처음엔 변경 3파일을 **개별 파일** bind-mount 했는데, 편집기가 파일을 원자
> 교체(새 inode)하므로 마운트가 **끊겨 컨테이너가 구 CSS 를 계속 서빙**했다(`stickyTop: 0px` 가
> 갱신되지 않아 최초 오진). 서빙본을 `curl | grep` 으로 대조해 잡았고, **디렉토리 마운트**로
> 바꿔 해소했다. 단일 파일 마운트 QA 는 이 실패 모드를 항상 동반한다.

**대상 데이터**: 제품 `건즈 글로벌 QA`(`product.gz_qa_g`) × DB `gunzgame` — 골격 **125개 테이블
· 846개 컬럼**(페이지당 30행). 사용자가 스크린샷으로 보고한 것과 같은 화면·같은 규모다.

**라이브 데이터 변경 0**: 입력은 전부 클라이언트 스테이징이며 `설명 입력분 저장`·`등록` 을 한
번도 누르지 않았다. 종료 시점 테이블 설명 목록 = `1건`(`gunzgame.item`) — 사용자 원본 스크린샷과
동일. 용어사전 178건도 불변.

## 1. 통합 표 — 행별 카드 테두리가 사라졌다 (AC-…-2)

가시 30행의 computed border 를 전수 측정. 좌/우/하 테두리 폭과 radius 의 **고유값 집합**:

```
{ "0px/0px/0px/0px/0px",   // 첫 행 (상단 divider 없음)
  "0px/0px/0px/1px/0px" }  // 나머지 29행 (상단 hairline 1px 만)
```

즉 좌·우·하 테두리 `0px` · radius `0px` — 종전 "행마다 1px full border + radius 카드" 가 완전히
사라지고 상단 hairline divider 만 남았다. 사용자 보고의 "격자 노이즈" 의 시각적 본체가 제거됨.

## 2. 열 정렬 — 30행 전부 픽셀 일치 (AC-…-2)

| 측정 | 결과 |
|---|---|
| 입력란 시작 x 편차 (30행) | **0.00px** |
| 입력란 끝 x 편차 (30행) | **0.00px** |
| 상태 열 우측 끝 편차 (30행) | **0.00px** |
| sticky 헤더 '설명' 열 시작 − 입력란 시작 | **0.00px** |

헤더와 데이터행이 CSS 토큰(`--meta-grid-name-w` / `--meta-grid-state-w`) **한 값**을 공유하므로
정렬이 구조적으로 보장된다(두 곳에 숫자를 따로 적는 방식이면 여기서 어긋난다).

## 3. ghost cell → 포커스 halo (AC-…-1, AC-…-3)

기본 상태 (30행 공통):

```
background-color: rgba(0, 0, 0, 0)   // 투명
border-top-color: rgba(0, 0, 0, 0)   // 투명
border-top-width: 1px                // 폭 유지 → hover/focus 시 레이아웃 이동 0
box-shadow: none
```

**실 트러스티드 클릭**(CDP, `admin-meta-bs-table:nth-of-type(3)` 의 설명 칸) 직후:

```
document.activeElement === el : true
background-color: rgb(255, 255, 255)
border-top-color: rgb(37, 99, 235)                        // --primary
box-shadow: rgba(37, 99, 235, 0.12) 0px 0px 0px 3px      // = base.css .field input:focus 와 동일 값
z-index: 1                                                // halo 가 인접 divider 위로
row background: color(srgb 0.145 0.388 0.922 / 0.06)     // :focus-within 행 틴트
```

→ **D1 해소 실증**: 종전 `outline:none; border-color` 단독이던 메타데이터 입력이, 이제 콘솔의
다른 폼(프로필·인증·드로어)과 **같은 3px halo 계약**을 쓴다.

> 본 Run 시점의 `--meta-ring` 은 리터럴 `rgba(...)` 였다. 이후 codex 적대 리뷰 P2-3(토큰 정책)
> 반영으로 `color-mix(in srgb, var(--primary) 12%, transparent)` 파생으로 바꿨고, **값이 바뀌지
> 않았음**은 Run 2 §3 의 합성 픽셀 대조로 확인했다.

단건 편집 폼(용어사전 `+ 새 항목`)에서도 동일 확인 — 첫 입력 computed
`box-shadow: rgba(37,99,235,0.12) 0 0 0 3px` · `transition-property: border-color, box-shadow, background-color`.

## 4. 상태 표시 — raw 글리프 → CSS dot + 시맨틱 색 (AC-…-4)

실 키보드 입력(CDP `type`)으로 상태 전이를 관측:

| | 텍스트 | class | color | ::before 배경 | ::before opacity |
|---|---|---|---|---|---|
| 입력 전 | `비어있음` | `admin-meta-bs-hint` | `rgb(90,88,82)` (`--text-2`) | `rgb(90,88,82)` | `0.42` |
| 입력 후 | `설명 입력됨` | `+ is-filled is-complete` | `rgb(21,128,61)` (`--tag-ok-fg`) | `rgb(22,163,74)` (`--success`) | `1` |

`::before` 는 실제로 `7px × 7px` · `border-radius: 50%` 로 렌더된다. 힌트 텍스트에 `●`/`○`
**raw 글리프 0**(`/[●○]/.test(...) === false`).

## 5. 등폭 토큰 실적용 (AC-…-6)

`.admin-meta-bs-table-name` computed `font-family`:

```
D2Coding, "D2Coding ligature", "Cascadia Code", SFMono-Regular, Consolas,
"Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace
```

→ 하드코딩 스택이 아니라 앱 토큰 `var(--mono)` 가 해소된 값. 같은 화면의 `.admin-meta-code`·
`.admin-meta-bundle-loc` 와 식별자 글꼴이 일치한다.

`+ 새 항목` 버튼 라벨 = ASCII `+ 새 항목` · 페이지 전체 텍스트에 전각 `＋` **0건**.

## 6. 저장 액션 버튼 — 줄바꿈 해소 (AC-…-7)

| 라벨 | 높이 | white-space | scrollWidth / width |
|---|---|---|---|
| `AI 로 설명 일괄 생성` | 24.0px | `nowrap` | 118 / 119.8 |
| `설명 입력분 저장` | 40.0px | `nowrap` | 134 / 133.9 |

사용자 스크린샷에서 2줄로 접혀 있던 `설명 입력분 저장` 이 단일 행으로 렌더되고 라벨 잘림도 없다.

## 7. sticky 열 헤더 — 사전 검증이 결함 1건을 적발했다 (AC-…-2)

### 7-a. 1차 실측 — FAIL (직전 행이 헤더 위에 비침)

`top: 0` 으로 두었더니 헤더가 **`padEdge = 290`** 에 고정됐다. sticky 는 스크롤포트의 *padding
box* 를 기준으로 붙는데 스크롤러 `.admin-detail-col` 의 `padding: 18px 22px` 때문에, 카드 상단
테두리(`272`)와 헤더 사이 **18px 띠로 직전 행이 반쯤 비쳐** 보였다. 캡처 판독으로 적발.

### 7-b. 수정 후 재실측 — PASS

`top: calc(-1 * var(--meta-grid-head-inset))` (=`-18px`) 로 border edge 까지 끌어올렸다.

| 측정 | 값 |
|---|---|
| computed `top` | `-18px` |
| 카드 border edge | `272` |
| `scrollTop=700` 시 헤더 top | **272** (= border edge, 오차 0) |
| `scrollTop=1000` 시 헤더 top | **272** (불변 — 정적이면 −350 이어야 함) |
| 헤더 위 3px 지점 `elementFromPoint` | `admin-pane` (페이지 chrome — **행 콘텐츠 아님**) |
| 패널 `overflow` | `clip` |

`overflow: clip` 이 load-bearing 이다 — 종전 `hidden` 은 패널을 scroll container 로 만들어
자손 sticky 를 무력화한다(신규 헤더와 기존 `.admin-meta-bs-pager` 양쪽 해당). 이 결합은
하네스가 `--meta-grid-head-inset` == `.admin-detail-col` padding-top 대조로 잠갔다.

## 8. columns 서브뷰 — 열 헤더가 숨는다 (설계 의도)

`컬럼 설명` 서브탭 전환 후: `gridHead.hidden = true` · computed `display: none` ·
결과 컨테이너가 상단 변을 되찾음(`border-top-width: 1px`). columns 모드 행은 접힘 헤더
구조라 "설명" 열이 존재하지 않으므로, 없는 열의 라벨을 띄우지 않는다(거짓 정보 방지).

## 9. 증거

- [`evidence/pb0008-metadata-pane-refresh-20260812.png`](../evidence/pb0008-metadata-pane-refresh-20260812.png)
  — 테이블 설명 골격 그리드. sticky 헤더가 카드 상단에 도킹(띠 없음) · 포커스 셀 halo ·
  green dot `설명 입력됨` · 30행 열 정렬.
- [`evidence/pb0008-metadata-form-refresh-20260812.png`](../evidence/pb0008-metadata-form-refresh-20260812.png)
  — 용어사전 단건 편집 폼. 밑줄 서브탭 인디케이터 · 보기 strip pill + 배지 · chevron select ·
  목록 카드 · 포커스 halo.
- [`evidence/headless-metadata-pane-refresh-20260812.png`](../evidence/headless-metadata-pane-refresh-20260812.png)
  — PRE-DEPLOY headless 계측 캡처(보조 게이트, `tests/headless/verify_metadata_pane_refresh_render.py`).

## 10. 미검증 / 이월

- **POST-DEPLOY 라이브 재확인** — 본 Run 은 격리 컨테이너(베이스 이미지 `d619259d`) 기준이다.
  머지·배포 후 라이브 baked 자산에서 1~8 을 재실측해 Run 2 로 append 한다 (JS/HTML 변경 포함
  cycle 이라 `docker cp` 프리뷰가 원리적으로 불충분 — 모듈 캐시·스탬프 미주입).
- 브라우저 확대(200%)·좁은 폭(<720px) 반응형은 미측정. `.admin-meta-form-grid` 는 720px
  미디어쿼리로 1열 전환되나 통합 표의 `clamp()` 열 폭은 실측하지 않았다.

---

# Run 2 — codex 적대 리뷰 반영 후 재실측 (Environment: Windows-browser)

**run_at**: 2026-08-12T19:15:00+09:00 · **verdict**: PASS

codex 적대 리뷰(P1 0 · P2 3)를 전건 반영한 뒤, 변경면을 실 Windows Chrome 150 에서 재확인했다.
격리 컨테이너를 **현재 라이브 이미지 `mysql-ai-web:a68fbbac`** 기준으로 재기동(Run 1 은
`d619259d`)해 베이스 skew 도 줄였다. 라이브 `web-a`/`web-b` 무접촉(검증 중 `d0241c93` healthy).

## 1. 잘린 식별자의 회수 경로 (P2-1)

`컬럼 설명` 서브뷰에서 `gunzgame` 골격 125테이블 로드 → 첫 테이블 펼침:

| 항목 | 실측 |
|---|---|
| 컬럼명 `title` | `["Currency", "Description"]` — 전체 이름 보존 |
| 타입 `title` | `["int", "varchar(128)"]` — 전체 타입 보존 |
| 컬럼 입력란 시작 x 편차 | **0.00px** (고정 폭 정렬 유지) |
| `gridHead.hidden` (columns 모드) | `true` (열 개념 불성립 → 숨김 유지) |

## 2. 동적 라벨의 전각 플러스 (P2-2)

렌더된 페이지 전체 텍스트 스캔 `/＋/.test(document.body.innerText)` → **false**.
정적 markup 3곳 + JS 동적 3곳(empty-state 문구·ENUM '코드 추가' 버튼) 모두 ASCII 로 통일됨.

## 3. 토큰 파생 halo 가 값을 바꾸지 않는다 (P2-3)

`--meta-ring` 을 리터럴 `rgba(37,99,235,.12)` → `color-mix(in srgb, var(--primary) 12%, transparent)`
로 전환했다. **문자열 비교로는 등가를 판정할 수 없다** — Chrome 은 `color-mix()` 를
`color(srgb …)` / `oklab(…)` 로 직렬화한다. 흰 배경 합성 픽셀로 대조:

| 계약 | computed box-shadow | 흰 배경 합성 RGB |
|---|---|---|
| `base.css .field input:focus` | `rgba(37, 99, 235, 0.12) 0px 0px 0px 3px` | `[228, 236, 253]` |
| `.admin-meta-input:focus` (파생) | `color(srgb 0.145098 0.388235 0.921569 / 0.12) 0px 0px 0px 3px` | `[228, 236, 252]` |

**Δ = 1 (한 채널, 1/255)** — srgb `color()` 경로의 반올림이며 지각 불가. 확산은 양쪽 3px,
테두리는 `rgb(37, 99, 235)` 동일. (headless 동일 검사에서는 Δ=0.) `color-mix()` 는 실 Chrome 150
에서 정상 해소되며 halo 가 실제로 렌더된다 — 파생 전환으로 기능이 죽지 않았다.

## 4. 남는 이월 (Run 1 §10 유지)

- **POST-DEPLOY 라이브 재실측** — 여전히 미완. 본 Run 도 격리 컨테이너 기준이다.
- 반응형(확대 200% · 폭 <720px) 미측정.
- 그래프 뷰 pane(공유 `.admin-meta-scope-select`) 실측 미수행.

---

# Run 3 — POST-DEPLOY 라이브 실측 (Environment: Windows-browser)

**run_at**: 2026-08-12T20:05:00+09:00 · **verdict**: PASS — **이월했던 라이브 축 종결**

Run 1·2 는 §13.2.9 격리 컨테이너 기준이었다. PR #1231 머지(main `e250dad7`) →
`make deploy-web-only` 후 **라이브 배포본의 baked 자산**에서 전 축을 재실측했다.
JS/HTML 변경을 포함하는 cycle 이라 `docker cp` 프리뷰가 원리적으로 불충분(모듈 캐시·스탬프
미주입)했고, 이 Run 이 그 사각을 닫는다.

## 배포 파리티

| 항목 | 실측 |
|---|---|
| web-a / web-b 이미지 | 양쪽 `mysql-ai-web:e250dad7` (= main HEAD) |
| 서빙 자산 스탬프 | `css/search-audit.css?v=06bd063c9b98` (신규 주입 — 수기 bump 0) |
| 서빙 HTML 에 열 헤더 markup | 존재 (`metadataBootstrapGridHead` × 2) |
| **엣지 무중단** | `no upstreams available` **0건** (12분 창) — 롤링 중 전면 503 0 |
| 접근 경로 | `https://localhost/admin` (Caddy :443), 실 Chrome 150.0.7871.128 |

## 실측 결과 — 프리뷰와 차이 0

제품 `건즈 글로벌 QA` × `gunzgame` 골격 **125테이블 / 846컬럼**(페이지당 30행).

| 축 | 라이브 실측 | Run 1·2 대비 |
|---|---|---|
| 행 카드 테두리 (30행 전수) | 고유값 `{0/0/0/0/0, 0/0/0/1px/0}` — 좌·우·하 0, radius 0 | 동일 |
| 입력란 시작/끝 x 편차 | **0.00 / 0.00px** | 동일 |
| 상태 열 우측 끝 편차 | **0.00px** | 동일 |
| 헤더 '설명' 열 − 입력란 시작 | **0.00px** | 동일 |
| ghost cell 기본 | bg `rgba(0,0,0,0)` · border `rgba(0,0,0,0)` · width `1px` · shadow `none` | 동일 |
| 포커스(실 트러스티드 클릭) | `color(srgb 0.145098 0.388235 0.921569 / 0.12) 0 0 0 3px` · border `rgb(37,99,235)` · bg `#fff` | 동일(토큰 파생 해소 확인) |
| 상태 전이(실 키보드 입력) | `비어있음` → `설명 입력됨` + `is-filled is-complete` · 라벨 `rgb(21,128,61)` · dot `rgb(22,163,74)` · raw 글리프 **false** | 동일 |
| 상태 dot | `7px` · `border-radius 50%` · opacity `0.42` | 동일 |
| 등폭 토큰 | `D2Coding` | 동일 |
| 저장 액션 버튼 | `AI 로 설명 일괄 생성: h24/nowrap` · `설명 입력분 저장: h40/nowrap` | 동일 |
| sticky 도킹 | computed `top: -18px` · `scrollTop=800` 에서 헤더 top **272 == border edge 272** | 동일 |
| 전각 `＋` (페이지 전체 텍스트) | **0건** | 동일 |

**라이브 데이터 변경 0** — 입력은 클라이언트 스테이징이고 `설명 입력분 저장` 을 누르지 않았다.
종료 시점 테이블 설명 목록 `1건`(`gunzgame.item`) — 사용자 원본 스크린샷과 동일.

## 증거

- [`evidence/pb0008-metadata-pane-refresh-postdeploy-20260812.png`](../evidence/pb0008-metadata-pane-refresh-postdeploy-20260812.png)
  — 라이브 배포본. sticky 헤더 카드 상단 도킹(띠 없음) · ghost cell hover 노출 · 상태 dot 열 정렬.

## 남는 이월 (축소)

- 반응형(확대 200% · 폭 <720px) 미측정 — 통합 표 열 폭이 `clamp()` 라 붕괴 위험은 낮으나 실측 아님.
- 그래프 뷰 pane(공유 `.admin-meta-scope-select`) 실측 미수행 — chevron·halo 개선이 그쪽에도
  적용되며 레이아웃 영향은 우측 padding 확보뿐.

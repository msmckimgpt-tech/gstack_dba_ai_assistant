---
run_at: 2026-07-29T09:30:00+09:00
session: ai/claude-corp/feature-0016-detail-panel-typo
scope: unit/feature-0003-agent-web-ui/src/static/graph/{graph.css,graph-ctxmenu.js} — 상세 패널 목록 행 타이포 위계·리듬·정렬
verdict: PASS (실렌더 정량 대조 — Windows-browser Run 은 사유 명시 후 POST-DEPLOY 이월)
---

### Run (2026-07-29) — detail-panel-typo: 상세 패널 시각 위계 교정 — **Environment: headless Chromium (실 CSS cascade + 레이아웃)**

#### 1. 사용자 리포트

> 작업된 결과를 확인했습니다. 다만, 디자인적으로 모범적이진 않은것처럼, 시각적으로 불편하게 느껴지는데
> 이러한 원인을 파악하고 개선해줄 수 있을까요?

#### 2. 진단 (라이브 배포본 `9cb3d4ea` computed style 실측 — 실제 Windows Chrome 150)

| 요소 | 크기 | 굵기 | 색 |
|---|---|---|---|
| 섹션 헤더 `사용하는 함수·프로시저 (57)` | 12.5px | 700 | `rgb(90,88,82)` |
| 그룹 라벨 `읽기 (39)` | 11px | 600 | `rgb(90,88,82)` |
| **루틴 이름(클릭 대상 = 주인공)** | **10.5px** | 400 | `rgb(90,88,82)` |
| **참조 컬럼(부가정보)** | **13px** | 400 | `rgb(128,125,114)` |

**근본 원인**: 행의 주 라벨에 `.amgr-link` — 즉 **부-액션 버튼 스타일**(`모두 펼치기`·`관계 상세`·`이 노드로 이동` 과
동일한 테두리 10.5px 칩) — 을 재사용했다. 그 결과 ① 목록의 주인공이 패널에서 가장 작아지고 ② 부가정보는
아무 규칙이 없어 base 13px 를 상속해 **주 라벨보다 24% 커지는 위계 역전**이 생겼으며 ③ 테두리 칩 폭이 내용
길이대로 벌어져 우측 경계가 톱니가 되고 ④ 컬럼 목록이 줄바꿈되면 행 높이가 튀어 수직 리듬이 깨졌다.
부수적으로 `h4` 색이 본문 항목과 같은 `--text-2` 라 제목/항목 구분 신호가 없었고, `h4` 안의
`.admin-meta-graph-muted` 가 `font-weight:700` 을 상속해 **"약하게" 의도가 굵게** 렌더됐다.

#### 3. 처리

같은 패널의 검증된 행 관용구(컬럼 섹션 `.amgr-col-select` — 전폭 무테두리 + hover 채움 + 12px)를 채택해
시각 언어를 통일: 신설 `.amgr-rtrow`(전폭 flex 버튼) + `.amgr-rtname`(12px/500, 본문 ink) +
`.amgr-rtcols`(10.5px, 우측 정렬, 폭 상한 38%, 말줄임). 행 = **하나의 버튼**이라 부가정보 영역도 클릭·hover
타깃이 된다(종전엔 이름 칩 밖은 죽은 영역). `h4` 색을 `--text` 로, `h4 .admin-meta-graph-muted` 굵기를 500 으로,
섹션 여백 10→16px·행 li 이중 여백 제거.

**말줄임 무음 손실 차단**: 이름·부가정보 **양쪽 모두** `title` 에 전문을 싣는다. 1차 수정에서 부가정보만
넣어 **이름이 잘리면 전문을 되찾을 길이 없는 결함**을 만들었고, 아래 측정의 `nameTitleOk` 지표가 그것을
`false` 로 적발해 교정했다.

#### 4. 실렌더 정량 대조 (playwright chromium-1208, 실제 패널 기하 323/295px · 57행 재현)

| 지표 | 수정 전 | 수정 후 |
|---|---|---|
| 행 높이 | 19~38px (**2종**) | **25px (1종)** |
| 행 폭 | 133~236px (가변) | **295px (균일)** |
| 우측 경계 x 좌표 | **18종** (톱니) | **1종** (정렬) |
| 주 라벨 | 10.5px / `#5a5852` | **12px / `#26251e`** |
| 부가정보 | **13px** (라벨의 1.24배 — 역전) | **10.5px** (라벨의 0.88배) |
| 섹션 헤더 색 | `#5a5852` (본문과 동일) | **`#26251e`** (본문 ink) |
| h4 내 muted 굵기 | **700** (의도-렌더 역전) | **500** |
| 콘텐츠 높이 | 1664px | 1637px (−1.6%) |
| 말줄임 시 전문 보존 | — | **이름 11/11 · 컬럼 11/11 title 보존** |

증적: `artifacts/feature-0016-detail-panel-typo/render-{before,after}.png`

#### 5. 자동 검증

- **신설 `test_detail_panel_typo.js` 24 PASS / 0 FAIL** — 위계 역전·bold 상속·톱니 경계·말줄임 무음손실·
  `.amgr-link` 재사용 회귀를 CSS 선언 단위로 잠근다. **반증 확인**: 수정 전 `graph.css` 로 실행하면
  **17 FAIL** (테스트가 실제로 이 결함을 잡는다는 증거).
- 그래프 헤드리스 전 스위트 **996 PASS / 0 FAIL** (기존 계약 무회귀 — hover-flow `data-*`·클릭 추적 포함).
- 컨테이너 pytest 전 스위트 **2835 passed / 2 skipped / 0 failed**, ruff clean.

#### 6. §18.8 적대검증 (codex review) — 부수 피해 1건 적발·흡수

- **[P2] 여백 리셋의 특이도 부수 피해** — 1차 수정의 `.admin-meta-graph-sec ul.amgr-list > li { margin: 0 }`
  는 특이도 **(0,2,2)** 라 `.amgr-row { margin: 4px 0 }` **(0,1,0)** 를 눌러, 같은 `ul.amgr-list` 안에 사는
  **관계 상세 카드(`<li class="amgr-row">`)가 서로 붙는** 회귀를 만들었다. `.amgr-dbgrp-allctl` 하단 여백도
  같은 이유로 소실. → 리셋 대상을 마크업의 명시 클래스 `li.amgr-rtli`(루틴 사용 행)로 좁혀 해소.
  `:has(> .amgr-rtrow)` 대신 명시 클래스를 쓴 이유: 셀렉터 지원 여부와 무관하게 대상이 확정된다.
- **실렌더 대조로 확증**(playwright, 카드 3개 + '모두 접기' 컨트롤 재현):

  | | 카드 margin | 카드 실측 간격 | '모두 접기' 하단 |
  |---|---|---|---|
  | 기준선(수정 전) | 3px / 3px | **3px** | 3px |
  | 1차 수정(넓은 리셋) | 0px / 0px | **0px** ← 붙음 | 0px |
  | 최종(좁힌 리셋) | 3px / 3px | **3px** ← 복원 | 3px |

  (카드가 4px 가 아니라 3px 인 것은 `.admin-meta-graph-sec li`(0,1,1)가 `.amgr-row`(0,1,0)를 이기는
  **기존 동작**이며 본 변경과 무관하다 — 기준선과 최종이 동일하므로 회귀 0.)
- 회귀 테스트 ⑤-b 신설(넓은 리셋 부활 차단 + `li.amgr-rtli` 부여 확인). **반증 확인**: 넓은 리셋 변종
  CSS 로 실행하면 ⑤·⑤-b 가 FAIL 한다.

#### 7. Windows-browser Run (PB-0008) — **미수행 사유 명시 + POST-DEPLOY 이월**

- **Environment: Windows-browser — 이번 커밋에서는 미수행.** 사유: 본 변경은 **CSS + JS 동반**이고, 신설
  `.amgr-rtname`/`.amgr-rtli` 마크업이 없으면 새 CSS 가 스타일할 대상이 없어 **JS 없는 CSS-only 주입 QA 는
  대표성이 없다**. 그런데 JS 를 컨테이너 `docker cp` 로 주입하는 QA 는 이 프로젝트에서 asset stamp 미주입 +
  Chrome ES 모듈 캐시로 **구버전이 실행돼 판정이 오염**되는 것으로 알려져 있다(프로젝트 기지식).
- 실제로 주입 QA 를 시도했고 그 한계를 관측했다: 서버 자산이 신버전임은 `fetch(..., {cache:'no-store'})`
  로 확증했으나(`amgr-rtli`/`amgr-rtname`/scoped reset 전부 존재), **브라우저가 렌더한 DOM 에는 신설 클래스가
  0개**였다(`li.amgr-rtli` 0 · `button.amgr-rtrow` 0). 즉 서빙 파일과 실행 코드가 어긋나는 그 함정이 그대로
  재현됐다. 따라서 이 경로의 결과는 판정 근거로 쓰지 않는다.
- **대체 실측**: 실 CSS cascade + 레이아웃 엔진(headless Chromium chromium-1208)으로 §4 의 정량 대조를
  수행했다. CSS 특이도·타입 스케일·flex 말줄임·행 기하는 **엔진이 계산하는 값**이라 이 경로로 충분히 검증되며,
  §6 의 부수 피해도 이 경로가 확증했다. 실 Windows 화면 확인(폰트 렌더링·실 데이터 분포)은 **머지·배포 후
  POST-DEPLOY Run** 으로 수행한다.
- ⚠️ **부수 사고 기록(정직성)**: 주입을 되돌리려 프로젝트 루트에서 `docker compose -f repo/docker-compose.yml
  up -d --force-recreate web-a web-b` 를 실행했는데, 이러면 compose 프로젝트명이 `repo` 가 아닌 상위 디렉터리명으로
  잡혀 잘못된 컨텍스트가 된다. 직후 `repo-{mysql,postgres,pgbouncer,minio}` 가 정지 상태로 관측되고 healthz 가
  `degraded`(`mysql_ok:false`) 로 떨어졌다. **복구**: `repo/` 안에서 `docker compose up -d --no-build mysql
  postgres pgbouncer minio` → healthz `ok`, 4개 전부 healthy. 주입 자산은 배포 이미지에서 원본을 추출해 교체
  (restart 는 컨테이너 fs 를 유지하므로 원복되지 않는다) — 잔재 grep 0 확인. web replica 는 재생성되지 않고
  무중단 유지됐다. **교훈: compose 는 반드시 `repo/` 안에서 호출한다(프로젝트명 = 디렉터리명).**

#### 8. 한계 / 후속

- **행 밀도는 거의 그대로**(1664→1637px, −1.6%). 사용자 불편의 원인은 밀도가 아니라 위계·정렬이라 판단해
  밀도는 손대지 않았다. 57행 1열 유지 — 이름이 최대 236px 라 295px 패널에서 2열은 성립하지 않는다.
- 이름 말줄임이 표본 57행 중 **11행(19%)** 에서 발생한다(부가정보가 38% 폭을 점유하는 행). 전문은 툴팁이
  보존하고 캔버스 관계선이 같은 정보를 중복 제공한다. 실데이터 분포는 POST-DEPLOY 로 재확인.
- 관계 섹션(`참조함`/`참조받음`)의 `.amgr-row` **테두리 카드**는 그대로 뒀다 — 방향 화살표·신뢰 배지·추적
  힌트를 담는 **복합 다중요소 행**이라 카드가 적절하고, "복합=카드 / 단일 항목=평행 행" 이라는 규칙으로
  일관된다(누락이 아니라 의도적 판단).
- **PB-0008 실 Windows 브라우저 검증은 배포 후**에 한다 — JS 를 컨테이너 `docker cp` 로 QA 하면 asset
  stamp 미주입 + Chrome 모듈 캐시로 구버전이 실행돼 판정이 오염된다(프로젝트 기지식).

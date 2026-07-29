---
run_at: 2026-07-29T11:13:00+09:00
session: ai/claude-corp/feature-0016-dpt-postverify
scope: POST-DEPLOY 라이브 검증 — detail-panel-typo (PR #1033 → main 36618965 → 배포 36618965)
verdict: PASS
---

### Run (2026-07-29 11:13) — detail-panel-typo POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상

PR #1033 머지(main `36618965`) → `bin/deploy-web.sh` 롤링 배포(`36618965`, soak PASS, 워커 포함) 후 **배포본**을
실제 Windows Chrome 150 으로 검증. 직전 cycle 커밋에서 "JS 동반 변경은 주입 QA 가 모듈 캐시로 오염된다"는 사유로
이월했던 Windows-browser Run 을 여기서 이행한다.

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`doctor` → `ok: true`, Chrome/150.0.7871.115)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://localhost/admin` · 배포본 healthz `git_commit=36618965` · web-a/web-b = `mysql-ai-web:36618965`
- **자산 스탬프 `?v=7529ce4ce347`** (신규) — `admin.js?v=7529ce4ce347` 로 로드됨을 DOM 에서 확인
- 데이터: `mysql-gz-dev` (건즈 실데이터), 앵커 `gunzgame.character`(직결 루틴 57건)
- Runner: AI
- Evidence: `artifacts/feature-0016-detail-panel-typo/pb0008-postdeploy/` — `pd-routine-rows.png`(수정 후 목록),
  `pd-relation-cards.png`(관계 상세 카드 간격), `live-before.png`(수정 전 같은 화면)

#### 3. 신 코드 실행 증거 (판정 전제)

주입 QA 의 오염(서버 파일은 신버전인데 브라우저가 구 모듈 실행)을 배제하기 위해 **DOM 에 신설 클래스가 실제
존재하는지**를 먼저 확인했다 — `li.amgr-rtli` **57개** · `button.amgr-rtrow` **57개** · 구 칩
`.amgr-link[data-rtuse]` **0개**. 신 코드가 라이브에서 실행 중임이 확정되므로 이하 측정이 유효하다.

#### 4. 측정 결과 (실 Windows Chrome computed style + 레이아웃 기하)

| # | 축 | 결과 |
|---|---|---|
| P1 | **위계 정상화** | 주 라벨 **12px / 500 / `rgb(38,37,30)`** · 부가정보 **10.5px / 400 / `rgb(128,125,114)`** → 부가정보/주라벨 = **0.88배**(종전 1.24배 역전 해소) — PASS |
| P2 | **섹션 헤더 구분** | `h4` **`rgb(38,37,30)` / 700**(종전 `rgb(90,88,82)` = 본문 항목과 동일) — PASS |
| P3 | **muted bold 상속 차단** | `h4` 내 muted **font-weight 500**(종전 700) / `rgb(128,125,114)` — PASS |
| P4 | **행 높이 균일** | 57행 전부 **25px (distinct = 1)**(종전 19~38px 2종) — PASS |
| P5 | **우측 경계 정렬** | 행 우측 x 좌표 **1종**(종전 18종 톱니) — PASS |
| P6 | **부수 피해 회귀 0** (codex R1-P2 흡수분) | 관계 상세 뷰에서 `ul.amgr-list > li.amgr-row` 카드 **57개** 렌더 · margin **3px/3px** · 실측 간격 **3px 균일** = 기준선 그대로. 넓은 리셋이었다면 0px 로 57개 카드가 전부 붙었을 자리다 — PASS |
| P7 | **직전 cycle 무회귀** | 절단 배너(`.amgr-trunc-note`) **0개** · 섹션 헤더 `사용하는 함수·프로시저 (57) · 읽기 39 · 쓰기 18` · 직결 루틴 57건 전량 — PASS |

#### 5. 실화면 판독 (증적 대조)

`live-before.png` 대비 `pd-routine-rows.png`: 종전에는 `Game_AccountCharacterGet` 뒤의 참조 컬럼
`CharNum, CID, Face, Hair, Level, Name, Sex, XP` 가 **주 라벨보다 큰 글씨로 인라인 흐름 + 줄바꿈**되어 다음 항목
영역까지 번졌다. 배포본에서는 같은 정보가 **우측 정렬 · 작은 회색 · 단일 행 말줄임**(`CharNum, CID, Face, ...`)으로
정돈되고, 행 우측 경계가 한 줄로 맞는다. 전문은 툴팁이 보존한다.

#### 6. 판정

**PASS** — 사용자가 지적한 "시각적으로 불편"의 4개 물리적 원인(위계 역전 · 제목/항목 무구분 · 톱니 경계 ·
행 높이 튐)이 배포본 실화면에서 모두 해소됐고, 적대검증이 잡은 부수 피해(관계 카드 간격)도 회귀 없음을 실측으로
확인했다.

#### 7. 미확인 / 후속

- **`REFERENCES` 관계가 있는 노드의 `참조함/참조받음` 섹션**은 현 라이브 데이터에 해당 엣지가 없어(샘플한 6개
  데이터소스·다수 테이블에서 `REFERENCES` 0건) 그 경로의 카드 렌더는 확인하지 못했다. 대신 **관계 상세 뷰의
  `.amgr-row` 카드 57개**로 같은 CSS 표면(= `ul.amgr-list` 안의 카드 여백)을 검증했으므로 부수 피해 축은 덮였다.
- 이름 말줄임 발생 비율의 실데이터 분포는 이번에 정량화하지 않았다(표본 앵커 1개). 다른 데이터소스에서 긴
  루틴명 비중이 높다면 `.amgr-rtcols` 폭 상한(38%)의 재조정 여지가 있다.

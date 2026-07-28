---
run_at: 2026-07-28T17:20:00+09:00
session: ai/claude/feature-0003-hover-rw-postverify
scope: 상세 패널 hover 강조 (방향·읽기/쓰기) 관계선 특정 + 데이터 흐름 애니메이션 — POST-DEPLOY 라이브 재확인 (graph-hover-flow)
verdict: PASS
---

# Run — PB-0008 POST-DEPLOY 라이브 재확인 (Environment: Windows-browser)

- 대상: PR #1016 머지(main `b36493a9`) + `make deploy-web-only` 무중단 롤링(web-a/web-b one-at-a-time
  + Caddyfile reconcile, **post-cutover soak 90s 통과**) 이후의 **main 기반 서빙본**.
- **왜 다시 보는가**: 사전 검증은 §13.2.9 격리 컨테이너(`web-hoverflow-test`:18097)에서 했고, 그
  이미지는 worktree 자산을 `docker cp` + 재스탬프(`?v=dev` → `?v=28b8c65898a7`)한 것이라 **빌드
  파이프라인(Dockerfile COPY → inject_asset_stamp)을 통과한 산출물이 아니다**. main 기반 이미지가
  실제로 같은 코드를 서빙하는지는 별도 사실이므로 배포 후 1회 재확인한다(§16.3 deploy-backed 완료
  기준 — 머지 ≠ 배포 완료).
- Runner: AI (`bin/win-browser.py` relay @ `http://172.26.144.1:9223`, `doctor.ok=true`) ·
  실 Windows Chrome **150.0.7871.115** · 대상 URL `https://localhost/admin?pb=hoverflowpost`
  (라이브 Caddy :443 경유 서빙본).

## 서빙 baked 2중 확인

- 엣지: `GET /healthz` → `{"status":"ok","git_commit":"b36493a9","mysql_ok":true,"pg_ok":true}`.
- 컨테이너: `repo-web-a-1` · `repo-web-b-1` 둘 다 이미지 `mysql-ai-web:b36493a9`,
  `GIT_COMMIT=b36493a9`.
- 자산 스탬프: 서빙 `admin.html` → `admin.js?v=3772f0cfa0c5` (`graph.css`/`styles.css` 동일 스탬프).
- 서빙 모듈 신규 심볼: `graph-renderer-pixi.js` — `_edgeMatchBetween` 3 · `_startHoverFlow` 2 ·
  `_stopHoverFlow` 6 · `_clearHoverLayer` 4 · `flowForward` 3 (**합 18건**) /
  `graph-ctxmenu.js` — `_metaHoverEdgeSpec` 4 · `data-edge-src` 7 · `data-rel-type` 3.
- 런타임 DOM: 관계 상세 27행이 **27/27** 모델 엣지 `data-edge-src`/`data-edge-tgt` 를 싣고,
  루틴 행은 `data-rel-type`(read/write)까지 적재 — 사전 Run 의 행 계약이 서빙본에서 성립.

## 대상 상태

- 데이터소스 `mssql-06656002eda6` → 검색 `AchievementQuest` → 테이블 선택 → `관계 상세`(27행) →
  `🕸 그래프에 펼치기` → **노드 300 · 관계 303** → 컬럼 `AchievementID` 캐럿 펼침 →
  trace **3행**(참조함 2 · 참조받음 1). 사전 Run 과 동일 상태(노드/관계 수·행 구성 일치).
- 왕복 REFERENCES 쌍이 두 행으로 존재(`AchievementQuest.AchievementID → Achievement.UniqueID` /
  `Achievement.UniqueID → AchievementQuest.AchievementID`) — 사용자 리포트의 직접 회귀 케이스.
- 측정: 그래프 캔버스 **1750×1050**, `toDataURL` 픽셀 비교, 채널 최대차 **임계 >16**
  (AA 노이즈 배제). 카메라 고정(`전체 보기` 후 무이동).

## 결과

| # | 축 | 관측 | 판정 |
|---|---|---|---|
| 0 | 대조군(측정 채널) | 무hover 2프레임 **0px** · 전 시나리오 후 원복 **0px** | PASS — 노이즈 0, 이하 비-0 은 전부 실신호 |
| 1 | 방향(같은 노드쌍) | 참조함 vs 참조받음 **73px**, 화살촉이 **상대 끝 ↔ self 끝** 으로 반전(6× 크롭 육안) | PASS |
| 2 | 대상 특정(참조 2행) | 참조함(Achievement.UniqueID) vs 참조함(AchievementReward.AchievementID) **17px** | PASS(#5·줌 대조로 확정) |
| 3 | 기하 비례 대조(줌 3단 확대) | ① **73 → 312px** · ② **17 → 108px** · 대조군 **0px 유지** | PASS — 차분이 줌에 비례 = 서로 다른 호/선 |
| 4 | 흐름 애니(참조선) | 250ms 간격 4구간 **440 / 434 / 440 / 433px** · t=0→1000ms 누적 192px(대시 주기 회귀) | PASS |
| 5 | 읽기/쓰기(ROUTINE_USES) | 쓰기 `spDeleteAchievementQuest` **3,743px** · 읽기 `spGetAchievementQuest` **2,275px** · **쓰기 vs 읽기 5,346px** (bbox 분리: 쓰기 544–722×144–631 vs 읽기 679–760×382–631) | PASS |
| 6 | 대상별 분기(다른 스키마 루틴) | 읽기 `dk_game_release_234.P_AchievementQuest_ReadAll_BackOffice` **2,297px**(bbox 417–722×620–731) · 같은 read 끼리 **3,948px** 차 | PASS |
| 7 | 흐름 애니(루틴선) | 쓰기 250ms **814px** · 읽기 250ms **413px** | PASS |
| 8 | 정리·잔재 | hover 전부 이탈 후 base 대비 **0px** (오버레이·rAF 잔재 0) | PASS |
| 9 | 콘솔 | 전 시나리오 `pageerror` **0건** | PASS |

- **사전 Run 대조**: 사전(격리 컨테이너, stamp `28b8c65898a7`)은 방향 축 441px · 읽기/쓰기 3,517px ·
  흐름 151px. 본 Run 은 캔버스 해상도·줌·카메라가 달라 절대값은 다르나 **구조가 동일**(방향 축 비-0 +
  화살촉 반전, 읽기/쓰기 대량 분리, 흐름 프레임차 비-0, 잔재 0). 정식 빌드 산출물에서도 같은 코드가
  서빙됨을 실증.
- Evidence: `artifacts/shared/win-browser-shots-hoverflow-post/`
  (`post01_dir_arrowhead.png` 방향 3분할 4× · `post02_flow_frames.png` 250ms 3프레임 5× ·
  `post03_rw_and_target.png` 쓰기/읽기/타-스키마 4분할 · `post04_zoom3_dir.png` 줌3단 방향 4분할 ·
  원본 `q**`/`w**`/`z**` 프레임 전량)
- 정리: 라이브 조작은 **읽기·카메라 전용**(검색·펼침·줌은 세션 로컬, 서버 mutation 0) · 자산 주입
  **0건**(서빙본 그대로 관측) · 전용 마커 탭만 사용(다른 세션 탭 무접촉).

## 드라이버 마찰 (실측 기록 — 재사용 시 함정)

1. **"가장 큰 canvas" 휴리스틱은 위장 0-diff 를 만든다.** 관리 콘솔이 대시보드로 리셋되면
   `document.querySelectorAll('canvas')` 최대 면적 후보가 **대시보드 차트 캔버스**가 되고, hover 전후가
   당연히 동일해져 **0px = 기능 실패**로 오판된다(실제로 첫 1:1 줌 측정 전건 0px 이 이 함정이었고 전량
   폐기·재측정했다). → `canvas_shot` 을 `#metadataGraphCanvas` 하위 캔버스로 **못 박고**, 매 캡처마다
   `metadataGraphView` 가시성 + 상태줄 문구를 함께 기록해 무효 캡처를 즉시 raise.
2. **공유 Windows Chrome 의 탭 하이재킹.** origin 접두만으로 탭을 핀 고정하면 병렬 세션이 같은
   `https://localhost/admin` 탭을 몰고 가(관측: 대상이 `gunzlogin` 스키마로 바뀜) 시나리오가 중간에
   무효화된다. → 전용 마커 URL(`?pb=hoverflowpost`)을 핀 키로 사용해 회피(선행 catcluster-polish Run 의
   "전용 새 탭" 교훈과 동일 계열).

## 한계 (정직 표기)

- `prefers-reduced-motion` 정적 폴백은 라이브에서 재확인하지 않았다 — OS 설정 토글이 공유 Windows
  환경에 부작용을 남기므로, 계약은 헤드리스 F 섹션(41 PASS)과 사전 Run 이 잠근다.
- #2 의 fit-줌 차분(17px)이 작은 것은 두 대상 컬럼이 화면상 근접했기 때문인데, **컬럼 노드 미렌더 시
  승격 대상이 동일 상위로 접혔는지**는 직접 단정하지 않았다. 대신 #3(줌 비례 확대 108px)과
  #6(다른 스키마 대상 3,948px 분리)으로 대상 특정 성립을 입증했다.

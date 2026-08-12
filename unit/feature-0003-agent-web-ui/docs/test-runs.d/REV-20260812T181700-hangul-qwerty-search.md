---
run_at: 2026-08-12T18:17:00+09:00
session: ai/claude/hangul-qwerty-search
scope: hangul-qwerty-search — 한/영 자판 교차 검색 (primitive 2벌 + 클라이언트 13곳 + 서버 6경로)
verdict: PASS
---

# Run — hangul-qwerty-search

## 1. 단위 (컨테이너 pytest — agent 이미지 + worktree 마운트)

| 대상 | 결과 |
|---|---|
| `tests/test_hangul_qwerty.py` (신규 39건) | PASS |
| `unit/feature-0002-agent-core/tests/test_graph_search_content.py` (갱신 2건 포함) | PASS |
| 전 스위트 (`feature-0002` + `feature-0003` + `feature-0023`) | **main 기준선과 동일** — 사전 실패 `test_oauth_exhaustion_gate::test_write_failure_after_successful_post_cannot_kill_slot_selection` 1건(`chattr` 부재, 환경 제약)만. 내 변경으로 인한 회귀 0 |

기준선 대조 방법: 같은 이미지·같은 env 로 `repo/`(main `a68fbbac`)를 `:ro` 마운트해 전 스위트를
돌려 실패 집합을 비교. 두 실행의 실패 집합이 동일함을 확인.

## 2. 프론트 하네스 (node, jsdom)

| 대상 | 결과 |
|---|---|
| `tests/verify_hangul_qwerty.mjs` (신규) | **48 PASS / 0 FAIL** |
| feature-0003 mjs 스위트 전체 | **54 종 전건 PASS** |

`verify_hangul_qwerty.mjs` 검증 축: (A) 두벌식 변환 왕복 13쌍 — 사용자 제시 4건
(`ㅎㅋ=gz`·`ㅈ듀=web`·`rmffhqjf=글로벌`·`tmzlem=스키드`) 포함, 겹받침(`닭`·`값`)·복합모음
(`의외`·`뷁`)·쌍자음(`까치`) 경계. (B) 후보 계약(첫 항목 원문 · 중복 없음 · **1자 후보 배제**).
(C) **JS↔Python 정본 매핑표 파일 대조**. (D) 배선 census — 옛 직접 부분일치 잔존 0(전-트리 walk,
파일 목록 하드코딩 없음) + 두 ESM 번들 모두 primitive 소비.

## 3. 뮤테이션 역검증 (하네스 비-vacuous 증명)

| 뮤테이션 | 하네스 반응 |
|---|---|
| 자모 매핑 훼손 (`ㅎ` → `G`) | 3건 FAIL |
| 한→영 후보 생성 제거 | 2건 FAIL |
| (복원 후) | 48 PASS / 0 FAIL |

## 4. 실측으로 포착한 결함 2건 (수정 전 재현)

1. **`from modules import` 는 이미지에서 feature-0002 패키지** — 배포 후에야 ImportError 로
   드러났을 경로. Dockerfile 레이아웃 실판독으로 선차단하고 primitive 를 `shared/` 로 이동.
2. **1자 변환 후보의 오탐** — 기존 하네스 `verify_product_picker_search` 가 `dk` → `아` 가
   "글로벌 라이브" 까지 잡는 것을 FAIL 로 포착. 후보 최소 길이 2자 게이트로 봉인(요청 예시
   4건은 전부 2자 이상이라 무손실).

## 5. 실 브라우저 (PB-0008 · Windows Chrome) — PASS

- **Environment**: Windows-browser · **Runner**: AI
- **Bridge**: relay `http://172.26.144.1:9223` → 실 Windows **Chrome/150.0.7871.128**
- **대상**: 격리 프리뷰 컨테이너 `web-hq-verify`(`http://localhost:18099`, `repo_dbnet`, 평문) —
  라이브 web 이미지 `mysql-ai-web:d0241c93` 에 **본 브랜치의 `src/` + `shared/` 만 bind-mount**.
  라이브 `web-a`/`web-b`·Caddy **무접촉**(검증 중 두 replica 계속 healthy, 종료 후 컨테이너 제거).
- **Evidence**: `/tmp/win-browser-shots/hq-05-dropup-webdu.png`(대화 화면 제품 드롭업 `ㅈ듀`),
  `hq-07-admin-hk-final.png`(관리 콘솔 제품 관리 `ㅎㅋ` — `4 / 19`)

### 5-1. 사용자 보고 화면 ① — 대화 하단 '이 대화의 제품' (종전: "검색 결과가 없습니다")

| 입력 | 결과 |
|---|---|
| `ㅈ듀` | **2건** — (WEB_QA) 국내 웹 - QA · (WEB_G_QA) 글로벌 웹 - QA · `검색 결과 없음` 미표시 |
| `ㅎㅋ` | 3건 — GZ_QA_KR · GZ_DEV · GZ_QA_G (드롭업은 접근 권한 제품만이라 관리 콘솔 4건보다 적음) |
| `tmzlem` | 1건 — (SR_QA) 스키드러쉬 - QA |
| `글로벌`(원문 회귀) | 2건 — WEB_G_QA · GZ_QA_G |

### 5-2. 사용자 보고 화면 ② — 관리 콘솔 > 제품 관리 (종전: "제품이 없습니다")

| 입력 | 결과 (전체 19건 중) |
|---|---|
| `ㅎㅋ` | **4 / 19** — GZ_KR · GZ_QA_KR · GZ_DEV · GZ_QA_G |
| `ㅈ듀` | 2 — WEB_QA · WEB_G_QA |
| `rmffhqjf` | 2 — 글로벌 웹 - QA · 건즈 글로벌 QA |
| `tmzlem` | 1 — 스키드러쉬 - QA |
| `건즈`(원문 회귀) | 4 — 종전과 동일 |
| `dk`(오탐 게이트) | 3 — DK 계열만. `dk` → `아` 후보가 배제되어 "글로벌 라이브" 오탐 **0** |

### 5-3. 서버 검색 경로 (대화 검색 모달 — SQL LIKE)

| 입력 | 결과 |
|---|---|
| `비교`(원문) | 20건 (더 있음) — 첫 결과 "쿼리 리뷰를 진행해주세요…" |
| `qlry`(= `비교` 의 영타) | **20건 (더 있음) — 첫 결과 동일** → 서버 SQL 경로에서 자판 변환 작동 |
| `zzqlryzz`(대조군) | **0건** — 무의미 검색어가 통과하지 않음 |

검색 외 조작 없음(읽기 전용). 대화 본문 검색은 정책상 감사 이벤트(`conversation.search.body`)를
남기므로 프리뷰 세션분 감사 행이 생성된다 — 데이터 변조 아님.

## 7. §18.8 적대 검증 반영 후 재검증 (codex, P1 0 · P2 5 · P3 1 전건 반영)

| 대상 | 결과 |
|---|---|
| `tests/verify_hangul_qwerty.mjs` | **49 PASS / 0 FAIL** (원문 1자 게이트 단언 추가) |
| `tests/test_hangul_qwerty.py` | **41 PASS** (감사·보관 escape 단언 신설) |
| feature-0003 프론트 mjs 스위트 | **54 종 전건 PASS** |
| 전 pytest 스위트 | **main 기준선과 동일** — `test_oauth_exhaustion_gate` 1건(`chattr` 부재)만 |

### 7-1. 쿼리 비용 실측 (P2-5 — 단정 대신 측정)

라이브 PG 에서 대화 검색 WHERE 를 `EXPLAIN (ANALYZE)` 로 재현.

- 모집단: `core_conversations` 349행 · `core_messages` 7,164행 · `messages` 1,956행 (현행 규모)
- 표본: 검색어 쌍 `비교`/`qlry` 1쌍, 각 1회 측정 (**단일 표본**)

| 조건 | Execution Time |
|---|---|
| 후보 1개 (종전 동작) | **108.2 ms** |
| 후보 2개 (원문 + 반대 자판) | **203.2 ms** (약 1.88×) |
| PG `statement_timeout` | 3,000 ms → 사용률 **6.8%** |

데이터가 현재의 10배 규모가 되면 timeout 에 근접할 수 있다 — 후보 상한이 2×이고 원문 2자
게이트가 최악 케이스를 줄이며 per-account 10req/min rate limit 이 유지되지만, **증가 추세는
재평가 대상**으로 REPORT §8 에 등재했다.

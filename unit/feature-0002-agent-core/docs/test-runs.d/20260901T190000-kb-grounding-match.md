---
run_at: 2026-09-01T19:00:00+09:00
session: ai/root/kb-grounding-match
scope: grounding 매칭 — 한도는 «매칭 후보»에, 판정은 «낱말 경계»로 (20260901T190000-kb-grounding-match)
verdict: PASS
---

### Run 0 — 결함 발견 (Environment: 배포본 `5a4d49fc` 안에서 GZ_QA_G 라이브 실측)
사용자 요청으로 직전 cycle 을 GZ_QA_G 로 실측하다 나왔다. **코드 리뷰로는 안 나올 결함**이다 —
둘 다 데이터의 규모·모양에 의존한다.

- 실제 GZ_QA_G task(`t_agRxTIgcrVlElJz3`, ProductId=119)로 `get_task_context` 구동 → 200 OK,
  `product.gz_qa_g` 해소, 번들 1,704자, 2개 층(용어·ENUM / 관계).
- **①** 배포본에서 `_fetch_glossary` 를 직접 호출: scope 총 **239행** 중 **200행만** 로드,
  `ORDER BY length DESC` 라 탈락 39건이 전부 최단 항목 —
  `AID`·`CCU`·`CID`·`CIID`·`PvE`·`재화`·`캐시`·`드롭`·`업적`·`복합키`·`선택도` ….
- **②** 자연스럽게 쓴 질문의 `BillingType` 이 컬럼명 `Type` 에 부분일치 →
  **DK온라인** ENUM(`Achievement.Type`)이 GZ_QA_G 번들에 유입. `Type` 단독으로도 재현.
  라이브 데이터로 `ACIDITY`→`CID`, `PvErr`→`PvE`, `소재화`→`재화` 도 같은 형태임을 확인.

### Run 1 — 경계 규칙 단위 (Environment: bare-runner pytest)
- 15종 표를 손으로 검증(오탐 차단 5 / 정상 유지 10) → 전건 기대 일치.
- `test_grounding_match.py` **13 passed** — ASCII 경계 · 한국어 조사 허용 · 한글 접두 차단 ·
  혼합/구분자 · 빈 입력 · SQL 후보필터(연접항 집합) · 한도 로그 · 배선 4건.

### Run 2 — 뮤테이션 실증 (§16.7 G11-b)
- ⚠ **1차 라운드 전량 무효**. 베이스라인이 RED 였다(내 SQL 재구성이 기존
  `test_role_scoped_read_sql` 을 깼는데, 그 실패가 7종 중 5종을 「KILL」로 보이게 했다).
  **뮤테이션은 baseline green 확인이 전제다** — 빠뜨리면 「전부 잡았다」는 가장 안심되는
  형태의 거짓 신호가 나온다.
- 기존 테스트 정정(파라미터를 위치 대신 **내용**으로 조회) 후 baseline GREEN → 재실행.
- 2차: 3종 생존(N1·N2 배선 미검사 / N8 부분 문자열 단언이 약화 뮤턴트를 통과).
  배선 테스트 3건 + 연접항 집합 단언으로 보강.
- 3차 **9/9 KILL** (N1~N9, baseline GREEN 확인 후).

### Run 3 — 컨테이너 전건
- `COMPOSE_PROJECT_NAME=repo make test` → **rc=0 · FAILED 0 · 6,904 tests** · ruff clean.

### Run 4 — 라이브 전후 대조 (Environment: 라이브 이미지 + 수정 소스 bind-mount, 라이브 무접촉)
같은 질문을 배포본(`repo-web-a-1`)과 수정본(`web-verify-gm`)에 각각 넣었다.

    질문: "gz_qa_g 에서 steam_billing_log 의 status 코드와 billingsummary 의 BillingType,
           증분 복제와 파티셔닝 키"

| 항목 | 수정 전(배포본) | 수정 후 |
|---|---|---|
| `steam_billing_log` · `billingsummary` · `파티셔닝 키` | 실림 | 실림(유지) |
| **`증분 복제`** (질문에 있음) | **누락** — 한도 밖 | **회복** |
| **`Achievement.Type`** (DK온라인, 질문에 없음) | **유입** | **차단** |
| `billingsummary.BillingType` · `steam_billing_log.status` · `steambillinglog.status` | 실림 | 실림(유지) |

**정상 매칭을 하나도 잃지 않고** 누락 1건 회복 + 오탐 1건 차단.

### Run 5 — POST-DEPLOY 라이브 재실측 (배포 `cceb2984`, 2026-09-01 19:2x KST) — **PASS**

- 배포: `sudo -E bin/deploy-web.sh` rc=0 · web-a/b `mysql-ai-web:cceb2984` · 워커 3종
  `mysql-ai-agent:cceb2984`(실물 `ps` 확인, 부분 완료 0) · 대화 스모크 PASS ·
  caddy `no upstreams available` **0건**(무중단).
- **동일 질문 재실측** (배포본 `repo-web-a-1`):
  - 용어 4건 — `steam_billing_log` · `billingsummary` · `파티셔닝 키` · **`증분 복제`(회복)**
  - ENUM 3건 — `billingsummary.BillingType` · `steam_billing_log.status` ·
    `steambillinglog.status`. **`Achievement.Type`(DK온라인) 없음(차단)**
- **한도 밖이라 영영 안 나오던 약어 회복** — 배포 전에는 로드 자체가 안 되던 항목들:

  | 질문 | 매칭 |
  |---|---|
  | `AID 가 뭐야` | `AID` |
  | `CCU 지표 설명해줘` | `CCU` |
  | `PvE 매칭 로그` | `PvE` |
  | `재화를 정산해줘` | `재화` (조사 뒤에 붙어도 매칭) |
  | `복합키 규칙` | `복합키` |

- **오탐 차단 재확인** — 전건 매칭 0:
  `acidity 컬럼 의미`(→`CID` 아님) · `pverr 로그`(→`PvE` 아님) ·
  `아이템 소재화 처리`(→`재화` 아님) · `raidlog 테이블`(→`AID` 아님).

### Run 6 — 미수행분 (정직)
- **답변 품질 변화**: `bootstrap_admin` 은 AI 미연결이라 대화 완주를 못 했다. 증명한 것은
  「프롬프트에 실리는 근거가 정확해졌다」까지다. AI 연결 계정에서의 완주 실측은 후속 항목.
- **`common` 의 DK온라인 전용 ENUM 9건**은 그대로다. 낱말 경계가 오탐 *경로*는 막았지만,
  DK 관련 어휘가 실제로 등장하는 다른 제품 질문에는 여전히 실린다 — 데이터 큐레이션 문제라
  cycle 1 소급 정리와 함께 다룬다.

---

## 소급 정리 적용 (cycle 1 승인분, 2026-09-01 19:45 KST)

### Run 7 — `glossary_tier_sweep.py --apply` (Environment: 배포본 컨테이너, 라이브 PG 쓰기)
- dry-run 재확인이 승인 시점과 **동일**: 범용 69 · 중복 36 · 교차제품 28(보고만).
- 적용: **범용 삭제 69행 · 중복 삭제 36행 = 105행**. `kb_glossary` 739→**634행**.
- 되돌리기 매니페스트 `/shared/glossary-sweep/20260901T194500-glossary-tier-sweep.json`
  (57KB). **복원 경로를 실제로 검증**했다 — 매니페스트 행 키
  (`scope_key`·`term`·`definition`·`role_key`·`source`·`term_tier`)가 `restore()` 가 읽는
  키와 정확히 일치하고, `general`+`duplicate` 105행이 모두 담겨 있다.
- 사용자가 지적한 범용어는 `kb_glossary` 에 **0행** — 정규화 표면형 9종
  (`복제이벤트`·`onlineddl`·`시점복구`·`멱등성`·`트랜잭션`·`cte`·`복합인덱스`·`증분복제`·`실행계획`)
  전건 부재. 대신 `glossary_feedback.status='skipped_general'` **57행**으로 남아 콘솔에서
  「그래도 등록」으로 되살릴 수 있다(조용히 버리지 않는다).
- GZ_QA_G 읽기 캐스케이드 239 → **204행**(한도 200 을 여전히 넘지만, G1 수정으로 한도는
  이제 **매칭 후보**에만 걸리므로 탈락이 발생하지 않는다).

### Run 8 — 정리 후 재실측 (같은 GZ_QA_G 질문)
- 용어 3건 · ENUM 3건. **`Achievement.Type`(DK온라인) 없음** — G2 차단 유지.
- G1 로 회복했던 약어는 **그대로 살아 있다**: `AID`·`CCU`·`PvE`·`복합키` 전건 매칭.
- ⚠ **`증분 복제` 는 이번엔 안 실린다 — 그리고 그게 맞다.** 두 시간 전 G1 수정이 「한도 밖」
  이던 이 용어를 회복시켰는데, 소급 정리가 같은 용어를 **범용어로 판정해 회수**했다.
  같은 용어가 한 세션에서 회복됐다가 제거된 셈이라 모순처럼 보이지만 원인이 다르다 —
  전자는 **버그**(짧다는 이유로 잘림), 후자는 **정책**(범용어는 제품 scope 에 두지 않는다,
  사용자 결정 2026-09-01). 지금은 `common` 큐에 `skipped_general` 로 있으므로,
  GZ_QA_G 의 정의가 제품 고유하다고 판단되면 관리자가 콘솔에서 되살릴 수 있다.

---

## 전역 ENUM 귀속 정정 (사용자 승인, 2026-09-01 20:00 KST)

### Run 9 — 진단
`common`(전역) ENUM **9행이 전부 제품 고유 내용**이었다 — 라벨에 `[DK온라인]`·`[건즈]`·
`[마이크로볼츠 PvE]` 가 명시돼 있다. 전역은 **모든 제품 프롬프트에 주입**되므로, G2(낱말 경계)
이후에도 그 테이블명이 질문에 실제로 나오면 남의 제품이 받는다.

⚠ **9행 전부 `source='manual'`**(2026-07-03 동일자). 사람이 의도해 전역에 넣은 것이라
소급 정리 스크립트의 원칙(「manual 행은 절대 건드리지 않는다」)에 따라 **자율 이동하지 않고
사용자 승인을 받았다**.

### Run 10 — 귀속을 데이터로 확정 (추측 금지)
라벨의 제품명은 **근거가 아니다**(이름은 실체를 안 따라온다). 세 축을 교차했다:

| 테이블 | 근거 | 귀속 |
|---|---|---|
| `Achievement` · `AchievementReward` | `table_descriptions`·`column_descriptions` 에 `product.dk_qa` | **DK_QA** |
| `Mission` | AGE 그래프에 `mysql-gz-qa-global`·`mysql-gz-qa-kr`·`mysql-gz-dev` | **GZ_QA_G · GZ_QA_KR · GZ_DEV** |
| `pverewardinfo` | AGE 그래프에 `mysql-mv-qa-game`·`mysql-mv-dev` | **MV_QA · MV_DEV** |

datasource→제품 매핑은 `WebProductDatasources` 조인으로 해소했다.
⚠ `pverewardinfo` 가 **해소되지 않는 scope**(`mysql-a4f572f222a2`)에도 있었다 — 삭제된
datasource 의 그래프 잔재다. F3(유령 정점 회수)의 실물 사례.

### Run 11 — 적용
- 되돌리기 매니페스트 **먼저** 기록(fail-closed):
  `/shared/glossary-sweep/20260901T200000-common-enum-reattribute.json`(원본 9행 + 계획).
- 결과: 제품 scope 등록 **15행** · `common` 삭제 **9행** → `common` ENUM **0행**.
  `dk_qa` 4 · `mv_qa` 4 · `mv_dev` 4 · `gz_qa_g` 1 · `gz_qa_kr` 1 · `gz_dev` 1.
- ⚠ **9행 → 15행으로 늘었다.** 읽기 캐스케이드가 `[제품, common]` 2단이라 **제품군 티어가
  없기 때문**이다 — 형제 제품 3개가 같은 테이블을 쓰면 3벌을 두는 수밖에 없다.
  중복을 늘리는 방향이지만, 대안(전역 유지)은 **무관한 제품까지** 받는 것이라 더 나쁘다.
  근본 해소는 `product-family` 티어 신설이고 이 cycle 범위 밖이다.

### Run 12 — 제품 격리 실측 (같은 질문, scope 만 바꿔서)

    질문: "Achievement 와 Mission, pverewardinfo 설명해줘"

| scope | 받은 ENUM |
|---|---|
| `product.gz_qa_g` | `Mission.MissionState` |
| `product.dk_qa` | `Achievement.Type` |
| `product.mv_qa` | `pverewardinfo.ri_reward_grade` |
| `product.kr_live` | **(없음)** |

각 제품이 **자기 것만** 받고 무관한 제품은 아무것도 받지 않는다. 정정 전에는 이 질문에
**네 scope 전부가 9행 전체**를 받았다.

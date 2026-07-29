---
run_at: 2026-07-29T17:20:00+09:00
session: ai/claude/feature-0016-graph-detail-cols-postdeploy
scope: 상세 패널 컬럼 3-소스 병합 + 즉석 introspect 보강 — 배포본 라이브 검증 (GDC.7)
verdict: PASS
---

### Run (2026-07-29) — graph-detail-columns POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상

`20260729T0659-graph-detail-columns` cycle 의 **GDC.7**. 사용자 리포트("테이블 내 포함된 컬럼이 '상세
패널' 에서는 출력되지 않거나 일부 누락")가 **실제 배포 자산**에서 해소됐는지, 그리고 기존에 정상이던
경로(그래프 SSOT 컬럼 + 큐레이션 설명)가 회귀하지 않았는지 실 브라우저로 판정한다. 헤드리스는 병합
규칙·보강 게이팅 계약만 고정하고, *패널에 실제로 렌더되는가* 는 판정하지 못한다.

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`doctor` → `ok: true`)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://localhost/admin` → 그래프 뷰 · edge `/healthz` `git_commit=2dd84737` · `mysql_ok`/`pg_ok` true
- 컨테이너: `repo-web-a-1` / `repo-web-b-1` 둘 다 `2dd84737` (one-at-a-time 롤링, `deploy-web.sh` EXIT=0)
- 자산 스탬프: `admin.js?v=ee17174eb8d2`
- 데이터소스 스코프: `mssql-06656002eda6` (mssql-qa-idc, 스키마 137개)
- Runner: AI
- Evidence: `artifacts/feature-0016-metadata-graph/20260729-graph-detail-columns/` 3매
  (`01_detail_columns_35.png` 리포트 케이스 · `02_cols_tail_secondrate8.png` 목록 끝 ·
  `03_curated_desc_preserved.png` 큐레이션 설명 보존)

#### 3. 신 코드 실행 증거 (판정 전제)

주입 QA 오염(서버 파일은 신버전인데 브라우저가 구 모듈 실행)을 배제하기 위해 **배포 이미지 자산 내용**을
먼저 확인했다.

| 시점 | web-a | web-b |
|---|---|---|
| 배포 전 (`cb06a4e3`) | `_metaDetailMergeColumns` **0회** | **0회** |
| 배포 후 (`2dd84737`) | **2회** | **2회** |

즉 서빙 자산이 신 구현이며, 롤링 중 한쪽만 갱신된 상태에서 판정하지 않았다.

#### 4. 판정 — 리포트 케이스 (그래프 미투영 경로)

**`cc_pyron.DT_ItemEnchantInfo`** — 사용자 스크린샷과 **동일 노드**. 그래프 `HAS_COLUMN` = **0**,
실 데이터소스 컬럼 = **35**.

| # | 항목 | 실측(배포본) | 판정 |
|---|---|---|---|
| ① | **컬럼 섹션 존재** | 헤더 `컬럼 (35) ⓘ` 렌더 — 종전엔 섹션 자체가 없었다(사용자 스크린샷: 헤더·FQN·"(설명 없음)"·"AI 능동 분석"뿐) | **PASS** |
| ② | **개수 정합** | 패널 목록 행 **35개** = 데이터소스 `INFORMATION_SCHEMA.COLUMNS` 실제 컬럼 수와 **일치** | **PASS** |
| ③ | **순서(ordinal)** | `UniqueID → SocketNum → EnchantType → FirstModuleID1 → FirstRate1 → …` 마지막 `SecondRate8` — 스키마 ORDINAL_POSITION 순 = 캔버스 ERD 배치와 동일 | **PASS** |
| ④ | **자료형 표기** | `UniqueID — bigint` / `SocketNum — int` 등 introspect 산출 자료형이 설명 자리에 표기 | **PASS** |
| ⑤ | **캔버스 불변** | 상세를 여는 것만으로 캔버스에 이 테이블의 컬럼이 펼쳐지지 않음(모델 무오염 계약) | **PASS** |

패널 헤더의 FQN 이 `cc_pyron.DT_ItemEnchantInfo`, 설명이 `(설명 없음 — 해당 서브탭에서 추가)` 로
사용자 스크린샷과 동일한 상태에서 **컬럼 섹션만 새로 채워졌다** — 대조가 명확하다.

#### 5. 판정 — 회귀 검증 (그래프 SSOT 경로)

**`dk_data_release.Item`** — 그래프 `HAS_COLUMN` = **75**(스코프 내 최다). 즉 보강이 필요 없는,
기존에도 정상이던 경로.

| # | 항목 | 실측 | 판정 |
|---|---|---|---|
| ⑥ | **개수 불변** | `컬럼 (75)` — 그래프 정점 수와 동일(introspect 로 부풀거나 줄지 않음) | **PASS** |
| ⑦ | **큐레이션 설명 보존** | `TemplateID — 아이템의 고유 템플릿 식별자` · `SortNum — 아이템 목록에서의 정렬 순서` · `Grade — 아이템의 등급` · `Weight — 아이템의 기본 무게` … 자료형 문자열로 **덮이지 않았다** | **PASS** |
| ⑧ | **다른 섹션 불변** | `사용하는 함수·프로시저 (20) · 읽기 1` 섹션 정상 렌더 | **PASS** |

⑦ 이 병합 우선순위 규칙(①그래프 SSOT > ③introspect)의 라이브 확증이다 — 규칙이 뒤집혔다면 큐레이션
설명 자리에 `int`/`nvarchar` 가 들어갔을 것이다.

#### 6. 판정 — codex P2-2 수정의 라이브 확증 (같은 키 재선택 race)

같은 노드(`cc_pyron.DT_ItemEnchantInfo`)를 **80ms 간격으로 연속 선택**해 이전 보강 요청이 늦게 도착하는
상황을 유도했다.

| # | 항목 | 실측 | 판정 |
|---|---|---|---|
| ⑨ | **패널 정합** | 재선택 후에도 `컬럼 (35)` · 첫 `UniqueID — bigint` · 끝 `SecondRate8 — int` — 낡은 스냅샷으로 덮이지 않음 | **PASS** |
| ⑩ | **pageerror** | 전 조작 구간(검색 → 그룹 펼침 → 노드 선택 → 재선택 → 스코프/노드 전환) 누적 **0건** | **PASS** |

수정 전 구현이라면 이전 요청이 `lastDetailKey` 가드를 통과해(키가 같으므로) 캡처해 둔 낡은
`nodes/edges/meta` 로 새 패널을 덮어썼을 지점이다.

#### 7. 정직 표기 — 이번 Run 이 확인하지 **않은** 것

- **empty-state 실패 문구**(introspect 불가 데이터소스에서 "조회 실패 사유" 표시)는 라이브에서 재현하지
  못했다 — 검증 스코프의 데이터소스가 전부 연결 정상이라 실패 경로가 발생하지 않았다. 이 축은 헤드리스
  계약(테스트 ⑫·⑭)으로만 고정돼 있다.
- **`truncated` 보강 트리거**(관계 과다 테이블에서 컬럼이 부분만 오는 케이스)도 이번 표본에서는 발생하지
  않았다(두 대상 모두 절단 없음). 게이팅 자체는 헤드리스 ⑧ 이 고정한다.
- 위 두 축은 **정상 경로가 아니라 예외 경로**라 라이브 재현에 특정 조건(연결 실패 datasource · cap 초과
  관계)이 필요하다. 사용자 리포트의 주 증상과 회귀 축은 위 §4·§5 로 판정됐다.

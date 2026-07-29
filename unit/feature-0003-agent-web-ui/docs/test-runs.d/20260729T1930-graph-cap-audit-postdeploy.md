---
run_at: 2026-07-29T19:30:00+09:00
session: ai/claude/feature-0016-cap-audit-postdeploy
scope: 상한 전수 감사 — 배포본 라이브 검증 (GCA.7)
verdict: PASS
---

### Run (2026-07-29) — graph-cap-audit POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상

`20260729T0900-graph-cap-audit` cycle 의 **GCA.7**. 사용자 리포트 2건("여전히 컬럼이 누락된 항목이
있으며, **노드 또한 누락된 대상**이 확인되었습니다")과 방향 지시("개수를 줄여 출력하는 최적화는 다른
방향으로")가 **실제 배포 자산**에서 해소됐는지, 그리고 상한을 푼 뒤의 **부하**가 감당 가능한지 판정한다.

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`doctor` → `ok: true`)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://localhost/admin` → 그래프 뷰 · edge `/healthz` `git_commit=defcdad9` · `mysql_ok`/`pg_ok` true
- 컨테이너: `repo-web-a-1`/`repo-web-b-1` = `defcdad9`(둘 다 `introspectMiss` 서빙 확인) ·
  `repo-insight-worker-1` = `mysql-ai-agent:defcdad9`(런타임 `_ROUTINE_CAP_DEFAULT = 20000` 확인)
- Runner: AI
- Evidence: `artifacts/feature-0016-metadata-graph/20260729-graph-cap-audit/` 2매
  (`01_cols_55.png` 리포트 케이스 · `02_empty_state_reason.png` 조회 실패 사유 표시)

#### 3. 판정 — ① 컬럼 부분 투영 (사용자 리포트 직접 대상)

**`cc_pyron.DT_Character_New`** — 사용자 스크린샷과 **동일 노드**. 그래프 `HAS_COLUMN` **2** · 실 데이터
소스 컬럼 **55**.

| # | 항목 | 실측(배포본) | 판정 |
|---|---|---|---|
| ① | **컬럼 개수** | 헤더 `컬럼 (55)` · 목록 행 **55** — 사용자 스크린샷의 `컬럼 (2)` 에서 전량 복구 | **PASS** |
| ② | **ordinal 순서** | `CharacterID → OwnerUniqueID → Removed → Name → Slot → Class → Sex → PlayerLevel …` 실제 스키마 ORDINAL_POSITION 순 | **PASS** |
| ③ | **자료형 표기** | `CharacterID — int` · `Name — nvarchar` · `Experience — bigint` … | **PASS** |
| ④ | **다른 섹션 불변** | `사용하는 함수·프로시저 (33) · 읽기 25` 정상 | **PASS** |
| ⑤ | **pageerror** | 전 조작 구간 **0** | **PASS** |

#### 4. 판정 — ② 노드 누락 (루틴 투영 상한)

cap 상향은 *앞으로의* introspect 에 적용되므로, 이미 잘린 스키마는 `bin/routine-backfill.sh` 로 복구했다.

| 지표 | 종전(cap 300) | 배포 후 |
|---|---|---|
| `cc_pyron` 루틴 정점 | **300** (정확히 cap) | **597** (실제 전량) |
| 300 초과 스키마 | **0** (전부 cap 에 묶임) | **38개** |
| 스키마 최대 루틴 수 | **300** | **896** |
| 그래프 전체 루틴 정점 | 23,507 | **30,632** (+7,125) |
| `routine_objects` SSOT(`cc_pyron`) | 300 | **597** |

→ 종전이라면 최대 스키마에서 **596개 노드가 사라져 있었다**. 전 datasource backfill 완료 후 그래프에
**+7,125 루틴 정점**이 복구됐다. 판정 **PASS**.

**backfill 잔여 오류(정직)**: 일부 스키마는 **본 변경과 무관한 기존 환경 사유**로 실패했다 —
`cc_dbrestore_test` 등 로그인 실패(MSSQL 18456, 계정 권한) · `ND_GAME_0` 등
`Invalid object name 'information_schema.ROUTINES'`(구버전 SQL Server). cap 과 무관한 접근/호환 문제이며
해당 스키마는 종전에도 루틴이 없었다.

#### 5. 판정 — ③ 검색 상한 소멸

| # | 검색어 | 종전 | 배포 후 | 판정 |
|---|---|---|---|---|
| ⑥ | `DT_Character_New` | 50건 · "상한(검색어를 좁혀보세요)" | **71건 전량** | **PASS** |
| ⑦ | `web_ranking` | 50건 상한 | **724건 전량** 렌더 · pageerror 0 | **PASS** |

⑦ 은 종전 상한(50/80)이면 대부분이 잘렸을 규모다. 724행 목록이 렌더되고도 조작이 정상이었다 —
목록 부담은 그룹 접기·lazy 주입이 담당한다는 전제가 라이브에서 확인됐다.

#### 6. 판정 — ④ 상한 해제 후의 부하 (본 변경의 실질 위험)

종전 `schema_tables limit=300` 으로 잘리던 **최대 스키마**(`mysql-f2b1fe2c288c:web_ranking`, 719 테이블)를
배포본 백엔드에서 직접 측정:

```
schema_tables(719 테이블): 201ms · nodes=724 edges=725 truncated=False · payload=347KB
```

절단 없이(`truncated=False`) 전량을 200ms 대에 반환한다. 판정 **PASS**(허용 범위).

#### 7. 판정 — ⑤ empty-state 정직화 (직전 cycle 에서 "라이브 재현 못 함"으로 남겼던 축)

`mysql-f2b1fe2c288c` 데이터소스는 실제로 **연결 불가**(`2003 (HY000): Can't connect to MySQL server on
10.103.204.62:3306`)인 상태였다. 그 스코프의 테이블 상세를 열자 패널이:

```
컬럼 (0) ⓘ
데이터소스 컬럼 조회 실패(권한/연결 확인, 또는 AI 능동 분석 사용)
```

→ **"컬럼 조회 중…" 에 고착되지 않고 실패 사유를 표시**했다. 직전 cycle 의 empty-state 정직화 +
codex **P2-1**(실패 시 재렌더) 수정이 라이브에서 작동한 증적이며, 그 Run 기록에서 "예외 경로라 라이브
재현 못 함" 으로 남겼던 축이 여기서 우연히 확인됐다. 판정 **PASS**.

#### 8. 정직 표기 — 이번 Run 이 확인하지 **않은** 것

- **대형 스키마 캔버스 펼침의 프레임레이트**: 719 테이블 스키마의 백엔드 응답(§6)과 검색 목록 렌더(§5)는
  확인했으나, 그 스키마를 캔버스에 **펼친 상태의 팬/줌 실-paint 성능**은 측정하지 않았다. 해당 데이터소스가
  연결 불가라 컬럼 introspect 가 동반되지 않는 조건이었고, 렌더-성능 주장은 §16.6 상 CDP 실-paint 또는
  host-side 실관측을 요구하므로 **미검증으로 남긴다** — 상한 해제의 렌더 측 영향은 후속 관측 대상이다.
- **일부 스키마의 복구는 환경 사유로 불가**: backfill 은 완료됐으나(§4) 로그인 실패(MSSQL 18456)·구버전
  SQL Server(`information_schema.ROUTINES` 부재) 스키마는 introspect 자체가 안 된다 — cap 과 무관한 기존
  접근/호환 문제이며 본 변경의 범위 밖이다.
- **`truncated` WARN 표면화**: 안전 가드(20000)에 걸리는 스키마가 라이브에 없어(최대 896) WARN 경로는
  발화하지 않았다 — 코드 계약으로만 존재한다.

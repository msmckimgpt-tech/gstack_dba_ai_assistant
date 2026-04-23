---
doc_type: OBSERVATIONS
scope: project
status: active
edit_policy: append
source_of_truth: false
---

# 사용 이력 관측 리포트 — agent_memory 기반

> 목적: 내부 테스트 단계의 `gstack_dba_ai_assistant` 사용 이력을 수치화해
> gap 분석·사례집·VP 데모의 원천 근거를 확보한다.
> 본 문서는 append 정책이며, 새 수집 주기가 생기면 아래 §2 이후에 섹션을 덧붙인다.

## § 1. 데이터 소스

### 1.1 접속 방법
- DB: `agent_memory` (docker-compose 서비스 `mysql`, container `repo-mysql-1`)
- 엔드포인트: host `mysql:3306` (컨테이너 내부), host `127.0.0.1:13306` (호스트)
- 접속 계정: `.env` 의 `DB_USER` / `DB_PASSWORD`
- 본 리포트의 모든 쿼리는 AGENTS.md §2.2 예외 조항에 따라 `mysql` client 직접 사용
  (메모리 DB 점검은 `make ask` / `make mysql` 금지)

```bash
docker exec repo-mysql-1 mysql -u root -p$MYSQL_ROOT_PASSWORD -D agent_memory -e "..."
```

### 1.2 수집 기간 (UTC)
- 범위: `2026-03-26T03:47:24Z` ~ `2026-04-22T03:06:17Z` (≈ 27 일)
- 저장 DB 의 `TIMESTAMP` 컬럼은 세션 TZ=`SYSTEM` 이므로 `Asia/Seoul` 로 저장됨.
  본 리포트는 표시용 절대시각을 `CONVERT_TZ(ts,'Asia/Seoul','+00:00')` 로 변환해 **UTC** 로 통일했다.
  시간 **차이** (wall-time / total-time) 는 동일 TZ 기준이므로 변환 없이 `TIMESTAMPDIFF` 로 계산했다.

### 1.3 대상 테이블 스냅샷

| 테이블 | 역할 | 행 수 |
|--------|------|------:|
| `agentcoreconversations` | 대화 루트 (owner / product / topic / created_at) | 66 |
| `agentcoremessages` | user/assistant/tool 메시지 + `tool_calls` JSON | 782 |
| `agentmemorysteps` | 레거시 step 로그 (Tool / SqlText / ResultSummaryJson) | 281 |
| `agentmemorykv` | 대화별 상태 kv (`last_status`, `last_status_at` 등) | 919 |
| `agentmemorymessages` | 병렬/요약용 메시지 (`MetaJson.forked_from_conversation_id` 포함) | — |
| `webaccounts` | 테스터 식별 (역할/사용자명) | 25 |

### 1.4 테스터 식별

질의 요청(`role='user'` 메시지) 주체별 분포:

| `owner_account_id` | `Username` | `Role` | 사용자 메시지 수 |
|:-:|---|---|---:|
| 1  | `bootstrap_admin` | admin    | 95 |
| 10 | `admin`           | admin    | 18 |
| 4  | `mckim`           | operator | 6  |
| 3  | `review_user01`   | operator | 1  |

> 실질 테스터는 `bootstrap_admin` + `admin` 2 계정이 지배적(95/120, 79%) 이다.
> `mckim`/`review_user01` 은 RBAC 회귀 검증성 대화이고 스크립트성 짧은 prompt 가 많다.

---

## § 2. 지표

### 2.1 turn 수 / 대화 길이 분포

**방법:** `agentcoremessages` 을 `conversation_id` 로 group 한 뒤 `role='user'` 카운트(= 사용자 turn) + 전체 메시지 수.

**원본 SQL:**
```sql
SELECT user_turns, COUNT(*) AS n_conv
FROM (
  SELECT conversation_id, COUNT(*) AS user_turns
  FROM agentcoremessages WHERE role='user'
  GROUP BY conversation_id
) t
GROUP BY user_turns ORDER BY user_turns;
```

**결과 — 사용자 turn 히스토그램 (user messages/conversation, n=42 대화):**

```
turns  n_conv    bar
  1    20  ████████████████████
  2     5  █████
  3     7  ███████
  4     1  █
  5     2  ██
  6     3  ███
  7     1  █
  9     1  █
 10     1  █
 11     1  █
```

- 평균 user turns: **2.86**
- 중앙값(median): **2**
- 최대: **11** (`20260415094324-ef64b3eb`) ⚠️ outlier

**전체 메시지(assistant+tool+user) 분포 (n=42):**

```
msgs       n_conv
  2–4        8
  6–10       7
  11–20     10
  21–30      9
  31–41      7
 114         1  ⚠️ outlier (20260415094324-ef64b3eb)
```

**해석:** 절반은 1–2 턴의 단발성 질의이고, 꼬리는 긴 탐구형 대화가 비중을 차지한다.

---

### 2.2 요청 → 첫 SQL 생성 wall time

**방법:** `agentcoremessages.role='user'` 메시지 각각에 대해 동일 `conversation_id` 에서 그 뒤에 발생한 첫 `execute_sql` tool_call 의 `created_at` 을 pair → `TIMESTAMPDIFF(SECOND)`.

**원본 SQL:**
```sql
WITH sql_events AS (
  SELECT conversation_id, id, created_at
  FROM agentcoremessages
  WHERE role='assistant'
    AND JSON_SEARCH(tool_calls, 'one', 'execute_sql') IS NOT NULL
), user_events AS (
  SELECT conversation_id, id AS user_id, created_at AS user_at
  FROM agentcoremessages WHERE role='user'
), paired AS (
  SELECT u.conversation_id, u.user_id, u.user_at,
    (SELECT MIN(s.created_at) FROM sql_events s
     WHERE s.conversation_id = u.conversation_id AND s.id > u.user_id) AS next_sql_at
  FROM user_events u
)
SELECT TIMESTAMPDIFF(SECOND, user_at, next_sql_at) AS secs
FROM paired WHERE next_sql_at IS NOT NULL;
```

**결과 (n=99 요청):**

| 지표 | 값 |
|---|---:|
| mean (전체) | 9,943.6 s |
| mean (≤ 3600 s, outlier 제외) | **66.1 s** |
| min | 2 s |
| max (outlier 제외) | 1,037 s |
| max (outlier 포함) | 964,195 s ≈ 11.2 일 ⚠️ |

**bucket 히스토그램:**

```
bucket          n
  0–5s         26  ██████████████████████████
  6–10s         0
 11–30s        17  █████████████████
 31–60s        34  ██████████████████████████████████
 1–2m          11  ███████████
 2–5m           5  █████
 5–30m          4  ████
 30–60m         0
 >60m           2  ██  ⚠️ 대화 재개성 outlier
```

**해석:** 짧은 SQL은 5초 내 생성되지만 30–60s 구간 34건이 체감 응답시간의 중위를 지배한다.

---

### 2.3 요청 → 완료 total 시간

**방법:** `agentcoreconversations.created_at` 과 해당 대화의 `agentmemorykv.last_status_at` 값(= `UpdatedAt`) 의 차이.

> 주의: `agentcoreconversations` / `agentmemorykv` 는 **collation** 이 다르다
> (`utf8mb4_unicode_ci` vs `utf8mb4_0900_ai_ci`) → `COLLATE` 명시 필수.

**원본 SQL:**
```sql
SELECT TIMESTAMPDIFF(SECOND, c.created_at, kv.UpdatedAt) AS total_secs
FROM agentcoreconversations c
JOIN agentmemorykv kv
  ON kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id
 AND kv.`Key`         COLLATE utf8mb4_unicode_ci = 'last_status_at';
```

**결과 (n=26 대화, 완료 상태 도달한 것만):**

| 지표 | 값 |
|---|---:|
| mean | 515.6 s ≈ 8.6 분 |
| min | 0 s |
| max | 1,725 s ≈ 28.8 분 |

**bucket 분포:**

```
<60s      : 5
60–300s   : 9
300–900s  : 5
>900s     : 7   ⚠️ 장기 태스크 (배치성 집계 질의)
```

**해석:** 전체의 ¼ 가 15 분 이상 걸린다. 주로 JSON unnest 또는 JOIN 대량 집계.

---

### 2.4 prompt 원문 목록

**방법:** `agentcoremessages` 중 `role='user'` 의 `content` 컬럼. 사내 분석용이므로 익명화 불필요.

**원본 SQL:**
```sql
SELECT LEFT(content, 200) AS prompt_preview, COUNT(*) AS n
FROM agentcoremessages WHERE role='user'
GROUP BY prompt_preview ORDER BY n DESC, prompt_preview;
```

**총계:** 120 user 메시지 / 72 distinct prompt (중복률 40%).

**Top 15 (빈도순):**

| n | prompt (앞 200 자) |
|--:|---|
| 9 | `현재 데이터베이스 목록을 보여줘` |
| 6 | `dblog 에서 영웅스킬 업그레이드의 가장 대중적인 테크트리를 영웅별 및 테크트리별로 집계해주세요. 전투시작 로그(battlebegin.MyHeroInfo) 안의 각 영웅 객체 Skill 배열(5개 스킬 레벨) 을 "테크트리" 로 간주합니다…` |
| 5 | `dblog 에서 전투시작(battlebegin) 관련 통계를 내주세요. MyHeroInfo JSON 배열 안에 포함된 영웅 Index 기준으로 가장 많이 사용된 영웅 50 종의 (hero_index, appearances, adoption_pct)…` |
| 5 | `dblog.battlebegin 과 dblog.battleend 를 (AccountId, ChapterIndex, DungeonIndex, Difficulty) 그리고 가능한 추가 키로 매칭해서, BattleType 별로 전투 수 / 승률 / 평균 PlayTime / 평균 Star 를 뽑아주세요…` |
| 4 | `너의 역할을 알려줘` |
| 4 | `현재 DB 목록 보여줘` |
| 3 | `\`MyHeroInfo\` 는 hero 리스트입니다. 각 hero 의 Skill 배열(5 레벨) 을 풀어서 테크트리로 집계해야 합니다. JSON_TABLE 을 써서 풀어주세요.` |
| 3 | `dblog.battlebegin.MyHeroInfo 를 펼쳐서 영웅별 (등장 수, 최고 Level, 평균 Level, Star>=2 비율) 을 뽑고, '많이 나오면서 평균 Level/Star 도 높은' 영웅 상위 20 을 제안해주세요…` |
| 3 | `dblog.equipgacharecord 테이블을 이용해, 한정가챠에서 유저가 특정 상품이 있을 때만 실제로 뽑고 나머지 일반 상품만 있을 때는 뽑지 않고 만료시키는 패턴이 있는지 확인해주세요…` |
| 3 | `먼저 \`dblog.battlebegin\` 의 \`MyHeroInfo\` 컬럼이 JSON 배열임을 확인하고, 하나의 샘플 row 를 읽어 구조를 설명해주세요.` |
| 2 | `adoption_pct 컬럼을 추가해주세요 — 분모는 \`MyHeroInfo IS NOT NULL AND MyHeroInfo <> ''\` 인 battlebegin 전체 행 수입니다.` |
| 2 | `BattleType 별로 count / sum(Win) / avg(PlayTime) / avg(Star) 를 집계해주세요.` |
| 2 | `hero_index 기준 상위 50개를 appearances DESC 로 정렬해주세요.` |
| 2 | `mysql.user 테이블에서 아무 행이나 하나 보여줘` |
| 2 | `win_rate 를 % 로 환산(소수점 2자리)해서 컬럼에 추가해주세요.` |

**해석:** 한 줄 메타 질의 (`현재 DB 목록`, `너의 역할`) 가 top 을 차지하면서도 **battlebegin.MyHeroInfo JSON unnest** 계열 집계 요청이 압도적 비중이다.

---

### 2.5 성공/중단/오류 비율

**방법:** `agentmemorykv.last_status` 값 분포.

**원본 SQL:**
```sql
SELECT Value AS status, COUNT(*) AS n
FROM agentmemorykv WHERE `Key`='last_status'
GROUP BY Value ORDER BY n DESC;
```

**결과 (n=26):**

| status | n | % |
|---|---:|---:|
| `done` | 20 | 76.9% |
| `error` | 3 | 11.5% |
| `processing` | 3 | 11.5% ⚠️ |

> `canceled` 상태는 본 수집 구간에서 관측되지 않았다 (cancel 기능 자체는 KV 의 `cancel_requested`/`cancel_run_id` 로 tracked 되지만 최종 `last_status` 로 떨어진 사례 없음).
> `processing` 3 건은 종료 전 run 이 세션 종료/컨테이너 재시작으로 kv 상 업데이트가 안 끝난 상태로 추정 — 완료/에러로 정착 못한 "stuck" 케이스.

---

### 2.6 SQL 오류 빈도

**방법:** `agentmemorysteps.ErrorText` 는 본 DB 에서 전부 NULL 이므로(레거시 컬럼 미사용), 실제 오류는 `agentcoremessages` 의 `role='tool'` content 에 들어간 `"SQL 실행 오류: <code>..."` / `"오류:..."` 패턴을 분류해 카운트.

**원본 SQL:**
```sql
SELECT
  CASE
    WHEN content LIKE 'SQL 실행 오류: 1064%' THEN '1064 syntax error'
    WHEN content LIKE 'SQL 실행 오류: 1146%' THEN '1146 table not found'
    WHEN content LIKE 'SQL 실행 오류: 1054%' THEN '1054 column not found'
    WHEN content LIKE 'SQL 실행 오류: 3143%' THEN '3143 invalid JSON path'
    WHEN content LIKE 'SQL 실행 오류: %'     THEN 'SQL other'
    WHEN content LIKE '오류:%'              THEN 'tool-level (whitelist/usage)'
    ELSE 'ok'
  END AS kind,
  COUNT(*) AS n
FROM agentcoremessages WHERE role='tool'
GROUP BY kind ORDER BY n DESC;
```

**결과 (n=281 tool 결과):**

| kind | n | % |
|---|---:|---:|
| ok                            | 226 | 80.4% |
| tool-level (whitelist/usage)  |  17 |  6.0% |
| 1064 syntax error             |  13 |  4.6% |
| 1054 column not found         |  11 |  3.9% |
| 1146 table not found          |   8 |  2.8% |
| SQL other (1046/1248/1582 …)  |   5 |  1.8% |
| 3143 invalid JSON path        |   1 |  0.4% |

**SQL-level 총 오류율: 38/281 = 13.5%.** (tool-level 17 건은 whitelist 위반/파라미터 누락으로 DB 에 쿼리가 도달조차 못 한 케이스.)

**tool-level 상위 패턴:**

- `오류: 접근이 허용되지 않은 스키마 참조: bb, be …` — alias 를 schema 로 오판하는 regex 오탐 ⚠️ (TASK-0040 에서 일부 완화했지만 여전히 발생)
- `오류: keyword는 필수입니다.` — `search_tables` 필수 파라미터 누락

**해석:** 1064/1054 가 절반 이상(24/38) → JSON_TABLE/CTE 계 복합 SQL 의 구문/컬럼 오류가 지배. `battlebegin.MyHeroInfo` 집계 성격과 일치.

---

### 2.7 자주 접근한 schema / table Top 10

**방법:** `agentcoremessages.tool_calls` 에서 `execute_sql` 의 인자 `.sql` 을 뽑아
[`unit/feature-0002-agent-core/src/modules/tools.py:69`](unit/feature-0002-agent-core/src/modules/tools.py#L69) 의 `_extract_sql_schema_refs` 로 파싱.
테이블 단위는 동일 정규식 패턴(`FROM/JOIN` chunk → `schema.table`) 을 확장 사용, 사용자 스키마(`dbauth`/`dbgame`/`dblog`/`agent_memory`) 및 `information_schema` 만 수용해 alias 오탐 배제.

**원본 SQL + Python:**
```sql
-- 1) SQL 텍스트 수집
SELECT JSON_UNQUOTE(JSON_EXTRACT(
         JSON_UNQUOTE(JSON_EXTRACT(tc.tc_item,'$.function.arguments')),
         '$.sql'))
FROM agentcoremessages m
  , JSON_TABLE(m.tool_calls,'$[*]' COLUMNS (
      tc_item JSON PATH '$',
      name VARCHAR(64) PATH '$.function.name'
    )) AS tc
WHERE m.role='assistant'
  AND m.tool_calls IS NOT NULL
  AND tc.name='execute_sql';
```
```python
# 2) Python 파싱 (docs/OBSERVATIONS 산출용 스크립트 /tmp/analyze.py)
from modules.tools import _extract_sql_schema_refs
for s in sql_texts:
    for sch in _extract_sql_schema_refs(s):
        schema_cnt[sch] += 1
```

**SQL 실행 총량:** 167 `execute_sql` 호출 / 282 tool_call item (일부 어시스턴트 turn 이 다중 호출).

**schema 참조 Top 10 (raw — alias 오탐 포함):**

| rank | schema token | n |
|:-:|---|---:|
| 1 | `dblog` | 127 |
| 2 | `b` | 27 ⚠️ alias 오탐 |
| 3 | `e` | 18 ⚠️ alias 오탐 |
| 4 | `information_schema` | 13 |
| 5 | `jt` | 9 ⚠️ JSON_TABLE alias |
| 6 | `bb` | 5 ⚠️ alias |
| 7 | `eg` | 4 ⚠️ alias |
| 8 | `agent_memory` | 3 |
| 9 | `dbgame` | 3 |
| 10 | `t` | 3 ⚠️ alias |

**schema 참조 (정제 — 사용자/메타 스키마만):**

| rank | schema | n |
|:-:|---|---:|
| 1 | `dblog` | 127 |
| 2 | `information_schema` | 13 |
| 3 | `agent_memory` | 3 |
| 4 | `dbgame` | 3 |
| 5 | `dbauth` | 2 |

**table 참조 Top 15:**

| rank | schema.table | n |
|:-:|---|---:|
| 1 | `dblog.battlebegin` | 85 |
| 2 | `dblog.battleend` | 26 |
| 3 | `dblog.chat` | 17 |
| 4 | `dblog.equipgacharecord` | 15 |
| 5 | `information_schema.tables` | 7 |
| 6 | `information_schema.schemata` | 3 |
| 7 | `dblog.event` | 3 |
| 8 | `information_schema.columns` | 3 |
| 9 | `dblog.v_myheroinfo` | 3 |
| 10 | `agent_memory.agentmemoryfacts` | 2 |
| 11 | `dbauth.accountinfoview` | 2 |
| 12 | `dbgame.hero` | 1 |
| 13 | `dblog.eventworldbossbattlebegin` | 1 |
| 14 | `dbgame.hero_index` | 1 |
| — | (기타 15 건 <= 1 회 호출) | — |

**해석:** `dblog.battlebegin` 하나가 전체 SQL 의 절반(85/167 ≈ 51%) — 사례집·데모의 **1 순위 앵커 테이블**이다.
`_extract_sql_schema_refs` 은 복잡 CTE/서브쿼리에서 alias 를 schema 로 오탐하는 기존 한계가 지속(⚠️ 항목) — TASK-0040 재정비 범위를 고려할 것.

---

### 2.8 대화 fork 빈도

**방법:** `agentmemorymessages.MetaJson` JSON 키 `forked_from_conversation_id` 가 존재하는 메시지 및 해당 `ConversationId` 를 집계 (TASK-0035 기반).

**원본 SQL:**
```sql
SELECT
  COUNT(DISTINCT ConversationId) AS forked_conversations,
  COUNT(*) AS forked_message_count,
  COUNT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(MetaJson,'$.forked_from_conversation_id'))) AS source_conversations
FROM agentmemorymessages
WHERE JSON_EXTRACT(MetaJson,'$.forked_from_conversation_id') IS NOT NULL;

-- 상세
SELECT ConversationId,
       JSON_UNQUOTE(JSON_EXTRACT(MetaJson,'$.forked_from_conversation_id')) AS src,
       COUNT(*) AS msgs
FROM agentmemorymessages
WHERE JSON_EXTRACT(MetaJson,'$.forked_from_conversation_id') IS NOT NULL
GROUP BY ConversationId, src;
```

**결과:**

| 지표 | 값 |
|---|---:|
| fork 로 생성된 대화 수 | **2** |
| fork 메시지 수 | 9 |
| 원본 대화 수 (source) | 1 (`20260421075518-571abdb6`) |
| 전체 대화 대비 fork 비율 | 2/66 ≈ 3.0% |

**상세:**

| forked conv | source conv | msgs |
|---|---|---:|
| `20260421082459-c039abbd` | `20260421075518-571abdb6` | 6 |
| `20260421082523-d9fbb21b` | `20260421075518-571abdb6` | 3 |

**해석:** TASK-0035 도입 직후 소수 테스터가 1 개 원본 대화를 두 갈래로 fork 한 초기 사용 패턴. 기능 자체는 살아있지만 **습관화 전 단계**.

---

## § 3. 관측된 outlier

- ⚠️ **극단 길이 대화 `20260415094324-ef64b3eb` (owner=10)**: 전체 메시지 114 개, 사용자 turn 11 회. 한 대화에서 SQL 을 반복 보정하며 이어 감 — 에이전트가 오류 복구에 긴 루프를 탔는지 확인 필요.
- ⚠️ **휴면 재개 대화 `20260326033537-5a6699ff`**: 3/26 시작 후 4/6 에 동일 대화에서 SQL 재실행 (wall time 964,195 s ≈ 11 일). 동일 대화 재사용 UX → `last_status` stuck 원인 추정.
- ⚠️ **중복 prompt Top 2**: `현재 데이터베이스 목록을 보여줘` (9 회) / `너의 역할을 알려줘` (4 회) 는 테스터의 **기동 스모크** 성격. 실제 분석 질의는 `dblog.battlebegin` JSON 집계 계열이 최다 중복 (6 회).
- ⚠️ **alias 오탐으로 인한 whitelist 차단 17 건**: `bb`/`be`/`jt` 등 alias 를 schema 로 오인 → 정상 SQL 이 tool-level 에서 차단. `_extract_sql_schema_refs` 의 CTE/서브쿼리 대응이 2 번째 개선 포인트.
- ⚠️ **`last_status=processing` 3 건**: 세션 종료 시 kv 정착이 안된 상태. `insight-worker` 또는 agent 종료 시 `last_status` 를 `error`/`interrupted` 로 마감시키는 책임자 부재.
- ⚠️ **prompt 다양성 낮음**: distinct/total = 72/120 = 60% → 같은 요청을 재사용하는 패턴(특히 `battlebegin` 시리즈 후속 질문) 이 다수. 사례집 작성 시 "체인 단위로 묶기" 가 합리적.

---

## § 4. 다음 단계 (DELEGATION #2 참고 포인트)

- **사례집 앵커 테이블**: `dblog.battlebegin` 단독이 SQL 의 절반. MyHeroInfo JSON unnest 사례를 데모의 “영웅 사례” 로 고정.
- **속도 서사**: p50 wall-time ≈ 30–60 s (2/3 이 1 분 이내). "60 초 안에 SQL 초안" 메시지로 VP 데모 스크립트 작성 가능.
- **오류 서사**: 1064/1054 (syntax/column) 가 오류의 63% — "에이전트가 스스로 오류를 보정한다" 스토리는 JSON_TABLE 실패 후 재작성 케이스(예: `20260422030207-97c0d0c3`) 로 뒷받침.
- **fork UX 채택률**: 3% — VP 데모에서는 "새 기능" 으로 포지셔닝하고 도입 전후 지표를 재측정할 것.
- **stuck 해소 로드맵**: `last_status=processing` 해소 책임(agent-core graceful shutdown / kv finalization) 을 별도 TASK 로 분리.
- **관측 보강 요청**:
  - `agentmemorysteps.ErrorText` 가 비어있음 → step 레벨 오류 추적은 `agentcoremessages.role='tool'` 텍스트 regex 에 의존 중. 정식 필드 채움이 권장됨.
  - `agentcoreconversations` 에 `forked_from_conversation_id` 가 없고 `agentmemorymessages.MetaJson` 에만 있음 → fork 통계용 top-level 필드 승격 검토.
- **다음 수집 주기**: `last_update_utc` 이후 새 데이터 누적 시 본 § 2 구조를 그대로 append.

---

## § 5. Gap Hypothesis & Observation Questions

> 목적: § 2–3 의 수치 근거에 기반해, 이후 "타겟된 관찰 session" 에서 테스터에게
> 물어볼 open-ended 질문의 **후보 초안** 을 정리한다. 본 섹션은 가설 제안이며,
> 실제 선정·우선순위 확정은 senior DBA (사람) 가 한다.
> 질문 설계 원칙: 중립 (lead 금지), open-ended ("어땠나요" / "어떻게 쓰세요"),
> 답변을 특정 방향으로 유도하지 않음.

### 5.1 Gap #1 — 중단 대화 (`last_status=error` / `processing` stuck)

**근거:**
- § 2.5 `last_status=error` 3 건 / `processing` stuck 3 건 (각 11.5%, 합 23%).
- § 2.5 `canceled` 상태는 수집 구간 0 건 (KV 에 `cancel_requested` 는 있으나 최종 status 로 정착 없음).
- § 3 `20260326033537-5a6699ff`: wall-time 964,195 s (≈ 11 일) — 재개성/휴면.
- § 2.6 SQL 오류 13.5% 중 tool-level 17 건은 쿼리가 DB 도달 전 차단.

**가설 후보 (H1.x):**
- H1.1 — `last_status=error` 로 끝난 대화는 AI 응답이 틀렸다기보다 **테스터가 답을 못 쓰겠다고 판단해 창을 닫았다**.
- H1.2 — `processing` stuck 3 건은 **AI 의 오류가 아니라 페이지 이탈/새로고침/컨테이너 재시작** 때문이다 (agent-core graceful shutdown 미비).
- H1.3 — `error` 상태 중 일부는 **whitelist 차단(tool-level 17 건)** 에 대한 테스터의 체념 반응 — alias 오탐을 사용자는 "내가 잘못 쓴 것" 으로 오해했다.
- H1.4 — 중단 직전의 prompt 는 **AI 가 구조를 이해하지 못한 테이블/스키마** 를 겨냥한 첫 시도다 (e.g. `dblog.battlebegin` 외부 테이블).
- H1.5 — 일부 중단은 **응답이 너무 늦어서** (§ 2.3 > 900 s 가 7 건, ¼) 테스터가 기다리기를 포기했다.
- H1.6 — 테스터는 UI 에 "취소" 버튼이 있다는 사실을 몰랐거나 신뢰하지 못해서, 대신 **탭을 닫는 방식으로 중단**했다 (→ `canceled` 0 건).

**관찰 질문:**
- Q1.a "최근에 이 도구 쓰다가 답을 다 받지 못한 채 자리를 떠난 적이 있나요? 그때 어떤 상황이었는지 생각나는 대로 들려주실 수 있을까요?"
- Q1.b "답이 오래 걸릴 때는 보통 어떻게 하세요?"
- Q1.c "대화를 중단하고 싶을 때 지금은 어떻게 하시나요?"

---

### 5.2 Gap #2 — 1~2 turn 만에 `done` 종료 (해결인지 포기인지 불분명)

**근거:**
- § 2.1 user turn 1 회 대화 20 건 / 2 회 5 건 = 합 25/42 = **60%**. 평균 2.86, 중앙값 2.
- § 2.5 `done` 은 단일 상태 (20/26 = 76.9%) 여서 "만족하고 끝냄" 과 "한 번 답 듣고 닫음" 을 구분 못함.
- § 2.3 `<60s` 완료 5 건 / `60–300s` 9 건 — 짧은 대화가 많다.
- § 2.4 top prompt 는 `현재 DB 목록 보여줘` (9 회) / `너의 역할을 알려줘` (4 회) 등 단발성 메타 질의.

**가설 후보 (H2.x):**
- H2.1 — 1-turn 대화의 대부분은 **스모크 / 확인성 질의** (DB 목록, 역할 질문) 이고 실제 분석 의도가 없다 — 이는 "해결" 도 "포기" 도 아닌 3 범주.
- H2.2 — 1-turn 종료는 실제로는 **답이 기대에 못 미쳤지만 테스터가 재질문 대신 직접 SQL 을 썼다** — AI 경로 이탈.
- H2.3 — 2-turn 종료는 **1 차 답 받고 추가 검증 없이 신뢰해서 끝냄** — 정확성 검증 공백.
- H2.4 — 테스터는 한 주제를 **새 대화로 다시 시작** 하는 습관이 있어, "1 turn done" 은 실상 세션 분할의 부산물이다 (§ 3 prompt 재사용 60%).
- H2.5 — 짧은 `done` 대화 일부는 **tool-level 차단** 이나 "동작 안 하는 것 같아 보이는 에러 메시지" 를 받고 닫은 사례지만 kv 에는 `done` 으로 기록됐다.
- H2.6 — 1-turn 의 기동 질의 (`현재 DB 목록 보여줘`) 는 **AI 가 어떤 DB 를 보는지 확인하는 의식** 이며, 그 응답 자체보다 "연결 살아있다" 신호가 목적이다.

**관찰 질문:**
- Q2.a "AI 에게 한 번 물어보고 바로 끝낸 경우는 어떤 경우였는지 기억나세요?"
- Q2.b "답을 받고 난 다음에 보통 뭘 하시나요?"
- Q2.c "같은 주제라도 새 대화를 시작하시는 편인가요, 한 대화에서 이어서 하시는 편인가요? 그렇게 하시는 이유가 있으실까요?"

---

### 5.3 Gap #3 — 동일 주제 반복 질의 (첫 답이 만족스럽지 않았다는 간접 신호)

**근거:**
- § 2.4 `dblog battlebegin.MyHeroInfo` JSON unnest 계열: 6 회 / 5 회 / 3 회 / 3 회 / 3 회 로 Top 15 중 여러 개 차지.
- § 2.4 distinct prompt 비율 72/120 = **60%** (재사용 40%).
- § 2.1 outlier `20260415094324-ef64b3eb`: 11 user turn / 114 메시지 — 동일 주제 장기 보정.
- § 2.7 `dblog.battlebegin` 혼자 SQL 의 51% (85/167) — 주제 집중도가 재질문 가능성을 높임.
- § 3 "prompt 다양성 낮음 → 체인 단위로 묶기 합리적".

**가설 후보 (H3.x):**
- H3.1 — `battlebegin.MyHeroInfo` 시리즈가 중복되는 이유는 **첫 답의 SQL 이 부분적으로 틀려서** 후속 turn 에서 보정을 요구한 결과다 (§ 2.6 1064/1054 와 연결).
- H3.2 — 같은 prompt 의 재실행은 **새 세션에서 컨텍스트가 날아가** 테스터가 동일 지시를 재입력해야 했기 때문이다.
- H3.3 — 반복은 **테스터가 다른 AI / 다른 포맷으로 동일 요청을 대조** 하고 있다는 신호다 (도구 신뢰도 검증 행위).
- H3.4 — 상위 빈도 `현재 데이터베이스 목록을 보여줘` (9 회) 는 **테스터 교대 / 세션 기동 의식** 이며, 분석 의도와는 무관하다.
- H3.5 — 중복 prompt 일부는 **이전 대화의 일부를 잘라 복사** 한 결과 (대화 fork 가 3% 에 그친 § 2.8 과 호환) — fork 대신 copy-paste 로 재생산.
- H3.6 — `너의 역할을 알려줘` 4 회는 **답 내용의 일관성 / 프롬프트 변화 여부를 테스트** 하기 위한 반복이다.
- H3.7 — 11-turn outlier 는 AI 가 JSON_TABLE 문법을 여러 번 틀려서, 테스터가 **문법 가이드를 점진적으로 주입** 해야 했던 케이스다 (§ 2.4 에 "JSON_TABLE 을 써서 풀어주세요" 3 회 별도 등장).

**관찰 질문:**
- Q3.a "같은 주제로 여러 번 물어보신 적이 있다면, 두 번째 세 번째에는 어떤 점이 달랐는지 기억하세요?"
- Q3.b "AI 답이 맞는지 확인하실 때 보통 어떤 방식으로 확인하세요?"
- Q3.c "예전에 했던 대화를 이어갈 수 있다면 쓰실 것 같으세요, 아니면 새로 시작하시겠어요? 왜 그렇게 느끼시나요?"

---

### 5.4 Gap #4 — `execute_sql` error 반복 (AI 의 schema 이해 오류 지점)

**근거:**
- § 2.6 SQL-level 오류 총 38/281 = **13.5%**. 1064 syntax 13 / 1054 column 11 / 1146 table 8 / 3143 JSON path 1.
- § 2.6 tool-level 17 건 (whitelist 위반) — alias (`bb`/`be`/`jt`) 를 schema 로 오탐 (§ 2.7 참고).
- § 3 outlier `20260415094324-ef64b3eb`: 114 메시지 / 11 turn — 오류 복구 루프 추정.
- § 2.7 `dblog.battlebegin` SQL 의 51% 집중 → 오류도 이 테이블 계열에 몰릴 가능성.
- § 4 "JSON_TABLE 실패 후 재작성" 사례 (`20260422030207-97c0d0c3`).

**가설 후보 (H4.x):**
- H4.1 — 1064 syntax 오류 대부분은 **JSON_TABLE / CTE 중첩** 에서 발생한다 (§ 2.4 의 MyHeroInfo 시리즈 빈도와 일치).
- H4.2 — 1054 column not found 는 AI 가 **이전 대화 / 스키마 카탈로그 캐시에서 실제와 다른 컬럼명** 을 생성했기 때문이다.
- H4.3 — 1146 table not found 8 건은 AI 가 **문서/예시 기반 테이블명 (`hero_index` 등) 을 가정** 했고 실제 스키마를 `describe_tables` 로 확인하지 않았다.
- H4.4 — tool-level whitelist 17 건은 AI 오류가 아닌 **도구 regex 버그** 지만, 테스터는 "AI 가 이상한 걸 쓴다" 로 인식한다 (UX 책임 경계 혼선).
- H4.5 — 오류 복구 루프가 긴 경우 (11-turn outlier), AI 가 **동일한 실수를 반복 재생산** 하며 수렴하지 못한다.
- H4.6 — 반복 오류가 특정 **테스터 페르소나(admin vs bootstrap_admin)** 에 치우친다 — 즉 요청 스타일이 AI 오류율의 주요 변수다.
- H4.7 — 3143 invalid JSON path 1 건 은 드물지만, **$.path 문법 오해** 가 AI 의 고정된 실수 패턴인지 단발 사고인지 불명.

**관찰 질문:**
- Q4.a "AI 가 만든 SQL 이 바로 돌지 않았을 때, 그 다음에 뭘 하셨는지 들려주실 수 있을까요?"
- Q4.b "에러 메시지가 나왔을 때 그 메시지가 이해 가셨나요? 어떤 부분에서 멈칫하셨어요?"
- Q4.c "직접 쓰신 SQL 이 더 잘 돌 거라고 판단되는 주제나 테이블이 있나요?"

---

### 5.5 Gap #5 — prompt 는 있으나 `execute_sql` 호출 없이 종료 (설명형 응답의 만족도 불명)

**근거:**
- § 2.7 execute_sql 총 167 호출 / user messages 120 → 평균 **1.39 SQL/prompt**, 하지만 1-turn 대화 20 건 중 일부는 실행 0 건일 가능성.
- § 2.4 `너의 역할을 알려줘` (4 회) / `현재 DB 목록 보여줘` (9 회) / `먼저 … JSON 배열임을 확인하고, 샘플 row 를 읽어 구조를 설명해주세요` (3 회) — **설명 요청형** prompt 존재.
- § 2.1 1-turn `done` 대화 20 건 (절반 가까이) — SQL 없는 종료 후보.
- § 2.5 `done` 라벨은 SQL 실행 여부를 구분하지 않는다.

**가설 후보 (H5.x):**
- H5.1 — `너의 역할을 알려줘` 류 메타 질의는 **SQL 없이 설명만 받고 만족** 하는 정상 케이스로, 해결/포기 모두 아닌 3 범주다.
- H5.2 — "구조를 설명해주세요" 계열 (3 회) 은 테스터가 **AI 의 스키마 이해도를 먼저 가늠** 한 뒤 분석을 시작하는 **워밍업 단계** 다.
- H5.3 — SQL 을 치지 않고 끝난 일부는 AI 가 "이 쿼리는 위험합니다 / 권한이 없습니다" 로 **거절** 했고, 테스터는 우회 요청을 포기했다 (tool-level 17 건의 간접 영향).
- H5.4 — 설명만 받고 끝난 대화에서 테스터는 **AI 설명을 자기 SQL 로 번역해 IDE/Workbench 에서 직접 실행** 했다 — 본 도구 경로 밖 완결.
- H5.5 — 1-turn done 중 일부는 **AI 답이 장황해서 읽기 포기** 한 케이스다 — 응답 길이 / 포맷 문제.
- H5.6 — 테스터는 **"AI 는 목록/설명만 하고 실행은 내가 한다"** 라는 멘탈 모델을 갖고 있어, SQL 호출이 없는 것이 정상이라고 느낀다.

**관찰 질문:**
- Q5.a "AI 에게 SQL 을 바로 실행해달라고 하기보다 설명이나 구조 확인을 먼저 부탁하는 경우가 있나요? 그럴 때는 어떤 상황이세요?"
- Q5.b "AI 의 답이 글로만 설명됐을 때, 그걸 받아서 이후에 어떤 작업으로 이어가세요?"
- Q5.c "이 도구에 물어보지 않고 다른 방법 (직접 SQL / Workbench / 다른 AI) 을 쓰신 적이 있다면 어떤 경우였어요?"

---

### 5.6 사용 안내 (관찰 session 준비)

- 위 질문은 **초안** 이다. 관찰 session 진행자는 테스터의 실제 대화 id 를 보조 자료로 들고 들어가, 답변이 모호할 때 **구체적 대화 하나를 보여주며** 재질문하는 방식을 권장한다 (e.g. `20260415094324-ef64b3eb` 의 화면 재현).
- 가설 H1.x ~ H5.x 중 데이터에서 가장 강한 신호는 (a) § 2.1 1-turn 60% 와 (b) § 2.6 JSON_TABLE 계 SQL 오류 집중이다. 시간이 제한되면 Gap #2, Gap #4 를 우선 커버한다.
- 관찰 session 종료 후에는 본 §5 섹션을 그대로 두고, 결과는 별도 섹션 (`§ 6. Session Findings`) 에 append 한다 (edit_policy: append 원칙).

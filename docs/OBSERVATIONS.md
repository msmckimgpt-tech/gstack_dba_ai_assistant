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

-- TASK-0034 복잡 QA 성능 테스트 검증용 "사람 정답" 쿼리.
-- 각 질문(Q1~Q5)에 대해, assistant 최종 답변과 대조할 기준 쿼리.
-- docker compose exec -T mysql mysql -uroot -pchange_me dblog -e "..." 로 실행.

-- ========================================================================
-- Q1: 영웅스킬 업그레이드 테크트리 랭킹
--   hero_index 별 Top 5 tech-tree (= Skill[] array joined by '-')
--   + 전체 Top 20 tech-tree (hero_index 무관)
-- ========================================================================

-- Q1-A: 영웅별 Top 5 테크트리 (샘플: hero_index=1,2,3)
WITH heroes AS (
  SELECT
    h.hero_index,
    h.skill_combo
  FROM dblog.battlebegin b,
       JSON_TABLE(
         b.MyHeroInfo, '$[*]'
         COLUMNS (
           hero_index INT PATH '$.Index',
           skill_json JSON  PATH '$.Skill'
         )
       ) h
  WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
  CROSS JOIN LATERAL (
    SELECT JSON_UNQUOTE(
             REPLACE(REPLACE(JSON_EXTRACT(h.skill_json, '$'), '[', ''), ']', '')
           ) AS skill_combo_raw
  ) x
),
-- (위 CTE 는 참고용 — MySQL 8 의 JSON_TABLE + LATERAL 조합이 환경마다 다르므로 실 검증에서는 아래 단순 쿼리 사용)
;

-- Q1-실행본 (단순 JSON_TABLE + REPLACE 체인):
SELECT
  hero_index,
  skill_combo,
  COUNT(*) AS cnt,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY hero_index), 2) AS pct_within_hero
FROM (
  SELECT
    JSON_EXTRACT(j.hero, '$.Index') AS hero_index,
    REPLACE(REPLACE(REPLACE(JSON_EXTRACT(j.hero, '$.Skill'), ',', '-'), '[', ''), ']', '') AS skill_combo
  FROM dblog.battlebegin b,
       JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
  WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
) e
GROUP BY hero_index, skill_combo
ORDER BY hero_index, cnt DESC;

-- Q1 전체 Top 20 (hero_index 무관):
SELECT skill_combo, COUNT(*) AS cnt
FROM (
  SELECT REPLACE(REPLACE(REPLACE(JSON_EXTRACT(j.hero, '$.Skill'), ',', '-'), '[', ''), ']', '') AS skill_combo
  FROM dblog.battlebegin b,
       JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
  WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
) e
GROUP BY skill_combo
ORDER BY cnt DESC
LIMIT 20;

-- ========================================================================
-- Q2: 전투시작 영웅 사용 Top 50
-- ========================================================================
SELECT
  JSON_EXTRACT(j.hero, '$.Index') AS hero_index,
  COUNT(*) AS appearances,
  ROUND(COUNT(*) * 100.0 / (
    SELECT COUNT(*) FROM dblog.battlebegin
    WHERE MyHeroInfo IS NOT NULL AND MyHeroInfo <> ''
  ), 2) AS adoption_pct
FROM dblog.battlebegin b,
     JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
GROUP BY hero_index
ORDER BY appearances DESC
LIMIT 50;

-- ========================================================================
-- Q3: 한정가챠 가치 품목 판별 (희소 데이터)
--   GachaIndex=3 (= 실제 가챠 진행) vs GachaIndex=18 (= 노출/만료)
--   HighGachaCategory 가 comma-separated 숫자 목록인 행만 처리.
-- ========================================================================
-- 전체 분포
SELECT GachaIndex, HighGachaCategory, COUNT(*) AS cnt
FROM dblog.equipgacharecord
GROUP BY GachaIndex, HighGachaCategory
ORDER BY cnt DESC
LIMIT 30;

-- 카테고리 플래그 분해 (index=3 = 시도, index=18 = 노출 추정)
SELECT cat, gacha_state, COUNT(*) AS cnt
FROM (
  SELECT
    TRIM(jt.cat) AS cat,
    CASE WHEN r.GachaIndex = 3 THEN 'attempt' ELSE 'expose' END AS gacha_state
  FROM dblog.equipgacharecord r,
       JSON_TABLE(
         CONCAT('[', REPLACE(r.HighGachaCategory, ',', '","'), ']'),
         '$[*]' COLUMNS (cat VARCHAR(20) PATH '$')
       ) jt
  WHERE r.HighGachaCategory REGEXP '^[0-9,]+$'
) t
GROUP BY cat, gacha_state
ORDER BY cat, gacha_state;

-- ========================================================================
-- Q4: BattleType 별 승률 × 평균 PlayTime × 평균 Star (Top 10)
--   battlebegin ↔ battleend 는 LogId 로 직접 JOIN 되지 않음.
--   실질적 JOIN 키는 (AccountId, Time~=) 또는 BattleType 를 직접 end 에도 저장할 수 있어
--   schema 에 따라 달라짐. 여기서는 battlebegin BattleType 과 bound 된 같은 Account/근접 Time 매칭.
-- ========================================================================
-- 단순화: battlebegin.BattleType 별 수량 (승률은 JOIN 기반이 필요해 별도)
SELECT BattleType, COUNT(*) AS begin_cnt
FROM dblog.battlebegin
WHERE BattleType IS NOT NULL
GROUP BY BattleType
ORDER BY begin_cnt DESC
LIMIT 10;

-- 전제: end 에도 BattleType 컬럼이 있는지 확인 (DESC dblog.battleend)
-- (battleend.Win/Star/PlayTime 만 존재 — BattleType 없으면 begin 과 매칭 필요)

-- AccountId + Time window 매칭 (5분 이내 같은 AccountId 의 battleend):
SELECT
  bb.BattleType,
  COUNT(*) AS battles,
  ROUND(SUM(be.Win) * 100.0 / COUNT(*), 2) AS win_rate_pct,
  ROUND(AVG(be.PlayTime), 1) AS avg_playtime_ms,
  ROUND(AVG(be.Star), 2) AS avg_star
FROM dblog.battlebegin bb
JOIN dblog.battleend be
  ON be.AccountId = bb.AccountId
 AND be.Time >= bb.Time
 AND be.Time <  bb.Time + INTERVAL 5 MINUTE
WHERE bb.BattleType IS NOT NULL
GROUP BY bb.BattleType
ORDER BY battles DESC
LIMIT 10;

-- ========================================================================
-- Q5: 육성된 메타 영웅 Top 20
-- ========================================================================
WITH hero_stats AS (
  SELECT
    JSON_EXTRACT(j.hero, '$.Index')  AS hero_index,
    JSON_EXTRACT(j.hero, '$.Level')  AS lvl,
    JSON_EXTRACT(j.hero, '$.Star')   AS star
  FROM dblog.battlebegin b,
       JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
  WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
)
SELECT
  hero_index,
  COUNT(*) AS appearances,
  MAX(CAST(lvl AS UNSIGNED)) AS max_level,
  ROUND(AVG(CAST(lvl AS UNSIGNED)), 2) AS avg_level,
  ROUND(AVG(CASE WHEN CAST(star AS UNSIGNED) >= 2 THEN 1 ELSE 0 END), 4) AS star2_ratio,
  ROUND(LOG10(COUNT(*) + 1) * AVG(CAST(lvl AS UNSIGNED))
        * (1 + AVG(CASE WHEN CAST(star AS UNSIGNED) >= 2 THEN 1 ELSE 0 END)), 2) AS score
FROM hero_stats
GROUP BY hero_index
ORDER BY score DESC
LIMIT 20;

"""TASK-0034 복잡 QA 성능 테스트용 질문 세트.

각 질문은 5 항목 (dict) 으로 구성:
- qid: 고유 식별자 (Q1~Q5)
- title: 요약 (파일명/로그용)
- main: 첫 turn 으로 던지는 주 질문
- follow_ups: 추가 턴 후보 (최대 19 개까지 쓸 수 있음).
  각 항목은 (trigger, prompt) 튜플. trigger 는 assistant 응답에 대한
  휴리스틱 — runner 가 상황을 판단해 적절한 follow-up 을 선택한다.
"""

QUESTIONS = [
    {
        "qid": "Q1",
        "title": "영웅스킬 업그레이드 테크트리 랭킹",
        "main": (
            "dblog 에서 영웅스킬 업그레이드의 가장 대중적인 테크트리를 영웅별 및 테크트리별로 집계해주세요. "
            "전투시작 로그(battlebegin.MyHeroInfo) 안의 각 영웅 객체 Skill 배열(5개 스킬 레벨) 을 "
            "\"테크트리\" 로 간주합니다. 영웅(Index)별 Top 5 테크트리 및 전체 Top 20 테크트리를 각각 "
            "(hero_index, skill_combo, count, pct_within_hero) 형식으로 정리해주세요."
        ),
        "follow_ups": [
            ("no_sql", "먼저 `dblog.battlebegin` 의 `MyHeroInfo` 컬럼이 JSON 배열임을 확인하고, 하나의 샘플 row 를 읽어 구조를 설명해주세요."),
            ("no_sql", "`MyHeroInfo` 는 hero 리스트입니다. 각 hero 의 Skill 배열(5 레벨) 을 풀어서 테크트리로 집계해야 합니다. JSON_TABLE 을 써서 풀어주세요."),
            ("no_aggregate", "각 영웅 Index 별로 테크트리(= Skill 배열을 `-` 로 join 한 문자열) 의 등장 수를 집계해주세요."),
            ("no_ranking", "집계 결과에서 영웅별 Top 5 테크트리를 추출해주세요 (영웅당 상위 5 개)."),
            ("no_ranking", "별도로 전체 테크트리 기준 Top 20 (hero_index 무관, skill_combo 중심) 도 뽑아주세요."),
            ("missing_pct", "각 hero_index 내부에서의 채택률(%)을 소수점 2자리로 추가해주세요."),
            ("ambiguous", "결과 표의 컬럼을 (hero_index, skill_combo, count, pct_within_hero) 로 정확히 맞춰서 다시 보여주세요."),
            ("need_summary", "상위 5 개 hero_index 를 보고 가장 많이 투입되는 영웅과 그들이 선호하는 테크트리 패턴을 2문장으로 요약해주세요."),
        ],
    },
    {
        "qid": "Q2",
        "title": "전투시작 영웅 사용 Top 50",
        "main": (
            "dblog 에서 전투시작(battlebegin) 관련 통계를 내주세요. MyHeroInfo JSON 배열 안에 포함된 "
            "영웅 Index 기준으로 가장 많이 사용된 영웅 50 종의 (hero_index, appearances, adoption_pct) 를 뽑아주세요. "
            "adoption_pct 는 MyHeroInfo 가 비어있지 않은 battlebegin 행 수 대비 영웅 등장 수 비율(%) 로 정의합니다."
        ),
        "follow_ups": [
            ("no_sql", "먼저 `battlebegin.MyHeroInfo` 샘플을 읽어 JSON 배열 구조를 확인해주세요."),
            ("no_sql", "JSON_TABLE 로 각 hero Index 를 풀어서 count 집계를 해주세요."),
            ("no_ranking", "hero_index 기준 상위 50개를 appearances DESC 로 정렬해주세요."),
            ("missing_pct", "adoption_pct 컬럼을 추가해주세요 — 분모는 `MyHeroInfo IS NOT NULL AND MyHeroInfo <> ''` 인 battlebegin 전체 행 수입니다."),
            ("ambiguous", "최종 결과에 컬럼 순서를 (rank, hero_index, appearances, adoption_pct) 로 맞춰주세요."),
            ("need_summary", "상위 5 hero_index 와 전체 50 위의 채택률 격차를 한 문장으로 요약해주세요."),
        ],
    },
    {
        "qid": "Q3",
        "title": "한정가챠 가치 높은 상품 판별",
        "main": (
            "dblog.equipgacharecord 테이블을 이용해, 한정가챠에서 유저가 특정 상품이 있을 때만 실제로 뽑고 "
            "나머지 일반 상품만 있을 때는 뽑지 않고 만료시키는 패턴이 있는지 확인해주세요. "
            "그런 '가치 높은 상품' (= 카테고리 코드) 이 무엇인지 집계로 보여주세요. "
            "참고: HighGachaCategory 는 이진 플래그처럼 작동하는 comma-separated 카테고리 코드 목록입니다 "
            "(예: '25,71,13,2'). 클래스명(Wizard, Warrior 등) 문자열도 섞여 있으니 분리해주세요."
        ),
        "follow_ups": [
            ("no_sql", "먼저 `equipgacharecord` 테이블 구조(DESC) 와 전체 row 수를 확인해주세요."),
            ("no_sql", "`HighGachaCategory` 컬럼 값 분포를 GROUP BY 로 상위 20 개 뽑아주세요."),
            ("no_aggregate", "값을 `(a) 숫자 comma-separated 목록 (카테고리 플래그)` 와 `(b) 클래스 이름 (Wizard 등)` 로 분류해주세요. 예: regex 로 `^[0-9,]+$` 패턴 매칭."),
            ("no_aggregate", "플래그 목록은 comma 로 split 해서 개별 카테고리 코드별 등장 수를 집계해주세요."),
            ("missing_pct", "가챠 시도 행위(GachaIndex=3 또는 RemainGachaChance IS NOT NULL) 와 단순 노출/만료 행위(GachaIndex=18 또는 RemainGachaChance IS NULL) 를 구분해서, 카테고리별 '시도시 등장 비율' vs '미시도시 등장 비율' 을 대조해주세요."),
            ("ambiguous", "두 비율의 차이가 큰 카테고리 (= '가치 높은 상품') 를 Top 10 으로 뽑아주세요."),
            ("need_summary", "관찰된 상위 카테고리가 어떤 의미일지(= 특정 장비 tier 인지, 희귀 영웅 클래스인지 등) 해석해주세요."),
        ],
    },
    {
        "qid": "Q4",
        "title": "BattleType 별 승률 × 평균 플레이타임 × 평균 Star",
        "main": (
            "dblog.battlebegin 과 dblog.battleend 를 (AccountId, ChapterIndex, DungeonIndex, Difficulty) "
            "그리고 가능한 추가 키로 매칭해서, BattleType 별로 전투 수 / 승률 / 평균 PlayTime / 평균 Star 를 뽑아주세요. "
            "BattleType 에 해당하는 전투가 많은 순으로 Top 10 을 보여주세요."
        ),
        "follow_ups": [
            ("no_sql", "먼저 `battlebegin` 과 `battleend` 의 스키마를 DESC 로 확인해주세요 — 특히 매칭 가능한 공통 키를 파악해야 합니다."),
            ("no_sql", "battlebegin 과 battleend 를 JOIN 하는 가장 합리적인 키 조합을 제안하고, 소규모 샘플(LIMIT 100)로 검증해주세요."),
            ("no_aggregate", "BattleType 별로 count / sum(Win) / avg(PlayTime) / avg(Star) 를 집계해주세요."),
            ("no_ranking", "집계 결과를 count DESC 로 정렬해서 상위 10 BattleType 를 뽑아주세요."),
            ("missing_pct", "win_rate 를 % 로 환산(소수점 2자리)해서 컬럼에 추가해주세요."),
            ("need_summary", "가장 승률이 높은 BattleType 과 가장 낮은 BattleType 의 차이를 한 문장으로 요약해주세요."),
        ],
    },
    {
        "qid": "Q5",
        "title": "육성된 메타 영웅 Top 20",
        "main": (
            "dblog.battlebegin.MyHeroInfo 를 펼쳐서 영웅별 (등장 수, 최고 Level, 평균 Level, Star>=2 비율) 을 뽑고, "
            "'많이 나오면서 평균 Level/Star 도 높은' 영웅 상위 20 을 제안해주세요. "
            "랭킹 산식은 당신이 합리적으로 정해도 됩니다. 다만 사용한 산식을 명시해주세요."
        ),
        "follow_ups": [
            ("no_sql", "MyHeroInfo 를 JSON_TABLE 로 풀어서 (hero_index, level, star) 뷰를 만들어주세요."),
            ("no_aggregate", "hero_index 별로 count, MAX(level), AVG(level), AVG(CASE WHEN star>=2 THEN 1 ELSE 0 END) 를 집계해주세요."),
            ("no_ranking", "랭킹 산식을 정의해주세요 — 예: `score = log10(count+1) * avg_level * (1 + star2_ratio)`. 그 산식으로 Top 20 을 뽑아주세요."),
            ("ambiguous", "최종 표 컬럼을 (rank, hero_index, appearances, max_level, avg_level, star2_ratio, score) 로 정리해주세요."),
            ("need_summary", "Top 3 영웅이 왜 상위인지(등장 빈도? 평균 레벨? Star?) 2문장으로 해설해주세요."),
        ],
    },
]

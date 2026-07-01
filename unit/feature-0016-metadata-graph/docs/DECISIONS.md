---
doc_type: FEATURE_DECISIONS
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001
- Status:
- Date:
- Context:
- Decision:
- Consequences:
- Supersedes:
- Superseded By:

## ADR-002 — 암묵 관계: 정적 confidence ↔ 동적 weight 분리 + 관찰·프로브 하이브리드 자기교정
- Status: Accepted
- Date: 2026-07-01
- Context: 게임 운영 DB 8,122 테이블이 FK 를 거의 선언 안 해 `table_relationships` 엣지가 0. FK 없이도
  "뉘앙스적(암묵) JOIN 관계" 를 파악해 사람·AI 가 쉽게 보되, **암묵 관계라 항상 올바른지 검증**되어 틀리면
  약해져 끊어지고 맞으면 강해져 신뢰로 재구성되어야 한다(사용자 요청). 기존 `confidence` 는 `GREATEST(...)`
  단조 증가라 감쇠·파단이 불가능했다.
- Decision:
  1. 정적 `confidence`(출처 prior)와 동적 `weight`(관찰·프로브로 갱신)를 **분리**. read·주입·그래프는 weight 기준.
  2. FK 미선언 관계를 **명명 규칙 휴리스틱**(name_fk: `<base>_id`→동명 테이블 PK / shared_key: 접두 키 공유)
     으로 추론(source='inferred', status='candidate'). 정밀도는 사후 검증이 보정.
  3. **검증 = 관찰 + 능동프로브 하이브리드**(사용자 결정): (a) 성공한 대화 JOIN 사용 = 양성, (b) insight
     워커가 실데이터 겹침(EXISTS 표본) 프로브로 candidate 를 검증(겹침률 ≥0.5 양성 / ==0 음성).
  4. **비대칭 전이**: 양성 점근 상승, 음성 곱셈 감쇠(더 빠름) → 틀린 관계가 안전하게 빨리 파단(broken).
     w≤0.15 broken(주입·그래프 제외), w≥0.85+양성누적 trusted. **FK 는 권위적 — 강등 불가.**
  5. 스키마 확장은 **비파괴 ADD COLUMN**(alembic 0026)만. 재추론 upsert 는 강화상태 보존(파단 부활 없음).
- Consequences: 그래프가 FK 0 이어도 추정 엣지(점선)로 채워지고, 사용·프로브로 신뢰 엣지(실선)로 승격되거나
  파단(숨김)된다. AI 는 `[추정 w=…]`/`[신뢰]` 태그로 신뢰 수준을 구분해 SQL 정확도 왜곡을 줄인다. 프로브는
  운영 DB read-only(키 컬럼 표본 LIMIT 50, cap)라 부하가 제한적. 라이브 e2e 는 cutover 된 AGE 스택 필요.
- Alternatives:
  - 관찰 기반만(프로브 없음): 추가 DB부하 0이나 미사용 엣지 검증 불가 → 하이브리드 대비 자기교정 느림(기각).
  - 능동 프로브 전수: 가장 엄밀하나 8K 테이블 운영 DB 부하 과다(기각). → candidate 한정 + cap 절충.
  - confidence 재사용(weight 미분리): 단조성 깨면 FK prior 손상 → 정적/동적 분리로 해소.
- Supersedes: (feature-0013 CONFIDENCE 단조 증가 모델을 weight 분리로 확장 — 대체 아님, 상위호환)
- Superseded By:

-- feature-0016 Phase 0 검증: AGE + pgvector + pg_trgm 공존 (AC-1)
-- 격리 컨테이너에서 psql -U postgres -d postgres -f 로 실행. 모든 단계 통과해야 PASS.

\set ON_ERROR_STOP on

-- 1) 세 확장 모두 설치 가능
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2) AGE 그래프 생성 + 노드/엣지 + Cypher MATCH
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('verify_g');

SELECT * FROM cypher('verify_g', $$
    CREATE (t:Table {name:'orders'})-[:HAS_COLUMN]->(c:Column {name:'customer_id'})
    RETURN t.name, c.name
$$) AS (t agtype, c agtype);

-- 다른 테이블 + REFERENCES 엣지 (관계 모델 smoke)
SELECT * FROM cypher('verify_g', $$
    CREATE (a:Column {name:'customer_id'})-[:REFERENCES {cardinality:'N:1'}]->(b:Column {name:'id'})
    RETURN a.name, b.name
$$) AS (a agtype, b agtype);

-- k-hop 이웃 패턴 (투영 API 의 핵심 질의 형태) smoke
SELECT * FROM cypher('verify_g', $$
    MATCH (t:Table {name:'orders'})-[:HAS_COLUMN]->(c:Column)
    RETURN t.name, c.name
$$) AS (t agtype, c agtype);

-- 3) pgvector 공존 회귀: vector 컬럼 + ivfflat 인덱스 + 거리 연산
CREATE TABLE _verify_vec (id int, emb vector(3));
INSERT INTO _verify_vec VALUES (1, '[1,2,3]'), (2, '[4,5,6]');
CREATE INDEX ON _verify_vec USING ivfflat (emb vector_cosine_ops) WITH (lists = 1);
SELECT id FROM _verify_vec ORDER BY emb <=> '[1,2,3]' LIMIT 1;

-- 4) pg_trgm 공존 회귀: trigram similarity + GIN
CREATE TABLE _verify_trgm (id int, txt text);
INSERT INTO _verify_trgm VALUES (1, '주문 테이블'), (2, '결제 로그');
CREATE INDEX ON _verify_trgm USING gin (txt gin_trgm_ops);
SELECT id FROM _verify_trgm WHERE txt % '주문' ORDER BY similarity(txt, '주문') DESC LIMIT 1;

-- 정리
SELECT drop_graph('verify_g', true);
DROP TABLE _verify_vec;
DROP TABLE _verify_trgm;

SELECT 'AGE+pgvector+pg_trgm coexist: PASS' AS result;

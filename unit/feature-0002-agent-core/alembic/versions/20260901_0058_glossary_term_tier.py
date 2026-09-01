"""kb_glossary/glossary_feedback 에 term_tier(전역 vs 제품) 축 추가.

⚠ 리비전 번호 0057 → **0058 재번호**(§13.1 감지-후-재번호): 병렬 세션이 같은 날
`0057_redteam_review_source` 를 먼저 머지해 번호가 충돌했다. down_revision 을 그
리비전으로 걸어 체인을 직렬로 잇는다 — 두 head 가 생기면 `upgrade head` 가 모호해진다.

## 왜 이 컬럼이 필요한가 (2026-09-01 사용자 신고)

「관리 콘솔 > 메타데이터 > 용어 사전」에 **일반적인 DB 용어**(복제 이벤트·Online DDL·
시점 복구 등)가 특정 제품 scope 로 제한 등록되고, 같은 개념이 제품마다 중복 등록되는
마찰이 관측됐다. 라이브 실측(2026-09-01): `source='auto'` 722행이 11개 제품 scope 에
흩어져 있고 그중 `트랜잭션`·`복합 인덱스`·`CTE`·`실행 계획(EXPLAIN)`·`B-tree 인덱스`
같은 범용 RDBMS 지식이 다수. 34개 용어가 2~4개 scope 에 중복, 표기변형까지 세면
`멱등성` 한 개념이 7행(4 scope)이었다.

**근본 원인은 축의 비대칭이다.** 읽기(`_kb_scope_candidates`)는
`[제품, (레거시 ds), common, '']` 2단 캐스케이드인데, 쓰기(`_glossary_autopropose`)는
**항상 제품 scope 하나**였다. 전역 티어가 읽기에만 존재하고 쓰기에는 없었다.

여기에 프롬프트가 그 비대칭을 증폭했다 — `GLOSSARY_SUGGEST_PROMPT` 가 confidence 를
"how clearly defined AND **how reusable**" 로 정의해, **범용일수록 confidence 가 올라가
자동승급 임계(0.85)를 넘고, 그렇게 가장 좁은 scope 에 자동등록**됐다. 재사용성이
저장 위치를 좁히는 방향으로 작동한 것이다.

## 이 마이그가 여는 축

`term_tier` — 이 용어가 **어디까지 통용되는가**. confidence(정의의 명확성)와 **직교**한다.

| tier | 뜻 | 저장 scope |
|---|---|---|
| `product` | 이 제품 고유 도메인 어휘 (테이블·컬럼·게임 내 개념) | `product.<key>` |
| `org` | 제품 무관하지만 이 조직/서비스 고유 어휘 | `common` |
| `general` | 범용 RDBMS·업계 표준 지식 (LLM 이 이미 아는 것) | **등록 안 함** |

`general` 을 저장하지 않는 이유(사용자 결정 2026-09-01): 프롬프트에 주입해도 모델이
이미 아는 내용이라 토큰만 먹고, 그 행들이 사전을 채워 진짜 도메인 어휘를 가린다.
다만 **판정 사실은 남긴다** — `glossary_feedback.status='skipped_general'` 로 적재해
① 무엇이 왜 걸러졌는지 관리자가 콘솔에서 확인할 수 있고 ② 같은 후보가 매 턴 다시
LLM 판정을 타지 않으며(재제안 억제) ③ 오분류를 관리자가 promote 로 되돌릴 수 있다.
조용히 버리면 "요즘 용어가 안 쌓인다" 와 구별되지 않는다.

## 스키마 변경 (additive·멱등·기존 데이터 무손실)

1. `kb_glossary.term_tier varchar(16) NOT NULL DEFAULT 'product'`
   기존 행은 전부 `product` 로 backfill — 실제로 그렇게 등록돼 있었으므로 **사실 그대로**다
   (소급 재분류는 이 마이그가 하지 않는다. `scripts/glossary_tier_sweep.py` 가 dry-run 을
   거쳐 운영자 판단으로 수행한다 — 자동 데이터 이동은 §12.3 파괴적 변경 축).
2. `glossary_feedback.term_tier` 동일 + `status` CHECK 에 `skipped_general` 추가.
3. 조회 인덱스 2개.

**DEPLOY TRAP (0013/0023 동형)**: superuser 로 적용되므로 신규 객체에 명시 GRANT 가
없으면 `agent_kb_rw` 가 permission denied 를 받는다. 컬럼 ADD 는 기존 테이블 GRANT 를
승계하므로 여기서는 시퀀스 GRANT 만 재확인한다(멱등).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0058_glossary_term_tier"
down_revision: Union[str, None] = "0057_redteam_review_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── 1. kb_glossary: term_tier(통용 범위) 축 ──────────────────────────────────────
-- 기본값 'product' — 기존 행이 실제로 제품 scope 에 등록돼 있었으므로 backfill 이 사실과 맞다.
ALTER TABLE kb_glossary ADD COLUMN IF NOT EXISTS term_tier varchar(16) NOT NULL DEFAULT 'product';
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ck_kb_glossary_term_tier;
ALTER TABLE kb_glossary ADD  CONSTRAINT ck_kb_glossary_term_tier
    CHECK (term_tier IN ('product', 'org', 'general'));
CREATE INDEX IF NOT EXISTS ix_kb_glossary_tier ON kb_glossary (term_tier, scope_key);

-- ── 2. glossary_feedback: term_tier + skipped_general 상태 ────────────────────────
ALTER TABLE glossary_feedback ADD COLUMN IF NOT EXISTS term_tier varchar(16) NOT NULL DEFAULT 'product';
ALTER TABLE glossary_feedback DROP CONSTRAINT IF EXISTS ck_glossary_feedback_term_tier;
ALTER TABLE glossary_feedback ADD  CONSTRAINT ck_glossary_feedback_term_tier
    CHECK (term_tier IN ('product', 'org', 'general'));

-- status CHECK 재정의 — 'skipped_general'(범용 판정으로 미등록) 추가.
-- ⚠ DROP → ADD 순서 고정: PG 는 ADD CONSTRAINT IF NOT EXISTS 를 지원하지 않으므로
--   재실행 멱등을 위해 항상 DROP 을 먼저 건다(0023 트리거 패턴과 동형).
ALTER TABLE glossary_feedback DROP CONSTRAINT IF EXISTS ck_glossary_feedback_status;
ALTER TABLE glossary_feedback ADD  CONSTRAINT ck_glossary_feedback_status
    CHECK (status IN ('pending', 'auto_promoted', 'promoted', 'rejected', 'skipped_general'));

CREATE INDEX IF NOT EXISTS ix_glossary_feedback_tier
    ON glossary_feedback (term_tier, status, created_at DESC);

-- ── 3. 표기변형 중복 조회용 정규화 인덱스 ─────────────────────────────────────────
-- `멱등성` / `멱등성(Idempotency)` / `멱등성(idempotent)` 이 서로 다른 행으로 공존하던 것을
-- 등록 시점에 잡으려면 정규화 표면형으로 조회해야 한다. 함수 인덱스로 그 조회를 seq-scan 이
-- 되지 않게 한다. 정규화식은 `kb_glossary.normalize_term_surface()` 와 **같은 규칙**이어야
-- 하며, 양쪽이 갈리면 인덱스가 안 쓰이거나(느림) 조회가 어긋난다(중복 미검출).
-- Python 쪽 계약: 괄호 이하 제거 → 공백/하이픈/언더스코어 제거 → 소문자.
CREATE INDEX IF NOT EXISTS ix_kb_glossary_term_norm ON kb_glossary (
    lower(regexp_replace(regexp_replace(term, '\s*[(（].*$', '', 'g'), '[[:space:]_-]', '', 'g'))
);

-- ── GRANT 재확인 (DEPLOY TRAP — 컬럼 ADD 는 테이블 GRANT 승계, 시퀀스만 멱등 재부여) ──
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_kb_glossary_term_norm;
DROP INDEX IF EXISTS ix_glossary_feedback_tier;
DROP INDEX IF EXISTS ix_kb_glossary_tier;

-- status CHECK 를 되돌리기 전에 skipped_general 행을 rejected 로 접는다 —
-- 그러지 않으면 제약 재추가가 실패해 downgrade 자체가 막힌다(감사 흔적은 보존).
UPDATE glossary_feedback SET status = 'rejected' WHERE status = 'skipped_general';
ALTER TABLE glossary_feedback DROP CONSTRAINT IF EXISTS ck_glossary_feedback_status;
ALTER TABLE glossary_feedback ADD  CONSTRAINT ck_glossary_feedback_status
    CHECK (status IN ('pending', 'auto_promoted', 'promoted', 'rejected'));

ALTER TABLE glossary_feedback DROP CONSTRAINT IF EXISTS ck_glossary_feedback_term_tier;
ALTER TABLE glossary_feedback DROP COLUMN IF EXISTS term_tier;
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ck_kb_glossary_term_tier;
ALTER TABLE kb_glossary DROP COLUMN IF EXISTS term_tier;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)

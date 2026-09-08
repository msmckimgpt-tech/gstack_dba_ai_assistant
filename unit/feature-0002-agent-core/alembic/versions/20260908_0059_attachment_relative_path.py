"""agent_runtime.core_attachments.relative_path — 폴더(디렉토리 트리) 첨부의 경로 보존.

REQ-20260908-attach-folder-tree.

**무엇을 푸는가**: 첨부는 지금까지 `original_filename`(basename) 만 보존했다. 사용자가 폴더를
통째로 올리면 브라우저는 파일들을 평평하게 펼쳐 보내고, 서버는 그것들이 원래 어느 폴더의
어디에 있었는지 알 방법이 없었다. 그 결과 ① 같은 이름의 파일이 서로 다른 폴더에 있어도
구분되지 않고(`src/config.json` 과 `test/config.json`) ② assistant 는 파일 목록만 볼 뿐
구조를 볼 수 없다.

`relative_path` 는 사용자가 선택한 **폴더 루트 기준 상대 경로**다(`src/utils/helper.py`).
NULL = 단일 파일 업로드(폴더 아님) — 「경로 있음 = 폴더의 일부」가 판정 규칙이다.

**original_filename 은 그대로 basename** 을 유지한다. 첨부를 파일명으로 지칭하는 경로가
이미 넓게 퍼져 있고(LLM 프롬프트의 `REFER TO ATTACHMENTS BY FILENAME`, `read_attachment`
도구, 검색 WHERE, 프론트 pill), 그 의미를 바꾸면 이 마이그레이션의 범위를 훨씬 넘는 회귀가
난다. 경로는 **추가 축**이지 기존 축의 대체가 아니다.

**버전 체인에 미치는 영향(load-bearing)**: 체인 스코프는
`(conversation_id, account_id, original_filename)` 였다. 폴더가 들어오면 서로 다른 폴더의
동명 파일이 **한 체인으로 합쳐져 서로를 supersede** 한다 — 사용자가 올린 파일이 목록에서
사라진다. 애플리케이션은 이 컬럼이 생긴 뒤 스코프에 경로를 포함한다
(`_find_latest_same_name_attachment`). 컬럼만으로는 그 결함이 닫히지 않으므로 코드 변경과
같은 cycle 에 있어야 한다.

**스키마 변경 (additive·멱등·기존 데이터 무손실)**: 컬럼 1개 ADD (nullable, DEFAULT 없음).
기존 행은 NULL — 「폴더 아님」이라는 사실 그대로다(소급 backfill 없음: 과거 업로드가 어느
폴더에서 왔는지는 존재한 적 없는 정보다).

**DEPLOY TRAP (0008/0058 동형)**: 본 마이그는 superuser 로 적용되지만, **컬럼 ADD 는 기존
테이블의 GRANT 를 승계**하므로 여기서는 신규 GRANT 가 필요 없다(신규 테이블/시퀀스 없음).

**MySQL 대응**: 첨부는 MySQL(agent_memory) 과 PG 를 dual-write 하므로 MySQL 쪽 컬럼은
`routers/_bootstrap_schema.py:_ensure_attachment_relative_path_schema` 가 fast/slow 양쪽
부트스트랩 경로에서 보장한다. 부트스트랩 DDL(`scripts/agent_runtime_schema.sql`) 에도 같은
컬럼을 반영해 fresh deploy 와 정합시킨다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0059_attachment_relative_path"
down_revision: Union[str, None] = "0058_glossary_term_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 폴더 첨부의 폴더-루트 기준 상대 경로. NULL = 단일 파일 업로드(폴더 아님).
ALTER TABLE agent_runtime.core_attachments
    ADD COLUMN IF NOT EXISTS relative_path varchar(1024);

COMMENT ON COLUMN agent_runtime.core_attachments.relative_path IS
    'REQ-20260908-attach-folder-tree: 폴더 업로드 시 선택한 폴더 루트 기준 상대 경로(src/a/b.py). NULL=단일 파일.';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    # expand-only. 되돌리면 폴더 구조 정보가 소실되므로 컬럼을 남긴다(무해한 nullable 컬럼).
    pass

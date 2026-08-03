#!/usr/bin/env python3
"""리뷰 답변의 **객체 상태 단정 ↔ 실제 도구 호출** 대조 스크린 (conversation_audit).

`FR-review-precondition-assumed-not-verified` 의 재발 감지용.

배경: 첨부 쿼리 리뷰 답변이 객체의 라이브 상태(존재/미존재/컬럼/키)를 단정하면서
그 객체를 조회한 적이 없는 경우가 많다. 2026-08-03 실측(90일): 상태 단정 84건 중
41건(48.8%)이 그 대화의 어떤 도구 결과에도 그 객체명이 없었고, `미확인` 표기는
**0건**이었다. 라이브 1건은 약 148만 행 실존 테이블을 "현재 미존재" 로 적어
대용량 PK 추가 리스크를 통째로 놓쳤다.

**이것은 지표가 아니라 스크린이다.** 정확한 위반율을 재지 못하며, 상한도 하한도
아니다(아래 오탐·누락 둘 다 존재). 쓸모는 **비율의 추세**와 **지목된 대화 목록**이며,
확정 판정은 그 대화를 직접 읽어서 한다.

측정 대상(정확히):
  - 모집단: `.sql` 첨부가 있는 대화의 **가장 긴** assistant 답변 1건(대화당 1건).
  - 주장: 한 **줄** 안에 (a) 백틱 인용 식별자와 (b) 한국어 상태 어휘(`_STATUS`)가
    함께 있는 경우. 집계 단위는 **줄이 아니라 객체**다 — 같은 객체를 여러 줄에서
    말해도 1건이며, 어느 한 줄에서라도 `미확인` 없이 단정하면 주장으로 센다.
    `미확인` 으로만 언급되고 단정이 한 번도 없는 객체는 정직 처리로 따로 센다
    (`honest_unknown_objects` — 행 수가 아니라 객체 수다).
  - 검증: 그 식별자(마지막 마디, 소문자)가 **그 대화 tool 결과 전체 문자열**에
    부분문자열로 등장하는지.

알려진 오탐(위반을 과대계상):
  - "…위험이 존재함" 처럼 객체와 무관한 상태 어휘가 같은 줄에 있으면 그 줄의 모든
    식별자를 상태 단정으로 센다.
  - 도구가 그 객체를 언급만 하고 실제로 상태를 확인하지 않았어도 "검증됨" 으로 센다
    (반대 방향 오탐 — 위반을 과소계상).
알려진 누락(위반을 과소계상):
  - 영어 상태 표현(`exists`/`does not exist`), 백틱 없는 식별자, 4자 미만 이름,
    인덱스/제약 이름(`IDX_`/`PK_` 등 — 도구 표에 이름으로 안 나와 대조 불가라 제외).
  - 한 줄에 여러 객체가 있고 `미확인` 이 하나만 있으면 그 줄 전체를 정직 처리로 센다.

사용:
  python3 bin/measure-precondition-grounding.py [--days 90] [--json]
`postgres-replica` 에 **READ ONLY 트랜잭션 + statement_timeout** 으로만 조회한다.
답변·도구 원문을 호스트로 가져와 대조하므로(대조가 문자열 매칭이라 불가피)
운영 데이터가 로컬 프로세스 메모리에 올라온다 — 결과 출력에는 객체명과 마스킹된
대화 접미사만 남긴다.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys

# 상태 어휘 — 객체의 라이브 상태를 단정하는 표현
_STATUS = (
    "미존재|존재하지 않|아직 없|없음|없습니다|이미 존재|신규 생성 예정|"
    "존재함|확인됨|만 존재|생성됨|추가됨"
)
# 주장 단위는 **줄**이다. 마크다운 표에서 식별자와 상태값은 서로 다른 셀에 있으므로
# `|` 로 끊으면 아무것도 못 잡는다(초기안의 실제 버그 — 3건 전부 0으로 셌다).
_CLAIM = re.compile(r"(?:" + _STATUS + r")")
_IDENT = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{3,})`")
_SECTION = re.compile(r"(적용\s*전제|prerequisite)", re.IGNORECASE)
_UNKNOWN = re.compile(r"미확인")

# 도구 이름 등 객체가 아닌 토큰 — 오탐 제거
_NOT_OBJECTS = {
    "search_tables", "search_routines", "describe_table", "describe_routine",
    "execute_sql", "get_sample_rows", "check_table_coverage", "explain_query",
    "scratch_sql", "read_attachment", "graph_navigate",
    # SQL 키워드·메타스키마 — 백틱으로 인용됐어도 DB 객체 주장이 아니다
    "merge", "information_schema", "performance_schema", "primary", "unique",
    "default", "current_timestamp", "auto_increment", "engine", "charset",
}

#: 인덱스/제약 이름은 도구 결과 표에 컬럼명으로만 나와 이름 대조가 성립하지 않는다
#: (조회했어도 미검증으로 세는 구조적 오탐) → 측정에서 제외한다.
_CONSTRAINT_NAME = re.compile(r"^(?:idx_|ix_|pk_|uk_|fk_|uq_)", re.IGNORECASE)

_SQL = """
BEGIN READ ONLY;
SET LOCAL statement_timeout = '120s';
COPY (
WITH sqlconv AS (
  SELECT DISTINCT conversation_id FROM agent_runtime.core_attachments
  WHERE original_filename ILIKE '%.sql' AND created_at > now() - interval '{days} days'
), ans AS (
  SELECT DISTINCT ON (m.conversation_id) m.conversation_id, m.id, m.content, m.created_at
  FROM agent_runtime.core_messages m JOIN sqlconv s USING (conversation_id)
  WHERE m.role='assistant' AND length(m.content) > 1500
  ORDER BY m.conversation_id, length(m.content) DESC
), tools AS (
  SELECT m.conversation_id, string_agg(m.content, ' ') AS toolblob
  FROM agent_runtime.core_messages m JOIN sqlconv s USING (conversation_id)
  WHERE m.role='tool' GROUP BY m.conversation_id
)
SELECT a.conversation_id, a.id, to_char(a.created_at,'YYYY-MM-DD HH24:MI'),
       a.content, coalesce(t.toolblob,'')
FROM ans a LEFT JOIN tools t USING (conversation_id)
ORDER BY a.created_at
) TO STDOUT WITH (FORMAT csv);
COMMIT;
"""


def _fetch(days: int) -> list[list[str]]:
    sql = _SQL.format(days=days)
    cmd = ["docker", "compose", "exec", "-T", "postgres-replica", "sh", "-lc",
           'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d agent_kb -q -f -']
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    # ON_ERROR_STOP 없이는 statement_timeout 으로 COPY 가 취소돼도 psql 이 0 으로 끝나
    # 빈 결과가 "대화 0건" 이라는 **정상 측정** 으로 보고된다(§18.8 codex P1). 둘 다 막는다.
    if out.returncode != 0:
        sys.stderr.write(out.stderr[:600])
        sys.exit(2)
    if not out.stdout.strip():
        sys.stderr.write("측정 실패: 결과가 비어 있습니다(타임아웃·권한·데이터 부재 구분 불가).\n"
                         + out.stderr[:400])
        sys.exit(3)
    csv.field_size_limit(10 ** 9)
    return list(csv.reader(io.StringIO(out.stdout)))


#: 측정 단위 = **답변 전체**. 초기안은 `적용 전제` 절로 스코핑했으나 데이터와 싸웠다 —
#: 어떤 답변은 그 문구를 인라인으로만 쓰고(절이 없음) 상태 단정은 본문에 두며, 어떤 답변은
#: 본문의 인라인 언급이 헤딩보다 먼저 잡혀 엉뚱한 구간을 잘랐다. 실제 해악은 "절 안" 이
#: 아니라 **조회한 적 없는 객체의 라이브 상태 단정** 이므로 절 경계를 버리고 전체를 본다.
_LOCAL_VAR = re.compile(r"^(?:[pv]_|@)", re.IGNORECASE)


def analyse(rows: list[list[str]]) -> dict:
    convs = with_section = 0
    claims = unverified = honest_unknown = 0
    offenders: list[dict] = []
    for cid, mid, when, answer, tools in rows:
        convs += 1
        sec = answer
        if _SECTION.search(answer):
            with_section += 1
        tl = tools.lower()
        # 객체별로 (단정 있었나, 미확인이었나) 를 모은 뒤 판정한다.
        # 초기안은 첫 등장에서 `seen` 에 넣어, 앞줄이 `미확인` 이면 뒷줄의 근거 없는
        # 단정을 통째로 놓쳤다(§18.8 codex P1).
        asserted: dict[str, str] = {}
        unknown_only: set[str] = set()
        for line in sec.splitlines():
            is_unknown = bool(_UNKNOWN.search(line))
            # `orders`: 미확인 처럼 상태 어휘 없이 미확인만 쓴 줄도 집계 대상이다.
            # 초기안은 `_CLAIM` 을 먼저 요구해 이런 줄을 통째로 건너뛰었고, 그 결과
            # **수정이 성공해도 `미확인` 카운터가 영원히 0** 이었다(§18.8 codex R3 P2)
            # — 즉 이 스크립트의 성공 신호 자체가 죽어 있었다.
            if not (_CLAIM.search(line) or is_unknown):
                continue
            for ident in _IDENT.findall(line):
                base = ident.split(".")[-1].lower()
                if (base in _NOT_OBJECTS or len(base) < 4
                        or _LOCAL_VAR.match(base) or _CONSTRAINT_NAME.match(base)):
                    continue      # 도구명·SQL 로컬변수·제약명은 DB 객체 주장이 아니다
                if is_unknown:
                    unknown_only.add(base)
                else:
                    asserted.setdefault(base, ident)
        local: list[str] = []
        for base, ident in asserted.items():
            claims += 1                       # 단정이 한 번이라도 있으면 주장으로 센다
            if base not in tl:
                unverified += 1
                local.append(ident)
        honest_unknown += len(unknown_only - set(asserted))
        if local:
            offenders.append({"conversation": cid[-8:], "at": when,
                              "msg": int(mid), "objects": local})
    rate = (unverified * 100.0 / claims) if claims else 0.0
    return {
        "conversations": convs,
        "mentions_precondition": with_section,
        "status_claims": claims,
        "unverified_claims": unverified,
        "unverified_rate_pct": round(rate, 1),
        "honest_unknown_objects": honest_unknown,
        "offending_conversations": offenders,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = analyse(_fetch(a.days))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    print(f"기간: 최근 {a.days}일 · `.sql` 첨부 대화 {r['conversations']}건")
    print(f"'적용 전제' 를 언급한 답변: {r['mentions_precondition']}건")
    print(f"객체 상태 주장: {r['status_claims']}건")
    print(f"  ├ 도구 결과에 그 객체가 없는 **미검증 주장**: {r['unverified_claims']}건 "
          f"({r['unverified_rate_pct']}%)")
    print(f"  └ `미확인` 으로만 언급된 **객체 수**: {r['honest_unknown_objects']}개 (위반 아님)")
    if r["offending_conversations"]:
        print("\n미검증 주장이 있는 대화:")
        for o in r["offending_conversations"]:
            print(f"  {o['at']}  …{o['conversation']}  msg={o['msg']}  {o['objects']}")
    print("\n(이 수치는 **스크린이지 지표가 아니다** — 오탐·누락이 둘 다 있어 상한도 하한도 "
          "아니다. 쓸모는 추세와 위 지목 목록이며, 확정은 그 대화를 직접 읽어서 한다. "
          "수정이 작동하면 비율이 줄고 `미확인` 객체 수가 는다.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

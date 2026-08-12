"""feature-0040 db-object-explorer: **역할 기반 DB 객체 분류 taxonomy** (SSOT).

배경 (REQ-20260812-db-object-explorer): assistant 의 구조 탐색 도구가 테이블·컬럼·인덱스·FK·
루틴까지만 있어, **트리거·이벤트·SQL Agent 작업·뷰·시노님·시퀀스** 는 탐색 수단이 없었다
(그래프 뷰도 동일 — AGE vlabel 이 Product/Datasource/Schema/Table/Column/GlossaryTerm/Routine 7종).

**왜 벤더 객체명이 아니라 '역할' 인가** (사용자 결정 2026-08-12): 궁극적으로 모든 DBMS 를
대응해야 하는데, 같은 일을 하는 객체의 이름이 벤더마다 다르다 — "시간표에 따라 자동 실행"은
MySQL 이 `EVENT`, SQL Server 가 `SQL Server Agent Job`, PostgreSQL 이 `pg_cron`, Oracle 이
`DBMS_SCHEDULER job` 이다. 벤더 객체명을 축으로 삼으면 DBMS 를 추가할 때마다 도구·그래프·
프롬프트의 어휘가 전부 갈라진다. **역할을 축으로 두고 벤더 객체를 그 역할의 구현체로 매핑**하면
축이 DBMS 수와 무관하게 고정되고, 신규 DBMS 는 `Dialect` 하위클래스가 매핑만 선언하면 된다.

## 역할 6종

| role        | 수행하는 일                          | MySQL      | SQL Server        |
|-------------|--------------------------------------|------------|-------------------|
| `routine`   | 호출되어 실행                        | PROCEDURE/FUNCTION | P/FN/IF/TF/…  |
| `view`      | 저장된 질의가 테이블처럼 조회됨      | VIEW       | VIEW              |
| `trigger`   | 데이터/DDL 변경에 반응해 자동 실행   | TRIGGER    | DML/DDL TRIGGER   |
| `schedule`  | 시간표에 따라 자동 실행              | EVENT      | Agent Job         |
| `alias`     | 다른 객체를 가리키는 이름            | (없음)     | SYNONYM           |
| `generator` | 값을 순차 생성                       | (없음)¹    | SEQUENCE          |

¹ MySQL 의 `AUTO_INCREMENT` 는 **컬럼 속성**이지 독립 객체가 아니다 — 역할은 존재하나 이 DBMS 에
  독립 객체로서는 없다(`UNSUPPORTED`). 이 구분이 중요한 이유는 아래 참조.

`routine` 은 **본 모듈이 신설한 것이 아니라** feature-0016 ADR-016 이 이미 `routine_objects` SSOT +
AGE `Routine` 라벨로 구현해 둔 역할이다. 여기서는 taxonomy 의 완결성을 위해 **선언만** 하고
(`OWNED_ELSEWHERE`), 저장·투영은 기존 경로가 계속 담당한다 — 잘 검증된 서브시스템을 새 테이블로
이관하는 것은 회귀 위험만 크고 얻는 것이 없다(ADR-DBOBJ-0001).

## 미지원(UNSUPPORTED) ≠ 부재(없음) — 본 모듈의 핵심 불변식

이 저장소는 **허위 부재**(false absence)를 반복 결함 클래스로 다뤄 왔다
(`FR-false-absence-zero-row-catalog-scope`: SQL Server 의 카탈로그 뷰가 DB 스코프라 2-part 조회가
구조적으로 0행 → 모델이 "프로시저가 없다" 고 단정). 역할 축을 도입하면 같은 함정이 **역할 단위로**
재발할 수 있다 — MySQL 에 `alias` 를 물으면 0행이 나오고, 모델은 그것을 "이 DB 에 시노님이 없다"
로 읽는다. 실제로는 **MySQL 에 시노님이라는 개념 자체가 없다**.

따라서 조회 계층은 세 상태를 반드시 구분해서 보고한다:

- `SUPPORTED`   — 이 DBMS 에 그 역할의 객체가 있고 조회 가능. 0행 = 진짜 0개.
- `UNSUPPORTED` — 이 DBMS 에 그 객체 개념이 없음. **0행이 아니라 "해당 없음"** 으로 보고한다.
- `PRIVILEGED`  — 개념은 있으나 조회에 추가 권한이 필요. 0행이 "없음" 인지 "권한 부족" 인지
                  구분 불가하므로 **반드시 그 모호성을 표면화**한다(AGENTS.md §16.7 G7-c —
                  근거 미확보 시 단정 금지). SQL Server Agent 작업이 여기 해당:
                  `msdb.dbo.sysjobs` 는 sysadmin 이 아니면 **자기가 소유한 작업만** 돌려주므로,
                  RO 계정의 0행은 "작업 없음" 을 의미하지 않는다.
- `DELEGATED`   — 지원되지만 **전용 도구가 따로 있음**(`routine` → `search_routines`/
                  `describe_routine`). 이 상태가 없으면 `routine` 이 위 세 상태 어디에도 못 들어가
                  `UNSUPPORTED` 로 떨어지고, 도구가 "MySQL 은 프로시저를 지원하지 않습니다" 라는
                  **명백한 거짓**을 말하게 된다 — 이 모듈이 막으려는 바로 그 실패를 이 모듈이
                  저지르는 셈이다. 조회를 거부하는 대신 정확한 도구로 안내한다.
"""
from __future__ import annotations

# ── 지원 상태 ────────────────────────────────────────────────────────────────
SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
PRIVILEGED = "privileged"
DELEGATED = "delegated"

# ── 역할 식별자 ──────────────────────────────────────────────────────────────
ROLE_ROUTINE = "routine"
ROLE_VIEW = "view"
ROLE_TRIGGER = "trigger"
ROLE_SCHEDULE = "schedule"
ROLE_ALIAS = "alias"
ROLE_GENERATOR = "generator"

# `routine` 은 feature-0016 ADR-016 의 routine_objects 가 소유한다 — 본 모듈의 수집·투영 대상 밖.
OWNED_ELSEWHERE = frozenset({ROLE_ROUTINE})

# DELEGATED 역할 → 안내할 전용 도구명. 도구 응답이 여기서 문구를 파생하므로 도구명이 바뀌면
# 이 표만 고치면 된다(도구 응답마다 이름을 하드코딩하면 하나가 반드시 stale 로 남는다).
DELEGATED_TOOLS: dict[str, tuple] = {
    ROLE_ROUTINE: ("search_routines", "describe_routine"),
}


def delegated_notice(role) -> str:
    """`DELEGATED` 역할을 물었을 때의 응답문 — 거부가 아니라 **정확한 도구로 재라우팅**."""
    r = normalize_role(role)
    tools = DELEGATED_TOOLS.get(r) or ()
    names = " / ".join(f"`{t}`" for t in tools) or "(전용 도구)"
    return (
        f"`{role_ko(r)}`({r}) 은(는) 이 DB 에 **존재하며 조회할 수 있습니다** — 다만 전용 도구가 "
        f"따로 있습니다: {names}. 이 도구 대신 그것을 사용하세요. "
        f"(이 응답은 '{role_ko(r)}이(가) 없다' 는 뜻이 아닙니다.)"
    )

# 역할 메타데이터. `ko`/`desc` 는 사용자·LLM 대면 어휘의 SSOT 다 — 도구 응답, 그래프 범례,
# 상세 패널이 모두 여기서 파생돼야 표현이 갈리지 않는다(§16.8 UI copy budget: 1문장 원칙).
#   icon  — 그래프 노드/목록의 시각 표식(루틴의 ƒ/⚙ 와 같은 계열).
#   order — 열거·범례의 고정 순서(사이클 간 진동 방지).
ROLES: dict[str, dict] = {
    ROLE_ROUTINE: {
        "ko": "함수·프로시저", "icon": "⚙", "order": 10,
        "desc": "호출되어 실행되는 저장 코드",
    },
    ROLE_VIEW: {
        "ko": "뷰", "icon": "▤", "order": 20,
        "desc": "저장된 질의가 테이블처럼 조회되는 객체",
    },
    ROLE_TRIGGER: {
        "ko": "트리거", "icon": "⚡", "order": 30,
        "desc": "데이터 변경에 반응해 자동 실행되는 코드",
    },
    ROLE_SCHEDULE: {
        "ko": "예약 작업", "icon": "⏱", "order": 40,
        "desc": "시간표에 따라 자동 실행되는 작업",
    },
    ROLE_ALIAS: {
        "ko": "별칭", "icon": "↪", "order": 50,
        "desc": "다른 객체를 가리키는 이름",
    },
    ROLE_GENERATOR: {
        "ko": "값 생성기", "icon": "#", "order": 60,
        "desc": "값을 순차 생성하는 객체",
    },
}

# 본 모듈(db_objects SSOT)이 수집·투영하는 역할 — taxonomy 전체에서 OWNED_ELSEWHERE 를 뺀 것.
COLLECTED_ROLES: tuple = tuple(
    r for r in sorted(ROLES, key=lambda k: ROLES[k]["order"]) if r not in OWNED_ELSEWHERE)

# 전체 역할(선언 순) — 도구 스키마 enum·문서 표 생성용.
ALL_ROLES: tuple = tuple(sorted(ROLES, key=lambda k: ROLES[k]["order"]))


def is_role(role) -> bool:
    return str(role or "").strip().lower() in ROLES


def normalize_role(role) -> str:
    """입력 문자열 → 정규 role id. 미상이면 ''.

    LLM 이 자연스럽게 쓰는 벤더 어휘(`event`, `job`, `synonym`, `sequence`, `procedure` …)와
    한국어 표기도 역할로 흡수한다 — 도구 인자에 벤더명을 넣었다는 이유로 실패시키면, 모델은
    "그런 객체는 조회할 수 없다" 로 결론내고 되묻지 않는다(관측된 give-up 패턴).
    """
    s = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not s:
        return ""
    if s in ROLES:
        return s
    return _ALIASES.get(s, "")


# 벤더 어휘·한국어 → 역할. 위 normalize_role 의 흡수 표.
_ALIASES: dict[str, str] = {
    # routine
    "procedure": ROLE_ROUTINE, "proc": ROLE_ROUTINE, "function": ROLE_ROUTINE,
    "stored_procedure": ROLE_ROUTINE, "routines": ROLE_ROUTINE,
    "프로시저": ROLE_ROUTINE, "함수": ROLE_ROUTINE,
    # view
    "views": ROLE_VIEW, "materialized_view": ROLE_VIEW, "matview": ROLE_VIEW,
    "뷰": ROLE_VIEW,
    # trigger
    "triggers": ROLE_TRIGGER, "dml_trigger": ROLE_TRIGGER, "ddl_trigger": ROLE_TRIGGER,
    "트리거": ROLE_TRIGGER,
    # schedule — 벤더 어휘가 가장 많이 갈리는 역할
    "event": ROLE_SCHEDULE, "events": ROLE_SCHEDULE, "scheduled_event": ROLE_SCHEDULE,
    "job": ROLE_SCHEDULE, "jobs": ROLE_SCHEDULE, "agent": ROLE_SCHEDULE,
    "agent_job": ROLE_SCHEDULE, "sql_agent": ROLE_SCHEDULE, "sql_agent_job": ROLE_SCHEDULE,
    "cron": ROLE_SCHEDULE, "pg_cron": ROLE_SCHEDULE, "scheduler": ROLE_SCHEDULE,
    "dbms_scheduler": ROLE_SCHEDULE,
    "이벤트": ROLE_SCHEDULE, "작업": ROLE_SCHEDULE, "잡": ROLE_SCHEDULE, "스케줄": ROLE_SCHEDULE,
    # alias
    "synonym": ROLE_ALIAS, "synonyms": ROLE_ALIAS, "dblink": ROLE_ALIAS,
    "database_link": ROLE_ALIAS, "foreign_table": ROLE_ALIAS,
    "시노님": ROLE_ALIAS, "별칭": ROLE_ALIAS,
    # generator
    "sequence": ROLE_GENERATOR, "sequences": ROLE_GENERATOR, "identity": ROLE_GENERATOR,
    "auto_increment": ROLE_GENERATOR,
    "시퀀스": ROLE_GENERATOR,
}


def role_ko(role) -> str:
    return (ROLES.get(normalize_role(role)) or {}).get("ko", str(role or ""))


def role_icon(role) -> str:
    return (ROLES.get(normalize_role(role)) or {}).get("icon", "◆")


def role_desc(role) -> str:
    return (ROLES.get(normalize_role(role)) or {}).get("desc", "")


def label(role) -> str:
    """`⚡ 트리거` 형태의 표시 라벨 — 도구 응답·그래프 범례 공통."""
    return f"{role_icon(role)} {role_ko(role)}".strip()


def unsupported_notice(role, dialect_name: str) -> str:
    """`UNSUPPORTED` 역할을 물었을 때의 응답문 — **0행이 아니라 '해당 없음'**.

    모듈 docstring 의 불변식(미지원 ≠ 부재)을 실제 문장으로 강제하는 단일 지점. 호출측이
    각자 문구를 지어내면 어느 하나가 "없습니다" 로 새고, 그 한 번이 곧 허위 부재다.
    """
    return (
        f"`{role_ko(role)}`({role}) 은(는) **{dialect_name} 에 존재하지 않는 객체 종류**입니다 — "
        f"조회 결과가 0건인 것이 아니라 이 DBMS 에 해당 개념이 없습니다. "
        f"'이 DB 에 {role_ko(role)}이(가) 없다' 고 서술하지 말고 '{dialect_name} 은 "
        f"{role_ko(role)}을(를) 지원하지 않는다' 고 서술하세요."
    )


def privileged_caveat(role, detail: str = "") -> str:
    """`PRIVILEGED` 역할의 결과에 반드시 동반되는 모호성 고지 (§16.7 G7-c).

    권한이 부족하면 카탈로그가 **오류 대신 부분/빈 결과**를 돌려주므로, 결과만 보고는
    "없음" 과 "안 보임" 이 구분되지 않는다. 그 사실을 결과와 **같은 문장 안에** 둔다.
    """
    tail = f" {detail}".rstrip() if detail else ""
    return (
        f"⚠ {role_ko(role)} 조회는 계정 권한에 따라 **보이는 범위가 달라집니다** — "
        f"결과가 비어 있어도 '{role_ko(role)}이(가) 없다' 고 단정할 수 없습니다"
        f"(권한 부족 시 오류 없이 빈 목록이 반환됩니다).{tail}"
    )

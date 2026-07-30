"""feature-0031-analysis-grounding — 통계 증거층(L0) + 분석 payload 주입(L1) 단위 테스트.

검증 축:
  A(프라이버시 불변식): 원시 샘플값이 저장 경로에 실리지 않는다 — 집계 산출물·upsert 파라미터
    양쪽에서 단정. 문자열 min/max 는 어떤 경로로도 나오지 않고, 형태 분류만 남는다.
  B(승격 정책): 첫 수집 = 카탈로그만 · refresh 간격 이내 = 수집 안 함 · 하루 1단계 · 상한 초과 금지 ·
    주간 시간창 상한.
  C(부하 게이트): `ds` 예산 거절 시 운영 DB 에 붙지 않고 다음 주기로 이월 · 슬롯 반납 누수 없음.
  D(payload 계약): 증거가 없으면 `evidence` 키 자체가 없다(종전 payload 와 동형) · 있으면 주입.
  E(thin 재정의): 항목 충족도 기준 — 계약대로 쓴 1~2문장 분석이 thin 으로 잡히지 않는다.
"""
import datetime as _dt

import pytest

from modules import metadata_stats as ms
from modules import node_analysis as na


# ── A: 프라이버시 불변식 ──────────────────────────────────────────────────────
def test_classify_pattern_returns_only_declared_classes():
    """분류 결과는 언제나 DB CHECK 제약(ck_metadata_column_stats_pattern)의 열거 안에 있다."""
    samples = [
        ["12345", "67890"], ["a1b2c3d4", "deadbeef"],
        ["550e8400-e29b-41d4-a716-446655440000"], ["u@example.com"],
        ["kim", "12345"], [], ["", "  "],
    ]
    for values in samples:
        assert ms.classify_pattern(values) in ms.VALUE_PATTERNS


def test_classify_pattern_never_echoes_input_values():
    """분류는 형태만 반환한다 — 입력 값이 반환 문자열에 섞이면 그 자체가 원시값 유출이다."""
    secret = "hong.gildong@corp.example.com"
    out = ms.classify_pattern([secret])
    assert out == "email_like"
    assert secret not in out


def test_classify_pattern_mixed_when_shapes_differ():
    assert ms.classify_pattern(["12345", "hong gildong"]) == "mixed"
    assert ms.classify_pattern(["", None]) == "empty"


def test_aggregate_sample_emits_no_raw_string_values():
    """문자열 컬럼 집계에는 값이 남지 않는다 — 길이·형태·카디널리티만."""
    columns = [{"name": "email", "data_type": "varchar"}, {"name": "age", "data_type": "int"}]
    rows = [("hong@example.com", 31), ("kim@example.com", 44), (None, 27)]
    stats = ms._aggregate_sample(columns, ["email", "age"], rows)

    email = stats["email"]
    flat = repr(email)
    assert "hong@example.com" not in flat and "kim@example.com" not in flat
    assert email["value_pattern"] == "email_like"
    assert email["len_avg"] > 0 and email["null_ratio"] == pytest.approx(1 / 3, abs=1e-4)
    # 문자열 컬럼에는 min/max 값이 존재하지 않는다(설계 불변식).
    assert "num_min" not in email and "num_max" not in email and "ts_min" not in email

    age = stats["age"]
    assert age["num_min"] == 27 and age["num_max"] == 44   # 숫자만 범위를 남긴다


def test_aggregate_sample_marks_unique_in_sample():
    columns = [{"name": "id", "data_type": "int"}]
    stats = ms._aggregate_sample(columns, ["id"], [(1,), (2,), (3,)])
    assert stats["id"]["unique_in_sample"] is True
    stats2 = ms._aggregate_sample(columns, ["id"], [(1,), (1,), (2,)])
    assert stats2["id"]["unique_in_sample"] is False


class _RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _RecordingConn:
    def __init__(self):
        self.cur = _RecordingCursor()

    def cursor(self):
        return self.cur


def test_upsert_never_binds_raw_string_values():
    """적재 파라미터에 원시 문자열이 실리지 않는다 — 스키마가 아니라 호출측에서도 단정한다."""
    catalog = {"columns": [{"name": "email", "data_type": "varchar", "is_nullable": True,
                            "char_max_len": 128}],
               "row_count_est": 100, "pk_columns": ["id"], "index_columns": ["id"],
               "fk_out": 0, "fk_in": 2}
    col_stats = {"email": {"distinct_est": 3, "null_ratio": 0.1, "len_min": 10, "len_max": 30,
                           "len_avg": 18.5, "value_pattern": "email_like", "unique_in_sample": False}}
    conn = _RecordingConn()
    ms._upsert(conn, "ds1", "app", "users", catalog, col_stats, stage=1, sampled_rows=100)

    bound = [p for _, params in conn.cur.calls for p in (params or ())]
    strings = [b for b in bound if isinstance(b, str)]
    # 문자열 바인딩은 식별자와 열거된 형태 분류뿐이다.
    allowed = {"ds1", "app", "users", "email", "varchar"} | set(ms.VALUE_PATTERNS)
    assert set(strings) <= allowed, strings


def test_load_evidence_exposes_no_string_extremes():
    """evidence 블록에도 문자열 극단값이 없다 — 문자열 컬럼은 길이·형태만."""
    class _C:
        def __init__(self):
            self._n = 0

        def cursor(self):
            return self

        def execute(self, sql, params=None):
            self._n += 1
            self._sql = sql

        def fetchone(self):
            return (1200, 3, ["id"], ["id", "email"], 1, 0, 1, 100,
                    _dt.datetime(2026, 7, 30, 1, 2, 3))

        def fetchall(self):
            return [("email", "varchar", True, 95, 0.05, None, None, None, None,
                     10, 30, 18.5, "email_like", False)]

        def close(self):
            pass

    ev = ms.load_evidence(_C(), "ds1", "app", "users")
    assert ev["row_count_est"] == 1200 and ev["pk_columns"] == ["id"]
    col = ev["columns"][0]
    assert col["pattern"] == "email_like" and col["len_avg"] == 18.5
    assert "min" not in col and "max" not in col      # 문자열 컬럼엔 극단값이 없다
    assert "unique_in_sample" not in col              # False 는 키를 만들지 않는다(토큰 절약)


def test_load_evidence_returns_none_without_table_row():
    class _C:
        def cursor(self):
            return self

        def execute(self, sql, params=None):
            pass

        def fetchone(self):
            return None

        def fetchall(self):
            return []

        def close(self):
            pass

    assert ms.load_evidence(_C(), "ds1", "app", "users") is None


# ── B: 승격 정책 ─────────────────────────────────────────────────────────────
def _now():
    return _dt.datetime(2026, 7, 30, 23, 0, 0, tzinfo=_dt.timezone.utc)   # 야간


def test_plan_stage_first_contact_is_catalog_only():
    """미수집 테이블의 첫 수집은 Stage 0 — 사용자 테이블을 읽지 않는다(보수적 시작)."""
    assert ms.plan_stage(None, None, now=_now(), ceiling=3) == 0


def test_plan_stage_skips_within_refresh_window(monkeypatch):
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 24 if "REFRESH" in name else fb)
    recent = _now() - _dt.timedelta(hours=1)
    assert ms.plan_stage(0, recent, now=_now(), ceiling=3) is None


def test_plan_stage_promotes_one_step_per_day(monkeypatch):
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 24 if "REFRESH" in name else fb)
    old = _now() - _dt.timedelta(hours=30)
    assert ms.plan_stage(0, old, now=_now(), ceiling=3) == 1
    assert ms.plan_stage(1, old, now=_now(), ceiling=3) == 2


def test_plan_stage_never_exceeds_ceiling(monkeypatch):
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 24 if "REFRESH" in name else fb)
    old = _now() - _dt.timedelta(days=30)
    assert ms.plan_stage(2, old, now=_now(), ceiling=2) == 2   # 상한 도달 → 같은 깊이 재수집
    assert ms.plan_stage(1, old, now=_now(), ceiling=1) == 1


def test_stage_ceiling_is_lower_during_business_hours(monkeypatch):
    knobs = {"AGENT_METADATA_STATS_MAX_STAGE": 3, "AGENT_METADATA_STATS_DAY_MAX_STAGE": 1}
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: knobs.get(name, fb))
    day = _dt.datetime(2026, 7, 30, 14, 0, 0)
    night = _dt.datetime(2026, 7, 30, 23, 0, 0)
    assert ms.stage_ceiling(day) == 1
    assert ms.stage_ceiling(night) == 3


def test_stage_sample_rows_grow_with_stage():
    assert ms.STAGE_SAMPLE_ROWS[0] == 0        # 카탈로그만 — 사용자 테이블 read 0
    assert ms.STAGE_SAMPLE_ROWS[1] < ms.STAGE_SAMPLE_ROWS[2] < ms.STAGE_SAMPLE_ROWS[3]


# ── C: 부하 게이트 ───────────────────────────────────────────────────────────
class _DenyingBudget:
    """`ds` 예산이 항상 거절하는 스텁 — 반납까지 관측한다."""

    def __init__(self):
        self.entered = 0
        self.exited = 0

    def acquire(self, key):
        outer = self

        class _CM:
            def __enter__(self):
                outer.entered += 1
                return False

            def __exit__(self, *a):
                outer.exited += 1
                return False

        return _CM()


def test_collect_table_defers_when_ds_budget_denies(monkeypatch):
    """예산 거절 시 운영 DB 에 붙지 않고 False 를 돌려준다(다음 주기 이월)."""
    import shared.resource_budget as rb
    budget = _DenyingBudget()
    monkeypatch.setattr(rb, "acquire", budget.acquire)

    import shared.db as db
    called = []
    monkeypatch.setattr(db, "connect", lambda **kw: called.append(kw) or (_ for _ in ()).throw(
        AssertionError("예산 거절인데 운영 DB 에 연결을 시도했다")))

    assert ms.collect_table({"engine": "mysql"}, _RecordingConn(), "ds1", "app", "t", 1) is False
    assert called == []
    assert budget.entered == 1 and budget.exited == 1   # 거절 경로도 슬롯을 반납한다


def test_enabled_follows_global_kill_switch(monkeypatch):
    import shared.resource_budget as rb
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 1)
    monkeypatch.setattr(rb, "background_enabled", lambda: False)
    assert ms.enabled() is False
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    assert ms.enabled() is True


def test_enabled_false_when_own_knob_off(monkeypatch):
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 0)
    assert ms.enabled() is False


def test_ensure_stats_is_fail_soft(monkeypatch):
    """수집 경로의 어떤 실패도 호출측으로 새지 않는다 — 분석은 증거 없이 계속된다."""
    monkeypatch.setattr(ms, "enabled", lambda: True)
    monkeypatch.setattr(ms, "_prev_state", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    ms.ensure_stats({"engine": "mysql"}, object(), "ds1", "app", "t")   # 예외 없이 반환


class _TxSpyConn:
    """savepoint 사용 여부를 관측하는 커넥션 스텁."""

    def __init__(self, fail_on=None):
        self.tx_opened = 0
        self.calls = []
        self._fail_on = fail_on or ""

    def transaction(self):
        import contextlib
        self.tx_opened += 1
        return contextlib.nullcontext()

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError("relation \"metadata_table_stats\" does not exist")

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


def test_reads_and_writes_run_inside_savepoint():
    """이 모듈은 노드 분석과 **같은 커넥션**을 쓴다 — 실패가 바깥 트랜잭션을 죽이면 안 된다.

    마이그레이션 전 배포 창에서 신규 테이블 SELECT 가 실패하면 psycopg 는 트랜잭션을 abort 시키고,
    savepoint 가 없으면 뒤따르는 노드 분석 쿼리가 전부 깨진다."""
    c = _TxSpyConn()
    ms._prev_state(c, "ds1", "app", "t")
    assert c.tx_opened >= 1
    c2 = _TxSpyConn()
    ms.load_evidence(c2, "ds1", "app", "t")
    assert c2.tx_opened >= 1


def test_missing_table_does_not_propagate(monkeypatch):
    """신규 테이블이 아직 없어도(배포 창) 호출측으로 예외가 새지 않는다."""
    monkeypatch.setattr(ms, "enabled", lambda: True)
    c = _TxSpyConn(fail_on="FROM metadata_table_stats")
    ms.ensure_stats({"engine": "mysql"}, c, "ds1", "app", "t")   # 예외 없이 반환
    assert ms.load_evidence(c, "ds1", "app", "t") is None


def test_failure_marks_error_without_wiping_existing_stats(monkeypatch):
    """수집 실패는 error 만 갱신한다 — 직전까지 유효했던 통계를 NULL 로 덮지 않는다."""
    import shared.db as db
    monkeypatch.setattr(db, "connect",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("boom 'secret-value'")))
    import shared.resource_budget as rb

    class _OkCM:
        def __enter__(self):
            return True

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(rb, "acquire", lambda key: _OkCM())
    c = _TxSpyConn()
    assert ms.collect_table({"engine": "mysql"}, c, "ds1", "app", "t", 1) is False

    writes = [sql for sql, _ in c.calls if "INSERT INTO metadata_table_stats" in sql]
    assert writes and "row_count_est" not in writes[0], "실패 경로가 전체 행을 재작성하면 안 된다"
    # 예외 문자열은 저장하지 않는다 — 드라이버 메시지에 조회한 값이 실려 올 수 있다.
    bound = [p for sql, params in c.calls if "metadata_table_stats" in sql for p in (params or ())]
    assert not any(isinstance(b, str) and "secret-value" in b for b in bound)
    assert "RuntimeError" in bound   # 예외 종류만 남긴다


def test_night_window_uses_local_clock(monkeypatch):
    """시간창은 서버 로컬 시각 기준이다 — plan_stage 가 UTC now 로 주·야를 가르면 안 된다."""
    seen = []
    monkeypatch.setattr(ms, "stage_ceiling", lambda now=None: seen.append(now) or 3)
    monkeypatch.setattr(ms, "_knob_int", lambda name, fb: 24 if "REFRESH" in name else fb)
    ms.plan_stage(0, _now() - _dt.timedelta(hours=30), now=_now())
    assert seen == [None], "UTC now 를 시간창 판정에 넘기면 서버 TZ 와 어긋난다"


# ── C: 식별자 인용 ───────────────────────────────────────────────────────────
def test_quote_ident_rejects_injection_shapes():
    assert ms._quote_ident("users; DROP TABLE x", "mysql") is None
    assert ms._quote_ident("col'--", "mysql") is None
    assert ms._quote_ident("", "mysql") is None
    assert ms._quote_ident("normal_col", "mysql") == "`normal_col`"
    assert ms._quote_ident("normal_col", "mssql") == "[normal_col]"


# ── D: payload 계약 ──────────────────────────────────────────────────────────
def test_split_table_key():
    assert na._split_table_key("ds1:app.users") == ("ds1", "app", "users")
    assert na._split_table_key("no-colon") == (None, None, None)
    assert na._split_table_key("ds1:noschema") == (None, None, None)


def test_table_evidence_none_keeps_payload_shape(monkeypatch):
    """증거가 없으면 evidence 키 자체가 생기지 않는다 — 종전 payload 와 동형."""
    monkeypatch.setattr(ms, "load_evidence", lambda *a, **k: None)
    assert na._table_evidence(object(), "ds1:app.users") is None


def test_table_evidence_is_fail_soft(monkeypatch):
    monkeypatch.setattr(ms, "load_evidence",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert na._table_evidence(object(), "ds1:app.users") is None


def test_ensure_table_stats_skips_without_multi_datasource(monkeypatch):
    monkeypatch.setattr(na._cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False, raising=False)
    called = []
    monkeypatch.setattr(ms, "ensure_stats", lambda *a, **k: called.append(a))
    na._ensure_table_stats(object(), "ds1:app.users")
    assert called == []


# ── E: thin 재정의 ───────────────────────────────────────────────────────────
def _analysis(summary, rel="", usage="", role=""):
    import json
    return json.dumps({"summary": summary, "relationships": rel, "usage": usage,
                       "caveats": "", "role": role}, ensure_ascii=False)


def test_contract_length_analysis_is_not_thin():
    """프롬프트 계약("한국어 1~2문장")대로 쓴 분석이 thin 으로 잡히지 않는다.

    종전 임계(120자)에서는 이런 정상 분석이 thin 이었고, REFINE_MAX 캡만이 재분석 폭주를
    막고 있었다 — 캡을 올리면 터지는 구조였다는 것이 이 판정 변경의 이유다."""
    text = _analysis("아이템 드롭 정의를 담는 컨텐츠 마스터 테이블이다.",
                     rel="스테이지 테이블과 stage_id 로 연결된다.",
                     usage="드롭률 조정 시 이 테이블을 조회한다.", role="master")
    assert na._analysis_is_thin(text, 20, "Table") is False


def test_thin_when_only_summary_filled():
    text = _analysis("아이템 드롭 정의를 담는 컨텐츠 마스터 테이블이다.")
    assert na._analysis_is_thin(text, 20, "Table") is True


def test_thin_placeholder_phrases_do_not_count_as_filled():
    text = _analysis("아이템 드롭 정의를 담는 컨텐츠 마스터 테이블이다.",
                     rel="연결 정보 없음", usage="없음")
    assert na._analysis_is_thin(text, 20, "Column") is True


@pytest.mark.parametrize("phrase", [
    "연결 정보 없음", "연결 정보 없음.", "연결 정보가 없습니다", "연결정보 없음",
    "해당 없음", "해당 사항이 없습니다", "정보 없음", "관련 정보가 없습니다", "N/A", "n/a", "—",
])
def test_placeholder_variants_are_not_counted_as_filled(phrase):
    """정확 일치만 보면 기존 분석문의 어미·구두점 변형이 '충족'으로 새어 들어간다.

    그러면 보충돼야 할 빈약 분석이 thin 판정을 통과해 back-refine 대상에서 빠진다."""
    assert na._is_filled(phrase) is False


@pytest.mark.parametrize("phrase", [
    "스테이지 테이블과 stage_id 로 연결된다.", "드롭률 조정 시 조회한다",
    "없음 컬럼과 조인된다",   # '없음'으로 시작하지만 실제 내용이 이어진다
])
def test_real_sentences_are_counted_as_filled(phrase):
    assert na._is_filled(phrase) is True


def test_table_role_counts_toward_completeness():
    """Table 노드는 role 도 충족 항목 — 관계가 비어도 role 이 유효하면 보충 대상이 아니다."""
    text = _analysis("아이템 드롭 정의를 담는 컨텐츠 마스터 테이블이다.",
                     rel="연결 정보 없음", usage="", role="master")
    assert na._analysis_is_thin(text, 20, "Table") is False
    assert na._analysis_is_thin(text, 20, "Column") is True   # 같은 본문도 Column 이면 빈약


def test_thin_still_true_for_empty_and_below_floor():
    assert na._analysis_is_thin(None, 20) is True
    assert na._analysis_is_thin(_analysis("짧음", rel="가나다라", usage="마바사아"), 20) is True
    assert na._analysis_is_thin("not-json{", 20) is False   # 파싱 불가는 보수적으로 비-thin

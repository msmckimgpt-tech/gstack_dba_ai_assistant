"""노드 상세 패널의 사실성 판정 노출 (feature-0036 P1 — 판정 소비처 연결).

**이 파일이 지키는 명제**: 화면에 붙는 판정은 **지금 보이는 그 문장**에 대한 것이어야 한다.

판정은 노드당 1행이라, 분석문이 갱신되면 그 행은 다른 문장에 대한 판정이 된다. 그걸 그대로
붙이면 확인 도장이 엉뚱한 문장에 찍히고, 운영자는 읽고 있는 서술이 검증된 것으로 오인한다 —
ADR-0036-01("확인하지 않은 서술에 도장을 찍지 않는다")을 표시 단계에서 되풀이하는 셈이다.

검증 축:
  A(해시 정합): 해시 일치 시에만 싣는다. 불일치·부재는 **키 자체를 싣지 않는다**.
  B(격리): 판정 조회가 실패해도 상세 패널은 정상 응답한다(판정만 사라진다).
  C(프론트 계약): 세 verdict 값만 렌더하고, 그 외/부재는 아무것도 그리지 않는다.
"""
import json
import pathlib

from modules import analysis_verify as av
from modules import node_analysis as na


_ANALYSIS = json.dumps({"summary": "계정별 아이템 보유 현황", "relationships": "",
                        "usage": "", "caveats": ""}, ensure_ascii=False)


class _Cur:
    """node_analysis_jobs 1행 + node_analysis_verdicts(해시 조건부) 를 흉내낸다."""

    def __init__(self, stored_hash=None, verdict_row=None, verdict_raises=False, label="Table"):
        self._label = label
        self._stored_hash = stored_hash
        self._verdict_row = verdict_row
        self._verdict_raises = verdict_raises
        self._last = None
        self.verdict_params = None

    def execute(self, sql, params=None):
        if "SAVEPOINT" in sql.upper():
            return
        if "FROM node_analysis_verdicts" in sql:
            if self._verdict_raises:
                raise RuntimeError("verdicts unavailable")
            self.verdict_params = params
            # 실제 SQL 은 WHERE ... AND analysis_hash=%s — 불일치면 0행이다. 그것을 재현한다.
            self._last = self._verdict_row if params and params[2] == self._stored_hash else None
        elif "FROM node_analysis_jobs" in sql:
            self._last = ("done", _ANALYSIS, "m1", None, "run1", self._label, "master")
        else:
            self._last = None

    def fetchone(self):
        return self._last

    def close(self):
        pass


class _Conn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur


def _get(monkeypatch, cur):
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (_Conn(cur), False))
    return na.get_node_analysis("ds1", "ds1:app.items")


# ── A: 해시 정합 ─────────────────────────────────────────────────────────────
def test_verdict_is_surfaced_for_the_matching_analysis(monkeypatch):
    cur = _Cur(stored_hash=av.analysis_hash(_ANALYSIS),
               verdict_row=("contradicted", "distinct_est 12 가 sampled_rows 100 보다 작다", 1, None))
    res = _get(monkeypatch, cur)
    assert res["verdict"]["verdict"] == "contradicted"
    assert "distinct_est" in res["verdict"]["reason"]
    assert res["verdict"]["evidence_stage"] == 1
    # 조회 조건 3요소를 **전부** 고정한다 — 해시만 단정하면 scope/node 를 뺀 구현(다른 노드의
    #   판정을 붙이는)이 테스트를 통과한다. ADR 이 기대는 PK 는 (scope, node, hash) 셋이다.
    assert cur.verdict_params == ("ds1", "ds1:app.items", av.analysis_hash(_ANALYSIS))


def test_stale_verdict_for_a_different_analysis_is_not_surfaced(monkeypatch):
    """분석문이 갱신되면 옛 판정은 **그 문장에 대한 것이 아니다** — 붙이지 않는다.

    이 테스트가 이 기능의 존재 이유다. 해시 조건을 빼는 변이(노드 키만으로 조회)는 옛 판정을
    새 문장에 붙여, 운영자가 검증되지 않은 서술을 검증된 것으로 읽게 만든다."""
    cur = _Cur(stored_hash="OLDHASH_FROM_A_PREVIOUS_VERSION",
               verdict_row=("supported", "근거", 1, None))
    res = _get(monkeypatch, cur)
    assert "verdict" not in res
    assert res["status"] == "done" and res["analysis"]["summary"]      # 상세는 그대로


def test_no_verdict_row_means_no_key(monkeypatch):
    """아직 판정되지 않았으면 아무 표시도 없다 — '미검증'과 '판정 실패'를 화면이 구분할 필요가 없다."""
    cur = _Cur(stored_hash=av.analysis_hash(_ANALYSIS), verdict_row=None)
    assert "verdict" not in _get(monkeypatch, cur)


def test_empty_verdict_value_is_rejected(monkeypatch):
    cur = _Cur(stored_hash=av.analysis_hash(_ANALYSIS), verdict_row=("", "근거", 1, None))
    assert "verdict" not in _get(monkeypatch, cur)


# ── B: 격리 ──────────────────────────────────────────────────────────────────
def test_verdict_lookup_failure_does_not_break_the_detail_panel(monkeypatch):
    """판정 표시가 없는 것이 상세 패널이 깨지는 것보다 낫다(신규 테이블 부재 배포 창 포함)."""
    cur = _Cur(stored_hash=av.analysis_hash(_ANALYSIS), verdict_raises=True)
    res = _get(monkeypatch, cur)
    assert res is not None and res["status"] == "done"
    assert "verdict" not in res


def test_non_table_nodes_skip_the_lookup(monkeypatch):
    """판정 대상은 Table 뿐이다 — Column/Routine/Schema 는 결과가 보장된 빈 왕복이다.

    라이브 done 행은 Column 5,192 / Routine 2,558 / Table 2,052 로, 가드가 없으면 노드 클릭의
    ~79% 가 그 왕복을 낸다(`product_classify` 는 Schema 키로 스키마마다 부른다)."""
    cur = _Cur(stored_hash=av.analysis_hash(_ANALYSIS),
               verdict_row=("supported", "근거", 1, None), label="Column")
    res = _get(monkeypatch, cur)
    assert "verdict" not in res
    assert cur.verdict_params is None, "Table 이 아닌데 판정을 조회했다"


def test_verdict_query_is_wrapped_in_a_savepoint():
    """워커·웹이 같은 커넥션을 쓸 때, 조회 실패가 트랜잭션 전체를 abort 시키면 안 된다."""
    import inspect
    src = inspect.getsource(na._verdict_for)
    assert "_savepoint" in src


# ── C: 프론트 계약 (CI 가 JS 를 실행하지 않으므로 소스로 고정) ────────────────
_CTXMENU = (pathlib.Path(__file__).resolve().parents[2]
            / "feature-0003-agent-web-ui" / "src" / "static" / "graph" / "graph-ctxmenu.js")


def _verdict_block() -> str:
    """판정 배지 렌더 블록의 **코드만** (주석 제거).

    주석에는 "왜 이렇게 안 했는가"를 적기 때문에 기각한 값(`#009E73`·"검증됨")이 그대로 등장한다.
    주석을 포함해 단정하면 설명을 쓸수록 테스트가 깨지고, 반대로 코드가 그 값을 되살려도 통과한다."""
    src = _CTXMENU.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("//"))
    # 경계는 길이가 아니라 **구조**로 잡는다 — 주변 코드가 길어졌다고 단정이 깨지면 안 된다.
    start = code.index("const V = {")
    end = code.index("if (a.summary)", start)
    return code[start:end]


def test_frontend_renders_only_the_three_declared_verdicts():
    body = _verdict_block()
    for v in av.VERDICTS:
        assert v in body, f"{v} 렌더 분기가 없다"
    # 미등록 값·부재는 아무것도 그리지 않는다(표 조회 결과가 없으면 렌더 skip).
    assert "res.verdict && V[res.verdict.verdict]" in body


def test_frontend_escapes_the_verdict_reason():
    """reason 은 LLM 이 쓴 문장이다 — 이스케이프 없이 innerHTML 에 넣으면 주입면이 된다.

    절단본(화면)과 전문(title) **양쪽** 다 이스케이프해야 한다 — title 속성도 주입면이다."""
    body = _verdict_block()
    assert "esc(shown)" in body and 'title="${esc(r)}"' in body


def test_frontend_uses_state_tag_palette_not_role_palette():
    """색은 역할 팔레트가 아니라 상태 태그 시스템(--tag-*)을 쓴다 (ADR-0036-09).

    역할 색을 재사용하면 `config`(#D55E00) 역할 칩과 contradicted 배지가 **같은 색·같은 모양**으로
    연달아 붙어 경보가 카테고리 태그로 읽힌다. --tag-* 는 대비(4.3~5.7:1)도 함께 보증한다 —
    역할 팔레트의 #009E73 은 흰 배경 대비 3.42:1 로, 팔레트 자신이 '4.5 미달'이라 라벨을 뒤집어
    구제한 값이다(테두리형 배지에는 그 구제 수단이 없다)."""
    body = _verdict_block()
    assert "var(--tag-" in body
    for role_color in ("#009E73", "#D55E00", "#8b949e"):
        assert role_color not in body, f"{role_color} 는 역할 팔레트/비저장소 값이다"


def test_frontend_label_does_not_claim_verification():
    """라벨은 "부합/검증됨"이 아니라 **"모순 없음"** 이다.

    판정 근거는 100행 안팎의 표본이고 실패한 판정은 애초에 기록되지 않는다(ADR-0036-01·생존편향).
    `✓` 같은 합격 도장을 붙이면 위층이 더 확신하게 되는, 이 층이 막으려던 실패를 표시 단계가
    되살린다(ANCHOR §1)."""
    body = _verdict_block()
    assert "모순 없음" in body
    assert "증거와 부합" not in body and "검증됨" not in body


def test_frontend_surfaces_evidence_stage():
    """얕은 증거로 내린 판정과 깊은 증거로 내린 판정이 화면에서 같아 보이면 안 된다.

    대상 선정이 stage 로 정렬까지 하는 이유가 "얕은 증거로 내린 판정은 정보가 적다" 이다."""
    body = _verdict_block()
    assert "evidence_stage" in body and "title=" in body


def test_legend_declares_that_no_badge_means_not_yet_judged():
    """"배지 없음 = 아직 판정 전"을 화면 어딘가는 말해야 한다.

    대상 2,052 노드 중 판정 보유는 94개다. 운영자의 지배적 경험은 "대부분 아무것도 없다" 이고,
    거기서 나오는 합리적 추론("표시 없는 것은 문제없다")은 정확한 반전이다."""
    html = (pathlib.Path(__file__).resolve().parents[2] / "feature-0003-agent-web-ui"
            / "src" / "static" / "admin.html").read_text(encoding="utf-8")
    assert "AI 표본 대조 판정" in html
    assert "배지가 없으면 아직 판정 전" in html

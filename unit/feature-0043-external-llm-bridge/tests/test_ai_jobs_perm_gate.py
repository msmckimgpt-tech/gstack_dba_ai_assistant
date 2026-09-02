"""feature-0043 TASK-20260902T160000 — 프로필 'AI 작업' 탭은 **열 수 있는 작업만** 보인다.

사용자 요청(2026-09-02): "계정 프로필 내 'AI 작업' 탭에서, 실제로 해당 계정이 접근할 수 있는
기능들에 대해서 권한을 소유하고 있을 경우에만 노출되도록 구성해주세요."

## 이 스위트가 잠그는 세 가지

1. **선언의 진위** — `JOB_SPECS[*]["perms"]` 에 적힌 권한 코드가 실제 권한 카탈로그에 있는가.
   오타는 조용하다: 없는 코드는 `_account_has_permission` 이 언제나 False 로 답하므로, 그
   항목은 **관리자를 포함한 전 계정에서 영구히 사라진다**. 화면에서 사라진 것은 오류로 보이지
   않기 때문에(그냥 "없는 기능") 사람이 신고하기까지 오래 걸린다.

2. **선언의 전수성** — 모든 종류가 `perms` 를 명시하는가. 선언을 빠뜨린 종류는 런타임에
   "요구 없음"(=노출)으로 흐른다. 그 기본값은 안전한 쪽이지만(집행은 서버가 계속 한다),
   빠뜨린 사실 자체는 여기서 잡아야 이 변경이 다음 종류에 자동으로 이어진다.

3. **배선** — GET 과 PUT 이 **같은** 필터를 통과하는가. 한쪽만 필터하면 두 결함 중 하나가 난다:
   - GET 만 필터 → 화면에서 감춘 항목이 저장 경로로 되살아난다(표시만 하는 장식 게이트).
   - PUT 만 필터 → 보이는 항목을 저장하지 못한다.
   그리고 PUT 의 「통째 교체」가 **보이는 범위로 한정**되는가 — 전체에 적용하면 권한이 빠진
   계정의 저장 버튼 한 번이 숨겨진 항목의 기존 설정을 증발시킨다.

역검증 기준: 아래 테스트들은 이 cycle 이전 코드(`perms` 필드 부재 ·
`visible_console_job_kinds` 부재 · `for kind, spec in JOB_SPECS.items()` 무필터 루프)에서
전부 실패해야 한다.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from shared import bridge_tasks as bt

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
PROFILE_PY = WEB_SRC / "routers" / "profile.py"
WEB_CONTEXT_PY = WEB_SRC / "web_context.py"
PROFILE_JS = WEB_SRC / "static" / "app" / "profile.js"


def _src(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _func_src(path: pathlib.Path, name: str) -> str:
    """함수 하나의 소스만 떼어 온다 — 파일 전역 substring 은 옆 함수의 코드로 통과한다."""
    tree = ast.parse(_src(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(_src(path), node) or ""
    raise AssertionError(f"{path.name} 에 {name} 가 없다")


def _web_context():
    """`web_context` 모듈. **`importorskip` 을 쓰지 않는다** — 이 스위트의 PYTHONPATH 는
    `feature-0003/src` 를 포함하므로(Makefile·ci.yml 동일) import 실패는 환경 결손이지 정상
    상태가 아니다. skip 으로 넘기면 아래 fail-closed 가드가 **조용히 꺼진 채** 통과한다.

    `web_context` 는 라우터와 달리 `app` 을 끌어오지 않아 import 부작용이 없다.
    """
    import web_context

    return web_context


def _catalog_codes() -> set[str]:
    """권한 카탈로그의 코드 집합.

    `web_context` 를 import 하지 않고 **소스에서** 읽는다 — 이 테스트는 워커 쪽 conftest 에서
    돌고, 웹 모듈은 그 경로에서 import 되지 않는다(모듈 부재로 SKIP 되면 게이트가 조용히
    꺼진다). `PERMISSION_DEFINITIONS` 리터럴을 AST 로 훑어 `"code"` 값만 모은다.
    """
    tree = ast.parse(_src(WEB_CONTEXT_PY))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "PERMISSION_DEFINITIONS" not in targets:
            continue
        codes: set[str] = set()
        for item in getattr(node.value, "elts", []):
            if not isinstance(item, ast.Dict):
                continue
            for key, value in zip(item.keys, item.values):
                if (isinstance(key, ast.Constant) and key.value == "code"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    codes.add(value.value)
        assert codes, "PERMISSION_DEFINITIONS 에서 code 를 하나도 추출하지 못했다 (추출기 파손)"
        return codes
    raise AssertionError("web_context.py 에 PERMISSION_DEFINITIONS 가 없다")


# ── 1. 선언 자체 ──────────────────────────────────────────────────────────────

def test_every_job_declares_perms():
    """모든 종류가 `perms` 를 **명시**한다 — 빠뜨림과 「요구 없음」을 구분한다."""
    missing = [k for k, spec in bt.JOB_SPECS.items() if "perms" not in spec]
    assert not missing, f"perms 선언 누락: {missing} (요구 없음이면 빈 튜플 ()을 명시할 것)"


def test_declared_perms_are_tuples_of_str():
    for kind, spec in bt.JOB_SPECS.items():
        perms = spec["perms"]
        assert isinstance(perms, tuple), f"{kind}.perms 는 tuple 이어야 한다 (got {type(perms)})"
        for code in perms:
            assert isinstance(code, str) and code.strip(), f"{kind}.perms 에 빈/비문자 코드"


def test_declared_perms_exist_in_permission_catalog():
    """⭐ 오타 방지 — 카탈로그에 없는 코드는 **전 계정에서 항목을 지운다**(조용한 소실)."""
    catalog = _catalog_codes()
    unknown = {
        kind: [c for c in spec["perms"] if c not in catalog]
        for kind, spec in bt.JOB_SPECS.items()
        if [c for c in spec["perms"] if c not in catalog]
    }
    assert not unknown, (
        f"권한 카탈로그에 없는 코드: {unknown}. 이 코드는 아무도 보유할 수 없어 해당 항목이 "
        f"관리자에게도 보이지 않게 된다 — 카탈로그(web_context.PERMISSION_DEFINITIONS) 와 대조할 것.")


def test_batch_jobs_declare_no_permission():
    """배경 배치는 RBAC 축이 아니라 **동의** 축이다 (`_batch_consenting_account`).

    권한을 지어 붙이면 실제로 그 작업을 받는 계정(동의한 러너 보유자)의 설정칸이 사라진다.
    """
    for kind in bt.BATCH_JOB_KINDS:
        assert bt.JOB_SPECS[kind]["perms"] == (), (
            f"{kind}: 배경 배치는 권한이 아니라 배경 작업 동의로 배급된다 — perms 는 () 여야 한다")


# ── 2. 판정 함수 계약 ─────────────────────────────────────────────────────────

def test_console_job_perms_reads_registry():
    assert bt.console_job_perms("metadata_bulk") == ("metadata.table.update",)
    assert bt.console_job_perms("insight_summary") == ()
    # 모르는 종류는 빈 튜플 — 예외를 던지면 목록 렌더 한 건이 화면 전체를 죽인다.
    assert bt.console_job_perms("__nope__") == ()
    assert bt.console_job_perms("") == ()
    assert bt.console_job_perms(None) == ()


def test_visible_kinds_hides_only_unpermitted():
    """권한 0 인 계정: 요구가 있는 종류만 사라지고, 요구 없는 종류는 남는다."""
    none = bt.visible_console_job_kinds(lambda _c: False)
    for kind, spec in bt.JOB_SPECS.items():
        if spec["perms"]:
            assert kind not in none, f"{kind}: 권한 없는데 노출됐다"
        else:
            assert kind in none, f"{kind}: 권한 요구가 없는데 사라졌다"


def test_visible_kinds_all_for_superuser():
    every = bt.visible_console_job_kinds(lambda _c: True)
    assert every == tuple(bt.JOB_SPECS), "전 권한 계정에는 JOB_SPECS 순서 그대로 전량 노출"


def test_visible_kinds_any_of_semantics():
    """서브뷰 권한 하나만 있어도 메타데이터 자동완성(단건)은 도달한다 — any-of."""
    only_glossary = bt.visible_console_job_kinds(lambda c: c == "metadata.glossary.update")
    assert "metadata_suggest" in only_glossary
    # 일괄은 metadata.table.update 만 인정하므로 함께 열리지 않는다(요구가 다르다).
    assert "metadata_bulk" not in only_glossary


def test_visible_kinds_preserves_registry_order():
    """순서가 곧 화면 순서다 — 권한에 따라 항목이 뒤섞이면 사용자가 자리를 잃는다."""
    partial = bt.visible_console_job_kinds(lambda c: c == "metadata.graph.analyze")
    assert list(partial) == [k for k in bt.JOB_SPECS if k in set(partial)]


# ── 2-b. 병합 규칙 — **행위**로 검사한다 (codex 2R P3) ────────────────────────
#
# 저장 경로의 핵심 회귀(빈/부분 본문·표기 변형·숨긴 값 보존)를 소스 문자열 단정으로만 잠그면,
# 실제로 값이 지워져도 테스트는 통과한다. 그래서 병합을 순수 함수로 떼어 **실 dict 로** 돌린다.

_M = {"model": "codex:luna", "effort": "medium"}
_N = {"model": "claude:haiku", "effort": "low"}


def test_merge_replaces_visible_and_preserves_hidden():
    stored = {"metadata_bulk": _M, "cluster_label": _N}
    # metadata_bulk 는 숨겨진 상태(권한 없음), cluster_label 만 보인다.
    out = bt.merge_visible_console_job_prefs(stored, {"cluster_label": _M}, {"cluster_label"})
    assert out["metadata_bulk"] == _M, "숨겨진 종류의 기존 설정이 지워졌다"
    assert out["cluster_label"] == _M, "보이는 종류가 교체되지 않았다"


def test_merge_clears_visible_when_incoming_empty():
    """[모두 기본값] 후 저장 = 보이는 항목 비우기. 이것은 **정당한 입력**이다."""
    stored = {"metadata_bulk": _M, "cluster_label": _N}
    out = bt.merge_visible_console_job_prefs(stored, {}, {"cluster_label"})
    assert "cluster_label" not in out
    assert out["metadata_bulk"] == _M, "비우기가 숨겨진 종류까지 지웠다"


def test_merge_drops_incoming_for_hidden_kinds():
    """권한 밖 종류를 본문에 실어 보내도 저장되지 않는다(fail-open 차단)."""
    out = bt.merge_visible_console_job_prefs({}, {"node_analysis": _M}, {"cluster_label"})
    assert "node_analysis" not in out, "숨긴 종류의 값이 저장됐다"


def test_merge_does_not_resurrect_hidden_value_from_incoming():
    """숨긴 종류는 **기존 값이 유지**될 뿐, 요청이 그 값을 바꿀 수 없다."""
    out = bt.merge_visible_console_job_prefs(
        {"node_analysis": _M}, {"node_analysis": _N}, {"cluster_label"})
    assert out["node_analysis"] == _M, "숨긴 종류를 요청이 덮어썼다"


@pytest.mark.parametrize("variant", [" node_analysis", "node_analysis ", "NODE_ANALYSIS"])
def test_merge_normalizes_before_filtering(variant):
    """표기 변형이 가시성 필터를 빠져나가 숨긴 항목을 덮어쓰지 못한다.

    정규화가 필터보다 **먼저**여야 성립한다 — 순서가 뒤집히면 이 케이스가 통과한다.
    """
    out = bt.merge_visible_console_job_prefs(
        {"node_analysis": _M}, {variant: _N}, {"cluster_label"})
    assert out.get("node_analysis") == _M, f"{variant!r} 가 숨긴 항목을 덮어썼다"


@pytest.mark.parametrize("junk", [None, [], "", 0, "not-json", {"jobs": 1}])
def test_merge_tolerates_non_dict_incoming(junk):
    """비-dict 입력에 예외를 던지지 않는다 — 라우터가 4xx 로 거르지만 함수도 견고해야 한다."""
    out = bt.merge_visible_console_job_prefs({"node_analysis": _M}, junk, {"cluster_label"})
    assert out == {"node_analysis": _M}


class _BoomCursor:
    """`SELECT` 가 던지는 커서 — 조회 실패를 «미설정» 으로 오인하는지 가른다."""

    def execute(self, *_a, **_k):
        raise RuntimeError("db read failed")

    def fetchone(self):  # pragma: no cover — execute 에서 이미 던진다
        return None


class _RowCursor:
    def __init__(self, value):
        self._value = value

    def execute(self, *_a, **_k):
        return None

    def fetchone(self):
        return (self._value,)


def test_lenient_read_swallows_failure_for_display():
    """읽기 경로는 조회 실패를 «미설정» 으로 본다 — 컬럼 없는 배포가 화면을 막지 않는다."""
    assert bt.console_job_prefs_for_account(_BoomCursor(), 7) == {}


def test_strict_read_raises_so_writes_never_build_on_unknown(  ):
    """쓰기 baseline 은 실패를 **예외**로 올린다 (codex 2R).

    실패를 `{}` 로 받으면 병합이 「보존할 것이 없다」고 판단해 **숨겨진 항목을 지운 문서**를
    쓰고 200 을 돌려준다 — 잃은 값이 화면에 없던 것이라 사용자는 알아채지 못한다.
    """
    with pytest.raises(Exception):
        bt.read_console_job_prefs_strict(_BoomCursor(), 7)
    # 정상 경로는 동치여야 한다 — 엄격판이 값을 다르게 읽으면 저장이 조용히 달라진다.
    raw = '{"cluster_label": {"model": "codex:luna", "effort": "medium"}}'
    assert (bt.read_console_job_prefs_strict(_RowCursor(raw), 7)
            == bt.console_job_prefs_for_account(_RowCursor(raw), 7))


def test_strict_read_rejects_missing_account_id():
    for bad in (0, None, "", "abc"):
        with pytest.raises(ValueError):
            bt.read_console_job_prefs_strict(_RowCursor("{}"), bad)


def test_put_uses_the_strict_read_for_its_baseline():
    src = _func_src(PROFILE_PY, "put_profile_console_jobs")
    assert "read_console_job_prefs_strict" in src, (
        "PUT 이 lenient 읽기를 baseline 으로 쓴다 — 조회 실패가 숨긴 설정을 지운다")
    # ⚠ `_store.` 접두를 함께 본다 — `account_console_job_prefs(` 만 찾으면
    #   `set_account_console_job_prefs(` 의 부분문자열로 매칭돼 항상 실패한다(하네스가 적발).
    assert "_store.account_console_job_prefs(" not in src, "lenient 읽기가 아직 남아 있다"


def test_safe_permission_check_survives_a_throwing_evaluator():
    """판정기가 던져도 화면이 죽지 않고 «요구 없는 종류» 로 축소된다 (codex 2R P2)."""
    def boom(_code):
        raise RuntimeError("permission store down")

    kinds = bt.visible_console_job_kinds(boom)
    assert kinds == tuple(k for k, s in bt.JOB_SPECS.items() if not s["perms"])
    assert kinds, "전면 실패 시에도 요구 없는 종류는 남아야 한다"


# ── 2-c. 레거시 묶음 함의 — fail-closed 회귀의 가장 그럴듯한 경로 ────────────
#
# 이 저장소의 권한은 **묶음(`kb.ingest.manual`·`metadata.*.manage`)이 원자 단위를 transitive 로
# 함의**한다(`_apply_permission_overrides`). 그 전개가 effective map 안에서 일어나므로 우리 필터도
# 같은 사실을 본다 — 만약 전개가 `require_permission` 안에서만 일어났다면, 묶음만 가진 계정에게
# 「실제로 쓸 수 있는 항목이 사라지는」 조용한 회귀가 났을 것이다.
#
# `web_context` 는 라우터와 달리 `app` 을 끌어오지 않아 이 conftest 에서 import 된다.


def test_legacy_bundle_permission_still_reveals_metadata_jobs():
    wc = _web_context()
    eff = wc._apply_permission_overrides(
        {"kb.ingest.manual"}, {}, catalog_codes=wc.PERMISSION_CODES)
    assert eff.get("metadata.table.update") is True, (
        "묶음 함의가 effective map 밖에서 일어난다 — 필터가 그 사실을 볼 수 없다")
    kinds = bt.visible_console_job_kinds(lambda c: bool(eff.get(c)))
    assert "metadata_suggest" in kinds and "metadata_bulk" in kinds, (
        "레거시 묶음만 보유한 계정에서 메타데이터 항목이 사라졌다 (fail-closed 회귀)")
    # 그래프 분석은 묶음 함의 대상이 아니다(graph-perm-split 2026-07-13) — 함께 새면 안 된다.
    assert "node_analysis" not in kinds, "묶음이 그래프 분석까지 함의한다 — 분리가 무너졌다"


def test_declared_perms_are_not_legacy_bundles():
    """선언은 **원자 단위**로 한다 — 묶음을 적으면 원자 단위만 받은 계정이 항목을 잃는다."""
    wc = _web_context()
    legacy = set(getattr(wc, "LEGACY_BUNDLE_PERMISSIONS", ()))
    for kind, spec in bt.JOB_SPECS.items():
        bad = [c for c in spec["perms"] if c in legacy]
        assert not bad, f"{kind}.perms 에 레거시 묶음 {bad} — 원자 단위 코드로 선언할 것"


# ── 3. 배선 (소스 층 — 웹 라우터는 이 conftest 에서 import 불가) ───────────────

def test_get_endpoint_iterates_visible_kinds_only():
    """GET 이 `JOB_SPECS` 전량이 아니라 추린 목록을 돈다."""
    src = _func_src(PROFILE_PY, "get_profile_console_jobs")
    assert "_visible_console_job_kinds(account)" in src, "GET 이 권한 필터를 부르지 않는다"
    assert "for kind, spec in _bt.JOB_SPECS.items()" not in src, (
        "GET 이 여전히 JOB_SPECS 전량을 순회한다 — 필터가 우회됐다")


def test_put_endpoint_delegates_merge_to_the_registry():
    """PUT 이 가시성 필터 + 정본 병합 함수를 통과한다.

    병합의 **행위**는 위 §2-b 가 실 dict 로 검사한다. 여기서 잠그는 것은 라우터가 그 규칙을
    실제로 통과하는가(=배선)다 — 두 검사가 함께여야 「함수는 맞는데 그 자리에 없다」를 막는다.
    """
    src = _func_src(PROFILE_PY, "put_profile_console_jobs")
    assert "_visible_console_job_kinds(account)" in src, "PUT 이 권한 필터를 부르지 않는다"
    assert "merge_visible_console_job_prefs" in src, "PUT 이 정본 병합을 우회한다"
    assert "account_console_job_prefs" in src, "보존하려면 기존 값을 먼저 읽어야 한다"
    # 라우터가 자기 병합을 다시 쓰지 않는가 — 두 벌이 되면 한쪽이 낡는다.
    assert "if k not in visible" not in src, "라우터가 병합 규칙을 중복 구현한다"


def test_put_rejects_malformed_body_instead_of_wiping():
    """깨진 본문을 「전부 비웠다」로 읽지 않는다 (codex 2R P2).

    빈 `jobs` 는 정당한 입력([모두 기본값] 후 저장)이라 서버가 그것과 사고를 구분해야 한다.
    """
    src = _func_src(PROFILE_PY, "put_profile_console_jobs")
    assert 'isinstance(body.get("jobs"), dict)' in src, "jobs 가 dict 인지 확인하지 않는다"
    assert "400" in src, "깨진 본문을 4xx 로 거절하지 않는다"
    # 파싱 실패를 `{}` 로 흘리면 위 검사가 무의미해진다.
    assert "body = {}" not in src, "파싱 실패가 빈 dict 로 흘러 거절 분기를 통과한다"


def test_both_endpoints_share_one_filter():
    """필터 정의는 한 곳 — 두 벌이 되면 GET 과 PUT 의 목록이 갈린다."""
    text = _src(PROFILE_PY)
    assert text.count("def _visible_console_job_kinds") == 1
    helper = _func_src(PROFILE_PY, "_visible_console_job_kinds")
    assert "bridge_tasks" in helper and "visible_console_job_kinds" in helper, (
        "판정 정본은 shared.bridge_tasks 다 — 라우터가 자기 규칙을 다시 쓰면 워커와 갈린다")
    assert "_account_has_permission" in helper, "실제 RBAC 헬퍼로 판정해야 한다"


def test_put_response_does_not_leak_hidden_kinds():
    src = _func_src(PROFILE_PY, "put_profile_console_jobs")
    tail = src[src.rindex("return JSONResponse"):]
    assert "if k in visible" in tail, "PUT 응답이 숨긴 종류의 이름·값을 되돌려준다"


# ── 4. 프런트 — 서버 판정을 그대로 그린다 ────────────────────────────────────

def _strip_js_comments(text: str) -> str:
    """주석 제거 — 구조 단언은 **코드**만 봐야 한다(주석에 쓴 반례가 위반으로 잡힌다)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def test_frontend_does_not_gate_ai_jobs_with_can():
    """`can()` 은 인자를 무시하는 display-permissive 헬퍼 — 분기 판정에 쓰면 갈래가 죽는다.

    권한 축은 서버가 판정하고 프런트는 목록을 그대로 그린다.
    """
    js = _strip_js_comments(_src(PROFILE_JS))
    body = js[js.index("function renderAiJobs"):js.index("async function loadAiJobs")]
    assert "can(" not in body, "AI 작업 목록 렌더가 can() 으로 항목을 거른다"


def test_frontend_handles_empty_job_list():
    """0 항목이 «오류» 로 보이지 않게 한다 — 빈 상자와 로드 실패는 다른 상태다."""
    js = _strip_js_comments(_src(PROFILE_JS))
    assert "_aiJobsSetEmpty" in js, "빈 목록 처리 경로가 없다"
    body = js[js.index("function renderAiJobs"):js.index("async function loadAiJobs")]
    assert "st.jobs.length" in body, "renderAiJobs 가 빈 목록을 분기하지 않는다"


@pytest.mark.parametrize("btn", ["saveAiJobsBtn", "resetAiJobsBtn"])
def test_frontend_disables_actions_when_empty(btn):
    js = _strip_js_comments(_src(PROFILE_JS))
    setter = js[js.index("function _aiJobsSetEmpty"):js.index("function _aiJobsModelOptions")]
    assert btn in setter and "disabled" in setter, f"{btn} 이 빈 목록에서 비활성화되지 않는다"


def test_frontend_blocks_save_before_first_successful_load():
    """첫 로딩 **중**에도 [저장] 은 «전부 지우기» 다 (codex 2R).

    행이 그려지기 전에는 `_collectAiJobs` 가 `{}` 를 만들고, 서버는 그것을 정당한 「비우기」로
    처리한다(그 의미는 [모두 기본값] 에 필요하다). 그래서 «비우려는 것» 과 «아직 못 받은 것» 을
    프런트가 갈라야 한다.
    """
    js = _strip_js_comments(_src(PROFILE_JS))
    loader = js[js.index("async function loadAiJobs"):js.index("function _collectAiJobs")]
    assert "_aiJobsState.loaded" in loader and "_aiJobsSetEmpty(true)" in loader, (
        "첫 로딩 중 저장 버튼이 열려 있다")
    setup = js[js.index("function setupAiJobsTab"):]
    assert "_aiJobsSetEmpty(true)" in setup, "배선 시점 초기 비활성이 없다"


def test_frontend_ignores_stale_load_responses():
    """겹친 요청의 **오래된 응답**이 최신 상태를 덮지 않는다 (codex 2R 미확정분, 자체 확정).

    `switchProfileTab` 이 탭 진입마다 · `saveAiJobs` 가 저장 뒤 다시 `loadAiJobs` 를 부르므로
    요청은 겹칠 수 있고 응답 순서는 보장되지 않는다. 늦게 온 옛 응답이 상태를 덮으면 화면이
    방금 저장한 값을 잃은 것처럼 되돌아가고, 그 상태에서 다시 저장하면 stale 값이 굳는다.
    """
    js = _strip_js_comments(_src(PROFILE_JS))
    loader = js[js.index("async function loadAiJobs"):js.index("function _collectAiJobs")]
    assert "_aiJobsReqSeq" in loader, "요청 세대 토큰이 없다 — 겹친 응답을 가릴 수 없다"
    assert "++_aiJobsReqSeq" in loader, "요청 시작 시 세대를 올리지 않는다"
    # 성공·실패 **양쪽** 이 가려져야 한다 — 한쪽만이면 다른 쪽으로 stale 이 새어든다.
    assert loader.count("seq !== _aiJobsReqSeq") >= 2, (
        "성공/실패 경로 중 한쪽만 stale 을 가린다")


def test_frontend_blocks_save_when_load_failed():
    """목록을 못 받았는데 [저장] 을 누르면 **빈 본문**이 나가 선택이 지워진다.

    「보이는 항목 통째 교체」와 「아무것도 못 봤다」가 서버에서 같은 모양이기 때문에, 막는
    지점은 프런트다.
    """
    js = _strip_js_comments(_src(PROFILE_JS))
    loader = js[js.index("async function loadAiJobs"):js.index("function _collectAiJobs")]
    catch_tail = loader[loader.index("catch"):]
    assert "_aiJobsSetEmpty(true)" in catch_tail, "로드 실패 경로가 저장을 막지 않는다"

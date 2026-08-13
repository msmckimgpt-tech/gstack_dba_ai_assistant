"""TASK-AIOPS — AI 운영 관제 패널 (관리 콘솔 > 감사 > AI 운영 현황) 회귀/보안 테스트.

검증 대상(`make test` agent 이미지, DB 없이 monkeypatch/fake 로 실행):
  T1  taxonomy self-surface — 등록 task 는 카테고리 매핑, 미등록/오타/None 은 ai.other.unmapped.
  T2  상태 축 임계 — ask-worker age 밴드(정상/저하/중단) + inprocess N/A(롤업 제외).
  T3  datasource 축 매핑 — ok/unstable/circuit_open → 정상/저하/중단 worst-of.
  T4  worst-of 배너 + PG 미가용 부분 degrade(200 유지, pg_available=False, banner=축 기반).
  T5  PG 가용(빈 결과) — 배너 정상, categories 빈, ask-worker na 롤업 제외.
  A1  권한 — console.aiops.read 없으면 403(TestClient require_permission).
  R1  _record_llm_usage latency_ms — 미전달=NULL(agent-core 11경로 byte-동치), 명시값 전달.
  R2  usage 없음(스트리밍 include_usage 미지원 등) → INSERT 미실행(정직 스킵).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import app
from routers import ai_ops
from shared.model_catalog import taxonomy_for, ai_categories, TASK_TAXONOMY


class _FakeRequest:
    def __init__(self, days=None):
        self.query_params = {} if days is None else {"days": str(days)}


def _body(resp):
    return json.loads(resp.body)


# ── T1: taxonomy self-surface ────────────────────────────────────────────────
def test_taxonomy_known_tasks_map_to_categories():
    assert taxonomy_for("agent")["category"] == "ai.reasoning.agent"
    assert taxonomy_for("prompt_gen")["category"] == "ai.prompt.autogen"
    assert taxonomy_for("metadata_summary")["category"] == "ai.metadata.autocomplete"
    # 라벨 보존
    assert taxonomy_for("node_analysis")["label"] == "그래프 노드 분석"
    # 등록된 모든 task 의 category 는 ai_categories() 라벨맵에 존재(고아 카테고리 없음)
    labels = ai_categories()
    for t, meta in TASK_TAXONOMY.items():
        assert meta["category"] in labels, f"{t} 의 category 가 라벨맵에 없음"


def test_taxonomy_unmapped_self_surface():
    # 미등록/오타/None/공백 → ai.other.unmapped, 원본 task 라벨 보존(운영자 식별용)
    assert taxonomy_for("brand_new_ai_task")["category"] == "ai.other.unmapped"
    assert taxonomy_for("brand_new_ai_task")["label"] == "brand_new_ai_task"
    assert taxonomy_for(None)["category"] == "ai.other.unmapped"
    assert taxonomy_for("")["category"] == "ai.other.unmapped"


def test_taxonomy_insight_pipeline_tasks_mapped():
    """aiops-taxonomy-unmapped(2026-08-03): 라이브에서 '미분류 활동' 으로 떨어지던 3 task."""
    for task, label in (("cluster_summary", "콘텐츠 그룹 요약"),
                        ("domain_summary", "도메인 종합 요약"),
                        ("analysis_verify", "분석문 사실성 검증")):
        tx = taxonomy_for(task)
        assert tx["category"] == "ai.insight.analyze", f"{task} 가 인사이트 분석에 편입되지 않음"
        assert tx["label"] == label


#: `_record_llm_usage` 의 task 를 **정적으로 확정할 수 없는** 호출부의 명시 목록. 키는 파일 경로
#: (라인 번호 아님 — 코드 이동에 브리틀), 값은 `{task 표현식(ast.unparse 정규형): 파생 규칙}`.
#: 파생 규칙은 `(producer 함수명, 포맷 템플릿, 산출되는 task 튜플)` 이며 테스트가
#: producer 호출부의 `task=` 리터럴을 수집해 템플릿을 적용한 뒤 **선언 튜플과 집합 동치**를
#: 요구한다 — 새 진입점(`_metadata_llm_complete(task="foo")`)이 추가되면 표현식은 그대로여도
#: 산출 집합이 달라져 red 가 된다. "정적으로 못 잡는 경로"를 조용한 사각이 아니라 검증된
#: 선언으로 만든다.
_DYNAMIC_TASK_CALLSITES: dict[str, dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py": {
        # `_metadata_llm_complete(..., task="summary"|"prompt_gen")` 두 진입점의 파생값.
        "f'metadata_{task}'": (
            "_metadata_llm_complete", "metadata_{}", ("metadata_summary", "metadata_prompt_gen"),
        ),
    },
}


def test_every_recorded_task_literal_is_registered():
    """소스에서 `_record_llm_usage` 로 기록하는 task 전수가 TASK_TAXONOMY 에 등록돼 있어야 한다.

    미분류 재발 방지 — 신규 계측이 taxonomy 등록 없이 들어오면 '운영 현황' 카테고리 드릴다운에서
    '미분류 활동' 으로 떨어지고, 그 사실은 라이브 데이터가 쌓인 뒤에야 드러난다(2026-07-28 에도
    같은 사유로 4종을 뒤늦게 편입한 전례).

    dict 대조가 아니라 **호출부 AST 전수 수집**이라 신규 task 가 자동으로 대상이 된다:
      · 직접 호출 리터럴 — `_record_llm_usage(m, "topic", resp)`
      · 래퍼 경유 리터럴 — task 를 그대로 흘리는 함수를 고정점으로 찾아(`_openai_chat_completion_
        with_deadline` 등) 그 호출부의 `task="agent"` 도 수집. keyword·positional 양쪽 바인딩.
      · f-string 등 동적 표현식 — `_DYNAMIC_TASK_CALLSITES` 의 파생 규칙으로 산출 집합을 계산해
        선언과 집합 동치 + 전량 등록을 단언. 산출을 정하는 producer 호출부의 task 가 리터럴이
        아니면(변수·**kwargs) 조용히 통과시키지 않고 실패시킨다.
    파싱 실패는 삼키지 않는다 — 스캐너가 조용히 눈감으면 게이트가 아니다.

    **한계(명시)**: 완전한 정적 해석기는 아니다. task 가 런타임 값으로만 결정되는 경로
    (`Class.method(instance, …)` 형태의 unbound 호출로 task 위치가 어긋나는 경우 등)는 원리상
    정적 확정이 불가하며, 그런 경로가 생기면 위 동적 목록 대조가 red 를 내어 사람이 판단하도록
    한다 — 게이트의 계약은 "모든 동적 경로를 해석한다"가 아니라 "미확정 경로를 조용히 통과시키지
    않는다"이다.
    """
    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    roots = [p for p in (repo_root / "shared",) if p.is_dir()]
    roots += [d for d in sorted(repo_root.glob("unit/*/src")) if d.is_dir()]
    assert roots, f"소스 트리를 찾지 못함(repo_root={repo_root}) — 스캐너가 무력화됨"

    # 파싱 실패는 즉시 실패 — `continue` 로 숨기면 문법 오류 파일의 신규 task 를 놓친다.
    trees: dict[str, ast.AST] = {}
    for root in roots:
        for py in root.rglob("*.py"):
            rel = str(py.relative_to(repo_root))
            trees[rel] = ast.parse(py.read_text(encoding="utf-8"), filename=rel)
    scanned_files = len(trees)

    def _literal(node) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
            return node.value
        return None

    def _callee(node) -> str | None:
        fn = node.func
        return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)

    def _starred_before(args, pos: int) -> bool:
        """`f(*prefix, "x")` 처럼 앞에 unpacking 이 있으면 positional 인덱스가 확정되지 않는다."""
        return any(isinstance(a, ast.Starred) for a in args[:pos + 1])

    # 함수 정의에서 `task` 파라미터의 positional 인덱스를 읽는다 — 호출부가 keyword 로 주든
    # positional 로 주든 같은 인자를 가리키게 하기 위함(keyword 만 보면 positional 호출을 놓친다).
    # 메서드의 self/cls 는 `obj.m(...)` 의 `node.args` 에 없으므로 인덱스에서 제외한다.
    #   메서드(첫 파라미터 self/cls)는 bound(`obj.m(...)`)/unbound(`C.m(obj, ...)`) 호출에서
    #   positional 인덱스가 한 칸 어긋나며 호출부만 보고는 구분할 수 없다 — 잘못 읽느니
    #   **미확정으로 취급해 실패**시킨다(fail-closed). 현 코드베이스의 sink 는 전부 모듈 함수다.
    def _task_pos(fdef) -> int | None:
        names = [a.arg for a in (list(getattr(fdef.args, "posonlyargs", [])) + list(fdef.args.args))]
        if names and names[0] in ("self", "cls"):
            return None
        return names.index("task") if "task" in names else None

    task_pos: dict[str, set[int | None]] = {}
    for tree in trees.values():
        for fdef in ast.walk(tree):
            if isinstance(fdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
                task_pos.setdefault(fdef.name, set()).add(_task_pos(fdef))

    # 각 Call 을 감싸는 함수 정의 — `task` 라는 **이름**이 그 함수의 파라미터인지 확인해야
    # "래퍼가 자기 파라미터를 흘리는 것"과 "런타임 지역변수"를 구분할 수 있다(후자는 미확정).
    enclosing: dict[int, object] = {}

    class _FnScope(ast.NodeVisitor):
        def __init__(self):
            self.stack: list = []

        def visit_FunctionDef(self, node):
            # 데코레이터·기본값·어노테이션은 **바깥 스코프**에서 평가된다 — 그 안의 호출을
            # 이 함수 내부로 기록하면 `task` 이름이 파라미터로 오인된다(fail-open 경로).
            for dec in node.decorator_list:
                self.visit(dec)
            self.visit(node.args)
            if node.returns is not None:
                self.visit(node.returns)
            self.stack.append(node)
            for stmt in node.body:
                self.visit(stmt)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            enclosing[id(node)] = list(self.stack)   # 중첩 클로저까지 포함한 스택 스냅샷
            self.generic_visit(node)

    for tree in trees.values():
        _FnScope().visit(tree)

    def _binds_task(n) -> bool:
        """이 AST 노드가 `task` 라는 이름을 (재)바인딩하는가."""
        if isinstance(n, ast.Name):
            return n.id == "task" and isinstance(n.ctx, ast.Store)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return n.name == "task"
        if isinstance(n, ast.alias):                       # import x as task
            return (n.asname or n.name.split(".")[0]) == "task"
        if isinstance(n, ast.ExceptHandler):               # except E as task
            return n.name == "task"
        if isinstance(n, ast.arg):                         # 중첩 함수/lambda 파라미터
            return n.arg == "task"
        if isinstance(n, getattr(ast, "MatchAs", ())) or isinstance(n, getattr(ast, "MatchStar", ())):
            return getattr(n, "name", None) == "task"      # case … as task
        if isinstance(n, getattr(ast, "MatchMapping", ())):
            return getattr(n, "rest", None) == "task"
        return False

    def _is_param_passthrough(node, arg) -> bool:
        """`arg` 가 이 호출을 감싼 함수의 `task` 파라미터를 그대로 넘기는 것인가."""
        if not (isinstance(arg, ast.Name) and arg.id == "task"):
            return False
        stack = enclosing.get(id(node)) or []
        fdef = stack[-1] if stack else None
        if fdef is None:
            return False
        names = {a.arg for a in (list(getattr(fdef.args, "posonlyargs", []))
                                 + list(fdef.args.args) + list(fdef.args.kwonlyargs))}
        if "task" not in names:
            return False
        # 파라미터라도 함수 안에서 **재바인딩**되면 넘어가는 값이 더 이상 호출부의 리터럴이
        # 아니다 — passthrough 로 보지 않고 미확정으로 떨군다. 대입/for/with-as/comprehension
        # (Name-Store) 뿐 아니라 def·class·import-as·except-as·match-as·중첩 파라미터까지
        # 이름을 가리는 모든 형태를 본다(fail-closed).
        own_args = {id(a) for a in ast.walk(fdef.args) if isinstance(a, ast.arg)}
        return not any(_binds_task(n) for n in ast.walk(fdef)
                       if n is not fdef and id(n) not in own_args)

    def _task_arg(node, callee: str, sinks: set[str]):
        """이 호출이 llm_usage 의 task 를 결정하는가 → 그 인자 노드(아니면 None)."""
        if callee not in sinks:
            return None
        for k in node.keywords:
            if k.arg == "task":
                return k.value
        positions = task_pos.get(callee) or {1 if callee == "_record_llm_usage" else None}
        # 동명 정의가 서로 다른 위치에 task 를 두면 어느 시그니처인지 확정할 수 없다 — 조용히
        # 잘못 읽느니 실패시킨다.
        assert len(positions) == 1, f"동명 함수 {callee} 의 task 파라미터 위치가 모호함: {positions}"
        pos = next(iter(positions))
        if pos is not None and len(node.args) > pos and not _starred_before(node.args, pos):
            return node.args[pos]
        return None

    def _is_sink_call(node, callee: str, sinks: set[str]) -> bool:
        return callee in sinks

    # sink 집합 고정점 — `_record_llm_usage` 로 자기 `task` 파라미터를 그대로 넘기는 함수(래퍼)를
    # 모은다. 래퍼의 래퍼도 수렴할 때까지 반복(무관한 `task=` 인자 오탐 없이 래퍼 경유를 흡수).
    sinks: set[str] = {"_record_llm_usage"}
    converged = False
    for _ in range(len(task_pos) + 1):
        grown = False
        for tree in trees.values():
            for fdef in ast.walk(tree):
                if not isinstance(fdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if fdef.name in sinks:
                    continue
                for node in ast.walk(fdef):
                    if not isinstance(node, ast.Call):
                        continue
                    arg = _task_arg(node, _callee(node) or "", sinks)
                    if arg is not None and _is_param_passthrough(node, arg):
                        sinks.add(fdef.name)
                        grown = True
                        break
        if not grown:
            converged = True
            break
    assert converged, "래퍼 체인이 수렴하지 않음 — 바깥 호출부를 놓칠 수 있다"

    producers = {rule[0] for exprs in _DYNAMIC_TASK_CALLSITES.values() for rule in exprs.values()}

    # sink 를 호출이 아닌 형태로 **참조**하면(별칭 할당·인자 전달) 그 별칭 호출은 이름으로
    # 추적되지 않는다 — 정적으로 못 따라가므로 조용히 통과시키지 않고 실패시킨다.
    alias_refs: list[str] = []
    for rel, tree in trees.items():
        call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for n in ast.walk(tree):
            if (isinstance(n, ast.Name) and n.id in (sinks | producers)
                    and isinstance(n.ctx, ast.Load) and id(n) not in call_funcs):
                alias_refs.append(f"{rel}:{n.lineno} {n.id}")

    found: dict[str, str] = {}                # task -> 최초 발견 위치
    dynamic: dict[str, dict[str, list[str]]] = {}   # 파일 -> {표현식: [위치…]}
    producer_args: dict[str, set[str]] = {}   # 동적 파생 producer -> 호출부 task 리터럴 집합
    unresolved_producer: list[str] = []       # task 를 리터럴로 확정 못한 producer 호출부
    unresolved_sink: list[str] = []           # task 인자를 특정 못한 sink 호출부(fail-closed)
    dynamic_encl: dict[tuple, set] = {}       # (파일, 표현식) -> 그 호출을 감싼 함수 이름 집합
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _callee(node) or ""
            if callee in producers:
                # producer 의 task 인자는 keyword/positional 양쪽에서 읽고, 문자열 리터럴이
                # 아니면(변수·**kwargs·미전달) 조용히 넘기지 않고 아래에서 실패시킨다 —
                # 누락은 산출 집합을 축소해 게이트를 무력화한다.
                p_arg = None
                for k in node.keywords:
                    if k.arg == "task":
                        p_arg = k.value
                if p_arg is None:
                    p_positions = task_pos.get(callee) or {None}
                    p_pos = next(iter(p_positions)) if len(p_positions) == 1 else None
                    if (p_pos is not None and len(node.args) > p_pos
                            and not _starred_before(node.args, p_pos)):
                        p_arg = node.args[p_pos]
                p_lit = _literal(p_arg) if p_arg is not None else None
                if p_lit is not None:
                    producer_args.setdefault(callee, set()).add(p_lit)
                elif not any(isinstance(k, ast.keyword) and k.arg is None for k in node.keywords):
                    unresolved_producer.append(
                        f"{rel}:{node.lineno} {callee}(task={ast.unparse(p_arg) if p_arg is not None else '<미전달>'})")
                else:
                    unresolved_producer.append(f"{rel}:{node.lineno} {callee}(**kwargs)")
            arg = _task_arg(node, callee, sinks)
            if arg is None:
                if _is_sink_call(node, callee, sinks):
                    # sink 호출인데 task 를 찾지 못했다(**kwargs·*args·메서드 sink·미전달) —
                    # 조용히 넘기면 그 경로의 신규 task 가 영영 게이트 밖이다. fail-closed.
                    unresolved_sink.append(f"{rel}:{node.lineno} {callee}(…)")
                continue
            lit = _literal(arg)
            if lit is not None:
                found.setdefault(lit, f"{rel}:{node.lineno}")
            elif not _is_param_passthrough(node, arg):
                # 래퍼가 자기 파라미터를 그대로 넘기는 것(위 고정점이 이미 흡수)은 제외하고,
                # f-string 등 **정적 확정이 불가능한** 표현식만 명시 목록 대조 대상으로 남긴다.
                expr_key = ast.unparse(arg)
                dynamic.setdefault(rel, {}).setdefault(expr_key, []).append(f"{rel}:{node.lineno}")
                _stack = enclosing.get(id(node)) or []
                dynamic_encl.setdefault((rel, expr_key), set()).update(
                    [f.name for f in _stack] or ["<module>"])

    # 스캐너가 아무것도 못 찾으면 vacuous pass 다 — 경로 변경/이동 시 조용히 무력화되지 않게 한다.
    assert scanned_files >= 50, f"스캔된 소스 파일이 비정상적으로 적음({scanned_files})"
    assert len(found) >= 10, f"수집된 task 리터럴이 비정상적으로 적음({sorted(found)})"

    missing = {t: where for t, where in found.items() if t not in TASK_TAXONOMY}
    assert not missing, (
        "llm_usage 에 기록되지만 TASK_TAXONOMY 미등록 → '미분류 활동' 으로 노출됨: " + str(missing))

    # 동적 task 호출부는 목록으로 고정한다 — 신규 항목이 생기면 여기서 red.
    unknown = {f: exprs for f, exprs in dynamic.items()
               if set(exprs) - set(_DYNAMIC_TASK_CALLSITES.get(f, {}))}
    assert not unknown, (
        "task 를 정적으로 확정할 수 없는 신규 _record_llm_usage 호출부: " + str(unknown) +
        " — 산출되는 task 를 TASK_TAXONOMY 에 등록하고 _DYNAMIC_TASK_CALLSITES 에 파생 규칙을 등재하라")

    assert not alias_refs, (
        "sink 함수를 호출이 아닌 형태로 참조(별칭·인자 전달) — 별칭 경유 호출은 정적으로 추적할 수 "
        "없다: " + str(alias_refs))

    assert not unresolved_sink, (
        "task 인자를 정적으로 특정할 수 없는 _record_llm_usage/래퍼 호출부: " + str(unresolved_sink) +
        " — task 를 명시 인자(리터럴 권장)로 전달하라. 미확정 경로는 통과시키지 않는다")

    assert not unresolved_producer, (
        "동적 파생 producer 의 task 를 리터럴로 확정할 수 없는 호출부: " + str(unresolved_producer) +
        " — task 는 문자열 리터럴로 전달하거나(권장), 새 파생 규칙을 _DYNAMIC_TASK_CALLSITES 에 등재하라")

    for f, exprs in _DYNAMIC_TASK_CALLSITES.items():
        for expr, (producer, template, declared) in exprs.items():
            # 선언된 동적 호출부가 소스에서 사라졌으면 목록이 stale — 정리하도록 실패시킨다.
            assert expr in dynamic.get(f, {}), \
                f"_DYNAMIC_TASK_CALLSITES 가 stale (소스에 없는 호출부): {f} :: {expr}"
            # 같은 파일·같은 표현식이라도 **다른 함수**에서 호출되면 파생 규칙이 다를 수 있다 —
            # 선언된 producer 함수(중첩 클로저 포함) 안의 호출만 이 규칙으로 승인한다.
            encl = dynamic_encl.get((f, expr), set())
            assert producer in encl, (
                f"{f} :: {expr} 를 감싼 함수 스택에 선언된 producer 가 없다 — 실제 {sorted(encl)} / "
                f"선언 {producer}")
            # producer 호출부의 실제 리터럴로 산출 집합을 재계산해 선언과 **집합 동치**를 요구한다
            # — 새 진입점(`task=\"foo\"`)이 추가되면 표현식이 같아도 여기서 red 가 된다.
            produced = {template.format(v) for v in producer_args.get(producer, set())}
            assert produced == set(declared), (
                f"{f} :: {expr} 의 산출 task 집합이 선언과 다름 — 실제 {sorted(produced)} / "
                f"선언 {sorted(declared)} (신규 {producer}(task=…) 진입점?)")
            undeclared = [t for t in produced if t not in TASK_TAXONOMY]
            assert not undeclared, (
                f"동적 호출부가 산출하는 task 중 TASK_TAXONOMY 미등록: {undeclared} ({f} :: {expr})")


# ── T2: ask-worker 축 임계 + inprocess N/A ───────────────────────────────────
def test_ask_worker_axis_inprocess_is_na(monkeypatch):
    monkeypatch.setattr(app, "_is_worker_mode", lambda: False)
    ax = ai_ops._ask_worker_axis(conn=None)
    assert ax["state"] == "na", "inprocess 모드는 N/A 여야 함(롤업 제외)"


def test_ask_worker_axis_age_bands(monkeypatch):
    monkeypatch.setattr(app, "_is_worker_mode", lambda: True)
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 10)
    assert ai_ops._ask_worker_axis(None)["state"] == "ok"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 90)
    assert ai_ops._ask_worker_axis(None)["state"] == "degraded"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 300)
    assert ai_ops._ask_worker_axis(None)["state"] == "down"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: None)
    assert ai_ops._ask_worker_axis(None)["state"] == "down", "heartbeat 부재 → 중단"


# ── T3: datasource 축 매핑 ───────────────────────────────────────────────────
def test_datasource_axis_worst_of(monkeypatch):
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {
        "ds_ok": {"status": "ok", "scan_outcome": "ok"},
        "ds_bad": {"status": "unstable", "scan_outcome": "error"},
    })
    assert ai_ops._datasource_axis()["state"] == "degraded"
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {
        "ds_ok": {"status": "ok", "scan_outcome": "ok"},
        "ds_dead": {"status": "ok", "scan_outcome": "circuit_open"},
    })
    assert ai_ops._datasource_axis()["state"] == "down"
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {})
    assert ai_ops._datasource_axis()["state"] == "unknown", "스캔 이력 없음/PG 미가용 → unknown"


# ── 공용: 축 소스 monkeypatch (건강한 기본값) ────────────────────────────────
def _patch_axes_healthy(monkeypatch, *, worker_mode=False):
    monkeypatch.setattr(app, "_read_llm_provider_status", lambda: {"state": "ok"})
    monkeypatch.setattr(app, "_is_worker_mode", lambda: worker_mode)
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 5)
    monkeypatch.setattr(app, "_insight_worker_liveness", lambda conn: {"alive": True, "age_sec": 5, "status": "ok"})
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {"ds": {"status": "ok", "scan_outcome": "ok"}})


# ── T4: PG 미가용 → 부분 degrade(200) ────────────────────────────────────────
def test_handler_pg_unavailable_partial_degrade(monkeypatch):
    _patch_axes_healthy(monkeypatch, worker_mode=False)  # inprocess → ask-worker na

    def _boom(*a, **k):
        raise RuntimeError("pg down")

    monkeypatch.setattr("shared.db._pg_connect_ro", _boom, raising=False)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(7), account={"id": 1}, conn=None))

    assert body["pg_available"] is False
    assert body["categories"] == []
    # provider ok + insight ok + datasource ok, ask-worker na 제외 → 배너 정상
    assert body["banner"]["state"] == "ok"
    ask = next(a for a in body["axes"] if a["key"] == "ask_worker")
    assert ask["state"] == "na"
    # PG 미가용은 Attention 에 표면화(은폐 금지)
    assert any("PG" in x["label"] or "미가용" in x["label"] for x in body["attention"])


# ── T5: PG 가용(빈 결과) → 배너 정상, categories 빈 ──────────────────────────
class _EmptyCur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): return None
    def fetchall(self): return []
    def fetchone(self): return None
    def close(self): return None


class _EmptyConn:
    def cursor(self, *a, **k): return _EmptyCur()
    def close(self): return None


def test_handler_pg_available_empty(monkeypatch):
    _patch_axes_healthy(monkeypatch, worker_mode=True)  # worker mode + age 5 → ask ok
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: _EmptyConn(), raising=False)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(7), account={"id": 1}, conn=None))

    assert body["pg_available"] is True
    assert body["categories"] == []
    assert body["banner"]["state"] == "ok"
    # worker mode + 정상 age → ask-worker ok(롤업 포함)
    ask = next(a for a in body["axes"] if a["key"] == "ask_worker")
    assert ask["state"] == "ok"
    assert body["kpis"]["workers_total"] == 2  # ask + insight 둘 다 롤업 대상


# ── A1: 권한 403 (TestClient require_permission) ─────────────────────────────
def test_ai_ops_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.aiops.read 없음
    resp = client.get("/api/admin/ai-ops")
    assert resp.status_code == 403


# ── R1/R2: _record_llm_usage latency_ms (byte-동치 NULL + 명시값 + usage 스킵) ─
class _CaptureCur:
    def __init__(self, sink): self.sink = sink
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.sink.append((sql, params))


class _CaptureConn:
    def __init__(self, sink): self.sink = sink
    def cursor(self, *a, **k): return _CaptureCur(self.sink)
    def commit(self): return None
    def close(self): return None


def _resp(pt=10, ct=5, tt=15, model="claude-haiku-4"):
    return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt), model=model)


def test_record_llm_usage_latency_column(monkeypatch):
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _CaptureConn(sink))

    # 미전달 → latency_ms=NULL 및 step_gap_ms=NULL (미측정=NULL). 컬럼 순서 (…, target, latency_ms,
    #   step_gap_ms, target_scope, cache_read_tokens, cache_write_tokens) — 0056(캐시 계측)이 맨 뒤에
    #   두 컬럼을 더하며 latency=params[-5], step_gap=params[-4], target_scope=params[-3] 로 두 칸씩
    #   밀렸다(의도된 계약 변경). 캐시는 usage 미제공 시 0(미측정 NULL 아님 — 0 이 사실이다).
    llm._record_llm_usage("claude-haiku-4", "agent", _resp())
    assert len(sink) == 1
    sql, params = sink[0]
    assert "latency_ms" in sql and "step_gap_ms" in sql
    assert "cache_read_tokens" in sql and "cache_write_tokens" in sql
    assert params[-5] is None, "latency 미전달 시 NULL"
    assert params[-4] is None, "step_gap 미전달 시 NULL"
    assert params[-3] is None, "target_scope 미전달·ContextVar 미설정 시 NULL"
    assert params[-2] == 0 and params[-1] == 0, "캐시 미제공 응답은 0"

    # 명시값 → 그대로 전달 (latency=params[-5], step_gap=params[-4])
    sink.clear()
    llm._record_llm_usage("claude-haiku-4", "agent", _resp(), latency_ms=123, step_gap_ms=1300)
    assert sink[0][1][-5] == 123    # latency_ms(전체 왕복)
    assert sink[0][1][-4] == 1300   # step_gap_ms(단계 간 간격)


def test_record_llm_usage_skips_without_usage(monkeypatch):
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _CaptureConn(sink))
    # usage 없음(스트리밍 include_usage 미지원 등) → INSERT 미실행(정직 스킵)
    llm._record_llm_usage("m", "prompt_gen", SimpleNamespace(usage=None, model="m"), latency_ms=50)
    assert sink == []


class _ColAbsentCur:
    """지정 컬럼이 스키마에 없다고 시뮬레이션 — 그 컬럼명을 포함한 INSERT 는 매번 예외(0033 3단 cascade 검증)."""
    def __init__(self, sink, absent_col): self.sink = sink; self.absent = absent_col
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None):
        if self.absent in sql:
            raise RuntimeError(f'column "{self.absent}" does not exist')
        self.sink.append((sql, params))


class _ColAbsentConn:
    def __init__(self, sink, absent_col):
        self.sink = sink; self.rolled_back = 0; self._cur = _ColAbsentCur(sink, absent_col)
    def cursor(self, *a, **k): return self._cur
    def commit(self): return None
    def rollback(self): self.rolled_back += 1
    def close(self): return None


def test_record_llm_usage_step_gap_column_absent_fallback(monkeypatch):
    # 0033: step_gap_ms 컬럼 부재(0033 미적용, 0032 target 은 적용 — agent image stale 등) →
    # step_gap 포함 INSERT 실패 → rollback → (target, latency_ms) 로 폴백해 usage 행 보존.
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    conn = _ColAbsentConn(sink, "step_gap_ms")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: conn)
    llm._record_llm_usage("claude-haiku-4", "agent", _resp(),
                          target="public.users", latency_ms=42, step_gap_ms=1300)
    # 0056 으로 사다리가 5단(…,cache / …,target_scope / …,step_gap / …,latency / latency)이 되어,
    #   step_gap_ms 를 포함하는 앞 3단이 실패한다(0047 시점 2단 → 0056 에서 3단).
    assert conn.rolled_back == 3              # step_gap 포함 INSERT 3회 실패 → rollback
    assert len(sink) == 1
    sql, params = sink[0]
    assert "step_gap_ms" not in sql and "target" in sql   # 폴백 = (…, target, latency_ms)
    assert params[-1] == 42                    # latency 마지막(step_gap 없는 폴백)


def test_record_llm_usage_target_column_absent_fallback(monkeypatch):
    # 0032: target 컬럼 부재(마이그 미적용) → target 포함 INSERT 전부(step_gap·target 2단) 실패 →
    # 최소 base(latency) 로 폴백해 usage 행 보존(계측 무중단).
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    conn = _ColAbsentConn(sink, "target")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: conn)
    llm._record_llm_usage("claude-haiku-4", "table_insight", _resp(),
                          target="public.users", latency_ms=42, step_gap_ms=1300)
    # "target" 부분문자열은 target_scope 단계도 매칭 → 앞 4단(0056 캐시단 포함) 실패 후 최소 base 성공.
    assert conn.rolled_back == 4              # target 포함 INSERT 4회 실패
    assert len(sink) == 1
    sql, params = sink[0]
    assert "target" not in sql and "step_gap_ms" not in sql   # 폴백 = base 컬럼
    assert params[4] == "table_insight"       # task 보존
    assert params[-1] == 42                    # latency 마지막 위치 보존


# ── 활동 feed 페이징(TASK-AIOPS-paging): cursor keyset + next_cursor + 엔드포인트 degrade/권한 ─
import datetime as _dt


def _act_rows(n, start_id):
    # TASK-20260702-audit-nav-ux: SELECT 컬럼 확장 반영 —
    # (id, task, model, resolved_model, total, prompt, completion, latency, created_at, run_id, conversation_id)
    # conversation_id 는 짝수 index 만 부여(연결 대화 있음/없음 두 경로 모두 커버).
    # 0032(TASK-20260703-aiops-target): 12번째 컬럼 target 추가 — 짝수 index 만 대상 부여(대상 있음/없음 두 경로).
    return [(start_id - i, "agent", "claude-haiku-4", "claude-haiku-4-served", 100, 60, 40, 12,
             _dt.datetime(2026, 7, 2, 0, 0, i % 60),
             "run-" + str(start_id - i), ("conv-" + str(start_id - i)) if (i % 2 == 0) else None,
             ("public.tbl_" + str(start_id - i)) if (i % 2 == 0) else None)
            for i in range(n)]


class _PlainCur:
    def __init__(self, rows): self._rows = rows; self.sql = None; self.params = None
    def execute(self, sql, params=None): self.sql = sql; self.params = params
    def fetchall(self): return self._rows


class _CtxCur(_PlainCur):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _RowConn:
    def __init__(self, rows): self._cur = _CtxCur(rows)
    def cursor(self, *a, **k): return self._cur
    def close(self): return None


class _ReqQ:
    def __init__(self, **params): self.query_params = {k: str(v) for k, v in params.items()}


def test_query_activity_no_cursor_has_more():
    from routers.ai_ops import _query_activity
    cur = _PlainCur(_act_rows(4, 100))  # limit=3, 4 rows → has_more
    items, nxt = _query_activity(cur, taxonomy_for, limit=3)
    assert len(items) == 3
    assert nxt == items[-1]["id"]                  # has_more → next_cursor = 마지막 id
    assert {"id", "latency_ms", "cost_usd", "label"} <= set(items[0].keys())
    # TASK-20260702-audit-nav-ux: 상세 확장용 additive 필드 노출 + 서빙/요청 모델 분리.
    assert {"req_model", "resolved_model", "prompt_tokens", "completion_tokens",
            "run_id", "conversation_id"} <= set(items[0].keys())
    # aiops-model-canonical: 주 모델 배지는 canonical family 로 표시(도넛과 정합). 'claude-haiku-4-served'
    #   → 'claude-haiku-4'. req_model/resolved_model 은 raw 보존(상세 '요청→서빙' 라우팅 audit).
    assert items[0]["model"] == "claude-haiku-4"            # 행 배지=canonical family
    assert items[0]["req_model"] == "claude-haiku-4"        # 요청 별칭 raw 보존
    assert items[0]["resolved_model"] == "claude-haiku-4-served"  # 실 서빙 raw 보존(canonical 화 안 함)
    assert items[0]["prompt_tokens"] == 60 and items[0]["completion_tokens"] == 40
    assert items[0]["run_id"] == "run-100" and items[0]["conversation_id"] == "conv-100"
    assert items[1]["conversation_id"] is None              # 홀수 index=대화 미귀속(정직 안내 경로)
    # 0032: 인사이트 분석 대상(target) 컬럼이 SELECT 되고 item 으로 통과 — 짝수=대상 있음, 홀수=None.
    assert ", target" in cur.sql
    assert items[0]["target"] == "public.tbl_100"
    assert items[1]["target"] is None
    assert "WHERE id <" not in cur.sql             # cursor 미지정 → WHERE 없음
    assert "ORDER BY id DESC" in cur.sql


def test_query_activity_with_cursor_no_more():
    from routers.ai_ops import _query_activity
    cur = _PlainCur(_act_rows(3, 50))              # limit=3, 3 rows → no has_more
    items, nxt = _query_activity(cur, taxonomy_for, cursor=97, limit=3)
    assert len(items) == 3 and nxt is None
    assert "WHERE id < %s" in cur.sql
    assert cur.params[0] == 97 and cur.params[1] == 4   # (cursor, limit+1)


class _NoTargetCur(_PlainCur):
    """0032: target 컬럼 부재(마이그 미적용/agent image stale) 시뮬레이션 —
    SELECT 에 ', target' 이 있으면 **매번** UndefinedColumn 흉내로 예외(컬럼이 없는 DB 라면 몇 번을
    시도해도 없다), base 컬럼 재실행만 통과. _query_activity 의 자가치유 폴백을 검증한다.
    (0056 으로 사다리가 3단이 되며, 종전의 '첫 실행만 실패' 플래그는 두 번째 target 시도를 통과시켜
     컬럼 부재 상황을 더는 재현하지 못했다 — 더블을 의도대로 정정.)"""
    def __init__(self, rows):
        super().__init__(rows)
        self.connection = self       # cur.connection.rollback() 대상
    def execute(self, sql, params=None):
        if ", target" in sql:
            raise RuntimeError('column "target" does not exist')
        super().execute(sql, params)
    def rollback(self):
        return None


def test_query_activity_target_column_absent_fallback():
    from routers.ai_ops import _query_activity
    cur = _NoTargetCur(_act_rows(3, 80))           # rows 는 target 포함이나 SELECT 는 폴백돼야 함
    items, nxt = _query_activity(cur, taxonomy_for, limit=3)
    assert len(items) == 3                         # 폴백해도 피드는 살아있음(usage 계측 무중단)
    assert all(it["target"] is None for it in items)   # target 컬럼 부재 → 전부 None(가드)
    assert ", target" not in cur.sql               # 최종 실행 SQL = base 컬럼(폴백 성공)


def test_query_activity_model_canonical_preserves_routing():
    """aiops-model-canonical: gemma 폴백 행 — 주 배지는 canonical('edge'),
    req_model/resolved_model 은 raw 보존(상세 '요청→서빙' 라우팅 audit 손실 없음)."""
    from routers.ai_ops import _query_activity
    # (id, task, model, resolved_model, total, prompt, completion, latency, created_at, run_id, conversation_id, target)
    row = (900, "agent", "claude-haiku-4", "gemma4:e2b", 100, 60, 40, 12,
           _dt.datetime(2026, 7, 2, 0, 0, 0), "run-900", "conv-900", None)
    items, _ = _query_activity(_PlainCur([row]), taxonomy_for, limit=3)
    it = items[0]
    assert it["model"] == "edge"                  # 배지 = canonical(gemma4:e2b) — 도넛과 정합
    assert it["req_model"] == "claude-haiku-4"     # raw 요청 alias 보존
    assert it["resolved_model"] == "gemma4:e2b"    # raw 실 서빙(폴백 audit) 보존


def test_query_activity_null_resolved_badge_canonical_raw_preserved():
    """M1 회귀 가드: resolved_model=NULL + 비-canonical req_model('auto', 보조 task/pre-migration 행).
    배지는 canonical('edge')로 정합화되나 resolved_model 은 None 유지(canonical 화 금지) — 프론트 상세가
    req_model 폴백(admin.js srvM=resolved||req_model)으로 '가짜 라우팅 화살표'(auto→edge)를 날조하지 않게 한다."""
    from routers.ai_ops import _query_activity
    row = (901, "summary", "auto", None, 50, 30, 20, 8,
           _dt.datetime(2026, 7, 2, 0, 0, 1), "run-901", None, None)
    items, _ = _query_activity(_PlainCur([row]), taxonomy_for, limit=3)
    it = items[0]
    assert it["model"] == "edge"                  # 배지 = canonical('auto')
    assert it["req_model"] == "auto"               # raw 요청 alias
    assert it["resolved_model"] is None            # 실 서빙 미기록 → None 유지(raw, canonical 화 안 함)


def test_activity_endpoint_with_data(monkeypatch):
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: _RowConn(_act_rows(4, 200)), raising=False)
    body = _body(ai_ops.admin_ai_ops_activity(_ReqQ(limit=3, cursor=500), account={"id": 1}, conn=None))
    assert body["pg_available"] is True
    assert len(body["items"]) == 3
    assert body["next_cursor"] == body["items"][-1]["id"]


def test_activity_endpoint_pg_degrade(monkeypatch):
    def _boom(*a, **k): raise RuntimeError("pg down")
    monkeypatch.setattr("shared.db._pg_connect_ro", _boom, raising=False)
    body = _body(ai_ops.admin_ai_ops_activity(_ReqQ(), account={"id": 1}, conn=None))
    assert body["pg_available"] is False and body["items"] == [] and body["next_cursor"] is None


def test_activity_endpoint_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.aiops.read 없음
    resp = client.get("/api/admin/ai-ops/activity")
    assert resp.status_code == 403

"""rel-selfheal 회귀 가드: shared.config 이름이 star-import 소비 모듈에서 해석 가능한지 검증.

배경 (2026-07-02): `AGENT_RELATIONSHIP_*` 가 shared/config.py 의 `__all__` 에 누락된 채
`from shared.config import *` 소비자(insight.py)에서 bare 로 참조되어 **NameError** —
per-schema `except Exception: continue` 가 이를 삼켜 insight 스캔의 스키마 처리 전체
(인사이트 갱신 + FK introspect + 암묵 추론 + 프로브)가 06-29 부터 3일간 조용히 정지했다
(table_insight 마지막 갱신 06-29 13:58 실측). `AGENT_SQL_FIX_MODEL`(llm.llm_fix_sql)도 동일.

이 테스트는 그 결함 클래스를 정적으로 봉인한다:
  config 에 정의된 UPPER_CASE 이름이 소스 어딘가에서 bare 로 참조되는 star-import 모듈마다,
  해당 이름이 모듈 네임스페이스에서 실제로 해석되는지(= __all__ 등재) 단언한다.

한계 (적대 패널 B-F10, 우회 실증됨 — "전수 검사" 아님): AST 스캔의 bound 집합이 스코프를
구분하지 않아, 어떤 함수의 **지역** 재바인딩(`X = 5`)이 다른 함수의 bare X 로드를 검사에서
면제시킬 수 있다(위음성). 최종 방어선은 아래 명시 이름 고정 테스트 — 신규 config 플래그를
star-import 소비자가 쓰게 되면 그 이름을 명시 목록에도 추가할 것. 정밀 스코프 분석
(symtable)은 복잡도 대비 이득이 작아 미채택.

DB/LLM 연결 불필요 — 순수 import + AST 검사.
"""
import ast
import pathlib
import re

import shared.config as _cfg

_SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"


def _config_defined_upper_names() -> set:
    """shared/config.py 모듈 수준에 정의된 UPPER_CASE 이름(설정 상수) 집합."""
    return {n for n in vars(_cfg) if re.fullmatch(r"[A-Z][A-Z0-9_]+", n)}


def _star_import_module_files() -> list:
    """`from shared.config import *` 를 쓰는 src/modules/*.py 파일 목록."""
    out = []
    for p in sorted((_SRC_ROOT / "modules").glob("*.py")):
        if "from shared.config import *" in p.read_text(encoding="utf-8"):
            out.append(p)
    return out


def _bare_loaded_names(tree: ast.AST) -> set:
    """모듈 AST 에서 Load 컨텍스트로 참조되는 bare Name 집합.

    함수-지역 명시 import(`from shared.config import X`)로 바인딩되는 이름은 제외한다 —
    그 경로는 __all__ 과 무관하게 안전하기 때문(kb_retrieval 의 HYBRID 플래그 패턴).
    """
    loaded, bound = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
        elif isinstance(node, ast.ImportFrom) and node.module == "shared.config":
            for a in node.names:
                if a.name != "*":
                    bound.add(a.asname or a.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
    return loaded - bound


def test_star_imported_config_names_resolve_at_runtime():
    """star-import 모듈이 bare 로 쓰는 config 상수는 그 모듈 네임스페이스에서 해석돼야 한다.

    해석 공급원은 (a) config.__all__ 등재(star-import 직접) 또는 (b) modules/__init__ 주입
    (다른 모듈 __all__ 경유) 둘 다 정당 — 불변식은 '런타임에 이름이 존재한다' 이다.
    (config.__all__ 만 정적으로 강제하면 (b) 로 공급되는 이름에 거짓 양성 —
    domain.CONFIRMATION_FOLLOWUP_CUES 등 4건 실측.)
    """
    import importlib
    defined = _config_defined_upper_names()
    problems = []
    for path in _star_import_module_files():
        mod = importlib.import_module(f"modules.{path.stem}")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in sorted(_bare_loaded_names(tree) & defined):
            if not hasattr(mod, name):
                problems.append(f"{path.name}: {name}")
    assert not problems, (
        "star-import 소비 모듈이 bare 로 참조하는 config 이름이 런타임 미해석 — "
        "NameError(조용한 기능 정지) 위험. config __all__ 등재 필요: " + ", ".join(problems)
    )


def test_relationship_flags_resolve_in_insight_namespace():
    """실제 import 결과 기준의 동적 확인 — insight 모듈 네임스페이스에서 관계 플래그가 해석된다."""
    from modules import insight
    for name in (
        "AGENT_RELATIONSHIP_INTROSPECT_ENABLED",
        "AGENT_RELATIONSHIP_INFERENCE_ENABLED",
        "AGENT_RELATIONSHIP_PROBE_ENABLED",
        "AGENT_RELATIONSHIP_INFER_CAP",
        "AGENT_RELATIONSHIP_PROBE_CAP",
        "AGENT_RELATIONSHIP_PROBE_SAMPLE",
        "AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS",
        "AGENT_RELATIONSHIP_REINFER_SEC",
    ):
        assert hasattr(insight, name), f"insight 네임스페이스에 {name} 미해석 (config __all__ 확인)"


def test_sql_fix_model_resolves_in_llm_namespace():
    from modules import llm
    assert hasattr(llm, "AGENT_SQL_FIX_MODEL"), (
        "llm 네임스페이스에 AGENT_SQL_FIX_MODEL 미해석 — llm_fix_sql 이 NameError 로 무력화된다"
    )

"""Knowledge base facade (TASK-0142).

이 모듈은 3376줄 god-module 였다. TASK-0142 에서 책임별 3개 모듈로 분할:
  - `kb_scope`     : scope SQL / PII 마스킹 / 에러 분류 / 유사도 / advisory lock / cache key / refresh
  - `kb_retrieval` : RAG doc/object 검색 + 벡터/trigram 임베딩 + fact 로딩 + prompt 선택 + payload
  - `kb_write`     : fact/rag upsert + dual-write + global publish + step-trace + zero-result 진단

기존 소비처 (tests, agent_core, insight, schema, render, sql_ops, domain, utils, db,
llm, kb_backend) 의 `from modules.knowledge import X` 와 `knowledge.X` (private helper
직접 접근 + monkeypatch 포함) 를 깨지 않도록 본 facade 가 3개 모듈의 **모든** top-level
심볼 (public `__all__` + private `_helper`) 을 re-export 한다. blast-radius 0.

공유 네임스페이스 (shared-globals) 보존
----------------------------------------
분할 전 모든 함수가 한 모듈 globals 를 공유했기에, test 가
`monkeypatch.setattr(knowledge, "_embed_query_vector", ...)` 한 뒤
`knowledge._load_rag_documents_for_request_pg(...)` 를 호출하면 패치가 호출 함수
내부 bare-name 조회에 그대로 반영됐다. 분할 후에도 이 seam 을 유지하기 위해, 본 facade
는 kb_scope/kb_retrieval/kb_write 의 함수 객체를 **facade 의 단일 globals dict** 를
`__globals__` 로 갖도록 재바인딩한다 (함수 본문 코드 객체는 그대로 — 순수 리팩터).
이로써 패치/상호참조가 분할 전과 동일하게 한 네임스페이스에서 해석된다.
"""
import logging
import types as _types

logger = logging.getLogger("agent_core.knowledge")

from . import kb_scope as _kb_scope
from . import kb_retrieval as _kb_retrieval
from . import kb_write as _kb_write

# 분할 전 정의 순서: kb_scope → kb_retrieval → kb_write (의존 단방향).
_KB_SUBMODULES = (_kb_scope, _kb_retrieval, _kb_write)

# 1) 세 모듈의 모든 top-level 심볼 (상수 포함) 을 facade globals 로 끌어온다.
#    private `_helper` 도 포함 — tests 가 `knowledge._load_rag_documents_for_request_pg`
#    같은 비-__all__ 헬퍼를 직접 접근/패치한다.
_GLOBALS = globals()
for _mod in _KB_SUBMODULES:
    for _name, _obj in vars(_mod).items():
        if _name.startswith("__"):
            continue
        _GLOBALS[_name] = _obj

# 2) shared-globals 재바인딩: 함수 객체를 facade 의 globals dict 를 __globals__ 로
#    갖는 동일-코드 함수로 교체. cross-module / monkeypatch 조회가 한 네임스페이스에서
#    해석되어 분할 전 단일 모듈 의미를 정확히 재현한다.
for _name, _obj in list(_GLOBALS.items()):
    if isinstance(_obj, _types.FunctionType) and getattr(_obj, "__module__", "").endswith(
        ("kb_scope", "kb_retrieval", "kb_write")
    ):
        _rebound = _types.FunctionType(
            _obj.__code__,
            _GLOBALS,
            _obj.__name__,
            _obj.__defaults__,
            _obj.__closure__,
        )
        _rebound.__dict__.update(_obj.__dict__)
        _rebound.__kwdefaults__ = _obj.__kwdefaults__
        _rebound.__doc__ = _obj.__doc__
        _GLOBALS[_name] = _rebound

# 3) public 계약: 분할 전 knowledge.__all__ 과 동일하게 세 모듈 __all__ 의 합집합.
__all__ = sorted(
    set(_kb_scope.__all__) | set(_kb_retrieval.__all__) | set(_kb_write.__all__)
)

for _tmp in ("_types", "_mod", "_name", "_obj", "_rebound", "_GLOBALS",
             "_KB_SUBMODULES", "_kb_scope", "_kb_retrieval", "_kb_write", "_tmp"):
    globals().pop(_tmp, None)

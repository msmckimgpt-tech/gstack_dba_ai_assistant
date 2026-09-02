"""feature-0043 — 러너가 **스스로 최신본으로 갈아 끼우고 재기동**한다 (사용자 결정 2026-09-02).

## 결정과 그 이유

웹 리서치로 상용 서비스의 방식을 대조한 뒤 사용자가 두 축을 정했다:

| 축 | 선택 |
|---|---|
| 낡음 판정 | **현행 유지 — 지문 완전 일치** |
| 화면 처리 | **조용한 자동 갱신** (GitHub Actions 셀프호스티드 러너와 같은 형태) |

두 선택은 짝이다. 지문 일치는 정확하지만 러너 파일이 거의 모든 배포에서 바뀌므로, **러너와
무관한 배포 하나가** 접속 중인 모든 러너를 낡음으로 뒤집는다(실측 2026-09-02: 재설치 3분 뒤
다른 세션의 배포가 착륙해 「업데이트 필요」가 다시 떴고, 연결 모달이 열린 채 굳었다).
그 사실을 조치 요구로 내보내면 하루에 몇 번씩 뜨는데 사용자가 할 일은 없다. 그래서 엄격함은
그대로 두고 **조치를 자동화**한다.

## 이 파일이 잠그는 것 — 그리고 왜 그것들인가

1. **개발 트리에서는 절대 갱신하지 않는다.** 모듈로 실행 중이면 `_self_build()` 가
   `agent/events.py` 의 지문을 돌려주므로 배포본과 **영원히** 다르다. 경로만 보고 진행하면
   러너가 개발자의 소스를 배포본으로 덮어쓴다. 판정은 **지문 일치**로만 한다.
2. **서버가 준 URL 을 쓰지 않는다.** 받은 파일은 다음 순간 **실행된다** — 응답을 바꿀 수
   있는 누구든 러너가 실행할 파일을 지목할 수 있게 하면 안 된다. 경로는 이 모듈의 상수다.
3. **검사한 것만 교체한다.** https 아님·200 아님·너무 작음·파이썬 아님 → 전부 거절.
4. **바뀌는 것이 없으면 재기동하지 않는다.** 받은 것이 지금 나와 같으면 그대로 둔다 —
   이 한 줄이 「배포본을 못 따라잡는 러너가 영원히 재기동하는」 고리를 끊는다.
5. **일하는 중에는 갱신하지 않는다.** 최신이 되자고 사용자가 방금 던진 질문을 죽이지 않는다.
6. **신고와 실제 능력이 같은 식에서 나온다.** 못 하면서 `self_update` 를 신고하면 화면이
   조치 안내를 감춘 채 **오지 않을 갱신**을 기다린다.
7. **재기동 전에 하트비트를 끊고 점유를 놓는다.** `os.execv` 는 `atexit` 를 부르지 않는다.
8. **화면은 접는 식을 하나만 쓴다.** 칩·모달 성공 조건·자동 실행 자격·「재실행해도 그대로」가
   모두 같은 축을 읽어야 한다 — 두 벌이면 하나만 고쳐지는 순간 화면이 자기 안에서 갈린다.
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_SRC = _UNIT / "feature-0043-external-llm-bridge" / "src"
AGENT_PKG = _SRC / "agent"
SELFUPDATE_PY = AGENT_PKG / "selfupdate.py"
LIFECYCLE_PY = AGENT_PKG / "lifecycle.py"
INIT_PY = AGENT_PKG / "__init__.py"
EVENTS_PY = AGENT_PKG / "events.py"
BUNDLE = _SRC / "bridge_agent.py"
MODAL_JS = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "app" / "connect-modal.js"
OAUTH_AS = _UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "oauth_as.py"
OAUTH_STORE = _UNIT / "feature-0003-agent-web-ui" / "src" / "oauth_store.py"
BRIDGE_TASKS = _UNIT.parent / "shared" / "bridge_tasks.py"


def _code(text: str) -> str:
    """주석을 걷어낸 코드만 — 구조 단언이 **설명문**에 걸려 참이 되지 않게."""
    out = []
    for ln in text.splitlines():
        s = ln.lstrip()
        if s.startswith(("#", "//", "*", "/*")):
            continue
        out.append(ln)
    return "\n".join(out)


def _nodoc(text: str) -> str:
    """주석 **과 docstring** 을 걷어낸 실행 코드만.

    `_code` 만으로는 부족하다 — 이 파일의 단언 중에는 「이 이름이 코드에 없어야 한다」가 있고,
    그 이름은 **왜 쓰지 않는지 설명하는 docstring** 에 등장한다. 설명문에 걸리는 단언은
    계약이 아니라 문구 검사가 된다(이 저장소가 이미 겪은 함정). `ast.unparse` 는 주석을
    떨어뜨리므로, docstring 만 걷어내면 남는 것이 곧 실행되는 코드다.
    """
    import ast

    tree = ast.parse(text)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            body.pop(0)
    return ast.unparse(tree)


@pytest.fixture(scope="module")
def su():
    """`selfupdate` 모듈을 단독으로 불러온다(패키지 import 부작용 없이)."""
    spec = importlib.util.spec_from_file_location("_su_probe", SELFUPDATE_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_su_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════════
#  A. 개발 트리 보호 — 이 모듈에서 가장 중요한 한 줄
# ══════════════════════════════════════════════════════════════════════════════


def test_module_layout_never_reports_a_bundle(su, tmp_path, monkeypatch):
    """⭐ 지문이 다르면 «단일 파일» 이 아니다 — 경로가 그럴듯해도 마찬가지."""
    fake = tmp_path / "bridge_agent.py"
    fake.write_text("print('나는 배포본이 아니다')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(fake)])
    assert su.running_bundle_path("deadbeefcafe") is None, \
        "지문이 다른 파일을 배포본으로 인정했다 — 개발 트리의 소스가 덮어써진다"


def test_matching_digest_is_accepted(su, tmp_path, monkeypatch):
    """반대 방향도 성립해야 판정이 쓸모가 있다(항진명제가 아님을 보인다)."""
    real = tmp_path / "bridge_agent.py"
    body = b"# " + b"x" * 100 + b"\n"
    real.write_bytes(body)
    monkeypatch.setattr(sys, "argv", [str(real)])
    assert su.running_bundle_path(su.agent_digest(body)) == str(real.resolve())


def test_unknown_self_build_is_never_a_bundle(su, tmp_path, monkeypatch):
    """지문을 모르면(`""`) 판정하지 않는다 — 모름을 일치로 읽으면 아무 파일이나 통과한다."""
    f = tmp_path / "bridge_agent.py"
    f.write_bytes(b"anything")
    monkeypatch.setattr(sys, "argv", [str(f)])
    assert su.running_bundle_path("") is None


def test_the_real_bundle_identifies_itself():
    """⭐ 실물 대조 — 빌드된 배포본을 그 파일로 실행하면 스스로를 배포본으로 인식한다."""
    if not BUNDLE.exists():
        pytest.skip("배포본 미빌드 — `make bridge-agent` 후 도는 검사")
    body = BUNDLE.read_bytes()
    spec = importlib.util.spec_from_file_location("_bundle_probe", BUNDLE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bundle_probe"] = mod
    argv0 = sys.argv
    sys.argv = [str(BUNDLE)]
    try:
        spec.loader.exec_module(mod)
        assert mod._self_build() == hashlib.sha256(body).hexdigest()[:12]
        assert mod.running_bundle_path(mod._self_build()) == str(BUNDLE.resolve())
        assert "self_update" in mod.AGENT_FEATURES
    finally:
        sys.argv = argv0
        sys.modules.pop("_bundle_probe", None)


def test_dev_tree_declares_no_self_update_capability():
    """⭐ 모듈 실행에서는 `self_update` 신고가 **빠져야** 한다 — 못 하면서 신고하면
    화면이 조치 안내를 감춘 채 오지 않을 갱신을 기다린다."""
    src = _code(LIFECYCLE_PY.read_text(encoding="utf-8"))
    assert "_SELF_UPDATE_OK[0] = (not getattr(args, \"no_self_update\", False)" in src, \
        "능력 판정이 사용자 선택만 보고 있다"
    assert "running_bundle_path(_self_build())" in src, \
        "실제 능력(단일 파일인가)을 보지 않는다"
    assert 'f != "self_update"' in src, "못 하는 경우에 신고를 지우지 않는다"


# ══════════════════════════════════════════════════════════════════════════════
#  B. 받는 경로 — 이 파일은 다음 순간 실행된다
# ══════════════════════════════════════════════════════════════════════════════


def test_download_path_is_a_constant_not_a_server_value():
    """⭐ 하트비트 응답의 `download_url` 을 따르지 않는다."""
    src = _nodoc(SELFUPDATE_PY.read_text(encoding="utf-8"))
    # 따옴표 종류는 보지 않는다 — `ast.unparse` 가 정규화하므로 그것에 걸면 계약이 아니라
    # 포매팅 검사가 된다.
    assert "SELF_UPDATE_PATH" in src and "/static/agent/bridge_agent.py" in src
    assert "download_url" not in src, \
        "서버가 지목한 곳에서 받는다 — 응답을 바꿀 수 있는 누구든 실행할 파일을 정하게 된다"
    life = _nodoc(LIFECYCLE_PY.read_text(encoding="utf-8"))
    assert "download_url" not in life.split("def try_self_update", 1)[1].split("\ndef ", 1)[0], \
        "갱신 경로가 서버 값을 참조한다"


def test_plaintext_base_is_refused(su, monkeypatch):
    """평문으로는 받지 않는다 — 받은 것을 실행하는 경로다.

    ⚠ 그냥 `fetch_deployed("http://…")` 를 부르고 `None` 을 확인하면 **헛통과**한다:
    가드를 지워도 DNS 가 실패해 `None` 이 나오기 때문이다(뮤테이션 M2 가 그렇게 살아남았다).
    그래서 «성공했을 응답» 을 물려 놓고 **호출 자체가 없었음**을 단정한다.
    """
    good = b"# ok\n" + b"x = 1\n" * 5000
    called = []

    class _Resp:
        status = 200

        def read(self):
            return good

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    def _spy(*a, **k):
        called.append(a)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _spy)
    assert su.fetch_deployed_agent("http://example.invalid", None) is None, \
        "평문 주소에서 받았다 — 이 파일은 다음 순간 실행된다"
    assert not called, "평문인데 네트워크 요청까지 나갔다(가드가 없다)"
    # 대조군: 같은 응답이라도 https 면 통과한다 — 위 단언이 항진명제가 아님을 보인다.
    assert su.fetch_deployed_agent("https://example.invalid", None) == good


@pytest.mark.parametrize("payload,why", [
    (b"", "빈 응답"),
    (b"# tiny\n", "너무 작음(오류 페이지·잘린 응답)"),
    (b"<html>login</html>\n" + b"x" * 30000, "파이썬이 아님"),
])
def test_bad_payloads_are_rejected(su, monkeypatch, payload, why):
    """크기·문법 검사를 통과한 것만 교체 대상이 된다."""
    class _Resp:
        status = 200

        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(su, "SELF_UPDATE_MIN_BYTES", 20000, raising=False)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert su.fetch_deployed_agent("https://example.invalid", None) is None, why


def test_a_good_payload_is_accepted(su, monkeypatch):
    """거절만 하면 이 함수는 쓸모가 없다 — 통과 경로도 검사한다."""
    good = b"# ok\n" + b"x = 1\n" * 5000

    class _Resp:
        status = 200

        def read(self):
            return good

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert su.fetch_deployed_agent("https://example.invalid", None) == good


def test_non_200_is_rejected(su, monkeypatch):
    """200 이 아닌 응답의 본문은 러너가 아니다(리다이렉트 안내·오류 페이지)."""
    class _Resp:
        status = 503

        def read(self):
            return b"x = 1\n" * 5000

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert su.fetch_deployed_agent("https://example.invalid", None) is None


# ══════════════════════════════════════════════════════════════════════════════
#  C. 교체 — 중간에 죽어도 반쪽 파일이 남지 않는다
# ══════════════════════════════════════════════════════════════════════════════


def test_install_is_atomic_and_keeps_mode(su, tmp_path):
    old = tmp_path / "bridge_agent.py"
    old.write_bytes(b"old\n")
    old.chmod(0o700)
    assert su.install_agent_file(str(old), b"new payload\n") is True
    assert old.read_bytes() == b"new payload\n"
    assert (old.stat().st_mode & 0o777) == 0o700, "권한이 바뀌었다 — 다음 실행이 막힐 수 있다"
    assert not list(tmp_path.glob(".bridge_agent.*")), "임시 파일이 남았다"


def test_install_writes_into_the_same_directory(su):
    """`os.replace` 의 원자성은 **같은 파일시스템** 안에서만 보장된다."""
    src = _code(SELFUPDATE_PY.read_text(encoding="utf-8"))
    body = src.split("def install_agent_file(", 1)[1].split("\ndef ", 1)[0]
    assert "dir=directory" in body, "임시 파일을 대상과 다른 곳에 만든다"
    assert "os.replace(" in body, "원자 교체가 아니다"


def test_install_failure_leaves_the_old_file(su, tmp_path):
    """못 쓰면 있던 파일 그대로 — 갱신하려다 멀쩡한 러너를 못 띄우게 만들지 않는다."""
    missing_dir = tmp_path / "nope" / "bridge_agent.py"
    assert su.install_agent_file(str(missing_dir), b"x") is False


# ══════════════════════════════════════════════════════════════════════════════
#  D. 절차 — 언제 하고 언제 미루는가
# ══════════════════════════════════════════════════════════════════════════════


def _try_self_update_body() -> str:
    return _code(LIFECYCLE_PY.read_text(encoding="utf-8")).split(
        "def try_self_update(", 1)[1].split("\ndef ", 1)[0]


def test_busy_runner_defers_instead_of_cancelling():
    """⭐ 최신이 되자고 사용자가 방금 던진 질문을 죽이지 않는다."""
    body = _try_self_update_body()
    assert "if active.count() > 0:" in body and "return False" in body
    assert "cancels" not in body, "갱신 경로가 진행 중 작업을 취소한다"


def test_same_digest_does_not_restart():
    """⭐ 무한 재기동 고리를 끊는 한 줄."""
    body = _try_self_update_body()
    assert "if new_build == mine:" in body, "받은 것이 나와 같은지 대조하지 않는다"
    idx_cmp = body.index("if new_build == mine:")
    idx_install = body.index("install_agent_file(")
    assert idx_cmp < idx_install, "대조가 교체 **뒤**다 — 같은 파일로도 재기동한다"


def test_there_is_a_floor_between_attempts():
    """배포가 몰리는 날 재기동이 연달아 일어나지 않게 하는 바닥."""
    body = _try_self_update_body()
    assert "SELF_UPDATE_MIN_INTERVAL_SEC" in body
    src = _code(SELFUPDATE_PY.read_text(encoding="utf-8"))
    assert re.search(r"SELF_UPDATE_MIN_INTERVAL_SEC\s*=\s*\d", src)


def test_heartbeat_and_claims_are_released_before_reexec():
    """⭐ `os.execv` 는 `atexit` 를 부르지 않는다 — 여기서 놓지 않으면 서버가 유령을 붙든다."""
    body = _try_self_update_body()
    i_stop = body.index("_SELF_UPDATE_STOP[0]()")
    i_release = body.index("release_own_claims_on_exit()")
    i_exec = body.index("reexec_self(")
    assert i_stop < i_exec and i_release < i_exec, "정리보다 재기동이 먼저다"
    assert i_stop < i_release, "하트비트를 끊기 전에 점유를 놓는다 — 그 사이 새 점유가 붙는다"


def test_reexec_preserves_the_original_arguments(su):
    """토큰은 환경에, 나머지는 argv 에 있다 — 둘 중 하나라도 잃으면 다시 못 뜬다."""
    src = _code(SELFUPDATE_PY.read_text(encoding="utf-8"))
    body = src.split("def reexec_self(", 1)[1].split("\ndef ", 1)[0]
    assert "sys.argv[1:]" in body, "인자를 넘기지 않는다"
    assert "sys.executable" in body, "인터프리터를 잃는다"


def test_self_update_runs_before_the_wait_call():
    """대기 **뒤**에 두면 질문 하나를 끌어와 놓고 갱신하러 나간다."""
    src = _code(LIFECYCLE_PY.read_text(encoding="utf-8"))
    i_upd = src.index("try_self_update(api, active)")
    i_wait = src.index('api.call("wait_for_request"')
    i_sup = src.index("if _SUPERSEDED.is_set():")
    assert i_sup < i_upd < i_wait, \
        "순서가 어긋난다 — 물러남 → 갱신 → 대기 여야 한다"


def test_stale_signal_is_quiet_when_the_runner_can_fix_itself():
    """조용한 자동 갱신 — 스스로 고칠 수 있으면 경고를 찍지 않는다(할 일이 없으므로)."""
    src = _code(LIFECYCLE_PY.read_text(encoding="utf-8"))
    blk = src.split('if _u.get("stale_build")', 1)[1].split("stop.wait(", 1)[0]
    assert "if _SELF_UPDATE_OK[0]:" in blk and "_SELF_UPDATE.set()" in blk
    assert "elif not _stale_said:" in blk, \
        "스스로 못 고치는 러너에게도 경고가 사라졌다 — 그때는 사람이 할 일이 있다"


# ══════════════════════════════════════════════════════════════════════════════
#  E. 신고 → 서버 → 화면
# ══════════════════════════════════════════════════════════════════════════════


def test_feature_name_is_shared_between_runner_and_server():
    """이름이 갈리면 신고는 가는데 아무도 못 알아본다."""
    assert 'RUNNER_FEATURE_SELF_UPDATE = "self_update"' in BRIDGE_TASKS.read_text(encoding="utf-8")
    assert '"self_update"' in EVENTS_PY.read_text(encoding="utf-8")


def test_server_reads_the_report_and_ships_it():
    store = OAUTH_STORE.read_text(encoding="utf-8")
    assert "def account_runner_self_updating(" in store
    body = store.split("def account_runner_self_updating(", 1)[1].split("\ndef ", 1)[0]
    assert "ORDER BY t.Id DESC LIMIT 1" in body, \
        "정본 러너 선택 축이 `account_runner_build` 와 다르다 — 두 값이 다른 러너의 것이 된다"
    assert "bridge_tasks.RUNNER_FEATURE_SELF_UPDATE" in body, "이름을 따로 적었다"
    api = OAUTH_AS.read_text(encoding="utf-8")
    assert '"runner_self_updating": runner_self_updating,' in api, "화면까지 도달하지 않는다"


def test_a_failed_lookup_falls_back_to_showing_the_notice():
    """모르면 **종전 화면**(조치 안내)으로 — 반대 방향은 안내를 조용히 지운다."""
    store = OAUTH_STORE.read_text(encoding="utf-8")
    body = store.split("def account_runner_self_updating(", 1)[1].split("\ndef ", 1)[0]
    # ⚠ except 블록의 **본문만** 본다. 「빈 줄까지」로 자르면 그 뒤의 `if not row: return False`
    #   가 딸려 들어와, `return True` 로 바꿔도 통과한다(뮤테이션 M11 이 그렇게 살아남았다).
    lines = body.split("except Exception", 1)[1].splitlines()[1:]
    block = []
    for ln in lines:
        if ln.strip() and not ln.startswith("        "):
            break                      # 들여쓰기가 풀렸다 = 블록 끝
        block.append(ln)
    assert "return False" in "\n".join(block), "조회 실패가 fail-open 이다"
    assert "return True" not in "\n".join(block)
    api = _code(OAUTH_AS.read_text(encoding="utf-8"))
    blk = api.split("runner_self_updating = False", 1)[1]
    assert "runner_self_updating = False" in blk, \
        "지문 판정이 실패한 조회에서 자기갱신 신고만 살아남는다"


def test_the_frontend_folds_staleness_in_exactly_one_place():
    """⭐ 칩·모달·자동 실행·「재실행해도 그대로」가 같은 축을 읽어야 한다."""
    js = _code(MODAL_JS.read_text(encoding="utf-8"))
    assert "function _actionableStaleOf(body)" in js
    # 접는 식(`runner_self_updating` 을 보는 곳)은 그 함수 안에만 있어야 한다.
    assert js.count("runner_self_updating") == 1, \
        "접는 식이 두 벌이다 — 하나만 고쳐지는 순간 화면이 자기 안에서 갈린다"
    # 그리고 원시 `runner_stale` 을 직접 읽는 곳이 남아 있으면 안 된다.
    raw = [ln for ln in js.splitlines()
           if "runner_stale" in ln and "_actionableStaleOf" not in ln
           and "function _actionableStaleOf" not in ln]
    assert len(raw) == 1, f"원시 낡음을 직접 읽는 곳이 남았다: {raw}"


def test_the_fold_defaults_to_showing_the_notice():
    """`runner_self_updating` 이 없는 응답(구 서버)은 종전대로 안내가 뜬다."""
    js = _code(MODAL_JS.read_text(encoding="utf-8"))
    body = js.split("function _actionableStaleOf(body)", 1)[1].split("\n}", 1)[0]
    assert "!== true" in body, \
        "`=== false` 로 쓰면 필드가 없는 구 서버 응답에서 안내가 조용히 사라진다"


# ══════════════════════════════════════════════════════════════════════════════
#  F. 배포본 — 모듈이 실제로 실려 나가는가
# ══════════════════════════════════════════════════════════════════════════════


def test_selfupdate_is_registered_in_the_bundle_order():
    """목록에서 빠진 모듈은 배포본에서 **조용히 사라진다**."""
    src = INIT_PY.read_text(encoding="utf-8")
    order = src.split("_EMIT_ORDER", 1)[1].split("\n)", 1)[0]
    assert '"selfupdate",' in order
    assert order.index('"selfupdate"') < order.index('"lifecycle"'), \
        "`lifecycle` 이 부르는 모듈이 그 뒤에 실린다"


def test_the_built_bundle_contains_the_self_update_path():
    if not BUNDLE.exists():
        pytest.skip("배포본 미빌드")
    body = BUNDLE.read_text(encoding="utf-8")
    assert "SELF_UPDATE_PATH" in body and "def running_bundle_path(" in body
    assert "def try_self_update(" in body


def test_the_bundle_is_stdlib_only():
    """러너는 사용자 머신에 홀로 놓인다 — 표준 라이브러리 밖을 쓰면 그 머신에서 죽는다."""
    if not shutil.which("python3") or not BUNDLE.exists():
        pytest.skip("배포본 미빌드")
    r = subprocess.run([sys.executable, "-c",
                        "import ast,sys;t=ast.parse(open(sys.argv[1],'rb').read());"
                        "mods=set()\n"
                        "for n in ast.walk(t):\n"
                        "    if isinstance(n, ast.Import):\n"
                        "        mods.update(a.name.split('.')[0] for a in n.names)\n"
                        "    elif isinstance(n, ast.ImportFrom) and n.module and not n.level:\n"
                        "        mods.add(n.module.split('.')[0])\n"
                        "print(','.join(sorted(m for m in mods if m not in sys.stdlib_module_names)))",
                        str(BUNDLE)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    extra = [m for m in r.stdout.strip().split(",") if m]
    assert not extra, f"표준 라이브러리 밖 import: {extra}"

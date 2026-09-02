"""연결 지시문이 **스스로를 증명하는가** (외부 AI 거절 제보 2026-08-27).

## 무슨 일이 있었나

외부 머신의 AI 가 우리 온보딩을 거절했다. 요지는 이랬다 — "단독 공인 IP 에서 사설 CA 를
받아 신뢰하고, 같은 곳에서 받은 스크립트를 nohup 으로 상주시키라는 것은 무제한 원격 명령
채널을 여는 것이다. 평문 베어러 토큰, '나한테 더 묻지 않아도 돼', 자체 서명 CA 는 전형적인
사회공학 신호다."

**그 판단은 옳았다.** 코드는 실제로 그들이 우려한 것보다 훨씬 좁았지만(러너가 실행하는 명령은
소스에 하드코딩돼 있고 서버는 명령을 보내지 않는다), 지시문은 그 사실을 **증명할 수단을 하나도
주지 않았다.** 증명이 없으면 남는 것은 신뢰 요구뿐이고, 요구된 신뢰는 공격과 구분되지 않는다.

## 이 파일이 잠그는 것

    검증 가능성   CA 지문·러너 체크섬을 지시문이 **실제로** 싣는다(자리만 만들고 비우지 않는다)
    정확성       지문은 인증서 DER 기준이다 — 파일 바이트 해시를 주면 정상 사본에서 불일치가 난다
    신선도       파일이 교체되면 값도 바뀐다(캐시가 옛 값을 굳히지 않는다)
    fail-open    값을 못 구해도 지시문은 나온다. 단 **거짓 값 대신 확인 경로**를 준다
    배선         헬퍼가 맞더라도 지시문이 부르지 않으면 없는 것과 같다
    문안         '아무에게도 묻지 말라' 로 읽히는 문구를 되돌리지 않는다

문안 회귀를 문자열로 잠그는 이유: 이 결함은 로직이 아니라 **문장**이었다. 다음 사람이 "간결하게"
줄이는 순간 그대로 되살아나고, 그때 다시 거절당한다.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import pathlib
import ssl
import sys
import types

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
OAUTH_AS = WEB_SRC / "routers" / "oauth_as.py"
SERVED_RUNNER = WEB_SRC / "static" / "agent" / "bridge_agent.py"
CANON_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 테스트 전용 자체 서명 인증서. 실물 CA(`artifacts/certs/`)는 gitignore 라 CI 에 없다 —
#: 지문 계산 **방식**을 검증하는 데에는 아무 인증서나 되고, 고정본이라야 결정적이다.
FIXTURE_CA_PEM = """\
-----BEGIN CERTIFICATE-----
MIIDLzCCAhegAwIBAgIUGRGXmiVK2VmTMqrN1bdoc4PfPsYwDQYJKoZIhvcNAQEL
BQAwJjEkMCIGA1UEAwwbYnJpZGdlLWhhbmRvZmYtdGVzdC1maXh0dXJlMCAXDTI2
MDgyNzEwMjEwOVoYDzIxMjYwODAzMTAyMTA5WjAmMSQwIgYDVQQDDBticmlkZ2Ut
aGFuZG9mZi10ZXN0LWZpeHR1cmUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDnoZ5aBNTE/h12nHvdsX7oUFel8SaArgZAAlxixEKs96C9Wz8GYE+sJ4/E
0vIrMWySLcjxkbfr8Ws/ijVVBuLxOHm4ppCqJuNcgfK7fa6MQl1tBE43GUNkOwc/
elV3zo06kodYFQe5W20/trlMuUwycbuooz7LtsSbTIUSUcpjR0/k7qs0ieSXssUL
YqcyOrjLfaISKqgiLxzKQqivzpR5/W2kwULr7nSTlVp7pMrMw4Y6TXT3llXrPN87
bbziKEXd79+U/Zij0I2+kWFmNjNAwuT5NCjexq+dnlYVY7mvLWRZDWjZZADqQ6Mx
CWzTBZYa5fHLkJigKxVR3Tg20xnTAgMBAAGjUzBRMB0GA1UdDgQWBBSY5aIVPHCP
dtgUrGfHPpIEMibFhDAfBgNVHSMEGDAWgBSY5aIVPHCPdtgUrGfHPpIEMibFhDAP
BgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQCji4emNLLl1HEXohb2
glJgIPRRYEkWwzkxz11AZVPbtipMuV73Yz5i4A0ttpxxPWx0wwLSNF4RUgtunEIS
reqeHbJa29lxdW8CsM5TDhDiloG5Z5iRJUgSjLWFOvZGtBPca7UPZnxAAq9Te0hg
lIrW9QUkjZOHfOw2uryNajIj6N5DqP34/Fn5iN8n2QJ6PHh4h7zj82MeTva4qgnW
Xyl040Qkegvb8O4hH5kHtl9C9ewOViF1OLF9iqgSMIjogWWlI9rulpQJ5AvsQHBq
T85CIU2YbLJ0RfOYc7tJMOq1CKk2h7xdkSiEauB9YN2hQ4nLG3auNO8pTcoGRkop
GpJ0
-----END CERTIFICATE-----
"""
#: `openssl x509 -noout -fingerprint -sha256` 이 위 인증서에 대해 내놓는 값.
#: **openssl 로 따로 뽑은 값을 여기 굳혀 둔다** — 우리 구현으로 기대값을 만들면 구현이 틀려도
#: 테스트는 통과한다(같은 실수를 두 번 하는 것과 같다).
FIXTURE_CA_FINGERPRINT = ("31:68:BF:C2:6B:0F:A8:8C:B6:56:DD:B0:3D:93:16:5B:"
                          "2C:0E:C6:D5:A1:38:A8:A7:ED:1A:27:10:22:67:F8:85")


def _func(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{path.name}: {name} 없음")


def _code_only(text: str) -> str:
    """주석·docstring 을 걷어낸 실행부. feature-0041 의 공용 헬퍼를 그대로 쓴다.

    자체 구현하지 않는 이유: 인라인으로 짠 약한 버전(`startswith('#')` 한 줄)이 **삼중따옴표
    문자열 안의 `#` 로 시작하는 줄**까지 버려, 실제로 출력되는 지시문 한 줄을 '주석' 으로 오인해
    삼켰다(뮤테이션 X10 이 그 틈으로 통과했다). 같은 함정에 네 번 데인 feature 가 이미 정본을
    갖고 있다.
    """
    spec = importlib.util.spec_from_file_location(
        "_srcutil_handoff", _UNIT / "feature-0041-external-ai-tool-surface" / "tests" / "_srcutil.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.code_only(text)


@contextlib.contextmanager
def _loaded(static_dir: pathlib.Path | None = None):
    """`oauth_as` 를 **실제로 로드**해 돌려준다 — 소스 문자열 검사만으로는 부족하기 때문.

    문자열 검사는 "그 줄이 있는가" 만 본다. 지문이 실제로 계산되는지, 파일이 없을 때 지시문이
    죽지 않는지는 **돌려 봐야** 안다(이 저장소가 여러 번 겪은 vacuous pass 의 형태다).

    `app` 은 DB·미들웨어를 끌고 오므로 이 경로가 실제로 쓰는 속성만 stub 으로 세운다.

    원복이 `app` 하나로 끝나지 않는 이유: 로드하려면 `feature-0003/src` 를 `sys.path[0]` 에
    꽂아야 하는데, 이 저장소에는 **top-level `modules` 패키지가 두 곳**(feature-0002·0003)에
    있어 먼저 import 된 쪽이 다른 쪽을 세션 내내 가린다(0043 conftest 가 경계하는 바로 그것).
    그래서 그 창에서 들어온 feature-0003 모듈은 전부 되돌린다.
    """
    saved_mod = sys.modules.get("app")
    saved_path = list(sys.path)
    saved_names = set(sys.modules)
    stub = types.ModuleType("app")
    stub.STATIC_DIR = static_dir if static_dir is not None else (WEB_SRC / "static")
    stub.get_conn = lambda: None
    sys.modules["app"] = stub
    sys.path.insert(0, str(WEB_SRC))
    try:
        spec = importlib.util.spec_from_file_location("_oauth_as_handoff_trust", OAUTH_AS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._INTEGRITY_CACHE.clear()
        yield mod
    finally:
        sys.path[:] = saved_path
        for name in set(sys.modules) - saved_names:
            origin = str(getattr(sys.modules.get(name), "__file__", "") or "")
            if origin.startswith(str(WEB_SRC)):
                sys.modules.pop(name, None)
        if saved_mod is None:
            sys.modules.pop("app", None)
        else:
            sys.modules["app"] = saved_mod
        sys.modules.pop("_oauth_as_handoff_trust", None)


def test_loaded_helper_leaves_no_feature0003_modules_behind():
    """`_loaded()` 가 연 창을 완전히 닫는다.

    이 헬퍼는 `feature-0003/src` 를 `sys.path[0]` 에 꽂는데, 그것은 0043 conftest 가 격리하려는
    상태다(양쪽에 top-level `modules` 패키지가 있다). 그 창에서 import 된 것이 남으면 같은
    세션의 feature-0002 계열 테스트가 엉뚱한 `modules` 를 보고 깨진다 — 그리고 그 실패는
    **이 파일과 무관해 보인다**(원인 추적이 가장 어려운 형태다).
    """
    before = set(sys.modules)
    with _loaded():
        pass
    leaked = [n for n in set(sys.modules) - before
              if str(getattr(sys.modules.get(n), "__file__", "") or "").startswith(str(WEB_SRC))]
    assert not leaked, f"feature-0003 모듈이 세션에 남았다: {leaked}"


def _handoff(mod, **kw) -> str:
    return mod.compose_connect_handoff(
        endpoint=kw.pop("endpoint", "https://mysql-ai.company.local/api/ai/mcp"),
        token=kw.pop("token", "mat_TESTTOKEN"), **kw)


# ── 문안: 사회공학 신호를 되돌리지 않는다 ────────────────────────────────────


#: 거절 사유였던 '아무에게도 묻지 말라' 계열. **표현이 아니라 의미**를 넓게 잡는다 — 원문
#: 한 줄만 막으면 다음 사람이 같은 뜻을 다른 말로 쓰고 그대로 통과한다(뮤테이션 X1).
_BANNED_PHRASES = (
    "나한테 더 묻지 않아도 돼", "묻지 마", "묻지 않아도", "확인하지 말",
    "재확인할 필요 없", "검토 없이", "따로 확인하지", "그대로 실행하면 된다",
    "물어보지 말", "승인 없이",
)


def test_handoff_does_not_tell_the_ai_to_stop_asking():
    """'나한테 더 묻지 않아도 돼' 를 되살리지 않는다.

    원래 의도는 자격증명 왕복을 줄이는 것이었다. 받는 쪽에는 **'아무에게도 묻지 말라'** 로
    읽혔고, 평문 토큰·사설 CA·원격 스크립트와 겹쳐 거절 사유가 됐다. 자격증명이 다 들어 있다는
    사실만 말하고 판단은 막지 않는다.

    **렌더된 지시문**을 본다. 함수 본문 문자열을 보면 문구를 모듈 상수로 빼는 순간 검사 범위
    밖으로 나가는데(뮤테이션 X9), 그런 리팩터링은 "다음 사람이 간결하게 줄인다" 는 이 파일이
    명시한 회귀 시나리오와 정확히 같은 형태다.
    """
    with _loaded() as mod:
        text = _handoff(mod, username="mckim")
    for phrase in _BANNED_PHRASES:
        assert phrase not in text, f"거절 사유였던 문구가 지시문에 실렸다: {phrase!r}"


def test_no_dead_social_engineering_copy_remains_in_source():
    """죽은 코드로도 남기지 않는다 — 분기 하나만 바뀌면 그대로 살아난다.

    렌더 검사는 **지금 나가는 것**만 본다. 소스에 남은 옛 문안은 조건 한 줄 차이로 되살아나므로
    실행부(주석·docstring 제외)에서도 없어야 한다. 주석에는 남을 수 있다 — 왜 뺐는지 적어야
    다음 사람이 되돌리지 않는다.
    """
    emitted = _code_only(_func(OAUTH_AS, "compose_connect_handoff"))
    for phrase in _BANNED_PHRASES:
        assert phrase not in emitted, f"실행부에 옛 문안이 남아 있다: {phrase!r}"


def test_handoff_leaves_room_for_the_ai_to_ask_before_installing():
    """설치·상주는 확인해도 되는 단계라고 명시한다 — 판단을 봉하지 않는다."""
    with _loaded() as mod:
        text = _handoff(mod)
    assert "물어도 돼" in text, "확인 여지를 주지 않으면 '아무에게도 묻지 말라' 와 같아진다"


def test_handoff_names_the_issuer():
    """발급자를 밝힌다 — 받는 AI 에게 이 지시문의 유일한 출처 표시다."""
    with _loaded() as mod:
        text = _handoff(mod, username="mckim")
        anon = _handoff(mod)
    assert "mckim 계정으로" in text, "발급자가 지시문에 없다 — 출처 불명의 붙여넣기와 같아진다"
    # 이름을 모를 때도 문장이 깨지지 않아야 한다(발급 경로가 죽으면 안 된다).
    assert "사용자가" in anon and "None" not in anon


# ── 검증 값: 자리만 만들고 비우지 않는다 ─────────────────────────────────────


def test_handoff_carries_verifiable_digests(tmp_path, monkeypatch):
    """CA 지문과 러너 체크섬이 **실제 값으로** 실린다 + 대조 명령을 함께 준다."""
    ca = tmp_path / "rootCA.pem"
    ca.write_text(FIXTURE_CA_PEM, encoding="utf-8")
    monkeypatch.setenv("BRIDGE_HANDOFF_CA_PATH", str(ca))
    with _loaded() as mod:
        text = _handoff(mod)
    assert FIXTURE_CA_FINGERPRINT in text, "CA 지문이 지시문에 없다 — 대조할 대상이 없다"
    assert hashlib.sha256(SERVED_RUNNER.read_bytes()).hexdigest() in text, (
        "러너 체크섬이 없다 — 내려받은 것이 우리가 서빙한 것인지 확인할 수 없다")
    # 값만 주고 확인 방법을 안 주면 대부분은 대조하지 않는다.
    assert "openssl x509" in text and "-fingerprint -sha256" in text
    assert "sha256sum bridge_agent.py" in text
    # 같은 채널로 온 값이 뿌리가 아니라는 것도 말한다(과신 방지).
    assert "그 자체가 근거는 아니다" in text and "/trust/" in text


def test_ca_fingerprint_is_certificate_der_not_file_bytes(tmp_path, monkeypatch):
    """지문은 인증서 DER 기준이다 — 파일 바이트 해시를 주면 정상 사본에서 불일치가 난다.

    PEM 은 줄바꿈·앞뒤 주석이 달라도 같은 인증서다. 바이트 해시를 실으면 받는 쪽이
    `openssl x509 -noout -fingerprint -sha256` 으로 확인할 때 **정상인데도 어긋난다** —
    안전장치가 아니라 오경보 장치가 된다.
    """
    ca = tmp_path / "rootCA.pem"
    ca.write_text(FIXTURE_CA_PEM, encoding="utf-8")
    with _loaded() as mod:
        got = mod._ca_fingerprint(str(ca))
    assert got == FIXTURE_CA_FINGERPRINT, f"openssl 과 다른 값을 낸다: {got}"
    # 바이트 해시 회귀를 명시적으로 막는다(둘 다 64자 hex 라 눈으로는 구분되지 않는다).
    file_bytes_sha = hashlib.sha256(ca.read_bytes()).hexdigest().upper()
    assert got.replace(":", "") != file_bytes_sha, "파일 바이트를 해싱하고 있다"
    # PEM 앞에 주석이 붙어도 같은 인증서이므로 값이 같아야 한다.
    ca2 = tmp_path / "rootCA-annotated.pem"
    ca2.write_text("# 사내 Root CA (2026 회전분)\n" + FIXTURE_CA_PEM, encoding="utf-8")
    with _loaded() as mod:
        assert mod._ca_fingerprint(str(ca2)) == FIXTURE_CA_FINGERPRINT, (
            "같은 인증서인데 값이 달라졌다 — 받는 쪽에 거짓 불일치를 만든다")


def test_ca_fingerprint_refuses_to_guess_on_a_multi_cert_bundle(tmp_path):
    """번들에 인증서가 여러 장이면 **값을 내지 않는다**.

    첫 장을 골라 실으면 받는 쪽은 다른 장을 확인하고 불일치를 본다 — 정상인데 중단하는,
    가장 나쁜 형태의 오경보다. 말할 수 없을 때는 '운영자에게 확인' 으로 넘기는 편이 옳다.
    """
    bundle = tmp_path / "bundle.pem"
    bundle.write_text(FIXTURE_CA_PEM + FIXTURE_CA_PEM, encoding="utf-8")
    with _loaded() as mod:
        assert mod._ca_fingerprint(str(bundle)) == "", "어느 장의 지문인지 말할 수 없는데 값을 냈다"


def test_runner_checksum_targets_the_file_that_is_actually_served(tmp_path):
    """체크섬은 **서빙되는 파일** 기준이다 — 정본을 해싱하면 둘이 갈린 순간 오경보가 된다."""
    fake_static = tmp_path / "static"
    (fake_static / "agent").mkdir(parents=True)
    served = fake_static / "agent" / "bridge_agent.py"
    served.write_bytes(b"# served copy\n")
    with _loaded(static_dir=fake_static) as mod:
        assert mod._runner_checksum() == hashlib.sha256(b"# served copy\n").hexdigest()


def test_digest_cache_follows_file_replacement(tmp_path):
    """CA 회전·러너 재배포 후에도 옛 값을 굳히지 않는다.

    캐시가 경로만 키로 삼으면 회전 직후 지시문이 **이전 인증서의 지문**을 계속 실어, 받는 쪽은
    정상 CA 를 받고도 불일치를 보고 중단한다(= 온보딩이 통째로 막힌다).
    """
    target = tmp_path / "runner.py"
    target.write_bytes(b"one")
    with _loaded() as mod:
        first = mod._cached_digest(str(target), lambda raw: hashlib.sha256(raw).hexdigest())
        assert first == hashlib.sha256(b"one").hexdigest()
        # size 가 같아도(같은 길이) 내용이 바뀌면 mtime 이 바뀐다 — 둘 다 키에 들어가야 한다.
        target.write_bytes(b"two")
        import os as _os
        st = _os.stat(str(target))
        _os.utime(str(target), (st.st_atime + 10, st.st_mtime + 10))
        assert mod._cached_digest(str(target), lambda raw: hashlib.sha256(raw).hexdigest()) == \
            hashlib.sha256(b"two").hexdigest(), "파일이 바뀌었는데 옛 값을 돌려준다"


def test_handoff_survives_missing_digest_files(tmp_path, monkeypatch):
    """값을 못 구해도 지시문은 나온다. 단 **거짓 값 대신 확인 경로**를 준다.

    무결성 값은 보강이지 연결의 전제가 아니다 — 여기서 예외가 나면 CA 파일 하나 때문에 발급
    자체가 죽는다. 반대로 없는 값을 지어내면 대조가 무의미해지므로, 빈 자리는 '운영자에게 확인'
    으로 대체한다.
    """
    # env override 로 부재 경로를 **실제 해석 경로에** 꽂는다. 모듈 상수를 setattr 로 덮으면
    # 그 상수가 기본 인자에 굳어 있을 때 조용히 무효가 되고, 그러면 이 테스트는 로컬에
    # `/certs/rootCA.pem` 이 없다는 **환경 사실** 덕에 통과한다(= 컨테이너에서만 깨진다).
    monkeypatch.setenv("BRIDGE_HANDOFF_CA_PATH", str(tmp_path / "absent.pem"))
    with _loaded(static_dir=tmp_path / "nope") as mod:
        text = _handoff(mod)
    assert "Authorization: Bearer" in text, "지시문 발급이 무결성 값 때문에 죽었다"
    assert text.count("서버가 계산하지 못함") == 2, "빈 값을 조용히 숨기거나 지어냈다"


def test_ca_path_is_resolved_at_call_time_not_import_time(tmp_path, monkeypatch):
    """CA 경로를 **호출 시점에** 해석한다 — 기본 인자에 굳히면 환경 변경이 반영되지 않는다.

    이 결함은 조용하다: 로컬에는 `/certs/rootCA.pem` 이 없어 어느 쪽이든 빈 값이 나오므로
    테스트가 통과하고, 파일이 실재하는 컨테이너에서만 어긋난다.
    """
    ca = tmp_path / "late.pem"
    ca.write_text(FIXTURE_CA_PEM, encoding="utf-8")
    with _loaded() as mod:
        # 모듈을 로드한 **뒤에** 환경을 바꾼다 — import 시점 바인딩이면 여기서 실패한다.
        monkeypatch.setenv("BRIDGE_HANDOFF_CA_PATH", str(ca))
        assert mod._ca_fingerprint() == FIXTURE_CA_FINGERPRINT, (
            "import 시점에 굳은 경로를 쓰고 있다 — 런타임 환경이 반영되지 않는다")


def test_ca_fingerprint_prefers_the_file_the_ai_actually_downloads():
    """지문은 **서빙되는 번들**(`/trust/rootCA.crt`) 기준을 우선한다.

    `/certs/rootCA.pem` 과 번들 사본은 같은 CA 이지만 **다른 파일**이다. CA 회전 후
    `bin/trust-bundle.sh` 재조립이 누락되면 둘이 갈리고, 받는 쪽은 정상 절차를 따랐는데
    불일치를 보고 중단한다 — 온보딩이 통째로 막히는 오경보다.
    """
    src = OAUTH_AS.read_text(encoding="utf-8")
    assert "/srv/trust/rootCA.crt" in src, "AI 가 받는 파일이 아니라 다른 사본으로 지문을 낸다"
    body = _func(OAUTH_AS, "_ca_bundle_path")
    assert body.index("_TRUST_BUNDLE_CA") < body.index("_CERTS_CA"), (
        "폴백이 기본보다 먼저 온다 — 우선순위가 뒤집혔다")
    # 마운트가 없으면 지문 자체가 사라지므로, compose 에 번들이 web 으로 들어와 있어야 한다.
    compose = (_UNIT.parent / "docker-compose.yml").read_text(encoding="utf-8")
    web_extra = compose[compose.index("x-web-extra:"):]
    web_extra = web_extra[:web_extra.index("\nservices:")] if "\nservices:" in web_extra else web_extra
    # **활성** 마운트만 인정한다 — 부분문자열로 보면 주석 처리된 줄도 통과하고(뮤테이션 X11),
    # 그때 `/srv/trust` 가 없어 폴백으로 떨어진다(= 이 테스트가 막겠다고 쓴 바로 그 오경보).
    mounts = [l.strip() for l in web_extra.split("\n") if l.strip().startswith("- ")]
    assert any(m.endswith("trust-bundle:/srv/trust:ro") for m in mounts), (
        "web 에 trust-bundle 이 **활성** 마운트되지 않았다(주석 처리 포함) — "
        "지문이 폴백 경로로만 나온다")


def test_digest_cache_does_not_pin_a_transient_failure(tmp_path):
    """한 번의 읽기 실패를 캐시에 박지 않는다.

    CA 회전 중 부분 기록처럼 **일시적인** 실패가 빈 값으로 굳으면, 파일이 멀쩡해진 뒤에도
    mtime·size 가 그대로인 한 계속 "(서버가 계산하지 못함)" 이 나간다 — 고장이 아닌데 고장으로
    보이고, 온보딩은 지문 없이 진행되거나 멈춘다.
    """
    target = tmp_path / "rootCA.pem"
    target.write_bytes(b"payload")
    calls = {"n": 0}

    def flaky(raw: bytes) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("회전 중 부분 기록")
        return hashlib.sha256(raw).hexdigest()

    with _loaded() as mod:
        assert mod._cached_digest(str(target), flaky) == ""
        assert mod._cached_digest(str(target), flaky) == hashlib.sha256(b"payload").hexdigest(), (
            "빈 값이 캐시에 박혀 파일이 멀쩡한데도 계속 '계산하지 못함' 이 나간다")


def test_digest_cache_notices_a_same_mtime_size_change(tmp_path):
    """mtime 이 같아도 **크기**가 바뀌면 다시 계산한다.

    mtime 을 bump 해서 검증하면 mtime 축만 잠기고 size 축은 비어 있다(뮤테이션 X12).
    초 단위 mtime 파일시스템에서 같은 초 안의 재배포가 정확히 이 형태다.
    """
    import os as _os

    target = tmp_path / "runner.py"
    target.write_bytes(b"aaa")
    st = _os.stat(str(target))
    with _loaded() as mod:
        digest = lambda raw: hashlib.sha256(raw).hexdigest()  # noqa: E731
        mod._cached_digest(str(target), digest)
        target.write_bytes(b"bbbbbbbbbb")
        _os.utime(str(target), (st.st_atime, st.st_mtime))   # mtime 동결, size 만 변경
        assert mod._cached_digest(str(target), digest) == hashlib.sha256(b"bbbbbbbbbb").hexdigest(), (
            "크기 변화를 놓친다 — 캐시 키에 size 축이 없다")


def test_digest_cache_does_not_grow_with_each_replacement(tmp_path):
    """캐시는 경로당 한 칸이다 — 교체마다 항목이 쌓이면 장수명 프로세스에서 누수가 된다."""
    target = tmp_path / "runner.py"
    with _loaded() as mod:
        import os as _os
        for i in range(5):
            target.write_bytes(f"rev{i}".encode())
            st = _os.stat(str(target))
            _os.utime(str(target), (st.st_atime + i + 1, st.st_mtime + i + 1))
            mod._cached_digest(str(target), lambda raw: hashlib.sha256(raw).hexdigest())
        assert len(mod._INTEGRITY_CACHE) == 1, (
            f"교체마다 캐시가 쌓인다({len(mod._INTEGRITY_CACHE)}칸) — 키에 mtime 이 들어갔다")


def test_handoff_wires_the_digest_helpers():
    """헬퍼가 맞더라도 지시문이 부르지 않으면 없는 것과 같다(배선 회귀 방어)."""
    body = _func(OAUTH_AS, "compose_connect_handoff")
    assert "_ca_fingerprint()" in body and "_runner_checksum()" in body, (
        "지시문이 무결성 헬퍼를 호출하지 않는다 — 값이 하드코딩됐거나 배선이 끊겼다")


def test_connect_endpoint_passes_the_issuer_through():
    """발급 엔드포인트가 `username` 을 실제로 넘기는가.

    헬퍼는 발급자를 렌더할 수 있지만 **유일한 호출부**가 안 넘기면 화면에는 늘 '사용자가' 만
    나온다 — 이 문안이 존재하는 이유(받는 AI 에게 유일한 출처 표시)가 통째로 사라지는데,
    헬퍼를 직접 부르는 테스트는 그것을 못 본다(뮤테이션 C2 가 그대로 통과했다).
    """
    src = OAUTH_AS.read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == "connect_issue_token")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "compose_connect_handoff"]
    assert calls, "발급 엔드포인트가 지시문을 싣지 않는다"
    missing = {"endpoint", "token", "username"} - {k.arg for k in calls[0].keywords}
    assert not missing, (
        f"connect_issue_token 이 {sorted(missing)} 를 넘기지 않는다 — "
        "헬퍼가 맞아도 사용자 화면에는 반영되지 않는다")


def test_handoff_actually_carries_the_token():
    """자격증명이 **실제로** 실리는가.

    머리말이 "인증 정보가 이미 들어 있어" 라고 말하므로, 토큰이 빠지면 그 문장이 거짓이 되고
    받는 AI 는 401 만 보고 멈춘다 — 신뢰를 얻으려던 지시문이 다시 신뢰를 잃는 경로다.
    접두어(`Authorization: Bearer`)만 검사하면 값이 플레이스홀더여도 통과한다(뮤테이션 X7).
    """
    with _loaded() as mod:
        text = _handoff(mod, token="mat_SENTINEL9")
    # ⚠ `"Authorization: Bearer mat_X" in text` 로는 부족하다 — 인증 섹션을 플레이스홀더로
    #   바꿔도 A 섹션의 `--header "Authorization: Bearer mat_X"` 가 대신 매칭시킨다(실측).
    #   **인증 줄 자체**에 앵커한다(strip 후 그 접두로 시작하는 줄만 본다).
    auth = [l.strip() for l in text.split("\n") if l.strip().startswith("Authorization: Bearer")]
    assert auth, "인증 줄이 없다"
    assert auth[0] == "Authorization: Bearer mat_SENTINEL9", (
        f"인증 줄에 실제 토큰이 없다: {auth[0]!r}")
    # 인증 줄 · MCP 등록 명령 · 설정 JSON · 러너 명령들 — 어느 하나만 비어도 그 경로가 죽는다.
    assert text.count("mat_SENTINEL9") >= 4, (
        f"토큰이 일부 경로에만 실렸다({text.count('mat_SENTINEL9')}회) — "
        "그 경로를 고른 AI 는 자격증명 없이 시작한다")


# ── 러너 안내: 단계를 나눈다 ─────────────────────────────────────────────────


def test_handoff_stages_the_runner_before_daemonizing():
    """`--check` → `--once` → 상주 순서다. 첫 명령이 데몬이면 '검증 없는 상주' 로 읽힌다."""
    with _loaded() as mod:
        text = _handoff(mod)
    assert text.index("--check") < text.index("--once") < text.index("nohup"), (
        "확인 단계가 상주 뒤에 온다 — 받는 쪽은 앞의 것을 먼저 실행한다")
    assert "sha256sum bridge_agent.py" in text
    assert text.index("sha256sum bridge_agent.py") < text.index("--check"), (
        "무결성 확인이 실행보다 뒤에 있다")
    # 되돌릴 방법을 함께 준다 — 끝낼 수 없는 상주는 그 자체가 거절 사유였다.
    # ⚠ `"kill" in text` 로는 부족하다: 안내 줄을 통째로 지워도 아래쪽 설명문의 "kill 한 번으로"
    #    와 `> bridge.log` 가 남아 통과한다(뮤테이션 X8 — 계약이 아무것도 안 잠그고 있었다).
    assert "종료: kill" in text, "종료 방법 안내가 없다"
    assert "로그: bridge.log" in text, "관측(로그) 안내가 없다"


def test_handoff_points_at_the_runner_source_and_its_contract():
    """소스를 읽어 보라고 **권한다** — 검증 가능한 주장만이 신뢰를 만든다."""
    with _loaded() as mod:
        text = _handoff(mod)
    assert "보안 계약" in text, "소스 어디를 봐야 하는지 말하지 않는다"
    assert "실행 가능한 코드나 셸 명령은 받지 않는다" in text, "무엇을 받지 않는지가 없다"
    # 내려받기 URL 이 서빙 경로와 **정확히** 같아야 한다. 부분문자열만 보면 캐시버스터
    # (`...bridge_agent.py?v=2`)가 붙어도 통과하는데, 그러면 받는 파일과 서버가 계산한 체크섬이
    # 갈릴 수 있다 — 이 파일이 막겠다고 선언한 바로 그 오경보다(뮤테이션 X15).
    dl = [l for l in text.split("\n") if l.strip().startswith("curl") and "bridge_agent.py" in l]
    assert dl and dl[0].rstrip().endswith("/static/agent/bridge_agent.py"), (
        f"내려받기 URL 이 서빙 경로와 다르다(쿼리·접미 포함): {dl}")


def test_handoff_discloses_the_operator_system_prompt_channel():
    """운영자 시스템 지침이 프롬프트 맨 앞에 실린다는 사실을 **숨기지 않는다**.

    종전 문안은 "서버는 명령도 코드도 보내지 않는다 — 오가는 것은 질문 텍스트와 답변이다" 였다.
    거짓이다: `claim_request` 는 운영자가 콘솔에서 정한 5단계 지침을 함께 주고, 러너는 그것을
    "이걸 시스템 프롬프트로 삼아 답하라" 로 **맨 앞**에 놓는다. 질문·대화이력은
    ⟦UNTRUSTED-DATA⟧ 로 구획되는데 이 필드만 구획 없이 권위가 승격된다.

    우리가 알려 준 확인 경로(`compose_prompt` 를 읽어라)를 따르면 30초 안에 드러나고, 그 순간
    **참인 주장들까지 함께 의심받는다.** 한 군데의 과장이 문서 전체의 신뢰를 깎는다.
    """
    with _loaded() as mod:
        text = _handoff(mod)
    assert "운영자가 설정한 시스템 지침" in text, "운영자 지침 채널을 고지하지 않는다"
    assert "답변 방식에 영향을 줄 수 있다" in text, "그 채널의 의미를 말하지 않는다"
    assert "system_prompt" in text, "무엇을 보면 확인되는지 알려주지 않는다"
    # 옛 단정이 되살아나면 다시 거절당한다.
    assert "오가는 것은 질문 텍스트와 답변이다" not in text, "거짓이던 옛 단정이 돌아왔다"


def test_handoff_is_honest_about_where_the_token_shows_up():
    """토큰이 프롬프트·argv 에도 실린다는 사실을 밝히고, 회피 수단을 준다.

    `save_conf` 가 토큰을 저장하지 않는 것은 참이지만, 그것을 "토큰을 디스크에 쓰지 않는다" 는
    **일반 주장**으로 확대하면 오도가 된다 — `compose_prompt` 가 프롬프트 본문에 토큰을 넣고
    그 전문이 argv 로 CLI 에 넘어가므로 `/proc/<pid>/cmdline` 과 세션 기록에 남는다.
    """
    with _loaded() as mod:
        text = _handoff(mod)
    assert "프롬프트 안에도" in text, "토큰의 실제 노출면을 말하지 않는다"
    assert "BRIDGE_TOKEN" in text, "회피 수단(환경변수)을 알려주지 않는다 — 코드에 이미 있다"


def test_handoff_gives_a_ca_path_that_works_without_the_ca(monkeypatch, tmp_path):
    """CA 를 **평문 경로로도** 준다 — https 로만 주면 부트스트랩 데드락이다.

    엣지 인증서를 서명한 것이 바로 그 CA 라, CA 가 없는 클라이언트의 https 요청은 self-signed
    로 실패한다. 그런데 같은 지시문이 "검증을 끄지 마" 라고 못박으므로 우회로도 없다 —
    막히거나, 규칙을 어기거나, 사람에게 되묻는 셋 중 하나가 된다. 엣지는 이 목적으로
    `/trust/*` 를 평문으로도 서빙한다(Caddyfile `http://` 블록 · HSTS 를 뺀 이유도 그것).
    """
    with _loaded() as mod:
        text = _handoff(mod, endpoint="https://mysql-ai.company.local/api/ai/mcp")
    assert "http://mysql-ai.company.local/trust/rootCA.crt" in text, (
        "CA 를 https 로만 준다 — 그 CA 가 없으면 그 요청 자체가 실패한다")
    # 평문을 쓰는 이유와, 그 위험을 무엇이 덮는지 함께 말한다(맹목적 평문 안내는 그 자체가 신호다).
    assert "이 한 번만 평문" in text and "지문 대조" in text, "평문을 쓰는 근거를 말하지 않는다"
    assert text.index("http://mysql-ai.company.local/trust/rootCA.crt") < \
        text.index("https://mysql-ai.company.local/trust/rootCA.crt"), (
        "https 를 먼저 제시한다 — 받는 쪽은 앞의 것을 먼저 시도한다")


def test_handoff_disambiguates_the_trust_page_link():
    """`/trust/` 는 **사람용 전역 설치** 안내다. 그 사실을 말하지 않으면 자기모순이 된다.

    "전역 설치를 요구하지 않는다" 고 말한 뒤 대조 근거로 그 링크를 주면, 검증하러 간 AI 는
    certutil·`security add-trusted-cert` 화면을 만난다 — 없애려던 거절 사유("TLS 를 가로채도록
    전역 허용")를 링크 한 번으로 재확인시켜 준다.
    """
    with _loaded() as mod:
        text = _handoff(mod)
    assert "사람이 브라우저로 쓰는 **전역 설치** 안내다" in text, "링크의 성격을 밝히지 않는다"
    assert "지문만" in text, "그 페이지에서 무엇만 보면 되는지 말하지 않는다"


def test_handoff_warns_that_a_rolling_deploy_can_skew_the_checksum():
    """배포 교대 중 체크섬 불일치를 **침해로 오인하지 않게** 한다.

    web-a/web-b 가 한 번에 하나씩 교체되는 동안, 브라우저(지시문 발급)와 AI 머신(파일 다운로드)은
    서로 다른 replica 에 닿을 수 있다 — 둘은 다른 클라이언트라 sticky 가 묶어 주지 않는다.
    고지가 없으면 정상 배포가 "멈추고 알려라" 를 발동시킨다.
    """
    with _loaded() as mod:
        text = _handoff(mod)
    assert "배포 교대 중일 수 있다" in text, "롤링 배포 중 스큐를 고지하지 않는다"
    assert "다시 받아" in text, "재확인 방법을 주지 않는다"


def test_handoff_explains_the_runner_without_sounding_like_evasion():
    """'턴 예산' 근거를 유지하되 **무엇을 옮기는지**를 밝힌다.

    종전 문구("러너는 예산이 없는 일반 프로세스라 그 일이 없다")는 감시 회피 설계로 읽혔다.
    사실관계는 그대로지만, 옮기는 것이 대기뿐이고 추론은 여전히 상대 계정·정책 아래 있다는
    것을 말하지 않으면 같은 오해가 반복된다.
    """
    with _loaded() as mod:
        text = _handoff(mod)
    assert "턴 예산" in text, "왜 러너인지 근거가 사라졌다(다음 사람이 되돌린다)"
    assert "옮기는 것은 **대기**뿐" in text, "무엇을 옮기는지 말하지 않는다"
    assert "우회하려는 장치가 아니" in text, "회피 오해를 푸는 문장이 없다"


# ── TLS·토큰: 성질을 밝힌다 ──────────────────────────────────────────────────


def test_handoff_scopes_the_private_ca_to_the_process():
    """사설 CA 신뢰가 **프로세스 한정**임을 말한다 — 전역 설치 요구로 읽히면 거절이 맞다."""
    with _loaded() as mod:
        text = _handoff(mod)
    assert "그 프로세스에만" in text
    assert "신뢰 저장소" in text, "시스템 저장소를 건드리지 않는다는 사실이 없다"
    # 검증을 끄라는 우회는 여전히 금지다(이 계약이 풀리면 지문은 장식이 된다).
    assert "NODE_TLS_REJECT_UNAUTHORIZED=0" in text and "검증을 끄지는 마" in text


def test_handoff_states_token_lifetime_and_revocation():
    """토큰의 수명·폐기 경로를 밝힌다 — 모르면 붙여넣기 토큰은 영구 비밀처럼 보인다."""
    with _loaded() as mod:
        text = _handoff(mod)
    assert "로그인 세션에 묶여 있다" in text
    assert "로그아웃하면 즉시 무효" in text
    assert "12시간" in text, "수명 상한이 없으면 장기 크리덴셜로 읽힌다"


# ── 러너 소스: 첫 화면에서 확인된다 ──────────────────────────────────────────


@pytest.mark.parametrize("path", [CANON_RUNNER, SERVED_RUNNER])
def test_runner_source_opens_with_a_security_contract(path):
    """소스를 연 사람이 **첫 화면에서** 무엇을 실행하는지 확인할 수 있어야 한다."""
    head = path.read_text(encoding="utf-8")[:4000]
    assert "## 보안 계약" in head, "보안 계약이 첫 화면에 없다 — 읽으라고 권해도 못 찾는다"
    for claim in ("서버에서 받는 것", "실행하는 것", "설치물 없음", "관측·종료"):
        assert claim in head, f"보안 계약에 '{claim}' 항목이 없다"
    # 확인 방법을 함께 준다 — 주장만 늘리는 것은 그 자체로 사회공학의 형태다.
    assert "grep -nE" in head, "직접 확인할 명령을 주지 않는다"


@pytest.mark.parametrize("path", [CANON_RUNNER, SERVED_RUNNER])
def test_runner_contract_is_accurate_about_what_it_receives_and_leaves(path):
    """계약 표가 **사실과 일치**한다 — 검증 가능한 문서에서 과장은 치명적이다.

    초판은 세 군데가 틀렸고 셋 다 grep 한 번에 깨졌다:
      · "명령도 코드도 받지 않는다" ← `system_prompt` 를 받아 프롬프트 맨 앞에 놓는다
      · "토큰을 디스크에 쓰지 않는다" ← `save_conf` 한정으론 참이나, 프롬프트·argv 로 나간다
      · "나가는 곳 한 곳 … 유일한 자리" ← 종전엔 `BRIDGE_OLLAMA_URL` 이 두 번째 URL 생성
        지점이었다. 2026-09-01 로컬 LLM 어댑터 제거로 **실제로 한 곳**이 됐고, 그러면
        문서가 그렇게 적어야 한다(거짓이 아니라 참이 된 문장을 계속 부정하지 않는다).
      · "끝나면 아무것도 남지 않는다" ← 같은 표가 `config.json` 을 남긴다고 적고 있다(자기모순)
    """
    head = path.read_text(encoding="utf-8")[:6000]
    assert "운영자 시스템 지침" in head, "받는 것 목록이 운영자 지침을 빠뜨렸다"
    assert "실행 가능한 코드나 셸 명령은 받지 않는다" in head, "무엇을 안 받는지가 부정확하다"
    assert "구획되지 않는다" in head, "그 지침이 구획 없이 온다는 사실을 말하지 않는다"
    # 2026-09-01: 로컬 LLM HTTP 어댑터를 제거해 URL 생성 지점이 **하나**가 됐다.
    # 그러면 문서의 「한 곳」이 참이 되므로, 두 번째 지점을 요구하던 단언을 뒤집는다 —
    # 되살아나면 문서가 다시 거짓이 되므로 그것을 잡는다.
    assert "BRIDGE_OLLAMA_URL" not in head, (
        "제거한 로컬 LLM URL 이 되살아났다 — 「나가는 곳 한 곳」이 다시 거짓이 된다")
    assert "하나뿐이다" in head or "**하나뿐**" in head, (
        "URL 생성 지점이 하나가 됐는데 문서가 그렇게 말하지 않는다")
    # 2026-09-01(TASK-20260901T140000): 토큰이 프롬프트 본문 → **자식 환경변수**로 옮겼다.
    # 계약은 그대로다 — 「노출면을 정직하게 적는다」. 노출면이 바뀌었으니 문장도 바뀌어야
    # 하고, 이 검사는 *새 사실* 이 적혀 있는지를 본다(옛 문장이 남아 있으면 그것이 거짓이다).
    assert "프롬프트 안에도 들어간다" not in head, "옛 노출면 서술이 남아 사실과 어긋난다"
    assert "환경변수로 들어간다" in head, "토큰의 실제 노출면을 말하지 않는다"
    assert "/proc/<pid>/environ" in head, "환경변수 경로의 잔여 노출을 감췄다"
    assert "0 은 아니다" in head, "노출이 사라졌다고 과장했다"
    assert "BRIDGE_TOKEN" in head, "어느 변수인지 알려주지 않는다"
    # 자기모순 금지: 같은 표 안에서 "아무것도 안 남는다" 와 "config.json 을 남긴다" 가 공존했다.
    assert "끝나면 아무것도 남지 않는다" not in head, "같은 표의 다른 행과 모순되는 문장이다"


@pytest.mark.parametrize("path", [CANON_RUNNER, SERVED_RUNNER])
def test_runner_contract_states_the_residual_trust_boundary(path):
    """남는 위험을 **정직하게** 적는다.

    서버가 보낸 질문 텍스트는 상대 AI 의 프롬프트가 된다. 그 AI 가 도구를 쓸 수 있다면 유도의
    여지는 남고, 이 파일이 없앨 수 있는 위험이 아니다. "전부 안전하다" 고 말하는 순간 이 문서
    전체가 신뢰를 잃는다 — 한 군데의 과장이 나머지 사실까지 의심하게 만든다.
    """
    # 6000 자: P0-Z4 가 헤더 앞부분에 "기동 시 1회 질의"(새 outbound + 계정 토큰 소모)를
    # 더하면서 이 절이 4118 자 위치로 밀렸다. 범위를 넓히되 **헤더 안**은 유지한다 —
    # 계약의 요지는 "파일을 열면 곧 보인다" 이지 특정 바이트 수가 아니다.
    head = path.read_text(encoding="utf-8")[:6000]
    assert "남는 신뢰 경계" in head, "잔여 위험을 감췄다"
    assert "권한 설정" in head and "낮추라고 요구하지" in head, (
        "상대 런타임의 방어선을 낮추지 않는다는 약속이 없다")


def test_runner_refuses_plaintext_to_anything_but_real_loopback():
    """토큰을 평문으로 내보내는 주소를 **호스트 기준**으로 막는다.

    접두 비교(`startswith("http://127.0.0.1")`)는 userinfo 와 서브도메인을 통과시킨다 —
    `http://127.0.0.1@evil.example` 의 실제 접속 대상은 `evil.example` 이고, urllib 은 거기로
    붙는다. 이 검사는 이번에 "보안 계약" 의 검증 가능한 항목으로 승격됐으므로, 우회 가능성은
    곧 계약 위반이다.
    """
    spec = importlib.util.spec_from_file_location("_bridge_agent_transport", CANON_RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for ok in ("https://mysql-ai.company.local", "https://112.185.196.20",
               "http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"):
        assert mod._transport_is_safe(ok), f"정상 주소를 막는다: {ok}"
    for bad in ("http://127.0.0.1@evil.example", "http://127.0.0.1.evil.example",
                "http://evil.example", "http://localhost.evil.example",
                "ftp://mysql-ai.company.local", "", "https://"):
        assert not mod._transport_is_safe(bad), f"토큰을 평문으로 내보낼 주소를 허용한다: {bad}"


def test_ca_path_env_override_uses_a_dedicated_name():
    """CA 경로 override 는 **전용 이름**을 쓴다.

    처음엔 `EXT_TOOL_CA_BUNDLE` 을 재사용했는데, 그것은 "우리가 외부에 붙을 때 검증에 쓸 CA"
    라는 정반대 의미의 이름이고 사용자 가이드가 값을 권하기까지 한다. 누군가 그 값을 web env 에
    넣는 순간 "서빙 파일 우선" 규칙이 조용히 무효가 되고(여러 장짜리 번들이면 지문이 통째로
    사라진다), 어떤 테스트도 깨지지 않는다.
    """
    body = _code_only(_func(OAUTH_AS, "_ca_bundle_path"))
    assert "EXT_TOOL_CA_BUNDLE" not in body, (
        "의미가 다른 기존 env 이름을 재사용한다 — 값이 공유되면 규칙이 조용히 뒤집힌다")
    assert "BRIDGE_HANDOFF_CA_PATH" in body, "전용 override 이름이 없다"

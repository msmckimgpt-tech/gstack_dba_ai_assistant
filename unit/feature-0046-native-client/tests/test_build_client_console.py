"""`build_client.py` 가 **레거시 콘솔 코드페이지에서 죽지 않는지** 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

한국어 Windows 에서 빌드를 돌렸더니 `DQAConnect.exe` 9,174,570 B 가 **정상 생성된 뒤**
마지막 안내 `print("⚠ 서명하지 않았습니다 …")` 가 `UnicodeEncodeError: 'cp949' codec` 로
죽었다. 종료 코드는 1. 산출물은 멀쩡한데 사람은 「빌드 실패」로, CI 는 실패로 읽는다.

이 스크립트는 `os.name != "nt"` 를 막아 **Windows 를 강제**한다. 그리고 비영어권 Windows 의
기본 콘솔은 UTF-8 이 아니다(한국어 = CP949). 즉 이 결함은 예외 상황이 아니라 **스크립트가
지정한 바로 그 환경의 기본값**에서 난다.

## 이 파일이 지키는 것 — 그리고 왜 소스 검사가 아닌가

「금지 문자를 안 쓴다」로는 못 지킨다. CP949 에 없는 것은 `⚠` 뿐이 아니다 — `—`(U+2014
EM DASH)도 없다(CP949 가 가진 것은 `―` U+2015). 이 저장소의 한국어 산문은 `—` 를 도처에
쓰므로 문자 목록 관리는 다음 문장에서 다시 깨진다. 그래서 **실제 CP949 스트림을 만들어
출력을 구동**한다. 소스에 무엇이 적혔는지가 아니라 그 환경에서 죽는지를 본다.

리눅스 CI 에서도 돈다 — `cp949` 코덱은 플랫폼과 무관하게 파이썬에 들어 있다.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import sys
from pathlib import Path

import pytest

_SCRIPT = (Path(__file__).resolve().parents[1]
           / "src" / "scripts" / "build_client.py")


def _load():
    """빌드 스크립트를 모듈로 적재한다(임포트 부작용 없음 — `main()` 호출 전까지)."""
    spec = importlib.util.spec_from_file_location("_build_client_uut", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _cp949_stream() -> io.TextIOWrapper:
    """한국어 Windows 콘솔과 **같은 인코딩·같은 에러 핸들러**의 실제 텍스트 스트림."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp949", errors="strict")


# ── 1. 대조군: 고치지 않으면 정말 죽는가 (테스트가 vacuous 하지 않다는 증명) ──────────

def test_cp949_stream_really_dies_without_the_fix():
    """`_make_stdio_lossy()` 를 **부르지 않으면** 같은 출력이 예외를 낸다.

    이 단정이 없으면 아래 테스트들은 「원래 안 죽는 것」을 확인하는 vacuous pass 가 된다.
    """
    s = _cp949_stream()
    with pytest.raises(UnicodeEncodeError):
        s.write("⚠ 서명하지 않았습니다")
        s.flush()


def test_em_dash_also_dies__not_just_the_warning_sign():
    """`—` 도 CP949 에 없다 — 문자 골라내기로 고치면 안 되는 이유의 실측."""
    s = _cp949_stream()
    with pytest.raises(UnicodeEncodeError):
        s.write("빌드 — 완료")
        s.flush()


# ── 2. 수정 후 동작 ────────────────────────────────────────────────────────────────

def test_after_fix_stdout_survives_unencodable_output(monkeypatch):
    mod = _load()
    out = _cp949_stream()
    monkeypatch.setattr(sys, "stdout", out)
    mod._make_stdio_lossy()
    print("⚠ 서명하지 않았습니다 — 첫 실행에서 SmartScreen 경고가 뜹니다")
    out.flush()


def test_after_fix_stderr_also_survives_unencodable_output(monkeypatch):
    """**stderr 도** 고쳐야 한다 — 두 스트림은 따로 설정된다.

    ⚠ 종전 판은 stderr 에 `"ERROR: 이 빌드는 Windows 에서 …"` 만 써서 이 축을 못 봤다.
    그 문장은 전부 한글이라 CP949 로 **표현된다** — stderr 를 고치지 않아도 통과했다
    (뮤턴트 M5 생존으로 드러남). 오류 경로는 `f"ERROR: 산출물이 없습니다: {exe}"` 처럼
    **경로를 끼워 넣으므로** 어떤 문자가 올지 스크립트가 정하지 못한다. 표현 불가 문자를
    실제로 흘려서 단정한다.
    """
    mod = _load()
    err = _cp949_stream()
    monkeypatch.setattr(sys, "stderr", err)
    mod._make_stdio_lossy()
    print("ERROR: 산출물이 없습니다 — C:\\사용자\\⚠\\DQAConnect.exe", file=sys.stderr)
    err.flush()


def test_korean_is_preserved__only_unencodable_chars_degrade(monkeypatch):
    """인코딩을 UTF-8 로 바꾸지 않았음을 **출력 바이트로** 확인한다.

    encoding 까지 바꾸면 CP949 콘솔에 UTF-8 바이트가 나가 **한글이 통째로 깨진다**.
    읽을 수 없는 로그는 죽는 로그보다 낫지 않다.
    """
    mod = _load()
    buf = io.BytesIO()
    out = io.TextIOWrapper(buf, encoding="cp949", errors="strict")
    monkeypatch.setattr(sys, "stdout", out)

    mod._make_stdio_lossy()
    print("서명하지 않았습니다 ⚠ 끝", end="")
    out.flush()

    decoded = buf.getvalue().decode("cp949")
    assert "서명하지 않았습니다" in decoded, "한글이 보존되어야 한다"
    assert "끝" in decoded, "표현 불가 문자 뒤의 한글도 살아야 한다"
    assert "⚠" not in decoded and "?" in decoded, "표현 못 하는 문자만 대체된다"


def test_encoding_attribute_is_not_switched_to_utf8(monkeypatch):
    mod = _load()
    out = _cp949_stream()
    monkeypatch.setattr(sys, "stdout", out)
    mod._make_stdio_lossy()
    assert sys.stdout.encoding.lower().replace("-", "") in ("cp949", "ms949", "uhc"), \
        f"encoding 을 바꾸면 안 된다 (현재: {sys.stdout.encoding})"
    assert sys.stdout.errors == "replace"


# ── 3. 견고성: 재설정할 수 없는 스트림 ─────────────────────────────────────────────

def test_streams_without_reconfigure_do_not_crash(monkeypatch):
    """`--windowed`·리다이렉트 환경에서 스트림이 대체돼 있어도 죽지 않아야 한다."""
    class _Bare:  # `reconfigure` 가 없는 스트림 (예: 일부 테스트 러너의 캡처 객체)
        def write(self, _s): return 0
        def flush(self): pass

    mod = _load()
    monkeypatch.setattr(sys, "stdout", _Bare())
    monkeypatch.setattr(sys, "stderr", None)
    mod._make_stdio_lossy()  # 예외 없이 통과해야 한다


def test_reconfigure_raising_is_swallowed(monkeypatch):
    class _Hostile:
        errors = "strict"
        def reconfigure(self, **_kw): raise ValueError("이미 닫힌 스트림")

    mod = _load()
    monkeypatch.setattr(sys, "stdout", _Hostile())
    monkeypatch.setattr(sys, "stderr", _Hostile())
    mod._make_stdio_lossy()


# ── 4. 배선: 순서가 틀리면 고쳐도 안 고쳐진다 ──────────────────────────────────────

def test_fix_runs_before_anything_that_prints():
    """`main()` 의 **첫 문장**이어야 한다.

    argparse 의 `--help`·에러 출력은 `parse_args()` 안에서 바로 나간다. 재설정이 그
    뒤에 있으면 그 경로는 여전히 죽는다 — 「고쳤는데 어떤 경로는 그대로」가 된다.
    """
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    first = main.body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call), \
        "main() 의 첫 문장이 호출이 아니다"
    assert getattr(first.value.func, "id", None) == "_make_stdio_lossy", \
        "_make_stdio_lossy() 가 main() 첫 문장이 아니다 — 앞선 출력 경로가 남는다"


def test_module_is_importable_without_side_effects():
    """`if __name__ == '__main__'` 밖에서 `main()` 을 부르지 않는다(적재만으로 빌드 금지)."""
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        assert not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", None) == "main"), \
            "모듈 최상위에서 main() 을 부르면 임포트만으로 PyInstaller 가 돈다"

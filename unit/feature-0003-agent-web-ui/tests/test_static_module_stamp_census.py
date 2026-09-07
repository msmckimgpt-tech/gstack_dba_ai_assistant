"""정적 ES module 의 **모든** import 는 스탬프 토큰(`?v=`)을 달고 있어야 한다.

# 왜 이 계약이 필요한가 (라이브 실측 2026-09-07)

`inject_asset_stamp.py` 는 소스의 `?v=dev` 토큰을 content-hash 로 **치환**한다. 치환기이지
삽입기가 아니다 — 토큰이 없는 참조는 **대상 자체가 아니다.** 그런데 캐시 정책은
「`?v=` 없음 = 조건부 GET(Cache-Control 미설정)」이라, 스탬프 밖으로 빠진 모듈에는
브라우저 휴리스틱 캐시가 걸린다(Last-Modified 기준 수 시간).

그래서 **배포는 성공하는데 페이지는 구 모듈을 쓴다.** 실측 2026-09-07: `client-bridge.js`
하나만 `?v=dev` 가 없었고(전체 참조 중 유일), 자동 연결 기능을 배포·재적재한 뒤에도 앱 창의
모듈에는 신규 export 가 존재하지 않았다(`import()` 로 모듈 인스턴스를 직접 확인). 서버가
서빙하는 파일은 새것이었으므로 «배포됨» 만 보는 검증은 이 결함을 통과시킨다.

`inject_asset_stamp.py` 의 docstring 은 이 간극을 **이미 알고 있었지만**(「하위 모듈이
무버전으로 import 하면 … 캐시버스터가 전파되지 않는 gap」) 그것을 지키는 것이 없었다.
아는 것과 지켜지는 것은 다르다 — 여기서 지킨다.
"""
from __future__ import annotations

import re
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "src" / "static"

#: `from "…"` · `import "…"` · `import("…")` 의 specifier. 따옴표 두 종류 모두.
_SPEC_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*)(['"])(?P<spec>[^'"]+)\1"""
)

#: 상대 참조만 본다 — 절대 URL·bare specifier 는 이 트리의 파일이 아니다.
def _is_local(spec: str) -> bool:
    return spec.startswith("./") or spec.startswith("../")


def _js_files() -> list[Path]:
    return [p for p in sorted(_STATIC.rglob("*.js")) if "vendor" not in p.parts]


def _specs(text: str) -> list[str]:
    return [m.group("spec") for m in _SPEC_RE.finditer(text)]


def test_the_scanner_sees_an_unstamped_import() -> None:
    """추출이 깨지면 이 파일의 다른 단정은 전부 «찾은 것이 없어서» 통과한다.

    양성 대조군을 먼저 세운다 — 스탬프 없는 참조를 실제로 집어내는지.
    """
    sample = (
        'import { a } from "./stamped.js?v=dev";\n'
        'import { b } from "./bare.js";\n'
        'const m = await import("../deep/other.js?v=dev");\n'
        'import "https://example.invalid/x.js";\n'
    )
    found = _specs(sample)
    assert "./bare.js" in found, found
    assert [s for s in found if _is_local(s) and "?v=" not in s] == ["./bare.js"], found


def test_every_local_module_import_carries_a_stamp() -> None:
    offenders: list[str] = []
    scanned = 0
    for path in _js_files():
        text = path.read_text(encoding="utf-8")
        for spec in _specs(text):
            if not _is_local(spec):
                continue
            scanned += 1
            if "?v=" not in spec:
                offenders.append(f"{path.relative_to(_STATIC)} → {spec}")
    # 표본이 비면 「전건 통과」는 아무 뜻이 없다 — 실측 시점 참조 수는 20 이상이었다.
    assert scanned >= 15, f"참조를 거의 못 찾았다({scanned}) — 추출이 깨졌을 가능성"
    assert not offenders, (
        "스탬프 없는 모듈 참조 — 빌드가 치환하지 못해 브라우저가 구 모듈을 쓴다:\n  "
        + "\n  ".join(offenders)
    )

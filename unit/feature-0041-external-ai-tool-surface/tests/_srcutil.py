"""소스 문자열 검사용 공용 헬퍼.

## 왜 있는가

"X 가 소스에 없어야 한다" 를 파일 전체 부분문자열로 검사하면 **주석·docstring 에 적힌 X** 가
통과시킨다. 이 feature 에서만 네 번 걸렸다:

| 검사 | 통과시킨 것 |
|---|---|
| PKCE `plain` 을 광고하지 않는다 | `# S256 전용 — plain 을 광고하면…` 주석 |
| `mcp` 의존이 requirements 에 있다 | `# ext-tool-mcp 서비스가…` 주석 |
| 콘솔 토큰이 15분 상수를 안 쓴다 | `수명은 ACCESS_TTL_SEC(15분)가 아니라…` docstring |
| 라우터가 SQL 가드를 자체 구현하지 않는다 | `# sqlglot AST 가드… 그대로 쓴다` 주석 |

매번 그 자리에서 필터를 손으로 짜다 보니 반복됐다. **부재를 단정하는 검사는 이걸 통과시킨다.**
"""
from __future__ import annotations


def code_only(text: str) -> str:
    """주석(`#`)과 삼중따옴표 docstring 을 걷어낸 실행부만 남긴다.

    완전한 파서가 아니다 — 부재 단정 검사의 오탐을 없애는 용도이며, 문자열 리터럴 안의 `#`
    처럼 드문 경우는 보수적으로 남긴다(남겨서 생기는 오탐이 지워서 생기는 미탐보다 낫다).
    """
    lines = [ln for ln in str(text or "").splitlines() if not ln.strip().startswith("#")]
    out: list[str] = []
    in_doc = False
    for ln in lines:
        marks = ln.count('"""') + ln.count("'''")
        if in_doc:
            if marks:
                in_doc = False
            continue
        if marks == 1:
            in_doc = True
            continue
        if marks >= 2:      # 한 줄짜리 docstring
            continue
        # 줄 끝 주석 제거 (문자열 안의 # 는 보수적으로 보존)
        if "#" in ln and ln.count('"') % 2 == 0 and ln.count("'") % 2 == 0:
            ln = ln.split("#", 1)[0]
        out.append(ln)
    return "\n".join(out)

"""unified diff 적용기 — 첨부 갱신의 **패치 전달** 경로 (FR-attach-delivery-truncated-by-output-cap).

왜 필요한가: 첨부 한 건을 갱신하려고 파일 **전문**을 재생성하면 출력 토큰이 파일 크기에 비례한다.
관측 사례(대화 `…1d8ed346`)는 6개 파일 전문을 한 응답에 담다가 출력 상한(100,000 토큰)에서 잘려
1개만 전달됐다. 실제 변경은 `USE Log_v2`→`log_v2` 같은 몇 줄이었다 — 8.5KB 를 재생성할 이유가 없다.

**설계 원칙: fail-closed.** 애매하면 적용하지 않는다. 잘못 적용된 패치는 조용히 틀린 파일을 만들고,
그건 전달 실패보다 나쁘다(CODE_REVIEW §1). 실패는 **모델이 고칠 수 있는 사유**와 함께 반환해
도구가 그대로 되돌려준다(L2 자기교정) — 모델은 전문(`content`) 경로로 폴백할 수 있다.

**§18.8 적대 패널(security + backend/qa)이 초판에서 실증한 3가지 무음 오적용** — 이 파일의 현재
구조는 그 셋을 구조적으로 불가능하게 만드는 것이 목적이다:
  1. `@@ -N,0 +M @@`(문맥 없는 삽입)이 **한 줄 앞**에 삽입됐다. unified diff 에서 `-N,0` 은
     "old 의 N번째 줄 **뒤**에 삽입" 인데 `N-1` 을 인덱스로 썼다. → 문맥 없는 hunk 자체를 거부한다
     (아래 §2). 검증할 문맥이 없는 삽입은 위치를 확인할 방법이 원리적으로 없다.
  2. 머리말의 선언 길이(`-l,c` / `+l,c`)를 **파싱만 하고 쓰지 않았다**. 잘린 패치(본문이 선언보다
     짧음)가 그대로 부분 적용되고 "성공" 을 반환했다 — 이 cycle 이 없애려는 바로 그 실패의 재현.
     → 선언 길이를 **본문 경계의 권위**로 삼는다(아래 §1).
  3. 마지막 hunk 뒤의 산문(모델이 덧붙인 설명)이 hunk 본문으로 흡수돼 파일에 기록됐다.
     → §1 이 같은 방식으로 막는다(선언 길이만큼만 읽는다).

허용 형식: 표준 unified diff 의 부분집합.
  - `--- a/x`, `+++ b/x`, `diff --git …`, `index …` 머리말은 무시한다(있어도 없어도 됨).
  - hunk 는 `@@ -old_start[,old_len] +new_start[,new_len] @@ [heading]`.
  - hunk 본문 줄: ` ` 문맥 / `-` 삭제 / `+` 추가 / `\\` (No newline at end of file — 무시).
  - **문맥 줄이 0인 hunk 는 거부**한다(§2).
"""
from __future__ import annotations

import re

__all__ = ["apply_unified_diff", "PatchError"]

_HUNK_RE = re.compile(r"^@@+\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")
# hunk 를 원 위치에서 못 찾았을 때 탐색할 최대 이동 범위(줄). 넘어가면 fail-closed.
_SEARCH_WINDOW = 400


class PatchError(ValueError):
    """패치를 안전하게 적용할 수 없음 — 사유는 모델이 읽고 고칠 수 있게 구체적으로."""


def _split_keep_eol(text: str) -> tuple[list[str], str]:
    """(줄 목록, 지배적 줄바꿈). 원본의 줄바꿈 종류를 **보존**하기 위해 함께 돌려준다.

    §18.8 [P2]: 초판은 CRLF 를 LF 로 통째 정규화해, 한 줄만 고쳐도 파일 전체가 변경된 것처럼
    보였다(diff 뷰 전면 빨강). 사용자에게 알리지 않는 전체 변형은 무음 절단과 같은 계열이다.
    """
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    eol = "\r\n" if crlf > lf else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), eol


def _parse_hunks(patch: str) -> list[dict]:
    """머리말의 **선언 길이만큼만** 본문을 읽는다(§1).

    선언이 없는 형식(`@@ -1 +1 @@`)은 unified diff 기본값 1 로 해석한다. 선언 길이에 도달하기 전에
    다음 hunk 머리말이나 입력 끝을 만나면 **잘린 패치**이므로 거부한다 — 그 상태를 부분 적용하면
    "성공했다고 보고된 반쯤 고쳐진 파일" 이 나온다.
    """
    lines, _ = _split_keep_eol(patch)
    hunks: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _HUNK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        old_len = int(m.group(2)) if m.group(2) is not None else 1
        new_len = int(m.group(4)) if m.group(4) is not None else 1
        hunk = {
            "old_start": int(m.group(1)),
            "old_len": old_len,
            "new_len": new_len,
            "header": lines[i].strip(),
            "old": [],
            "new": [],
        }
        i += 1
        seen_old = seen_new = 0
        while i < n and (seen_old < old_len or seen_new < new_len):
            raw = lines[i]
            if _HUNK_RE.match(raw):
                break  # 다음 hunk 시작 — 선언 길이를 못 채웠다
            i += 1
            if raw.startswith("\\"):  # "\ No newline at end of file"
                continue
            tag, rest = (raw[0], raw[1:]) if raw else (" ", "")
            if tag == " ":
                hunk["old"].append(rest)
                hunk["new"].append(rest)
                seen_old += 1
                seen_new += 1
            elif tag == "-":
                hunk["old"].append(rest)
                seen_old += 1
            elif tag == "+":
                hunk["new"].append(rest)
                seen_new += 1
            else:
                raise PatchError(
                    f"hunk `{hunk['header']}` 본문에 알 수 없는 접두 문자 {tag!r} 가 있습니다: "
                    f"{raw[:60]!r}. 각 줄은 ' '(문맥) · '-'(삭제) · '+'(추가) 중 하나로 시작해야 합니다."
                )
        if seen_old != old_len or seen_new != new_len:
            raise PatchError(
                f"hunk `{hunk['header']}` 의 본문이 머리말이 선언한 크기와 다릅니다"
                f"(선언 -{old_len}/+{new_len}, 실제 -{seen_old}/+{seen_new}). "
                "패치가 중간에서 잘렸거나 머리말의 줄 수가 틀렸습니다. **적용하지 않았습니다** — "
                "전체 hunk 를 다시 보내거나 content 로 전문을 보내세요."
            )
        hunks.append(hunk)
    return hunks


def _find_at(src: list[str], old: list[str], preferred: int) -> int:
    """old 블록이 정확히 일치하는 시작 인덱스. 없으면 -1, 모호하면 -2."""
    n = len(old)
    if 0 <= preferred <= len(src) - n and src[preferred:preferred + n] == old:
        return preferred
    hits: list[int] = []
    lo = max(0, preferred - _SEARCH_WINDOW)
    hi = min(len(src) - n, preferred + _SEARCH_WINDOW)
    for i in range(lo, hi + 1):
        if src[i:i + n] == old:
            hits.append(i)
            if len(hits) > 1:
                return -2  # 모호 — fail-closed
    return hits[0] if hits else -1


def apply_unified_diff(original: str, patch: str) -> str:
    """original 에 unified diff 를 적용한 새 본문. 안전하게 적용 못 하면 PatchError.

    보장:
      - hunk 본문 경계는 **머리말의 선언 길이**가 정한다(잘린 패치·후행 산문 차단).
      - 모든 hunk 는 문맥/삭제 줄이 **정확히** 일치해야 적용한다(공백 무시 없음).
      - **문맥 줄이 없는 hunk 는 거부**한다 — 위치를 검증할 방법이 없다.
      - 원 위치에서 어긋나면 ±400줄 안의 **유일한** 일치만 허용한다(복수 일치 = 거부).
      - 하나라도 실패하면 **전체를 적용하지 않는다**(부분 적용 금지).
      - 원본의 지배적 줄바꿈(CRLF/LF)을 보존한다.
    """
    if not str(patch or "").strip():
        raise PatchError("patch 가 비어 있습니다.")
    hunks = _parse_hunks(patch)
    if not hunks:
        raise PatchError(
            "patch 에서 hunk 를 찾지 못했습니다. `@@ -<시작>,<줄수> +<시작>,<줄수> @@` 머리말이 있는 "
            "unified diff 형식이어야 합니다(```diff 펜스 안의 내용만 보내세요)."
        )

    src, eol = _split_keep_eol(original)
    out: list[str] = []
    cursor = 0  # 원본에서 아직 복사하지 않은 위치
    for idx, hunk in enumerate(hunks, 1):
        old, new = hunk["old"], hunk["new"]
        if not old:
            # §2: 삭제도 문맥도 없는 순수 삽입. `-N,0` 의 N 해석이 애매하고(초판이 한 줄 앞에
            # 넣었다) 검증할 대상이 아예 없다. 모델은 앵커 줄 하나만 문맥으로 넣으면 되므로
            # 거부 비용이 낮다.
            raise PatchError(
                f"hunk #{idx} `{hunk['header']}` 에 문맥 줄이 없습니다(순수 삽입). 삽입 위치를 "
                "검증할 수 없어 적용하지 않았습니다. 삽입 지점 **앞뒤의 기존 줄을 최소 1줄** "
                "문맥(' ' 로 시작)으로 포함해 다시 보내세요."
            )
        preferred = max(0, int(hunk["old_start"]) - 1)
        at = _find_at(src, old, preferred)
        if at == -2:
            raise PatchError(
                f"hunk #{idx} `{hunk['header']}` 의 문맥이 파일에서 **여러 곳**과 일치해 적용 위치를 "
                "확정할 수 없습니다. 문맥 줄을 더 포함해 고유하게 만들거나, patch 대신 content 로 "
                "전문을 보내세요."
            )
        if at < 0:
            _ctx = next((ln for ln in old if ln.strip()), "")
            raise PatchError(
                f"hunk #{idx} `{hunk['header']}` 의 문맥이 파일 내용과 일치하지 않습니다"
                + (f" (예상한 줄: {_ctx[:80]!r})" if _ctx else "")
                + ". 줄 번호·공백·대소문자가 현재 파일과 정확히 같아야 합니다. "
                "`read_attachment` 로 현재 본문을 다시 확인해 patch 를 만들거나, content 로 전문을 보내세요."
            )
        if at < cursor:
            raise PatchError(
                f"hunk #{idx} `{hunk['header']}` 가 앞선 hunk 와 겹치거나 순서가 뒤바뀌었습니다. "
                "hunk 는 파일 순서대로, 겹치지 않게 배열해야 합니다."
            )
        out.extend(src[cursor:at])
        out.extend(new)
        cursor = at + len(old)
    out.extend(src[cursor:])
    return eol.join(out)

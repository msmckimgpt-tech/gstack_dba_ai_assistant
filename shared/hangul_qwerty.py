"""한글 자판 ↔ 영문(QWERTY) 자판 상호 변환 — 서버측 정본.

프론트 정본은 ``unit/feature-0003-agent-web-ui/src/static/hangul-qwerty.js`` 이며 **두 파일의 매핑표는 같은 값**이다
(회귀 잠금: ``tests/test_hangul_qwerty.py`` + ``tests/verify_hangul_qwerty.mjs`` 가 동일
케이스 표를 각각 단언한다). 클라이언트 인메모리 필터로는 덮이지 않는 검색 — 대화 본문
검색, 아카이브 대화 검색처럼 **SQL LIKE 로 DB 를 조회하는 경로** — 가 이 모듈을 쓴다.

용도: 사용자가 한/영 전환을 잊고 친 검색어(`ㅈ듀` ↔ `web`)를 반대 자판으로 옮긴 **후보
문자열**로 만들어, 호출부가 원문과 후보를 ``OR`` 로 함께 매칭하게 한다.

주의 — 대소문자: 쌍자음·이중모음은 Shift 입력이다(ㄲ=R, ㅃ=Q, ㅉ=W, ㄸ=E, ㅆ=T, ㅒ=O,
ㅖ=P). ``search_variants`` 에는 **소문자화 전 원문**을 넘겨야 `Rk`→`까` 가 산다. LIKE 는
서비스 collation 이 대소문자 무시라 후보 자체는 소문자로 돌려준다.
"""

from __future__ import annotations

CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3

# 자모 → 키 시퀀스 (복합 자모는 두 키의 연속 입력).
JAMO_TO_KEY = {
    "ㄱ": "r", "ㄲ": "R", "ㄴ": "s", "ㄷ": "e", "ㄸ": "E", "ㄹ": "f", "ㅁ": "a", "ㅂ": "q", "ㅃ": "Q",
    "ㅅ": "t", "ㅆ": "T", "ㅇ": "d", "ㅈ": "w", "ㅉ": "W", "ㅊ": "c", "ㅋ": "z", "ㅌ": "x", "ㅍ": "v", "ㅎ": "g",
    "ㅏ": "k", "ㅐ": "o", "ㅑ": "i", "ㅒ": "O", "ㅓ": "j", "ㅔ": "p", "ㅕ": "u", "ㅖ": "P",
    "ㅗ": "h", "ㅛ": "y", "ㅜ": "n", "ㅠ": "b", "ㅡ": "m", "ㅣ": "l",
    "ㅘ": "hk", "ㅙ": "ho", "ㅚ": "hl", "ㅝ": "nj", "ㅞ": "np", "ㅟ": "nl", "ㅢ": "ml",
    "ㄳ": "rt", "ㄵ": "sw", "ㄶ": "sg", "ㄺ": "fr", "ㄻ": "fa", "ㄼ": "fq",
    "ㄽ": "ft", "ㄾ": "fx", "ㄿ": "fv", "ㅀ": "fg", "ㅄ": "qt",
}

# 키 → 자모 (단일 자모만 — 복합은 아래 조합표가 만든다).
KEY_TO_JAMO = {
    "r": "ㄱ", "R": "ㄲ", "s": "ㄴ", "e": "ㄷ", "E": "ㄸ", "f": "ㄹ", "a": "ㅁ", "q": "ㅂ", "Q": "ㅃ",
    "t": "ㅅ", "T": "ㅆ", "d": "ㅇ", "w": "ㅈ", "W": "ㅉ", "c": "ㅊ", "z": "ㅋ", "x": "ㅌ", "v": "ㅍ", "g": "ㅎ",
    "k": "ㅏ", "o": "ㅐ", "i": "ㅑ", "O": "ㅒ", "j": "ㅓ", "p": "ㅔ", "u": "ㅕ", "P": "ㅖ",
    "h": "ㅗ", "y": "ㅛ", "n": "ㅜ", "b": "ㅠ", "m": "ㅡ", "l": "ㅣ",
}

JUNG_COMBINE = {
    "ㅗㅏ": "ㅘ", "ㅗㅐ": "ㅙ", "ㅗㅣ": "ㅚ",
    "ㅜㅓ": "ㅝ", "ㅜㅔ": "ㅞ", "ㅜㅣ": "ㅟ",
    "ㅡㅣ": "ㅢ",
}
JONG_COMBINE = {
    "ㄱㅅ": "ㄳ", "ㄴㅈ": "ㄵ", "ㄴㅎ": "ㄶ",
    "ㄹㄱ": "ㄺ", "ㄹㅁ": "ㄻ", "ㄹㅂ": "ㄼ", "ㄹㅅ": "ㄽ", "ㄹㅌ": "ㄾ", "ㄹㅍ": "ㄿ", "ㄹㅎ": "ㅀ",
    "ㅂㅅ": "ㅄ",
}
# 겹받침 분해 — 받침 뒤에 모음이 오면 **뒷 자음만** 다음 음절 초성으로 이월(닭+ㅏ → 달가).
JONG_SPLIT = {v: (k[0], k[1]) for k, v in JONG_COMBINE.items()}

_CHO_INDEX = {c: i for i, c in enumerate(CHO)}
_JUNG_INDEX = {v: i for i, v in enumerate(JUNG)}
_JONG_INDEX = {t: i for i, t in enumerate(JONG) if t}

_VOWELS = set(JUNG)


def decompose_syllable(ch: str):
    """완성형 음절 1자를 자모 리스트로 분해. 음절이 아니면 None."""
    if not ch:
        return None
    code = ord(ch)
    if code < _HANGUL_BASE or code > _HANGUL_LAST:
        return None
    offset = code - _HANGUL_BASE
    jong_idx = offset % 28
    jung_idx = (offset % 588) // 28
    cho_idx = offset // 588
    out = [CHO[cho_idx], JUNG[jung_idx]]
    if jong_idx:
        out.append(JONG[jong_idx])
    return out


def hangul_to_qwerty(text: str | None) -> str:
    """한글(완성형 음절·호환 자모)을 대응 QWERTY 키 시퀀스로 옮긴다."""
    s = "" if text is None else str(text)
    parts: list[str] = []
    for ch in s:
        jamos = decompose_syllable(ch)
        if jamos:
            for j in jamos:
                parts.append(JAMO_TO_KEY.get(j, j))
            continue
        parts.append(JAMO_TO_KEY.get(ch, ch))
    return "".join(parts)


def _compose_syllable(cho: str, jung: str, jong: str) -> str | None:
    if not cho or not jung:
        return None
    ci = _CHO_INDEX.get(cho)
    vi = _JUNG_INDEX.get(jung)
    if ci is None or vi is None:
        return None
    ti = _JONG_INDEX.get(jong, 0) if jong else 0
    return chr(_HANGUL_BASE + (ci * 21 + vi) * 28 + ti)


def qwerty_to_hangul(text: str | None) -> str:
    """QWERTY 키 시퀀스를 한글 IME 와 동일한 조합 규칙으로 한글 문자열로 옮긴다.

    자판에 대응하지 않는 문자(숫자·공백·기호)는 조합을 끊고 그대로 통과시킨다.
    """
    s = "" if text is None else str(text)
    out: list[str] = []
    cho = jung = jong = ""

    def flush() -> None:
        nonlocal cho, jung, jong
        if cho and jung:
            out.append(_compose_syllable(cho, jung, jong) or "")
        else:
            # 미완성 조합은 낱자 그대로 — `gz` → `ㅎㅋ` 가 이 경로다.
            out.append((cho or "") + (jung or "") + (jong or ""))
        cho = jung = jong = ""

    for ch in s:
        jamo = KEY_TO_JAMO.get(ch)
        if not jamo:
            flush()
            out.append(ch)
            continue

        if jamo in _VOWELS:
            if jong:
                split = JONG_SPLIT.get(jong)
                carry = split[1] if split else jong
                jong = split[0] if split else ""
                done = _compose_syllable(cho, jung, jong)
                out.append(done if done else ((cho or "") + (jung or "") + (jong or "")))
                cho, jung, jong = carry, jamo, ""
                continue
            if jung:
                merged = JUNG_COMBINE.get(jung + jamo)
                if merged:
                    jung = merged
                    continue
                flush()
                jung = jamo
                continue
            if not cho:
                flush()
                out.append(jamo)
                continue
            jung = jamo
            continue

        # 자음.
        if not cho:
            flush()
            cho = jamo
            continue
        if not jung:
            # 초성만 있는데 자음이 또 왔다 — `gz`(ㅎ+ㅋ) 처럼 낱자 두 개로 갈린다.
            flush()
            cho = jamo
            continue
        if not jong:
            if jamo in _JONG_INDEX:
                jong = jamo
                continue
            # 받침이 될 수 없는 자음(ㄸ·ㅃ·ㅉ) → 음절을 닫고 다음 초성으로.
            flush()
            cho = jamo
            continue
        merged_jong = JONG_COMBINE.get(jong + jamo)
        if merged_jong:
            jong = merged_jong
            continue
        flush()
        cho = jamo

    flush()
    return "".join(out)


def _has_hangul(s: str) -> bool:
    for ch in s:
        code = ord(ch)
        if _HANGUL_BASE <= code <= _HANGUL_LAST or 0x3131 <= code <= 0x318E:
            return True
    return False


def _has_qwerty_letter(s: str) -> bool:
    return any(("a" <= ch <= "z") or ("A" <= ch <= "Z") for ch in s)


# 자판 변환을 적용할 최소 길이. **원문과 후보 양쪽**에 건다.
#  - 후보 쪽: 짧은 영문이 1글자 한글이 되기 쉽고(`dk` → `아`), 그 1글자는 아무 행에나 걸려
#    **원래 맞던 검색을 오염**한다(실측: 제품 검색 `dk` 가 "글로벌 라이브" 까지 잡음).
#  - 원문 쪽: 반대 방향도 같다 — 1자 한글 `가` 가 `rk` 로 확장되면 `marketing`·`worker` 처럼
#    무관한 행이 잡힌다(codex 적대 리뷰 P2). 한 글자 검색어는 이미 매우 넓다.
# 프론트 정본(`static/hangul-qwerty.js` MIN_VARIANT_LEN)과 같은 값이어야 한다.
MIN_VARIANT_LEN = 2


def search_variants(raw: str | None) -> list[str]:
    """검색어 원문에서 **부분일치에 쓸 후보 문자열들**을 만든다.

    - ``[0]`` 은 항상 원문(strip + 소문자) — 기존 동작과 동일한 우선 후보.
    - 한글이 있으면 영문 자판 변환본을, 알파벳이 있으면 한글 조합본을 덧붙인다.
    - 변환 결과가 원문과 같거나 비면 넣지 않는다(무의미한 OR 항 방지).
    """
    src = ("" if raw is None else str(raw)).strip()
    if not src:
        return []
    out = [src.lower()]

    def push(value: str) -> None:
        t = (value or "").strip().lower()
        if len(t) >= MIN_VARIANT_LEN and t not in out:
            out.append(t)

    if len(src) < MIN_VARIANT_LEN:
        return out                      # 1자 검색어는 자판 교정 대상 아님(위 주석)
    if _has_hangul(src):
        push(hangul_to_qwerty(src))
    if _has_qwerty_letter(src):
        push(qwerty_to_hangul(src))
    return out


def alternate_layout_variants(raw: str | None) -> list[str]:
    """``search_variants`` 에서 **원문을 뺀** 반대 자판 후보만. 호출부가 기존 원문 매칭
    로직을 그대로 두고 OR 항만 덧붙일 때 쓴다(원문 이중 스캔 방지)."""
    variants = search_variants(raw)
    return variants[1:] if len(variants) > 1 else []


def matches_search_query(haystack: str | None, raw: str | None) -> bool:
    """haystack 이 검색어(또는 반대 자판 변환본)를 부분 문자열로 포함하는가."""
    variants = search_variants(raw)
    if not variants:
        return True
    hay = ("" if haystack is None else str(haystack)).lower()
    return any(v in hay for v in variants)

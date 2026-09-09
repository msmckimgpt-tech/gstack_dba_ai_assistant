"""Order-preserving attachment alignment; normalization never implies equality."""
from __future__ import annotations

import difflib
import re

_WORD = re.compile(r"\w+", re.UNICODE)
_WEAK_KEYS = {(), ("begin",), ("end",), ("else",), (";",), ("(",), (")",)}
_LINE_PAIR_CAP = 1_000_000
_MYERS_STATE_CAP = 40_000
_FUZZY_CELL_CAP = 40_000
_FUZZY_TOKEN_PAIR_CAP = 2_000_000
_FUZZY_MIN_RATIO = 0.60


def _line_key(line: str) -> tuple[str, ...]:
    """Scan once; even an unterminated quoted span consumes its whole suffix."""
    tokens = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch.isspace():
            i += 1
        elif ch in "'\"[`":
            start = i
            closing = "]" if ch == "[" else ch
            i += 1
            while i < len(line):
                if line[i] == "\\" and ch != "[":
                    i = min(len(line), i + 2)
                elif line[i] == closing:
                    i += 1
                    if i < len(line) and line[i] == closing:
                        i += 1
                    else:
                        break
                else:
                    i += 1
            tokens.append(line[start:i])
        else:
            word = _WORD.match(line, i)
            end = word.end() if word else i + 1
            tokens.append(line[i:end].casefold())
            i = end
    return tuple(tokens)


def _bounded_myers_matches(left: list[tuple], right: list[tuple]):
    """Keep repeated SQL anchors without quadratic scans of every occurrence."""
    n, m = len(left), len(right)
    frontier = {1: 0}
    trace = []
    work = 0
    states = 0
    for distance in range(n + m + 1):
        states += len(frontier)
        if states > _MYERS_STATE_CAP:
            return None
        trace.append(frontier.copy())
        for diagonal in range(-distance, distance + 1, 2):
            work += 1
            if work > _LINE_PAIR_CAP:
                return None
            if diagonal == -distance or (diagonal != distance and
                    frontier[diagonal - 1] < frontier[diagonal + 1]):
                x = frontier[diagonal + 1]
            else:
                x = frontier[diagonal - 1] + 1
            y = x - diagonal
            while x < n and y < m and left[x] == right[y]:
                x, y = x + 1, y + 1
                work += 1
                if work > _LINE_PAIR_CAP:
                    return None
            frontier[diagonal] = x
            if x >= n and y >= m:
                pairs = []
                for d in range(distance, -1, -1):
                    previous = trace[d]
                    k = x - y
                    if k == -d or (k != d and previous[k - 1] < previous[k + 1]):
                        prev_k = k + 1
                    else:
                        prev_k = k - 1
                    prev_x = previous[prev_k]
                    prev_y = prev_x - prev_k
                    while x > prev_x and y > prev_y:
                        x, y = x - 1, y - 1
                        pairs.append((x, y))
                    x, y = prev_x, prev_y
                return list(reversed(pairs))
    return None


def align_lines(left: list[str], right: list[str]) -> tuple[list[tuple[int | None, int | None]], bool]:
    """Align normalized anchors, then similar lines in the remaining gaps.

    Budgets are deterministic so context expansion cannot change the alignment.
    Unmatched/over-budget gaps retain positional replacement and every source line.
    """
    lk = [_line_key(s) for s in left]
    rk = [_line_key(s) for s in right]
    large = len(lk) * len(rk) > _LINE_PAIR_CAP
    matches = _bounded_myers_matches(lk, rk) if large else None
    limited = large and matches is None
    if limited:
        # A depleted bounded search must never fall back to an unbounded matcher.
        prefix = 0
        while prefix < min(len(lk), len(rk)) and lk[prefix] == rk[prefix]:
            prefix += 1
        suffix = 0
        while (suffix < min(len(lk), len(rk)) - prefix and
               lk[len(lk) - suffix - 1] == rk[len(rk) - suffix - 1]):
            suffix += 1
        matches = list(zip(range(prefix), range(prefix)))
        matches.extend(zip(range(len(lk) - suffix, len(lk)), range(len(rk) - suffix, len(rk))))
    result: list[tuple[int | None, int | None]] = []
    cells_left = _FUZZY_CELL_CAP
    tokens_left = _FUZZY_TOKEN_PAIR_CAP

    def positional(i1: int, i2: int, j1: int, j2: int) -> None:
        for offset in range(max(i2 - i1, j2 - j1)):
            result.append((i1 + offset if i1 + offset < i2 else None,
                           j1 + offset if j1 + offset < j2 else None))

    def similar(i1: int, i2: int, j1: int, j2: int) -> None:
        nonlocal cells_left, tokens_left, limited
        n, m = i2 - i1, j2 - j1
        cost = sum(map(len, lk[i1:i2])) * sum(map(len, rk[j1:j2]))
        if not n or not m:
            positional(i1, i2, j1, j2)
            return
        if n * m > cells_left or cost > tokens_left:
            limited = True
            positional(i1, i2, j1, j2)
            return
        cells_left -= n * m
        tokens_left -= cost
        # Maximum-weight monotone matching avoids greedy early, weaker matches.
        scores = [[0.0] * (m + 1) for _ in range(n + 1)]
        choices = [bytearray(m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            a = lk[i1 + i - 1]
            for j in range(1, m + 1):
                b = rk[j1 + j - 1]
                weight = 0.0
                if a and b and a not in _WEAK_KEYS and b not in _WEAK_KEYS:
                    if a == b:
                        weight = 2.0
                    elif 2 * min(len(a), len(b)) / (len(a) + len(b)) >= _FUZZY_MIN_RATIO:
                        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
                        if sm.quick_ratio() >= _FUZZY_MIN_RATIO:
                            ratio = sm.ratio()
                            if ratio >= _FUZZY_MIN_RATIO:
                                weight = ratio
                best, direction = scores[i - 1][j], 1
                if scores[i][j - 1] > best:
                    best, direction = scores[i][j - 1], 2
                if weight and scores[i - 1][j - 1] + weight > best:
                    best, direction = scores[i - 1][j - 1] + weight, 3
                scores[i][j], choices[i][j] = best, direction
        pairs = []
        i, j = n, m
        while i and j:
            direction = choices[i][j]
            if direction == 3:
                pairs.append((i1 + i - 1, j1 + j - 1))
                i, j = i - 1, j - 1
            elif direction == 1:
                i -= 1
            else:
                j -= 1
        li, rj = i1, j1
        for i, j in reversed(pairs):
            positional(li, i, rj, j)
            result.append((i, j))
            li, rj = i + 1, j + 1
        positional(li, i2, rj, j2)

    if matches is not None:
        li = rj = 0
        for i, j in matches:
            if i != li or j != rj:
                similar(li, i, rj, j)
            result.append((i, j))
            li, rj = i + 1, j + 1
        similar(li, len(lk), rj, len(rk))
    else:
        matcher = difflib.SequenceMatcher(
            lambda key: key in _WEAK_KEYS, lk, rk, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                result.extend(zip(range(i1, i2), range(j1, j2)))
            else:
                similar(i1, i2, j1, j2)
    return result, limited


def unified_from_rows(rows: list[dict], fromfile: str, tofile: str, context: int) -> str:
    """Emit a standard patch using the same alignment as both rendered views."""
    changed = [i for i, row in enumerate(rows) if row["type"] != "equal"]
    if not changed:
        return ""
    ranges: list[tuple[int, int]] = []
    for i in changed:
        start, end = max(0, i - context), min(len(rows), i + context + 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], end)
        else:
            ranges.append((start, end))
    left_count, right_count = [0], [0]
    for row in rows:
        left_count.append(left_count[-1] + (row["left_no"] is not None))
        right_count.append(right_count[-1] + (row["right_no"] is not None))

    def span(before: int, after: int) -> str:
        length = after - before
        start = before + 1 if length else before
        return str(start) if length == 1 else f"{start},{length}"

    output = [f"--- {fromfile}", f"+++ {tofile}"]
    for start, end in ranges:
        output.append(f"@@ -{span(left_count[start], left_count[end])} "
                      f"+{span(right_count[start], right_count[end])} @@")
        deleted: list[str] = []
        inserted: list[str] = []
        for row in rows[start:end]:
            if row["type"] == "equal":
                output.extend(deleted + inserted)
                deleted, inserted = [], []
                output.append(" " + row["left"])
            else:
                if row["left_no"] is not None:
                    deleted.append("-" + row["left"])
                if row["right_no"] is not None:
                    inserted.append("+" + row["right"])
        output.extend(deleted + inserted)
    return "\n".join(output)

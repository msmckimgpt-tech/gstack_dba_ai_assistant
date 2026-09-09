"""REQ-20260908-attach-folder-tree — 첨부 상대 경로의 정규화·검증·트리 렌더 단일 정본.

폴더를 통째로 첨부하면 각 파일은 「폴더 루트 기준 상대 경로」를 함께 가진다
(`webkitRelativePath` 또는 드롭된 디렉토리 엔트리의 fullPath). 그 문자열은 **브라우저가
보낸 사용자 입력**이므로 서버가 신뢰하지 않는다 — 경로 traversal(`../`), 절대 경로,
드라이브 문자, NUL·제어문자, 과도한 길이/깊이를 모두 여기서 잘라낸다.

web(feature-0003 업로드·목록)과 agent-core(feature-0002 LLM 컨텍스트) **양쪽이 같은 규칙**을
써야 하므로 shared 에 둔다 — 정규화가 갈리면 저장된 경로와 프롬프트에 그려지는 트리가
어긋나고, 그 어긋남은 "assistant 가 없는 파일을 말한다" 로 사용자에게 도달한다.
(`shared/share_window.py` 가 같은 이유로 shared 에 있다.)

**경로는 추가 축이지 파일명의 대체가 아니다**: `OriginalFilename` 은 계속 basename 이고,
첨부를 파일명으로 지칭하는 기존 계약(LLM 프롬프트 `REFER TO ATTACHMENTS BY FILENAME`,
`read_attachment(filename=...)`, 검색, 프론트 pill)은 그대로 유효하다.
"""
from __future__ import annotations

# 상한 — DB 컬럼(varchar(1024))과 정합. 초과분은 거절이 아니라 **폴더 정보 폐기**(None)로
# 처리한다: 파일 자체는 올라가야 한다(경로는 부가 정보이지 업로드의 전제가 아니다).
MAX_PATH_LEN = 1024
MAX_SEGMENT_LEN = 255
MAX_DEPTH = 32

# 경로 세그먼트에서 통째로 제거하는 문자 — NUL·제어문자.
_CONTROL_CHARS = {chr(c) for c in range(0x20)} | {chr(0x7F)}


def normalize_relative_path(raw: object, filename: str | None = None) -> str | None:
    """클라이언트가 보낸 상대 경로를 안전한 정규 형태로 되돌린다. 안전하지 않으면 None.

    반환값이 None 이면 「폴더 정보 없음」 — 단일 파일 업로드와 같게 취급한다.

    정규화:
      - 백슬래시(`\\`) → 슬래시. Windows 에서 온 경로를 한 형태로 모은다.
      - 절대 경로 표시 제거: 선행 `/`, `C:` 류 드라이브 접두, UNC(`//host`).
      - 세그먼트 단위로 `.`/`..`/빈 문자열을 **버린다**(traversal 차단 — `..` 를 상위 이동으로
        해석하지 않고 그냥 제거한다: 상대 경로는 표시·구조 용도이지 파일시스템 접근에 쓰이지
        않으므로, 해석하지 않는 편이 단순하고 안전하다).
      - 제어문자 제거, 세그먼트 길이 절단.
      - 깊이·전체 길이 상한 초과 시 **앞(루트 쪽)을 잘라 꼬리를 남긴다**(`…/en/messages.json`).
        버리지 않는 이유: 경로 유무가 버전 체인 스코프를 가르므로, 두 파일의 경로를 함께
        버리면 둘이 한 체인으로 합쳐져 서로를 supersede 한다 — 이 함수가 지키려는 성질이
        상한 때문에 깨지는 셈이다. 꼬리만으로도 형제 파일은 구분된다.

    `filename` 이 주어지면 마지막 세그먼트를 그 값으로 **고정**한다 — 경로의 basename 과
    업로드된 파일명이 어긋나면(클라이언트가 둘을 따로 보내므로 가능하다) 목록·트리와 실제
    파일이 다른 것을 가리키게 된다. 파일명 쪽이 권위다.
    """
    if raw is None:
        return None
    text = raw if isinstance(raw, str) else str(raw)
    text = text.replace("\\", "/").strip()
    if not text:
        return None

    segments: list[str] = []
    for seg in text.split("/"):
        seg = "".join(ch for ch in seg if ch not in _CONTROL_CHARS).strip()
        if not seg or seg in (".", ".."):
            continue
        # 드라이브 문자(`C:`)·스킴 잔재를 담은 세그먼트는 경로 루트 표기이므로 버린다.
        if len(seg) == 2 and seg[1] == ":" and seg[0].isalpha():
            continue
        if len(seg) > MAX_SEGMENT_LEN:
            seg = seg[:MAX_SEGMENT_LEN]
        segments.append(seg)

    if filename:
        safe_name = "".join(ch for ch in str(filename) if ch not in _CONTROL_CHARS).strip()
        safe_name = safe_name.replace("\\", "/").split("/")[-1]
        # §18.8 security [P2]: `filename` 도 raw multipart 값이라 `.`/`..` 일 수 있다. 위 세그먼트
        # 루프가 그것들을 걸러낸 **뒤에** 파일명을 써 넣으므로, 여기서 다시 보지 않으면 이 함수의
        # 불변식(「`..` 는 남기지 않는다」)이 override 경로로만 깨진다 — `normalize_relative_path(
        # "proj/x", "..")` → `proj/..`. 지금은 이 값을 파일시스템에 쓰는 소비자가 없지만, 폴더
        # 보존 ZIP 내보내기처럼 경로를 실제로 결합하는 소비자가 생기는 순간 그대로 결함이 된다.
        if safe_name in (".", ".."):
            safe_name = ""
        if safe_name:
            if segments and segments[-1] != safe_name:
                segments[-1] = safe_name[:MAX_SEGMENT_LEN]
            elif not segments:
                segments = [safe_name[:MAX_SEGMENT_LEN]]

    if not segments:
        return None
    # 세그먼트가 파일명 하나뿐이면 폴더 정보가 없는 것 — 단일 파일 업로드와 동일하다.
    if len(segments) < 2:
        return None

    # §18.8 backend [P2]: 상한 초과를 **None 으로 접으면 이 REQ 가 닫으려던 결함이 되돌아온다.**
    #
    #   `…/en/messages.json` 와 `…/ko/messages.json` (깊은 지역화 트리)이 둘 다 None 이 되면,
    #   두 번째 업로드가 「경로 없는」 분기로 떨어져 파일명으로 첫 번째를 찾고 **v2 로 편입하며
    #   supersede** 한다 — 사용자는 2개를 올렸는데 목록에 1개가 남고 토스트는 "새 버전" 이라 한다.
    #   경로 유무가 체인 스코프를 가르는 이상, 「폐기」는 곧 「합쳐짐」이다.
    #
    # 그래서 버리지 않고 **꼬리를 남긴다** — 구분에 쓰이는 정보는 경로의 끝(파일 쪽)이고,
    # 잘리는 것은 공통 접두(루트 쪽)다. 앞이 잘렸음을 `…` 로 남겨 표시가 사실을 감추지 않게 한다.
    if len(segments) > MAX_DEPTH:
        segments = ["…"] + segments[-(MAX_DEPTH - 1):]
    path = "/".join(segments)
    if len(path) > MAX_PATH_LEN:
        kept: list[str] = []
        total = 0
        for seg in reversed(segments):
            if total + len(seg) + 1 > MAX_PATH_LEN - 2:   # "…/" 자리 확보
                break
            kept.append(seg)
            total += len(seg) + 1
        segments = ["…"] + list(reversed(kept)) if kept else [segments[-1][:MAX_PATH_LEN - 2]]
        path = "/".join(segments)
    # 꼬리만 남아 파일명 하나가 됐으면 폴더 정보가 실질적으로 없는 것 — None 과 같다.
    if len([x for x in segments if x != "…"]) < 2:
        return None
    return path


def path_or_filename(relative_path: object, filename: object) -> str:
    """첨부의 **체인·표시 키**. 경로가 있으면 경로, 없으면 파일명.

    버전 체인 스코프가 이 값을 쓴다 — 파일명만으로 스코프하면 `src/config.json` 과
    `test/config.json` 이 한 체인으로 합쳐져 **서로를 supersede** 하고, 사용자가 올린
    파일이 목록에서 사라진다. 폴더 첨부가 들어온 이상 「같은 파일」의 정의는 경로다.
    """
    rp = relative_path if isinstance(relative_path, str) else (str(relative_path) if relative_path else "")
    rp = rp.strip()
    if rp:
        return rp
    return str(filename or "")


def parent_dir(relative_path: object) -> str:
    """상대 경로의 디렉토리 부분(`src/utils/a.py` → `src/utils`). 경로 없으면 빈 문자열."""
    rp = relative_path if isinstance(relative_path, str) else (str(relative_path) if relative_path else "")
    rp = rp.strip()
    if not rp or "/" not in rp:
        return ""
    return rp.rsplit("/", 1)[0]


def render_directory_tree(entries, *, indent: str = "  ", max_lines: int = 0) -> list[str]:
    """(relative_path, label) 목록을 ASCII 디렉토리 트리 라인들로 그린다.

    `entries` 는 `(relative_path | None, label)` 의 iterable. `relative_path` 가 없는 항목은
    루트 직하에 파일로 놓는다(단일 파일 업로드 — 폴더에 속하지 않는다는 사실 그대로).

    LLM 프롬프트와 사람용 표시가 **같은 함수**를 쓴다 — 둘이 갈리면 assistant 가 보는 구조와
    사용자가 보는 구조가 달라지고, 그 차이는 대화 중에만 드러난다.

    `max_lines > 0` 이면 그 줄 수를 넘는 디렉토리를 **접어서**(`src/utils/ (24 files)`) 상한
    안에 맞춘다 — 절단은 반드시 관측 가능해야 하므로 접힌 사실과 파일 수를 남긴다(무음 절단
    금지). 프롬프트 소비자가 이 상한을 쓴다: 첨부는 append-only 라 트리가 **매 턴** 실리고,
    300 파일 폴더 하나가 ~2,500 토큰을 대화 끝까지 상시 점유한다.

    같은 (경로, 이름) leaf 가 여럿이면 **한 줄로 접고 개수를 적는다** — assistant 편집본이
    사용자 계보와 같은 경로를 승계하므로(정상 상태) 그대로 그리면 같은 파일이 두 번 그려져
    모델이 "파일이 둘 있다" 고 답한다.

    출력 예:
        my-project/
          src/
            utils/
              helper.py
            main.py
          README.md
    """
    # 디렉토리 트리를 중첩 dict 로 세운다. 파일은 리스트에 모아 디렉토리 뒤에 정렬 출력.
    root: dict = {"dirs": {}, "files": []}

    def _node_for(parts: list[str]) -> dict:
        node = root
        for part in parts:
            child = node["dirs"].get(part)
            if child is None:
                child = {"dirs": {}, "files": []}
                node["dirs"][part] = child
            node = child
        return node

    for relative_path, label in entries:
        rp = relative_path if isinstance(relative_path, str) else (str(relative_path) if relative_path else "")
        rp = rp.strip()
        if not rp:
            root["files"].append(str(label))
            continue
        parts = [p for p in rp.split("/") if p]
        if len(parts) <= 1:
            root["files"].append(str(label))
            continue
        _node_for(parts[:-1])["files"].append(str(label))

    def _dedup(names: list[str]) -> list[str]:
        """같은 자리의 동명 leaf 를 한 줄로 접고 개수를 적는다(계보 공존은 정상 상태다)."""
        seen: dict[str, int] = {}
        for n in names:
            seen[n] = seen.get(n, 0) + 1
        out = []
        for n in sorted(seen, key=str.lower):
            out.append(n if seen[n] == 1 else f"{n} ({seen[n]} versions/lineages)")
        return out

    def _count_files(node: dict) -> int:
        return len(node["files"]) + sum(_count_files(c) for c in node["dirs"].values())

    def _count_lines(node: dict) -> int:
        return (len(_dedup(node["files"]))
                + sum(1 + _count_lines(c) for c in node["dirs"].values()))

    lines: list[str] = []

    def _emit(node: dict, depth: int) -> None:
        pad = indent * depth
        for name in sorted(node["dirs"].keys(), key=str.lower):
            child = node["dirs"][name]
            # 상한이 걸려 있고 이 서브트리를 통째로 그리면 넘칠 때는 **접는다**.
            if max_lines > 0 and len(lines) + 1 + _count_lines(child) > max_lines:
                lines.append(f"{pad}{name}/ ({_count_files(child)} files, collapsed)")
                continue
            lines.append(f"{pad}{name}/")
            _emit(child, depth + 1)
        for fname in _dedup(node["files"]):
            if max_lines > 0 and len(lines) >= max_lines:
                lines.append(f"{pad}… (더 있음 — 위 목록이 전량이다)")
                return
            lines.append(f"{pad}{fname}")

    _emit(root, 0)
    return lines

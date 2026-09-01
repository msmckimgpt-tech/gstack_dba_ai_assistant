"""REQ-20260828-attach-lineage-ui — 계보가 화면에 드러나야 한다 (사용자 제보 2026-08-28).

## 무엇이 잘못돼 있었나

assistant 편집본은 사용자 계보를 잇지 않고 **새 root 로 분기**한다(2026-08-14 결정). 그 결과
같은 파일명에 계보가 여럿 공존하는데, 화면 두 곳이 그 사실을 말하지 않았다:

1. **단건 계보는 비교 자체가 불가능** — 분기한 계보는 v1 뿐이라 첨부 목록의 버전 펼침 토글
   (`verCount > 1`)이 뜨지 않았고, 토글이 없으면 그 안의 「⇄ 버전 비교」 진입점도 화면에
   존재하지 않는다. **비교 대상(원본 계보)이 바로 옆에 있는데** 도달 경로가 없었다.
   모달은 이미 계보 축을 지원한다(`hasLineageAxis`) — 막고 있던 것은 목록 쪽 게이트였다.
2. **목록에 계보 구성이 안 보임** — 같은 이름의 행이 여럿 뜨는데 어느 것이 내가 올린 것이고
   어느 것이 거기서 갈라진 AI 계보인지, 각 계보가 파일 몇 개인지가 어디에도 없었다.

말풍선 칩 경로는 이미 고쳐져 있었다(`verNum > 1 || _isAiEdit`, REQ-20260814) — **목록만
뒤처져 비대칭**이었다. 그 비대칭을 여기서 잠근다.

검증: JS 소스 구조 계약(§16.7 G10) + 서버 직렬화 계약. 주석 문구가 통과시키지 못하도록
비교는 **주석을 걷어낸** 본문에서 한다.
"""
from __future__ import annotations

import re
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "src"
COMPOSER = _WEB / "static" / "app" / "composer.js"
MESSAGES = _WEB / "static" / "app" / "messages.js"
DIFF = _WEB / "static" / "app" / "attach-diff.js"
CSS = _WEB / "static" / "css" / "chat.css"
CONV_STORE = _WEB / "routers" / "_conv_store.py"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """`//` 주석과 `/* */` 블록을 걷어낸 JS 본문.

    이 저장소가 반복해서 겪은 함정이다 — 주석에 적힌 계약 문구가 단언을 통과시키면 코드가
    그 반대여도 green 이 된다.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


def _fn_body(text: str, name: str) -> str:
    """`function name(` 부터 다음 최상위 `function` 직전까지."""
    pat = r"^(?:export\s+)?(?:async\s+)?function\s+"
    m = re.search(pat + re.escape(name) + r"\s*\(", text, re.M)
    assert m, f"{name} 을 찾지 못했다"
    rest = text[m.end():]
    nxt = re.search(pat + r"\w+\s*\(", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# ── L1. 단건 계보에서도 비교할 수 있다 ─────────────────────────────────────

def test_versions_box_compare_gate_includes_lineage_axis():
    """비교 진입점이 **계보 축**도 본다 — `versions.length > 1` 하나로 막지 않는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    m = re.search(r"const\s+canCompare\s*=\s*([^;]+);", body)
    assert m, "canCompare 판정을 찾지 못했다"
    expr = m.group(1).strip()
    assert "hasLineageAxis" in expr, f"비교 진입점이 계보 축을 보지 않는다: {expr}"
    # ⚠ **토큰 존재만 보면 `&&` 로 회귀해도 통과한다**(codex P2). `&&` 는 정확히 반대 의미다 —
    #   버전이 2개 **이면서** 계보도 2개일 때만 열리므로 단건 계보는 여전히 막힌다.
    assert "||" in expr and "&&" not in expr, (
        f"두 조건이 OR 가 아니다: {expr} — AND 면 단건 계보는 그대로 막힌다")
    # 실제로 계산해 본다: 소스 문자열이 아니라 **값**으로 계약을 고정한다.
    py = (expr.replace("versions.length", "V").replace("hasLineageAxis", "L")
          .replace("||", " or ").replace("&&", " and "))
    for V, L, want in ((1, True, True), (3, False, True), (1, False, False), (2, True, True)):
        assert eval(py, {}, {"V": V, "L": L}) is want, (
            f"canCompare({V=}, {L=}) 가 {want} 가 아니다 — {expr}")


def test_lineage_axis_requires_two_heads():
    """계보 축은 head 가 **2개 이상**일 때만 성립한다(하나면 '계보 비교' 가 무의미)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    m = re.search(r"hasLineageAxis\s*=\s*([^;]+);", body)
    assert m, "hasLineageAxis 판정이 없다"
    assert ">" in m.group(1) and "1" in m.group(1), (
        f"계보 축 판정이 개수를 보지 않는다: {m.group(1).strip()}")


def test_version_toggle_opens_for_single_version_lineage():
    """펼침 토글이 **같은 이름의 다른 계보가 있을 때**도 뜬다.

    토글이 없으면 그 안의 비교 진입점에 도달할 수 없다 — 게이트가 두 겹이라 위쪽(L1)만
    고치면 화면에서는 여전히 아무것도 달라지지 않는다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"const\s+verToggle\s*=\s*\(([^)]+)\)", body)
    assert m, "verToggle 판정을 찾지 못했다"
    expr = m.group(1).strip()
    assert "verCount > 1" in expr and "_hasSiblings" in expr, (
        f"토글이 버전 수만 본다: {expr} — 단건 계보는 비교 UI 에 도달할 길이 없다")
    assert "||" in expr and "&&" not in expr, (
        f"두 조건이 OR 가 아니다: {expr} — AND 면 단건 계보는 그대로 막힌다")
    py = (expr.replace("verCount", "C").replace("_hasSiblings", "S")
          .replace("||", " or ").replace("&&", " and "))
    for C, S, want in ((1, True, True), (4, False, True), (1, False, False)):
        assert eval(py, {}, {"C": C, "S": S}) is want, (
            f"verToggle({C=}, {S=}) 가 {want} 가 아니다 — {expr}")


def test_compare_button_label_matches_what_it_opens():
    """버전이 하나뿐인 계보에서 버튼 문구는 「계보 비교」다.

    같은 문구를 쓰면 눌러 보고 나서야 무엇이 열리는지 안다 — 약속과 사실을 맞춘다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    assert "계보 비교" in body, "단건 계보에서도 「버전 비교」라고만 말한다"
    assert re.search(r"singleVersion\s*=\s*versions\.length\s*<\s*2", body), (
        "단건 판정이 없다 — 문구가 상황을 따라가지 않는다")


def test_single_version_does_not_preselect_a_version_pair():
    """단건 계보에서는 버전 쌍을 preselect 하지 않는다(같은 번호 쌍은 서버가 400)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    m = re.search(r"openAttachmentDiffModal\(\s*\n?\s*attachmentId,\s*versions,\s*(.+?),\s*\n?\s*lineages\)",
                  body, re.S)
    assert m, "비교 모달 호출을 찾지 못했다"
    assert "singleVersion" in m.group(1), (
        f"단건인데 버전 쌍을 지정한다: {m.group(1).strip()}")


# ── L2. 목록이 계보 구성을 말한다 ──────────────────────────────────────────

def test_list_groups_lineages_by_filename():
    """목록이 **파일명으로 계보를 묶는다** — 목록은 계보당 head 한 행이므로 그것이 계보 집합."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_lineageByName" in body, "같은 이름의 계보 지형을 만들지 않는다"
    assert "original_filename" in body, "묶는 기준이 파일명이 아니다"


def test_list_row_shows_lineage_badge_only_when_siblings_exist():
    """계보 배지는 **형제 계보가 있을 때만** 붙는다.

    계보가 하나뿐인 흔한 첨부에 `계보 1/1` 을 달면 아무 정보도 주지 않으면서 240px 폭의
    이름줄만 먹는다(§16.8 예산).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_hasSiblings" in body, "형제 계보 판정이 없다"
    m = re.search(r"if\s*\(\s*_hasSiblings\s*\)\s*\{", body)
    assert m, "계보 배지가 형제 유무와 무관하게 붙는다"
    assert "linBadge" in body[m.end(): m.end() + 900], "배지 생성이 그 가드 안에 없다"


def test_lineage_badge_is_rendered_into_the_name_row():
    """만든 배지를 **실제로 넣는다** — 만들고 안 넣으면 화면은 그대로다(배선 사각)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "${linBadge}" in body, "계보 배지를 마크업에 넣지 않는다"


def test_lineage_origin_is_not_invented_when_parent_unknown():
    """분기 부모가 목록에 없으면 **아는 만큼만** 말한다 — 모르는 것을 지어내지 않는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_fromRow" in body, "분기 부모를 되짚지 않는다"
    assert "다른 파일에서 갈라진 계보" in body, (
        "부모를 못 찾은 경우의 문구가 없다 — 없는 사실을 단정하게 된다")


def test_lineage_composition_is_stated_by_the_card_not_repeated_in_the_box():
    """옆 계보의 존재는 **여전히 화면에 있다** — 다만 자리가 옮겨졌다.

    REQ-20260828 이 버전 박스에 「이 계보: … / 다른 계보 N개」 안내문을 넣은 이유는 그 사실이
    화면 어디에도 없었기 때문이다. REQ-20260831 이 그룹 카드를 도입하면서 같은 사실을
    **구조로**(머리의 `계보 N` · 행의 `⤷ 갈라짐` 칩 · 정체성 라벨 · 토글 `버전 N개`) 말하게
    됐고, REQ-20260901 에서 박스의 문구는 되풀이가 되어 걷어냈다(사용자 지적).

    여기서 잠그는 것은 **보장이 사라지지 않았다**는 것이다 — 위치만 바뀌었지 사실은 남아야 한다.
    """
    box = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    assert "attach-list-versions-lineage" not in box, (
        "박스가 카드 머리와 같은 사실을 되풀이한다")
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert "계보 ${count}" in card, "카드 머리가 계보 수를 말하지 않는다"
    lst = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "⤷" in lst, "분기 사실이 행에서도 사라졌다"   # 문구는 title/aria, 화면은 글리프
    assert "_identityLabel" in lst, "계보 정체성이 행에서도 사라졌다"
    assert "버전 ${verCount}개" in lst, "이 계보의 파일 수(버전 토글)가 사라졌다"


def test_versions_box_does_not_reintroduce_a_lineage_note():
    """박스에 계보 안내문을 **되살리지 않는다** — 짧은 되풀이도 되풀이다."""
    box = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    assert "attach-list-versions-lineage" not in box, "박스가 계보 안내 요소를 되살렸다"
    # ⚠ 「다른 계보」 문자열 자체를 금지하지 않는다 — 비교 버튼의 `title` 은 그 버튼이 **무엇을
    #   여는지**를 설명하는 정당한 용례다(상시 렌더되는 안내문과 다르다). 금지 대상은
    #   «화면에 늘 떠 있는 되풀이 문구» 이므로 요소 자체로 판정한다.
    assert not re.search(r"note\.textContent\s*=", box), "안내문 조립이 남아 있다"


# ── L3. 토글 문구는 한 곳에서 만든다 ───────────────────────────────────────

def test_toggle_label_has_one_source():
    """토글 문구를 세 곳(초기·토글·로드완료)이 각자 조립하지 않는다.

    각자 조립하면 단건 계보에서 라벨이 「계보 N개」→「버전 1개」로 튄다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "verToggleLabel" in body, "토글 라벨 단일 출처가 없다"
    assert not re.search(r"`버전 \$\{verCount\}개 \$\{hidden", body), (
        "토글 재설정이 라벨을 다시 조립한다")


# ── L4. 서버 계약 ──────────────────────────────────────────────────────────

def test_list_payload_carries_branch_parent():
    """목록 직렬화가 **분기 부모**를 싣는다 — `/versions` 와 같은 사실을 말하게 한다."""
    src = _src(CONV_STORE)
    i = src.find("def _serialize_attachment_for_api")
    assert i > 0
    body = src[i: i + 4000]
    assert 'payload["branched_from_attachment_id"]' in body, (
        "목록에 분기 부모가 없다 — 화면이 계보 관계를 설명할 근거가 없다")
    assert "_meta_json_to_dict" in body, (
        "MetaJson 을 정규화하지 않는다 — MySQL(longtext) 경로에서 문자열로 와 항상 None 이 된다")


def test_degraded_reason_gate_untouched():
    """인접한 `degraded_reason` 게이트는 **건드리지 않는다**.

    같이 고치면 이 cycle 범위 밖에서 표시가 바뀐다(MySQL 경로에서 종전에 안 나가던 필드가
    갑자기 나간다). 별도 판단이 필요한 변경이라 분리한다.
    """
    src = _src(CONV_STORE)
    i = src.find("def _serialize_attachment_for_api")
    body = src[i: i + 4000]
    m = re.search(r'if isinstance\(meta, dict\):\s*\n\s*#[^\n]*\n\s*if meta\.get\("degraded_reason"\)',
                  body)
    assert m, "degraded_reason 이 원래 게이트(isinstance dict)를 벗어났다"


# ── L5. 두 진입점이 같은 계약을 쓴다 (비대칭 방지) ─────────────────────────

def test_bubble_chip_and_list_agree_on_lineage_axis():
    """말풍선 칩과 첨부 목록이 **같은 사실**로 판정한다.

    이 결함의 본질이 비대칭이었다 — 칩은 REQ-20260814 에서 고쳐졌고 목록만 남았다.
    """
    chip = _code_only(_src(MESSAGES))
    assert "lineages.length < 2" in chip, "칩 경로의 계보 축 판정이 사라졌다"
    box = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    assert "linHeads.length > 1" in box or "hasLineageAxis" in box, (
        "목록 경로가 계보 축을 보지 않는다 — 두 진입점이 다시 갈린다")


def test_modal_accepts_single_version_with_lineage_axis():
    """모달이 단건 계보 + 계보 축 조합을 실제로 받는다(진입점만 열고 모달이 막으면 무의미)."""
    body = _code_only(_src(DIFF))
    assert re.search(r"list\.length\s*<\s*2\s*&&\s*!hasLineageAxis", body), (
        "모달이 계보 축과 무관하게 버전 2개를 요구한다")


# ── L6. 스타일 ─────────────────────────────────────────────────────────────

def test_lineage_badge_has_style_and_does_not_collapse():
    """배지가 이름 말줄임에 먹히지 않는다(`flex-shrink: 0`) — 기존 버전 배지와 같은 규칙."""
    css = _src(CSS)
    i = css.find(".attach-list-item-lineage {")
    assert i > 0, "계보 배지 스타일이 없다"
    rule = css[i: css.find("}", i)]
    assert "flex-shrink: 0" in rule, "배지가 이름 말줄임에 먹힌다"
    assert "white-space: nowrap" in rule, "배지가 줄바꿈으로 쪼개진다"


def test_list_resolves_lineage_origin_from_root_not_head():
    """계보 출처는 **root 행**에서 해소한다 — head 행에는 분기 표식이 없다.

    라이브 실측(2026-08-28): 1246 에서 갈라진 계보의 head 는 v4(id 1256)인데, 분기 표식은
    그 계보의 root(1249)에만 있어 head 행만 보면 `null` 이었다. 행만 믿으면 다중 버전
    계보는 **갈라진 적 없는 것**으로 그려진다.
    """
    src = _src(_WEB / "routers" / "conversations.py")
    i = src.find("lineage_origin")
    assert i > 0, "계보 출처 해소가 없다"
    body = src[i - 2000: i + 3000]
    assert "RootAttachmentId" in body, "root 기준으로 모으지 않는다"
    assert "lineage_branched_from_attachment_id" in src, "계보 출처를 응답에 싣지 않는다"


def test_lineage_origin_is_one_query_not_per_row():
    """root 조회는 **한 번의 IN**이다 — 행마다 조회하면 N+1."""
    src = _src(_WEB / "routers" / "conversations.py")
    i = src.find("lineage_origin: dict[int, int] = {}")
    assert i > 0
    body = src[i: i + 1600]
    assert "IN (" in body, "IN 조회가 아니다 — 행마다 왕복한다"
    assert "for lr in" in body, "결과를 한 번에 순회하지 않는다"


def test_client_prefers_lineage_origin_over_row_origin():
    """클라이언트가 **계보** 출처를 우선한다(행 표식은 root 행에만 있다)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"_originId\s*=\s*Number\(([^)]*)\)", body, re.S)
    assert m, "출처 해소가 없다"
    expr = m.group(1)
    assert expr.index("lineage_branched_from") < expr.index("a.branched_from"), (
        "행 표식을 계보 표식보다 먼저 본다 — 다중 버전 계보에서 출처를 잃는다")


def test_modal_title_follows_the_axis():
    """계보 간 비교에서 제목이 「계보 비교」다 — 축과 제목이 어긋나지 않는다.

    종전에는 축과 무관하게 "버전 비교" 로 고정이었다. 계보 간에서는 견주는 대상이 한 줄기의
    버전이 아니라 **다른 계보**다. 사용자가 계보를 못 보는 것이 이번 제보의 본질이므로,
    제목이 계보를 감추면 같은 결함이 모달에서 반복된다.
    """
    body = _code_only(_src(DIFF))
    assert 'class="attach-diff-titleword"' in body, "제목 문구가 갱신 가능한 요소가 아니다"
    m = re.search(r'_word\s*=\s*axis === "time" \? ("[^"]+") : ("[^"]+")', body)
    assert m, "제목 문구가 비교 축을 따라가지 않는다"
    assert m.group(1) == '"계보 비교"' and m.group(2) == '"버전 비교"', (
        f"축별 문구가 뒤바뀌었다: time={m.group(1)}, else={m.group(2)}")
    assert re.search(r"titleWordEl\.textContent\s*=\s*_word", body), (
        "계산한 문구를 제목에 넣지 않는다(만들고 안 쓰면 화면은 그대로)")


def test_modal_accessible_name_follows_the_axis():
    """**접근성 이름**도 축을 따라간다 (codex P2).

    눈에 보이는 제목만 고치면 스크린리더에는 계속 "첨부 버전 비교" 가 읽혀, 계보 축에서
    틀린 제목이 그쪽에만 남는다 — 보이는 화면과 읽히는 화면이 갈린다.
    """
    body = _code_only(_src(DIFF))
    assert re.search(r'setAttribute\("aria-label",\s*`첨부 \$\{_word\}`\)', body), (
        "dialog 의 aria-label 이 고정 문구다")


def test_axis_is_only_referenced_where_it_exists():
    """`axis` 를 **그 변수가 사는 함수 안에서만** 쓴다.

    이 파일에는 모달이 둘이다 — 전용 diff 모달(`openAttachmentDiffModal`, 계보 축 있음)과
    원문 모달(`openAttachmentSourceModal`, 계보 축 **없음**). 두 함수의 `syncHead`/제목 코드가
    비슷하게 생겨서, 원문 모달 쪽에 `axis` 를 쓰면 그 화면이 열릴 때마다 **ReferenceError**
    로 죽는다(이 cycle 에서 실제로 한 번 그렇게 썼고, 소스 문자열만 보는 단언은 통과시켰다).
    """
    src = _src(DIFF)
    i_diff = src.index("export function openAttachmentDiffModal")
    i_src = src.index("export function openAttachmentSourceModal")
    assert i_diff < i_src
    source_modal = _code_only(src[i_src:])
    assert not re.search(r"\baxis\b", source_modal), (
        "원문 모달이 `axis` 를 참조한다 — 그 스코프에 없는 변수라 화면이 열리는 순간 죽는다")
    diff_modal = _code_only(src[i_diff:i_src])
    assert re.search(r"let\s+axis\s*=", diff_modal), "diff 모달에 axis 선언이 없다"


def test_lineage_labels_do_not_claim_ownership():
    """계보 문구가 **소유권을 단정하지 않는다** (codex P2).

    목록 payload 에는 업로더 `account_id` 가 없다. 그런데 종전 문구는 사람이 올린 첨부를
    모두 "내 파일"·"내가 올린 계보" 라고 말했다 — **그룹 대화에서 다른 멤버가 올린 파일**도
    내 것이라고 화면이 거짓말한다.

    아는 것은 "사람이 올렸나 / AI 가 만들었나" 뿐이다. 딱 그만큼만 말한다.
    """
    for fn in ("_loadConversationAttachmentList", "_renderAttachmentVersionsBox"):
        body = _code_only(_fn_body(_src(COMPOSER), fn))
        for claim in ('"내 ', '"내가 ', "'내 ", "'내가 "):
            assert claim not in body, (
                f"{fn} 의 계보 문구가 소유권을 단정한다({claim!r}) — 그룹 대화에서 남의 "
                "업로드를 내 것이라 말하게 된다")
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "업로드한 파일" in body and "사용자가 올린 계보" in body, (
        "주체 중립 문구가 없다")

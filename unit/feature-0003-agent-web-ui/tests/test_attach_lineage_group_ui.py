"""REQ-20260831-attach-lineage-visibility — 계보 **비교 가시성** 재설계 (사용자 제보 수렴 2026-08-31).

## 무엇이 잘못돼 있었나

선행 cycle(REQ-20260828-attach-lineage-ui)이 계보의 **존재**를 화면에 올렸다 — 배지 `계보 1/2`,
버전 박스의 안내문, 단건 계보에서도 열리는 비교 진입점. 그런데 사용자 불만은 그 뒤로도 반복
수렴했다. 존재를 말하는 것과 **견주기 쉬운 것**은 다른 문제였기 때문이다:

1. **평면 형제 행** — 같은 파일의 계보 둘과 무관한 다른 파일이 목록에서 **시각적으로 동급**.
   어느 둘이 한 파일의 갈래인지 판별하려면 파일명을 글자 단위로 대조해야 했다.
   NN/g 의 공통영역(common region) 원칙: enclosure(테두리·배경)는 근접성을 **압도**한다 —
   행 간격만으로는 "같은 파일의 갈래" 가 전달되지 않는다.
2. **분기가 그려지지 않음** — 관계는 산문·툴팁("다른 파일에서 갈라짐")에만 있었다. 보려면
   읽어야 했다. 커밋 그래프(GitKraken 계열)가 레인+커넥터로 분기를 *그리는* 이유가 이것이다.
3. **비교 진입 2단계** — 계보를 **펼쳐야** 비교 버튼이 나타났다. Figma 의 브랜치 리뷰처럼
   비교는 그룹의 1급 액션이어야 한다.
4. **서수는 정체성이 아님** — `계보 1/2` 는 "몇 번째" 를 말할 뿐 "누구의 갈래인가" 를 말하지
   않는다. 순서가 바뀌면 같은 계보가 어제와 다른 번호로 보인다.
5. **차이 규모 신호 없음** — 열어 봐야 크게 다른지 한 줄 다른지 알 수 있었다.

여기서 잠그는 것은 그 다섯의 **구조**다(§16.7 G10 — 점수정이 아니라 구조 테스트).
검증은 JS 소스 구조 계약 + CSS 규칙. 주석 문구가 통과시키지 못하도록 비교는 **주석을 걷어낸**
본문에서 한다(이 저장소가 반복해 겪은 함정).
"""
from __future__ import annotations

import re
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "src"
COMPOSER = _WEB / "static" / "app" / "composer.js"
DIFF = _WEB / "static" / "app" / "attach-diff.js"
CSS = _WEB / "static" / "css" / "chat.css"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


def _fn_body(text: str, name: str) -> str:
    pat = r"^(?:export\s+)?(?:async\s+)?function\s+"
    m = re.search(pat + re.escape(name) + r"\s*\(", text, re.M)
    assert m, f"{name} 을 찾지 못했다"
    rest = text[m.end():]
    nxt = re.search(pat + r"\w+\s*\(", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _css_rule(css: str, selector: str) -> str:
    i = css.find(selector + " {")
    assert i >= 0, f"CSS 규칙이 없다: {selector}"
    return css[i: css.find("}", i)]


# ── G1. 공통영역 — 같은 파일의 계보를 하나의 카드가 감싼다 ──────────────────

def test_lineage_group_card_exists_and_encloses():
    """그룹 카드가 **실제 컨테이너**다 — 이름표만 바꾼 것이 아니라 자식을 담는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert 'className = "attach-lineage-group"' in body, "그룹 카드 컨테이너가 없다"
    assert 'className = "attach-lineage-group-head"' in body, "그룹 머리가 없다"
    assert 'className = "attach-lineage-group-body"' in body, "그룹 본문(멤버 자리)이 없다"
    assert re.search(r"el\.append\(head,\s*body\)", body), (
        "머리·본문을 카드에 넣지 않는다 — 만들고 안 붙이면 화면은 그대로다")
    assert re.search(r"return\s*\{[^}]*\bbody\b", body, re.S), (
        "호출부가 멤버를 넣을 자리(body)를 돌려받지 못한다")


def test_rows_are_appended_to_the_group_not_the_flat_list():
    """멤버 행이 **카드 안**으로 들어간다.

    이 단언이 이 cycle 의 핵심이다 — 카드를 그려도 행이 `listEl` 직속으로 남으면 화면은
    종전과 똑같이 평면이다(배선 사각: 만들었는데 안 쓰는 결함 클래스).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_hostEl.appendChild(entry)" in body, (
        "행을 그룹이 아닌 목록에 직접 붙인다 — 카드가 아무것도 감싸지 않는다")
    assert not re.search(r"^\s*listEl\.appendChild\(entry\);", body, re.M), (
        "행을 listEl 에 직접 붙이는 경로가 남아 있다 — 카드를 우회한다")
    assert re.search(r"_hostEl\s*=\s*_card\.body", body), (
        "형제 계보가 있어도 host 가 카드 본문으로 바뀌지 않는다")


def test_group_card_is_created_once_per_filename():
    """카드는 파일명당 **한 번** 만든다 — 멤버마다 만들면 계보 수만큼 카드가 쌓인다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_groupCards" in body, "카드 재사용 맵이 없다"
    assert re.search(r"if\s*\(!_card\)\s*\{", body), "이미 만든 카드를 재사용하지 않는다"
    assert re.search(r"_groupCards\.set\(", body), "만든 카드를 등록하지 않는다"


def test_group_members_are_rendered_adjacently():
    """계보 멤버가 목록에서 **붙어서** 나온다.

    카드는 연속한 형제만 감쌀 수 있다 — 서버 순서가 계보를 흩어 놓으면 카드 안에 첫 멤버만
    들어가고 나머지는 뒤쪽에 남는다(부분 그룹핑이 오히려 더 헷갈린다).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_orderedArr" in body, "렌더 순서를 확정하지 않는다"
    assert re.search(r"for\s*\(const a of _orderedArr\)", body), (
        "루프가 여전히 서버 순서(arr)를 그대로 돈다")
    assert "_emittedGroups" in body, "그룹을 통째로 방출한 사실을 기억하지 않는다 — 중복 렌더된다"
    assert re.search(r"_orderedArr\.push\(\.\.\.grp\)", body), (
        "그룹을 통째로 넣지 않는다 — 멤버가 흩어진 채 남는다")


def test_single_lineage_attachments_stay_ungrouped():
    """계보가 하나뿐인 흔한 첨부는 **카드를 두르지 않는다**.

    모든 행을 카드로 감싸면 enclosure 가 아무것도 구분하지 못한다(공통영역의 신호가 죽는다).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"if\s*\(grp\.length\s*<\s*2\)\s*\{\s*_orderedArr\.push\(x\);", body)
    assert m, "단일 계보를 그룹 경로에서 빼지 않는다"
    i_gate = body.find("if (_hasSiblings) {")
    i_card = body.find("_attachLineageGroupCard(")
    assert 0 <= i_gate < i_card, "카드 생성이 형제 유무 가드 안에 있지 않다"


# ── G2. 분기를 그린다 — 산문이 아니라 레일/커넥터 ──────────────────────────

def test_unnamed_attachments_are_not_grouped_together():
    """이름 없는 첨부는 **묶지 않는다** — 빈 이름이 한 키로 모이면 서로 무관한 첨부가
    한 카드 안에서 "같은 파일의 갈래" 로 단정된다(근거 없는 주장).

    배지 시절에는 잘못 센 숫자였지만 카드는 enclosure 로 **관계를 주장**한다 — 같은 데이터
    결함이 더 강한 거짓말이 된다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"const nm = String\(x\.original_filename \|\| \"\"\);\s*\n\s*if \(!nm\) continue;", body)
    assert m, "빈 파일명을 그룹핑에서 제외하지 않는다"


def test_branch_is_marked_on_the_row_for_css_to_draw():
    """분기 여부가 **클래스로** 행에 새겨진다 — CSS 가 그릴 근거."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert 'entry.classList.add("in-lineage-group")' in body, "그룹 멤버 표식이 없다"
    assert re.search(r'entry\.classList\.add\("is-branch"\)', body), (
        "갈라져 나온 계보를 표시하지 않는다 — CSS 가 분기를 그릴 수 없다")
    # 판정식 자체(서수 아님)는 test_branch_indent_uses_branch_data_not_ordinal 이 잠근다.


def test_css_draws_rail_and_connector():
    """레일(세로줄) + elbow(가지)가 **실제로 그려진다**.

    클래스만 붙이고 CSS 가 없으면 화면은 그대로다 — 이 저장소가 반복해 겪은 배선 사각.
    """
    css = _src(CSS)
    rail = _css_rule(css, ".attach-lineage-group-body::before")
    assert "position: absolute" in rail and "width:" in rail, "레일이 그려지지 않는다"
    elbow = _css_rule(css, ".attach-list-entry.in-lineage-group::before")
    assert "position: absolute" in elbow and "height:" in elbow, "가지(elbow)가 그려지지 않는다"
    branch = _css_rule(css, ".attach-lineage-group-body > .attach-list-entry.is-branch")
    assert "margin-left" in branch, "갈라진 계보가 들여쓰기로 구분되지 않는다"


def test_group_card_is_a_common_region_not_bare_rows():
    """카드가 **테두리+배경**을 갖는다 — 근접성만으로는 그룹이 전달되지 않는다(NN/g)."""
    rule = _css_rule(_src(CSS), ".attach-lineage-group")
    assert "border:" in rule, "테두리가 없다 — enclosure 가 성립하지 않는다"
    assert "background:" in rule, "배경 구분이 없다"


# ── G3. 비교는 그룹의 1급 액션 ─────────────────────────────────────────────

def test_group_level_compare_button_exists_and_is_wired():
    """그룹 머리의 비교 버튼이 **모달을 실제로 연다**.

    §16.7 G3 — 주장한 affordance 는 배선까지 확인한다. 버튼만 있고 핸들러가 없으면
    사용자는 눌러 보고 나서야 안다.
    """
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert 'className = "attach-lineage-group-cmp"' in card, "그룹 비교 버튼이 없다"
    assert "aria-label" in card, "접근성 이름이 없다 — 스크린리더에 '⇄' 만 읽힌다"
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert re.search(r"_card\.cmpBtn\.addEventListener\(\s*\"click\"", body), (
        "그룹 비교 버튼에 핸들러가 없다 — 눌러도 아무 일이 없다")
    assert "openAttachmentDiffModal(" in body, "그룹 비교가 모달을 열지 않는다"


def test_group_compare_opens_on_the_lineage_axis():
    """그룹 비교는 **계보 축**으로 열린다.

    사용자가 "계보 비교" 를 눌렀는데 버전 화면이 뜨면 축 토글을 스스로 찾아 눌러야 한다
    (의도와 착지의 불일치). 이 계보에 버전이 여럿이면 종전 기본값은 버전 축이었다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"openAttachmentDiffModal\(\s*_first\.id,(.+?)\);", body, re.S)
    assert m, "그룹 비교의 모달 호출을 찾지 못했다"
    assert 'axis: "time"' in m.group(1), f"계보 축을 요청하지 않는다: {m.group(1).strip()}"
    # 모달이 그 요청을 실제로 존중하는가 — 호출 쪽만 고치면 착지는 그대로다.
    diff = _code_only(_src(DIFF))
    assert re.search(r'preselect\?\.axis\s*===\s*"time"', diff), (
        "모달이 호출부의 축 지정을 무시한다")
    assert re.search(r'hasLineageAxis\s*&&\s*preselect\?\.axis\s*===\s*"time"', diff), (
        "계보 축이 없을 때도 time 으로 열려 select 가 비어 뜬다")


def test_group_compare_fetches_lineages_before_opening():
    """모달은 `lineages` 가 있어야 계보 축이 성립한다 — 열기 전에 조회한다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    i = body.find("_card.cmpBtn.addEventListener")
    seg = body[i: i + 1400]
    assert "/versions" in seg, "계보 정보를 조회하지 않는다 — 모달이 축 없이 열린다"
    assert "vr?.lineages" in seg, "조회한 계보를 모달에 넘기지 않는다"
    assert "catch" in seg and "showToast" in seg, (
        "조회 실패가 조용히 삼켜진다 — 눌러도 아무 일이 없는 것처럼 보인다")


# ── G4. 서수 → 정체성 ──────────────────────────────────────────────────────

def test_lineage_identity_is_the_row_label_not_an_ordinal():
    """행의 1차 라벨이 **누구의 갈래인가**를 말한다 — 서수도, 되풀이되는 파일명도 아니다.

    REQ-20260901: 정체성이 배지에서 **행 라벨**로 올라왔다. 그룹 카드가 파일명을 이미 한 번
    말하므로, 행에서 파일명을 되풀이하는 대신 그 자리를 정체성에 준다(위계 역전).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"_rowLabel\s*=\s*(.+?);\n", body, re.S)
    assert m, "행 라벨 조립을 찾지 못했다"
    label = m.group(1)
    assert "_hasSiblings" in label, "그룹 밖에서도 라벨을 바꾼다 — 단독 첨부는 파일명이 맞다"
    assert "original_filename" in label, "그룹이 아닐 때 파일명으로 돌아가지 않는다"
    assert "_identityLabel" in label, "라벨이 계보 정체성을 쓰지 않는다"
    ident = re.search(r"_identityOf\s*=\s*\(x\)\s*=>(.+?);\n", body, re.S)
    assert ident and "is_assistant_generated" in ident.group(1) and "uploader_username" in ident.group(1), (
        "정체성이 작성 주체·업로더를 말하지 않는다")
    # 서수는 **기본 라벨**이 아니다. 다만 정체성이 겹치는 경계(같은 사람이 같은 이름을 독립
    # 업로드)에서는 서수가 유일한 구분 수단이라 그때만 덧붙인다(codex P2) — 그 분기 안에만
    # 있어야 한다.
    ordinal = re.search(r"계보 \$\{_linIdx\}/\$\{_linTotal\}", body)
    if ordinal:
        gated = re.search(
            r"_identityLabel\s*=\s*_identityCollides\s*\?[^;]*계보 \$\{_linIdx\}/\$\{_linTotal\}",
            body, re.S)
        assert gated, "서수가 충돌 분기 밖에서 기본 라벨로 쓰인다"
    # 서수를 **버리지는 않는다** — title 로 내린다(정보를 없애는 것이 목적이 아니다).
    assert "_linTitle" in body and "_linIdx" in body, "서수를 title 에서도 잃었다"


def test_branch_chip_carries_only_the_branch_fact():
    """분기 칩은 **갈라졌다는 사실만** 진다 — 정체성은 라벨이 이미 말했다.

    둘을 한 칩에 담으면 같은 행에서 같은 사실이 두 번 나온다(사용자가 지적한 중복 축).
    갈라지지 않은 계보에는 칩 자체가 붙지 않는다 — 늘 뜨는 배지는 정보가 아니다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"linBadge\s*=\s*(_branched[^;]*);", body, re.S)
    assert m, "분기 칩 조립을 찾지 못했다"
    chip = m.group(1)
    assert "갈라짐" in chip, "분기 사실을 말하지 않는다"
    assert "_upName" not in chip and "_linWho" not in chip, (
        "칩이 정체성을 되풀이한다 — 라벨과 겹친다")
    assert chip.rstrip().endswith('""'), "갈라지지 않은 계보에도 칩이 붙는다"


def test_identity_badge_still_does_not_claim_ownership():
    """정체성 문구가 소유권을 단정하지 않는다 (선행 cycle 계약 유지).

    목록 payload 에 업로더 account_id 가 없다 — 그룹 대화에서 남의 업로드를 "내 것" 이라
    말하게 된다. 서수를 정체성으로 바꾸면서 이 경계를 넘기 쉬우므로 여기서 다시 잠근다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    for claim in ('"내 ', '"내가 ', "'내 ", "'내가 "):
        assert claim not in body, f"계보 문구가 소유권을 단정한다({claim!r})"


def test_branched_lineage_is_marked_in_the_badge():
    """갈라져 나온 계보는 배지에서도 드러난다(글리프 + 파선 테두리 — 색 하나에 의존하지 않는다)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert re.search(r"_branched\s*=\s*_originId\s*>\s*0", body), "분기 판정이 없다"
    assert '"⤷ "' in body or "⤷" in body, "분기 글리프가 없다"
    rule = _css_rule(_src(CSS), ".attach-list-item-lineage.branched")
    assert "dashed" in rule, "색·글리프 외의 형태 신호가 없다(색각 이상 사용자에게 소실)"


# ── G5. 변경 규모 — 열기 전에 알린다 ───────────────────────────────────────

def test_size_delta_chip_is_computed_and_rendered():
    """크기 차이 칩이 **계산되고 마크업에 들어간다**."""
    helper = _code_only(_fn_body(_src(COMPOSER), "_attachSizeDelta"))
    assert "Number.isFinite" in helper, "비정상 값이 그대로 렌더된다"
    assert re.search(r'd === 0', helper), "차이가 0 일 때도 칩을 만든다(정보 없는 칩)"
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "sizeDeltaChip" in body, "크기 차이 칩을 만들지 않는다"
    assert "${sizeDeltaChip}" in body, "만든 칩을 마크업에 넣지 않는다(배선 사각)"
    assert "attach-list-item-sizedelta" in body, "칩에 스타일 훅이 없다"
    _css_rule(_src(CSS), ".attach-list-item-sizedelta")


# ── G7. 적대 리뷰(codex) 지적 조치 — 없는 관계를 주장하지 않는다 ──────────

def test_branch_indent_uses_branch_data_not_ordinal():
    """들여쓰기(=파생 주장)는 **분기 데이터**로만 붙인다 (codex P1).

    서수(`_linIdx > 1`)로 붙이면, 같은 이름을 두 번 **독립 업로드**한 경우에도 두 번째가
    첫 번째에서 갈라져 나온 것처럼 그려진다 — 화면이 없는 관계를 만들어낸다. 목록을 파일명으로
    묶는 것 자체는 옳지만(사용자가 찾는 것은 "이 이름으로 뭐가 있나"), **파생은 별개 주장**이다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r'if \(([^)]+)\) entry\.classList\.add\("is-branch"\)', body)
    assert m, "분기 표식 부여를 찾지 못했다"
    cond = m.group(1).strip()
    assert cond == "_branched", f"분기 표식이 데이터가 아닌 것으로 판정된다: {cond}"
    assert re.search(r"_branched\s*=\s*_originId\s*>\s*0", body), (
        "_branched 가 분기 부모 id 로 판정되지 않는다")


def test_group_count_title_does_not_claim_derivation():
    """그룹 머리의 계보 수 설명이 **파생을 주장하지 않는다** (codex P1 동류).

    묶는 기준은 이름이다. "갈라진" 이라고 쓰면 독립 업로드 2건에도 관계를 단정하게 된다.
    """
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    m = re.search(r"countEl\.title\s*=\s*(.+?);\n", card)
    assert m, "계보 수 설명을 찾지 못했다"
    assert "갈라진" not in m.group(1), f"이름으로 묶은 것에 파생을 주장한다: {m.group(1).strip()}"


def test_group_compare_guards_against_stale_render():
    """응답이 늦게 오는 사이 화면이 바뀌면 **모달을 열지 않는다** (codex P2).

    대화를 옮기거나 휴지통으로 전환하면 이 카드는 이미 DOM 에서 떨어졌는데, 그때 열면
    지금 보고 있지 않은 대화의 비교 화면이 위에 뜬다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    i = body.find("_card.cmpBtn.addEventListener")
    seg = body[i: i + 1600]
    assert "document.contains(_card.el)" in seg, "카드가 문서에서 떨어졌는지 보지 않는다"
    assert "state.activeConversationId !== convId" in seg, "대화가 바뀌었는지 보지 않는다"
    assert seg.index("document.contains") < seg.index("openAttachmentDiffModal"), (
        "가드가 모달을 연 뒤에 온다 — 순서가 뒤바뀌면 가드가 아니다")


def test_group_card_is_a_group_in_the_accessibility_tree():
    """시각적 enclosure 를 **접근성 트리에도** 전달한다 (codex P2).

    맨 `div` 면 스크린리더는 머리와 자식 행을 한 덩어리로 인식하지 못한다 — 눈으로만 보이는
    그룹은 그룹이 아니다.
    """
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert re.search(r'setAttribute\("role",\s*"group"\)', card), "role=group 이 없다"
    assert re.search(r'setAttribute\("aria-label"', card), "그룹 이름이 없다"


def test_row_accessible_name_distinguishes_lineages():
    """같은 이름의 계보가 여럿이면 **행의 접근성 이름이 서로 달라야** 한다 (codex P2).

    화면에서는 칩·들여쓰기가 구분하지만 칩은 포커스 대상이 아니라 title 이 읽히지 않는다 —
    스크린리더로는 세 행이 모두 "report.csv 원문 보기" 가 된다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_srWho" in body, "행 접근성 이름에 계보 정체성을 싣지 않는다"
    m = re.search(r'nameBtn\.setAttribute\("aria-label",\s*(.+?)\);', body)
    assert m and "_srWho" in m.group(1), (
        f"만든 정체성 문구를 접근성 이름에 넣지 않는다: {m.group(1) if m else None}")
    assert re.search(r"_srWho\s*=\s*_hasSiblings", body), (
        "계보가 하나뿐인 흔한 첨부에도 군더더기를 붙인다")


def test_version_toggle_exposes_expanded_state():
    """펼침 상태를 `▾/▴` 문자에만 두지 않는다 (codex P2) — `aria-expanded` 로 노출한다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert body.count('setAttribute("aria-expanded"') >= 3, (
        "초기·토글·로드완료 세 지점 중 빠진 곳이 있다 — 한 곳만 빠져도 상태가 어긋난다")
    assert re.search(r'aria-expanded",\s*hidden \? "false" : "true"', body), (
        "토글 시 상태가 따라가지 않는다")


def test_size_delta_treats_unknown_size_as_unknown():
    """크기 미상을 **0 바이트로 읽지 않는다** (codex P2).

    `null`/`undefined` 를 `|| 0` 으로 흡수하면 "모른다" 가 "0 이다" 로 바뀌어 `−100000B`
    (파일이 줄었다)를 화면이 단정한다. 모르면 아무 말도 하지 않는 것이 맞다.
    """
    helper = _code_only(_fn_body(_src(COMPOSER), "_attachSizeDelta"))
    assert "|| 0" not in helper, "미상 값을 0 으로 흡수한다"
    assert re.search(r"!Number\.isFinite\(a\)\s*\|\|\s*!Number\.isFinite\(b\)", helper), (
        "두 값 모두의 유한성을 보지 않는다")


def test_group_signals_meet_contrast_floor():
    """그룹 테두리·레일·텍스트가 **보이는** 색이다 (codex P2).

    종전 초안은 `var(--border)`(#e6e5e0)를 카드 배경(#f0efea) 위에 써 대비 1.10:1 — 사실상
    보이지 않았다. 그룹 테두리와 레일은 «내용 이해에 필요한 그래픽»(WCAG 1.4.11)이지 장식이
    아니다 — 이 카드가 곧 "같은 파일의 갈래" 라는 유일한 신호다.
    """
    css = _src(CSS)
    for sel in (".attach-lineage-group",
                ".attach-lineage-group-body::before",
                ".attach-list-entry.in-lineage-group::before"):
        rule = _css_rule(css, sel)
        assert "var(--border)" not in rule, (
            f"{sel} 가 배경과 1.10:1 인 --border 를 쓴다 — 신호가 배경에 묻힌다")
    assert "#8c8a7c" in _css_rule(css, ".attach-lineage-group-body::before"), "레일 색이 약하다"
    name = _css_rule(css, ".attach-lineage-group .attach-list-item-name-text")
    # 주석에 근거로 적힌 색이 아니라 **선언된 color** 를 본다.
    decl = re.search(r"color:\s*([^;]+);", re.sub(r"/\*.*?\*/", "", name, flags=re.S))
    assert decl and "#807d72" not in decl.group(1), (
        f"낮춘 파일명이 AA(4.5:1) 미달 색이다 — 낮춤 ≠ 못 읽게 함: {decl and decl.group(1)}")


# ── G8. 적대 리뷰 2라운드 — 조용한 오답·무음 절단 ──────────────────────────

def test_group_compare_refuses_when_lineage_axis_missing():
    """계보 축이 없으면 **열지 않는다** (codex 2R P1).

    서버의 계보 해소는 fail-soft 라 `lineages: []` 로 떨어질 수 있다. 그 상태로 모달을 열면
    축 지정이 조용히 무시되고 이 계보의 **버전 비교**가 뜬다 — 사용자가 「계보 비교」를 눌렀는데
    다른 것을 비교하는 **조용한 오답**이다. 못 하면 못 한다고 말한다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    i = body.find("_card.cmpBtn.addEventListener")
    seg = body[i: i + 2200]
    m = re.search(r"if \(_lins\.length < 2\) \{(.+?)\}", seg, re.S)
    assert m, "계보 축 부재를 검사하지 않는다 — 축이 조용히 버전 비교로 격하된다"
    assert "showToast" in m.group(1) and "return" in m.group(1), (
        "축이 없을 때 조용히 진행한다 — 알리고 멈춰야 한다")
    assert seg.index("_lins.length < 2") < seg.index("openAttachmentDiffModal"), (
        "검사가 모달을 연 뒤에 온다 — 가드가 아니다")


def test_lineage_truncation_is_reported_not_silent():
    """계보 목록이 상한에 걸려 잘리면 **그 사실을 밝힌다** (codex 2R P1, §16.7 G9-b).

    밝히지 않으면 목록의 그룹 카드는 "계보 21" 이라 말하는데 비교 화면 선택지는 20개뿐이고,
    사용자는 빠진 계보가 있다는 것 자체를 알 수 없다 — 화면이 없는 완전성을 주장한다.
    """
    store = _src(_WEB / "routers" / "_conv_store.py")
    i = store.find("def _load_filename_lineage_heads")
    seg = store[i: i + 3200]
    assert re.search(r"int\(limit\)\s*\+\s*1", seg), (
        "정확히 limit 만 읽는다 — '마침 20개' 와 '잘림' 을 구분할 수 없다")
    assert "_lineage_heads_truncated" in seg, "절단 사실을 표식으로 남기지 않는다"
    ep = _src(_WEB / "routers" / "attachments.py")
    assert '"lineages_truncated"' in ep, "응답에 절단 신호를 싣지 않는다"
    assert "_lineage_heads_truncated" in ep, "로더의 표식을 읽지 않는다"
    diff = _code_only(_src(DIFF))
    assert "attach-diff-trunc" in diff, "모달이 절단 사실을 화면에 밝히지 않는다"
    assert re.search(r"preselect\?\.truncated", diff), "모달이 절단 신호를 보지 않는다"
    _css_rule(_src(CSS), ".attach-diff-trunc")


def test_async_error_path_also_guards_staleness():
    """실패 토스트도 **지금 화면**의 것일 때만 띄운다 (codex 2R P2).

    대화를 옮긴 뒤 옛 요청의 실패 토스트가 뜨면 사용자는 지금 화면이 실패한 줄로 읽는다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    i = body.find("_card.cmpBtn.addEventListener")
    seg = body[i: i + 2400]
    catch_i = seg.find("} catch (e) {")
    assert catch_i > 0, "그룹 비교의 catch 를 찾지 못했다"
    catch_seg = seg[catch_i: catch_i + 500]
    assert "document.contains(_card.el)" in catch_seg, "실패 경로에 stale 가드가 없다"
    assert catch_seg.index("document.contains") < catch_seg.index("showToast"), (
        "가드가 토스트 뒤에 온다 — 이미 떴다")


def test_unknown_size_is_rejected_before_number_conversion():
    """미상 크기를 **변환 전에** 막는다 (codex 2R P2).

    `Number(null) === 0` 이라 변환 뒤 `isFinite` 검사는 미상을 통과시킨다 — "모른다" 가
    "0 바이트" 로 바뀌어 `+97.7KB` 같은 없는 사실을 화면이 단정한다.
    """
    helper = _code_only(_fn_body(_src(COMPOSER), "_attachSizeDelta"))
    m = re.search(r"_bad\s*=\s*\(v\)\s*=>(.+?);", helper, re.S)
    assert m, "변환 전 미상 판정이 없다"
    guard = m.group(1)
    for tok in ("null", "undefined", '""'):
        assert tok in guard, f"미상 판정이 {tok} 을 걸러내지 않는다"
    assert helper.index("_bad(bytes)") < helper.index("Number(bytes)"), (
        "미상 판정이 변환 뒤에 온다 — Number(null)===0 을 막지 못한다")
    # 호출부가 `|| 0` 으로 헬퍼의 가드를 무력화하지 않는지 (미상 기준을 0 으로 바꿔 넘기기).
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert not re.search(r"_base\s*=\s*Number\(_sibs\[0\]\?\.size\s*\|\|\s*0\)", body), (
        "호출부가 미상 기준을 0 으로 바꿔 넘겨 헬퍼의 가드를 무력화한다")


def test_size_delta_only_on_derived_lineages():
    """기준이 되는 첫 계보에는 칩을 붙이지 않는다(자기 자신과의 차이는 0)."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert re.search(r"if\s*\(_hasSiblings\s*&&\s*_linIdx\s*>\s*1\)", body), (
        "첫 계보에도 크기 차이를 붙인다")


def test_size_delta_does_not_claim_content_difference():
    """문구가 **크기** 차이임을 밝힌다 — 내용 차이라고 말하지 않는다 (§16.7 G3 주장-사실 정합).

    우리가 아는 것은 바이트뿐이다. "8KB 차이" 를 "내용이 그만큼 다름" 으로 읽히게 두면
    같은 크기의 전혀 다른 파일에서 화면이 거짓말한다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    i = body.find("attach-list-item-sizedelta")
    seg = body[max(0, i - 500): i + 500]
    assert "크기" in seg, "크기 차이임을 밝히지 않는다"
    assert "비교에서 확인" in seg, "내용 차이는 비교에서 봐야 함을 안내하지 않는다"


# ── G6. 카피 예산 — 같은 낱말이 서로 다른 뜻으로 흩어지지 않는다 ───────────

def test_versions_box_note_is_compressed():
    """버전 박스 안내가 짧아졌다 — 그룹 카드가 파일명·계보 수·비교를 이미 이고 있다.

    종전 문구는 한 줄에 네 사실("이 계보: 누구 · 갈라짐 · 파일 N개 / 같은 이름의 다른 계보 M개")
    을 담아 240px 폭에서 세 줄로 접혔다 (§16.8 사용자 대면 텍스트 예산).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    m = re.search(r"note\.textContent\s*=\s*(.+?);\n", body, re.S)
    assert m, "계보 안내 문구를 찾지 못했다"
    txt = m.group(1)
    assert "이 계보:" not in txt, "박스 안에서 '이 계보:' 를 다시 말한다(스코프 중복)"
    assert "같은 이름의 다른 계보" not in txt, "파일명 스코프를 문장에서 되풀이한다"
    assert "다른 계보" in txt, "다른 계보의 존재를 말하지 않는다(선행 cycle 계약)"


def test_group_head_says_filename_once():
    """파일명은 그룹 머리에서 한 번 — 좁은 패널의 가용 폭을 갈래 정보에 돌려준다."""
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert 'className = "attach-lineage-group-name"' in card, "그룹 머리에 파일명이 없다"
    rule = _css_rule(_src(CSS), ".attach-lineage-group-name")
    assert "text-overflow: ellipsis" in rule, "긴 파일명이 카드를 밀어낸다"


def test_single_version_toggle_label_says_what_it_opens():
    """단건 계보의 토글은 「상세」다 — 그룹 머리가 이미 「계보 N」을 말한다.

    종전 fallback 은 `계보 N개` 였다(그 시절엔 이 토글을 열어야 계보 비교에 닿았다). 이제
    계보 비교는 그룹 머리의 1급 액션이므로, 같은 문구를 옆에서 되풀이하면 **누르면 다른
    계보가 나올 것처럼** 읽힌다(라이브 실측 2026-08-31).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"verToggleLabel\s*=\s*(.+?);\n", body, re.S)
    assert m, "토글 라벨을 찾지 못했다"
    label = m.group(1)
    assert "계보" not in label, f"토글이 그룹 머리와 같은 낱말을 되풀이한다: {label.strip()}"
    assert "상세" in label, f"토글이 여는 것(이 계보의 상세)을 말하지 않는다: {label.strip()}"


def test_author_color_axis_is_actually_applied():
    """작성 주체 색축이 **실제 토큰**으로 칠해진다.

    인접 규칙은 `var(--muted)` 를 쓰는데 그 토큰은 이 저장소에 정의돼 있지 않다
    (실재 토큰은 `--text-muted`) — 그래서 사용자 계보 칩이 본문색 그대로 렌더돼 AI 칩과의
    색 대비가 성립하지 않았다(라이브 computed 실측 rgb(38,37,30) = 본문색). 정의되지 않은
    토큰은 **조용히 무시**되므로 CSS 를 읽는 것만으로는 드러나지 않는다.
    """
    css = _src(CSS)
    rule = _css_rule(css, ".attach-lineage-group .attach-list-item-lineage")
    assert "var(--muted)" not in rule, "정의되지 않은 토큰을 다시 쓴다 — 색이 칠해지지 않는다"
    assert "--text-2" in rule, "실재 토큰으로 중립색을 주지 않는다(대비 상향분 반영)"
    ai = _css_rule(css, ".attach-lineage-group .attach-list-item-lineage.ai")
    assert "#2563eb" in ai, "AI 계보 색이 없다 — 두 주체가 같은 색이면 축이 성립하지 않는다"
    # REQ-20260901: 그룹 안 행 라벨은 이제 **파일명이 아니라 정체성**이라 낮추지 않고 올린다.
    name = _css_rule(css, ".attach-lineage-group .attach-list-item-name-text")
    assert "font-weight: 600" in name, "정체성 라벨이 1순위로 올라오지 않았다"
    assert "--text-2" in name, "정체성 라벨이 AA 미달 색이다"
    ai = _css_rule(css, ".attach-lineage-group .attach-list-item-name-text.is-ai-lineage")
    assert "#2563eb" in ai, "작성 주체 색축이 라벨로 옮겨오지 않았다"


def test_group_head_wraps_instead_of_clipping():
    """240px 최소 폭에서 비교 버튼이 잘리지 않고 다음 줄로 접힌다(패널 최소 폭 규약)."""
    rule = _css_rule(_src(CSS), ".attach-lineage-group-head")
    assert "flex-wrap: wrap" in rule, "좁은 폭에서 버튼이 잘린다"
    cmp_rule = _css_rule(_src(CSS), ".attach-lineage-group-cmp")
    assert "flex-shrink: 0" in cmp_rule and "white-space: nowrap" in cmp_rule, (
        "비교 버튼이 찌그러진다")

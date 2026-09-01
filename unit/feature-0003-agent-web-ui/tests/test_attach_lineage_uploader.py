"""REQ-20260901-attach-lineage-uploader — 공유 대화에서 계보를 **누가 올렸는지**로 가른다
+ 그룹 카드 안 되풀이 제거 (사용자 지적 2026-09-01).

## 무엇이 잘못돼 있었나

선행 cycle(REQ-20260831)이 계보를 카드로 묶고 정체성 칩을 올렸지만, **사람이 올린 계보는 전부
「사용자 계보」** 였다. 1:1 대화에서는 맞는 말이지만 **공유 대화에서는 서로 다른 멤버의 계보가
글자 하나 다르지 않게** 보인다.

라이브 실측(2026-09-01): 대화 `20260813083932-46763d6e` 는 계정 **10·50** 이 같은 이름의 파일을
각각 올려 동명 계보 4쌍이 공존한다. 화면에는 그 8행이 전부 「사용자 계보」로 뜬다.

⭐ **같은 화면에서 assistant 는 이미 구분하고 있었다.** `_build_attachment_context_section` 의
`## FILE VERSION LINEAGES` 는 `uploaded by jmkimmasangsoft.com` / `uploaded by admin` 으로
계보마다 업로더를 이름으로 싣는다(라이브 프롬프트 렌더로 확인). 즉 **모델은 아는데 사용자
화면만 몰랐다** — 데이터가 없어서가 아니라 목록 payload 가 그 필드를 버려서였다.

두 번째 지적은 **되풀이**다. 그룹 카드 하나에 같은 파일명이 3번(머리 1 + 행 2), 같은 종류
아이콘이 3번 실렸다. 좁은 패널에서 그 반복이 정작 갈래를 가르는 정보를 밀어낸다.

여기서 잠그는 것은 그 둘의 **구조**다(§16.7 G10).
"""
from __future__ import annotations

import re
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "src"
COMPOSER = _WEB / "static" / "app" / "composer.js"
CSS = _WEB / "static" / "css" / "chat.css"
CONV = _WEB / "routers" / "conversations.py"
STORE = _WEB / "routers" / "_conv_store.py"


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


# ── U1. 서버가 업로더를 싣는다 ─────────────────────────────────────────────

def test_list_payload_carries_uploader_account():
    """목록 직렬화가 **업로더 account_id** 를 싣는다 — 없으면 화면이 계보를 가를 근거가 없다."""
    conv = _src(CONV)
    assert re.search(r'ser\["account_id"\]\s*=\s*_uid or None', conv), (
        "업로더를 싣지 않는다 — 공유 대화에서 계보가 전부 '사용자 계보' 로 뭉뚱그려진다")
    assert re.search(r'_uid\s*=\s*int\(row\.get\("AccountId"\)\s*or\s*0\)', conv), (
        "업로더를 행에서 직접 읽지 않는다")


def test_list_endpoint_resolves_uploader_names_in_one_query():
    """업로더 **표시명**을 한 번의 IN 조회로 붙인다 — 행마다 조회하면 N+1."""
    src = _src(CONV)
    i = src.find("uploader_names")
    assert i > 0, "업로더 표시명 해소가 없다"
    body = src[i: i + 1800]
    assert "WebAccounts" in body, "계정 표시명 원천을 조회하지 않는다"
    assert "IN (" in body, "IN 조회가 아니다 — 행마다 왕복한다"
    assert 'ser["uploader_username"]' in src, "해소한 이름을 응답에 싣지 않는다"


def test_uploader_name_failure_is_soft_and_not_invented():
    """이름 해소 실패가 목록을 막지 않고, **없는 이름을 만들지도 않는다**.

    실패를 조용히 삼켜 「내 파일」로 격하하면 그룹 대화에서 남의 업로드를 내 것이라 말하게 된다
    (선행 cycle 이 세운 계약).
    """
    src = _src(CONV)
    i = src.find("uploader_names")
    body = src[i: i + 2000]
    assert "except Exception" in body and "warning" in body, (
        "이름 해소 실패가 로그 없이 사라진다 — 사실이 빠진 것을 알 수 없다")
    assert re.search(r'ser\["uploader_username"\]\s*=\s*uploader_names\.get\(_uid\)\s*or\s*None', src), (
        "미해소를 빈 문자열/기본 이름으로 메운다 — 없는 사실을 만든다")


# ── U2. 공유 대화에서만 이름으로 가른다 ────────────────────────────────────

def test_identity_uses_uploader_name_in_shared_conversations():
    """공유 대화면 **업로더 이름**으로, 1:1 이면 종전 문구로.

    1:1 은 업로더가 늘 자기 자신이라 이름이 정보 0 이면서 240px 이름줄만 먹는다(§16.8).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_isShared" in body, "공유 대화 판정이 없다"
    assert re.search(r"_isShared\s*=\s*isGroupConversation\(_convForList\)", body), (
        "저장소 단일 술어(isGroupConversation)를 쓰지 않는다 — 판정이 두 벌이 된다")
    m = re.search(r"_identityOf\s*=\s*\(x\)\s*=>(.+?);\n", body, re.S)
    assert m, "계보 정체성 헬퍼를 찾지 못했다"
    ident = m.group(1)
    assert "_isShared" in ident and "uploader_username" in ident, (
        "공유 대화에서도 업로더를 쓰지 않는다 — 멤버별 계보가 구분되지 않는다")


def test_unknown_uploader_is_stated_not_guessed():
    """이름을 모르면 **「업로더 미상」** 이라 적는다 — 「내 파일」로 격하하지 않는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "업로더 미상" in body, "미상 상태의 문구가 없다 — 모르는 것을 지어내게 된다"
    for claim in ('"내 ', '"내가 ', "'내 ", "'내가 "):
        assert claim not in body, f"소유권을 단정한다({claim!r})"


def test_uploader_name_comes_from_the_payload_not_the_session():
    """이름은 **payload** 에서 온다 — 세션 사용자로 대신하면 남의 파일에 내 이름이 붙는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    body_ident = re.search(r"_identityOf\s*=\s*\(x\)\s*=>(.+?);\n", body, re.S)
    assert body_ident, "정체성 헬퍼가 없다"
    expr = body_ident.group(1)
    assert "uploader_username" in expr, f"payload 가 아닌 곳에서 이름을 가져온다: {expr}"
    assert "state.user" not in expr, "세션 사용자를 업로더로 단정한다"


# ── U3. 되풀이 제거 ────────────────────────────────────────────────────────

def test_filename_is_not_repeated_inside_the_group_card():
    """그룹 안 행은 파일명을 되풀이하지 않는다 — 카드 머리가 이미 한 번 말했다.

    ⚠ 요소 자체는 지우지 않는다(「원문 보기」 클릭 대상 + 접근성 이름). **문구만** 바꾼다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r'attach-list-item-name-text.*?>\$\{escapeHtml\((\w+)\)\}</span>', body, re.S)
    assert m, "행 라벨 렌더를 찾지 못했다"
    assert m.group(1) == "_rowLabel", (
        f"행이 여전히 파일명을 직접 렌더한다: {m.group(1)}")
    # 클릭 대상·접근성 이름은 그대로 파일명이어야 한다(어포던스·AT 를 깎지 않는다).
    assert "nameBtn" in body and "원문 보기" in body, "원문 보기 어포던스가 사라졌다"
    assert re.search(r'nameBtn\.setAttribute\("aria-label",\s*`\$\{a\.original_filename', body), (
        "접근성 이름에서 파일명을 잃었다 — 화면에서 지운 것을 AT 에서도 지우면 안 된다")
    assert 'title="${nameSafe}"' in body, "행 title 에서 파일명을 잃었다"


def test_kind_icon_is_rendered_once_per_group_not_per_row():
    """종류 아이콘도 카드 머리에서 한 번 — 행마다 되풀이하지 않는다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r'\$\{_hasSiblings \? "" : `<span class="attach-list-item-icon">', body)
    assert m, "그룹 안에서도 행 아이콘을 렌더한다"
    card = _code_only(_fn_body(_src(COMPOSER), "_attachLineageGroupCard"))
    assert 'className = "attach-lineage-group-icon"' in card, "카드 머리에 아이콘이 없다"
    assert re.search(r'setAttribute\("aria-hidden",\s*"true"\)', card), (
        "장식 아이콘이 접근성 트리에 노출된다 — 카드 이름이 이미 파일명을 말한다")
    assert re.search(r"titleEl\.append\(iconEl, nameEl\)", card), (
        "아이콘과 파일명을 한 덩어리로 묶지 않는다 — 머리가 접힐 때 아이콘만 떨어져 나간다")
    assert re.search(r"head\.append\(titleEl,", card), "만든 덩어리를 머리에 붙이지 않는다"
    rule = _css_rule(_src(CSS), ".attach-lineage-group-title")
    assert "min-width: 0" in rule, "파일명이 말줄임되지 않아 덩어리가 칩을 밀어낸다"
    assert re.search(r"_attachLineageGroupCard\(\s*_gname, _linTotal, _kinds\.size === 1", body, re.S), (
        "카드에 종류 아이콘을 넘기지 않는다 — 항상 기본 클립만 뜬다")


def test_version_badge_does_not_repeat_ai_inside_group():
    """그룹 안 버전 배지는 `v2` 만 — 라벨이 이미 「AI 수정본」이라 말했다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"_verBadgeRow\s*=\s*(.+?);\n", body, re.S)
    assert m, "그룹용 버전 배지 분기가 없다"
    expr = m.group(1)
    assert "_hasSiblings" in expr and "isAi" in expr, "그룹·AI 조건 없이 배지를 바꾼다"
    assert "AI 수정" not in expr.split("title=")[0], "배지가 'AI 수정' 을 되풀이한다"
    assert "verBadge" in expr, "그룹 밖에서 종전 배지로 돌아가지 않는다"


def test_row_label_carries_the_author_colour_axis():
    """작성 주체 색축이 **라벨로** 옮겨왔다 — 칩이 정체성을 놓았으므로 색도 함께 옮긴다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "is-ai-lineage" in body and "is-user-lineage" in body, "라벨에 주체 클래스가 없다"
    css = _src(CSS)
    ai = _css_rule(css, ".attach-lineage-group .attach-list-item-name-text.is-ai-lineage")
    assert "#2563eb" in ai, "AI 라벨 색이 없다 — 두 주체가 같은 색이면 축이 성립하지 않는다"
    base = _css_rule(css, ".attach-lineage-group .attach-list-item-name-text")
    assert "font-weight: 600" in base, "정체성이 1순위로 올라오지 않았다"


# ── U4. assistant 쪽 계약은 이미 있었다 — 회귀로 잠근다 ────────────────────

def test_assistant_prompt_still_names_the_lineage_uploader():
    """프롬프트가 계보마다 **업로더 이름**을 싣는 계약을 유지한다.

    이 cycle 의 발견은 「모델은 아는데 화면만 몰랐다」였다 — 화면을 고치면서 그 원천을 깨면
    비대칭이 반대 방향으로 되살아난다. 여기서 원천을 함께 잠근다.
    """
    core = (_WEB.parents[1] / "feature-0002-agent-core" / "src" / "agent_core.py")
    src = core.read_text(encoding="utf-8")
    # 앞쪽 주석에도 같은 문구가 있다 — **실제 렌더 지점**(lines.append)을 잡는다.
    i = src.find('lines.append("## FILE VERSION LINEAGES')
    assert i > 0, "계보 요약 섹션 렌더 지점이 사라졌다"
    body = src[i: i + 5000]
    assert "_uploader_labels" in body, "업로더 표시명을 쓰지 않는다"
    assert 'f"uploaded by {_nm}"' in body, "사람 계보를 이름으로 귀속하지 않는다"
    assert "overall latest" in body, "시간순 최신 축이 사라졌다"


# ── U5. 적대 리뷰(codex) 지적 조치 ─────────────────────────────────────────

def test_uploader_is_added_only_by_the_list_endpoint():
    """업로더는 **목록 응답에만** 붙는다 (codex P2).

    공유 serializer 에 넣으면 `/api/attachments/{id}` 메타·`/versions` 의 `versions[]`·휴지통·
    history/tool 응답까지 업로더 id 를 싣는다 — 「목록 payload 에만 추가」라는 범위를 넘는
    최소권한 회귀. 기존에 노출되던 것은 `/versions` 의 `lineages[].account_id` 뿐이었다.
    """
    store = _src(STORE)
    i = store.find("def _serialize_attachment_for_api")
    body = store[i: i + 5000]
    assert 'payload["account_id"]' not in body, (
        "공유 serializer 가 업로더를 싣는다 — 전 소비자로 노출이 번진다")
    conv = _src(CONV)
    assert re.search(r'ser\["account_id"\]\s*=\s*_uid or None', conv), (
        "목록 엔드포인트가 자기 응답에 업로더를 붙이지 않는다")


def test_shared_predicate_uses_the_requested_conversation():
    """공유 여부는 **이 응답이 속한 대화**로 판정한다 (codex P2).

    `currentConversation()` 으로 판정하면, 응답이 늦게 오는 사이 대화를 옮겼을 때 그룹 A 의
    행이 1:1 B 의 성격으로 분류돼 업로더명이 사라진다(반대 방향도 성립).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert re.search(r"_convForList\s*=.*?c\.id === convId", body, re.S), (
        "대화 객체를 convId 로 찾지 않는다")
    assert re.search(r"_isShared\s*=\s*isGroupConversation\(_convForList\)", body), (
        "여전히 «지금 화면의 대화» 로 판정한다")


def test_stale_list_response_is_dropped():
    """늦게 온 목록 응답은 **버린다** — 남의 대화 첨부가 새 화면에 그려지면 안 된다."""
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"if \(state\.activeConversationId !== convId\) return;", body)
    assert m, "stale 응답 가드가 없다"
    assert body.index("activeConversationId !== convId") < body.index('listEl.innerHTML = ""'), (
        "가드가 DOM 커밋 뒤에 온다 — 이미 그려졌다")


def test_colliding_identities_get_a_disambiguator():
    """라벨이 겹치면 **서수를 덧붙인다** (codex P2).

    같은 사람이 같은 이름을 독립으로 두 번 올리면 두 행 모두 「Alice」 이고, 독립 업로드라
    `⤷ 갈라짐` 칩도 없어 구분 수단이 사라진다. 겹칠 때만 붙여 흔한 2계보(사람↔AI)에는
    군더더기를 만들지 않는다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert "_identityCollides" in body, "라벨 충돌 판정이 없다"
    assert re.search(r"_sibs\.filter\(\(x\) => _identityOf\(x\) === _selfIdentity\)\.length > 1", body), (
        "형제들의 라벨과 대조하지 않는다")
    m = re.search(r"_identityLabel\s*=\s*_identityCollides\s*\?\s*(.+?)\n", body, re.S)
    assert m and "_linIdx" in m.group(1) and "_linTotal" in m.group(1), (
        "충돌 시에도 구분 가능한 식별자를 붙이지 않는다")


def test_accessible_name_matches_the_visible_identity():
    """접근성 이름이 **화면과 같은 정체성**을 말한다 (codex P2).

    화면에는 `Alice`/`Bob` 이 보이는데 AT 에는 둘 다 「사용자 계보」로 읽히면, 이 cycle 이 연
    구분이 스크린리더 사용자에게는 닫힌 채다(시각 표면만 고친 반쪽 개선).
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"_srWho\s*=\s*_hasSiblings(.+?);\n", body, re.S)
    assert m, "접근성 정체성 문구를 찾지 못했다"
    sr = m.group(1)
    assert "_selfIdentity" in sr, "AT 이름이 화면 라벨과 다른 출처를 쓴다"
    assert '"사용자 계보"' not in sr, "AT 이름이 업로더를 지운 고정 문구로 남아 있다"


def test_group_icon_does_not_misrepresent_mixed_kinds():
    """형제들의 종류가 갈리면 머리 아이콘은 **중립 클립** (codex P3).

    행 아이콘을 걷어냈으므로 머리 아이콘이 그룹 전체를 대표한다 — 첫 행의 종류만 남으면
    나머지를 잘못 대표한다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    assert re.search(r"_kinds\s*=\s*new Set\(_sibs\.map", body), "형제 종류를 모으지 않는다"
    assert re.search(r'_kinds\.size === 1 \? kindIcon\(a\.kind\) : "📎"', body), (
        "종류가 갈려도 첫 행의 아이콘으로 그룹을 대표한다")


# ── U6. 한 줄 간소화 + 남은 되풀이 제거 (REQ-20260901-lineage-row-compaction) ──

def test_version_rows_do_not_repeat_the_filename():
    """버전 행이 파일명을 되풀이하지 않는다 (사용자 지적 2026-09-01).

    이 박스는 언제나 한 계보 안이고, 그 파일명은 그룹 카드 머리(계보 여럿) 또는 목록 행(단독
    계보)이 이미 말했다. 행마다 또 적으면 같은 이름이 화면에 3~4번 실린다.
    ⚠ 마우스 확인 경로는 남긴다 — 행 `title` 로 이동.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_renderAttachmentVersionsBox"))
    assert 'className = "attach-list-version-name"' not in body, (
        "버전 행이 여전히 파일명을 렌더한다")
    assert re.search(r"row\.title\s*=\s*v\.original_filename", body), (
        "파일명 확인 경로를 통째로 잃었다 — 화면에서 뺐으면 title 로라도 남겨야 한다")


def test_version_row_is_a_single_line():
    """버전 행이 **한 줄**이다 — 2줄이던 근거(파일명)가 사라졌으므로.

    좁아지면 `wrap` 이 접는다(고정 2줄이 아니라 필요할 때만 — 잘림 대신 줄바꿈 원칙).
    """
    rule = _css_rule(_src(CSS), ".attach-list-version-row")
    assert "flex-direction: row" in rule, "여전히 세로 2줄 구조다"
    assert "flex-wrap: wrap" in rule, "좁은 폭에서 잘린다 — 접힘 경로가 없다"


def test_lineage_row_is_a_single_line_in_group():
    """그룹 안 계보 행도 **한 줄** — 업로드 주체와 파일 정보·버튼이 갈라져 있지 않다."""
    rule = _css_rule(_src(CSS), ".attach-lineage-group .attach-list-item-info")
    assert "flex-direction: row" in rule, "정체성 줄과 메타 줄이 여전히 분리돼 있다"
    assert "flex-wrap: wrap" in rule, "좁은 폭에서 잘린다 — 접힘 경로가 없다"
    # 메타 래퍼는 `display: contents` 로 **투명화**했다 — 자식(텍스트·액션)이 행의 직접 flex
    # 항목이 되어 폭을 나눠 갖는다. 래퍼로 남기면 액션이 메타 **안에서** 텍스트와 다퉈
    # 이름이 길어질수록 텍스트가 2~3줄로 접힌다(실측: info 205px 중 메타 62px).
    meta = _css_rule(_src(CSS), ".attach-lineage-group .attach-list-item-meta")
    assert "display: contents" in meta, "메타 래퍼가 남아 액션과 텍스트가 폭을 다툰다"
    acts = _css_rule(_src(CSS), ".attach-lineage-group .attach-list-item-actions")
    assert "margin-left: auto" in acts, "액션이 오른쪽 끝으로 밀리지 않는다"


def test_neutral_upload_status_is_not_shown_raw():
    """상태는 **뜻이 있을 때만** 적는다 — 서버 enum 을 화면에 흘리지 않는다.

    `uploaded` 는 텍스트 첨부에서 정상이자 영구 상태라 모든 행에 붙는 상수였고(스크린샷 실측),
    사용자가 할 수 있는 것도 없다. 다만 **모르는 enum 은 계속 보여 준다** — 조용히 삼키면
    새로 생긴 실패 상태가 화면에서 사라진다.
    """
    body = _code_only(_fn_body(_src(COMPOSER), "_loadConversationAttachmentList"))
    m = re.search(r"statusLabel\s*=\s*(.+?);\n", body, re.S)
    assert m, "상태 라벨 조립을 찾지 못했다"
    expr = m.group(1)
    assert '"uploaded" ? ""' in expr.replace(" ", " "), "중립 상태를 여전히 원문으로 노출한다"
    assert "읽기 완료" in expr and "오류" in expr, "뜻이 있는 상태를 잃었다"
    assert "a.status ||" in expr, "모르는 enum 을 조용히 삼킨다 — 새 실패 상태가 사라진다"

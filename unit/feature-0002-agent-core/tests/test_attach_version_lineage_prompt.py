"""REQ-20260814-attach-version-branching — 계보 분기의 프롬프트 인지 계약.

사용자 결정(2026-08-14): assistant 수정본을 사용자 계보에 편입하지 않고 **별도 계보로 분기**한다.
그러면 한 파일명에 계보가 둘 이상 공존하고 "최신" 이 두 뜻을 갖는다:

  · **계보 내 최신** — 한 체인 안의 최고 버전(그 사람의 최신 / 내 수정본의 최신)
  · **시간순 최신** — 파일명이 같은 모든 체인을 통틀어 가장 나중 것

모델이 둘을 구분하지 못하면 "최신본을 고쳤다" 면서 남의 계보를 집거나 오래된 것을 집는다.
여기서 고정하는 것은 **프롬프트가 두 축을 모두 사실로 싣는가** 다.

MySQL SELECT 컬럼 순서(생성시각 append 후):
  0 Id, 1 ConversationId, 2 OriginalFilename, 3 Kind, 4 MimeType, 5 SizeBytes, 6 SizeBucket,
  7 UploadStatus, 8 MetaJson, 9 RootAttachmentId, 10 VersionNumber, 11 CreatedByRole,
  12 AccountId, 13 CreatedAt
"""
from __future__ import annotations

import json
from datetime import datetime

import agent_core


class _RowsConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *a, **k):
        rows = self._rows

        class _Cur:
            def execute(self, sql, params=None):
                pass

            def fetchall(self):
                return rows

            def close(self):
                pass

        return _Cur()


def _row(aid, fname, *, uploader=50, version=1, root=None, role="user", created="2026-08-13 18:20",
         branch_of=None):
    meta = {}
    if branch_of:
        meta["branch_of_attachment_id"] = branch_of
    return (
        aid, "conv-x", fname, "text", "text/plain", 100, "small", "uploaded",
        json.dumps(meta), root, version, role, uploader,
        datetime.strptime(created, "%Y-%m-%d %H:%M"),
    )


def _build(rows, ids, monkeypatch, *, labels=None, account_id=50):
    monkeypatch.setenv("ATTACHMENT_IDS", ",".join(str(i) for i in ids))
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: labels)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    return agent_core._build_attachment_context_section(_RowsConn(rows), ids, account_id, "conv-x")


def _lineage_block(out: str) -> str:
    """계보 요약 블록만 잘라낸다(다른 섹션 문구에 오탐하지 않도록)."""
    head = "## FILE VERSION LINEAGES"
    if head not in out:
        return ""
    tail = out.split(head, 1)[1]
    return tail.split("\n## ", 1)[0]


# ── 단일 계보: 아무것도 붙지 않는다 ────────────────────────────────────────

def test_single_lineage_adds_no_block(monkeypatch):
    """계보가 하나면 '최신' 이 모호하지 않다 — 프롬프트를 낭비하지 않는다."""
    out = _build([_row(10, "report.sql", version=2, root=9)], [10], monkeypatch)
    assert "FILE VERSION LINEAGES" not in out


def test_distinct_filenames_are_not_merged(monkeypatch):
    """파일명이 다르면 서로 다른 파일이다 — 계보 공존이 아니다."""
    out = _build([_row(10, "a.sql"), _row(11, "b.sql", role="assistant")], [10, 11], monkeypatch)
    assert "FILE VERSION LINEAGES" not in out


# ── 계보 공존: 두 축을 모두 싣는다 ─────────────────────────────────────────

def test_two_lineages_render_both_axes(monkeypatch):
    """사용자 계보 + AI 계보가 공존하면 두 축('계보 내'/'시간순')을 모두 명시한다."""
    rows = [
        _row(10, "report.sql", uploader=50, version=2, root=9, created="2026-08-13 18:20"),
        _row(20, "report.sql", uploader=50, version=1, role="assistant",
             created="2026-08-13 18:25", branch_of=10),
    ]
    out = _build(rows, [10, 20], monkeypatch)
    blk = _lineage_block(out)
    assert blk, "계보가 둘이면 요약 블록이 있어야 함"
    assert "per-lineage latest" in blk and "overall latest" in blk, "두 축이 모두 명시돼야 함"
    assert '"report.sql" — 2 lineages' in blk


def test_overall_latest_marks_the_newest_by_time(monkeypatch):
    """시간순 최신에 마커가 붙는다 — 버전 번호가 더 낮아도 시간이 나중이면 그쪽이다.

    이 케이스가 정확히 함정이다: AI 분기는 v1 인데 사용자 계보는 v2 다. 번호만 보면 v2 가
    최신처럼 보이지만 시간순 최신은 v1(AI) 이다.
    """
    rows = [
        _row(10, "report.sql", version=2, root=9, created="2026-08-13 18:20"),
        _row(20, "report.sql", version=1, role="assistant", created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch))
    marked = [ln for ln in blk.splitlines() if "overall latest" in ln and "attachment_id=" in ln]
    assert len(marked) == 1, f"시간순 최신 마커는 정확히 1건이어야 함: {marked}"
    assert "attachment_id=20" in marked[0], "더 나중에 만들어진 AI 분기가 시간순 최신"


def test_older_assistant_edit_is_not_marked_latest(monkeypatch):
    """반대 순서도 정확해야 한다 — 사용자가 AI 수정 뒤에 다시 올렸으면 사용자 것이 시간순 최신."""
    rows = [
        _row(20, "report.sql", version=1, role="assistant", created="2026-08-13 18:25", branch_of=10),
        _row(11, "report.sql", version=3, root=9, created="2026-08-13 19:00"),
    ]
    blk = _lineage_block(_build(rows, [20, 11], monkeypatch))
    marked = [ln for ln in blk.splitlines() if "overall latest" in ln and "attachment_id=" in ln]
    assert len(marked) == 1 and "attachment_id=11" in marked[0]


def test_branch_origin_is_shown(monkeypatch):
    """AI 계보에는 **어디서 갈라졌는지**가 표시된다 — 트리 복원의 단서."""
    rows = [
        _row(10, "report.sql", version=2, root=9),
        _row(20, "report.sql", version=1, role="assistant", created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch))
    assert "branched from attachment_id=10" in blk


def test_uploader_name_used_when_available(monkeypatch):
    """그룹이면 계보 소유자를 표시명으로 밝힌다(누구 기준 최신인지가 요구의 핵심)."""
    rows = [
        _row(10, "report.sql", uploader=50, version=1),
        _row(20, "report.sql", uploader=50, version=1, role="assistant",
             created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch, labels={50: "jm.kim"}, account_id=10))
    assert "uploaded by jm.kim" in blk


def test_other_members_ai_lineage_is_marked_read_only(monkeypatch):
    """타 멤버의 요청으로 만들어진 AI 계보는 **내가 이어서 수정할 수 없다**고 밝힌다.

    §18.8 적대 리뷰 [P2]: 저장 경로는 source 의 AccountId 가 호출자와 같을 때만 새 버전을 만든다.
    모든 assistant row 를 "by you" 로 적으면 모델이 편집을 시도했다 조용히 거부당하고, 사용자에겐
    "수정했다" 는 말만 남는다.
    """
    rows = [
        _row(10, "report.sql", uploader=50, version=1),
        _row(20, "report.sql", uploader=50, version=1, role="assistant",
             created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch, labels={50: "jm.kim"}, account_id=10))
    assert "READ-ONLY for you" in blk
    assert "(by you)" not in blk, "타인 소유 AI 계보를 내 것이라 적으면 안 됨"


def test_own_ai_lineage_is_marked_extendable(monkeypatch):
    """내 요청으로 만들어진 AI 계보는 이어서 수정할 수 있음을 밝힌다(무회귀 축)."""
    rows = [
        _row(10, "report.sql", uploader=50, version=1),
        _row(20, "report.sql", uploader=50, version=1, role="assistant",
             created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch, labels={50: "jm.kim"}, account_id=50))
    assert "your lineage — you can extend it" in blk
    assert "READ-ONLY for you" not in blk


def test_block_instructs_disambiguation_before_acting(monkeypatch):
    """모델이 '최신' 을 임의로 골라 행동하지 않도록 계약을 싣는다."""
    rows = [
        _row(10, "report.sql", version=2, root=9),
        _row(20, "report.sql", version=1, role="assistant", created="2026-08-13 18:25", branch_of=10),
    ]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch))
    assert "say which one you mean before acting" in blk
    assert "never overwrites the other lineage" in blk


def test_missing_created_at_does_not_break_rendering(monkeypatch):
    """생성시각이 없는 행(구 경로·폴백)이 섞여도 블록 생성이 죽지 않는다."""
    legacy = (10, "conv-x", "report.sql", "text", "text/plain", 100, "small", "uploaded",
              json.dumps({}), 9, 2, "user", 50)  # CreatedAt 없음(13개 컬럼)
    rows = [legacy, _row(20, "report.sql", version=1, role="assistant", branch_of=10)]
    blk = _lineage_block(_build(rows, [10, 20], monkeypatch))
    assert '"report.sql" — 2 lineages' in blk
    assert "시각 미상" in blk


def test_edit_directive_states_branching(monkeypatch):
    """도구 지시가 '내 편집은 사용자 파일을 덮어쓰지 않는다' 를 명시한다.

    이 문장이 없으면 모델이 "원본을 최신 버전으로 교체했습니다" 같은 허위 서술을 한다.
    """
    src = agent_core.SYSTEM_PROMPT
    assert "YOUR EDITS LIVE IN THEIR OWN VERSION CHAIN" in src
    assert "never claim a version number from the other lineage as yours" in src


# ── FR-attachment-version-bump-forks-new-root (conversation_audit 2026-08-26) ────────────
#
# 라이브 관측(대화 …945b2aca): 사용자가 "v0 에서 **동일한 명칭으로 버전만 상승**시켜 첨부파일을
# 전달" 을 명시 요청했는데, assistant 는 `attachment-new` 블록을 다시 emit 해 **root=NULL·v1** 인
# 독립 첨부를 하나 더 만들었다(동명 v1 4건). 능력은 있었다 — 스코프에 원본 id 가 있었고
# `_materialize_assistant_attachment_edits` 는 assistant 계보의 v+1 연장을 이미 지원한다.
#
# 근본은 **계약이 프로덕션에 미도달**한 것이다. 계보 계약은 `SYSTEM_PROMPT` 본문(위
# test_edit_directive_states_branching)에만 있었고, 운영자 `WebSystemPrompts` global row 가 base 를
# 통째로 대체하는 프로덕션에서는 사라진다. 코드-권위 주입 지침 2종은 둘 다 "the user attached"
# 프레이밍이라 **assistant 전달본의 버전 상향을 아무도 claim 하지 않았고**, 유일하게 그 상황을
# claim 하는 지침이 `attachment-new` 였다. 아래 테스트가 고정하는 것:
#   1. 계보 계약이 **drift-내성 표면**(코드-append directive)에 있다.
#   2. `attachment-new` 지침이 스스로 경계를 긋는다(미존재 파일 전용).
#   3. 도구 설명이 assistant 전달본을 갱신 대상으로 명시한다.
#   4. ATTACHED FILES 가 assistant 전달본에 **v1 이어도** 계보·진입점을 싣는다.


def test_lineage_contract_lives_on_drift_proof_surface():
    """계보 계약은 운영자 row 가 base 를 대체해도 살아남는 상수에 있어야 한다.

    `SYSTEM_PROMPT` 본문에만 있으면 프로덕션 미도달 — 이번 마찰의 기전 그 자체다.
    """
    d = agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    assert "VERSION LINEAGES" in d
    assert "CONTINUES your chain" in d, "assistant 계보 연장 규칙이 drift-내성 표면에 있어야 함"
    assert "does NOT raise anything" in d, "동명 attachment-new 가 버전 상향이 아님을 명시해야 함"


def test_update_directive_trigger_covers_assistant_delivered_files():
    """갱신 지침의 발동 조건이 '사용자가 첨부한 파일' 로 좁으면 assistant 전달본이 새어나간다."""
    d = agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    assert "OR one YOU delivered earlier in this conversation" in d
    # 종전 문구는 EDIT 정의를 사용자 소유 파일로 한정했다 — 그 좁힘이 되살아나면 회귀다.
    assert "Improving the user's OWN attached file is an EDIT" not in d


def test_new_directive_bounds_itself_to_nonexistent_files():
    """`attachment-new` 는 아직 없는 파일 전용임을 스스로 밝혀야 한다.

    이 경계가 없으면 "네가 만든 파일을 첨부로 전달" 이라는 넓은 발동 조건이 **버전 상향 요청까지
    흡수**한다(라이브에서 실제로 그렇게 됐다).
    """
    d = agent_core._ATTACHMENT_NEW_DELIVERY_DIRECTIVE
    assert "ONLY for a file that does not exist in this conversation yet" in d
    assert "a file YOU already delivered here" in d
    assert "forks an unrelated v1" in d


def test_update_attachment_tool_description_covers_assistant_delivered():
    """도구 설명이 대상을 '사용자가 첨부한 파일' 로만 규정하면 모델은 자기 파일에 안 쓴다."""
    import modules.tools as tools

    desc = next(
        t["function"]["description"] for t in tools._ATTACHMENT_TOOL_DEFS
        if t["function"]["name"] == "update_attachment"
    )
    assert "네 전달본" in desc, "assistant 전달본이 갱신 대상임을 명시해야 함"
    assert "버전만 올려줘" in desc
    assert "사용자가 첨부한 텍스트/CSV 파일을" not in desc, "종전 좁은 프레이밍 회귀"


def test_assistant_v1_row_carries_lineage_hint(monkeypatch):
    """assistant 전달본은 **v1 이어도** 계보·버전상향 진입점을 싣는다(이번 마찰의 직접 축).

    종전에는 version>1 에서만 표식이 붙었고 FILE VERSION LINEAGES 블록도 동명 계보가 2개 이상일
    때만 렌더돼, `attachment-new` 로 갓 만든 v1 전달본은 **무표식**이었다.
    """
    rows = [_row(1239, "v0_immediate_mitigation.sql", uploader=10, version=1, role="assistant")]
    out = _build(rows, [1239], monkeypatch, account_id=10)
    assert "FILE VERSION LINEAGES" not in out, "계보가 하나면 요약 블록은 여전히 안 붙는다"
    line = next(ln for ln in out.splitlines() if "attachment_id=1239" in ln)
    assert "🤖AI-owned v1 (yours)" in line
    # §18.8 codex [P2]: 갱신 방법은 행마다 반복하지 않고 범례에서 한 번만 설명한다.
    assert "update_attachment" not in line, "행에 방법을 반복하면 첨부 상한에서 토큰이 폭증한다"
    assert "↳ 🤖AI-owned" in out and "update_attachment(attachment_id=<the id on that line>)" in out


def test_user_uploaded_row_has_no_ai_lineage_hint(monkeypatch):
    """사용자 업로드 파일에는 AI 계보 힌트가 붙지 않는다(오탐 0)."""
    out = _build([_row(77, "user_file.sql", uploader=10, version=1)], [77], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=77" in ln)
    assert "AI-delivered" not in line


def test_other_members_assistant_row_is_not_offered_as_update_target(monkeypatch):
    """타 계정 요청으로 만들어진 AI 파일에 갱신 진입점을 권하면 안 된다.

    저장 경로가 `AccountId` 일치를 강제하므로(`_materialize_assistant_attachment_edits`) 권하면
    모델이 시도했다 조용히 거부당하고 사용자에겐 "갱신했다" 는 말만 남는다.
    """
    rows = [_row(88, "shared.sql", uploader=50, version=1, role="assistant")]
    out = _build(rows, [88], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=88" in ln)
    assert "(another member's)" in line
    assert "(yours)" not in line


def test_unverified_owner_assistant_row_is_fail_closed(monkeypatch):
    """소유 계정을 확인할 수 없으면 갱신 진입점을 권하지 않는다(fail-closed).

    legacy row 는 `AccountId` 가 비어 있을 수 있다. 그런 행을 "네 계보" 로 적으면 저장 경로가
    (`AccountId or 0` 대 호출자 id 불일치로) 거부하는데 모델은 갱신했다고 말한다 — 라벨이
    가드보다 넓어지면 안 된다.
    """
    rows = [_row(99, "legacy.sql", uploader=0, version=1, role="assistant")]
    out = _build(rows, [99], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=99" in ln)
    assert "(owner unverified)" in line
    assert "(yours)" not in line


def test_assistant_v2_keeps_both_version_and_lineage_labels(monkeypatch):
    """버전이 오른 AI 전달본은 기존 🔄 표식과 계보 힌트를 함께 유지한다(무회귀)."""
    rows = [_row(90, "report.sql", uploader=10, version=2, root=89, role="assistant")]
    out = _build(rows, [90], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=90" in ln)
    assert "🔄v2(이전 v1 대비 갱신 — AI 수정본)" in line
    assert "🤖AI-owned v2 (yours)" in line


# ── §18.8 codex 적대 리뷰 흡수분 (2026-08-26) ──────────────────────────────────
#
# [P1] 갱신-가능 판정이 저장 경로 `AccountId` 가드보다 넓었다. 세 갈래였다:
#      ① 전역 지침이 "모든 AI 전달본" 을 대상으로 규정 ② 도구 설명이 "참조 가능한 첨부 전부"
#      ③ 파일 라인은 fail-closed 로 고쳤는데 `## FILE VERSION LINEAGES` 요약이 `not uploader`
#         때문에 같은 행을 다시 "your lineage — you can extend it" 으로 되돌림(술어 불일치).
# [P2] `attachment-new` 지침이 자기모순 — 발동 조건은 무조건, 경계는 절 끝에만.
# [P2] 행마다 갱신 방법을 반복해 첨부 상한(200건)에서 ~32KB 증가.


def test_ownership_predicate_is_fail_closed():
    """소유권 판정 정본 — 확인 불가는 own 이 아니다(저장 경로가 거부하므로)."""
    f = agent_core._assistant_lineage_ownership
    assert f(50, 50) == "own"
    assert f(50, 10) == "other"
    assert f(0, 10) == "unknown"      # legacy row (AccountId NULL)
    assert f(None, 10) == "unknown"
    assert f(50, 0) == "unknown"      # 계정 컨텍스트 부재
    assert f("x", 10) == "unknown"    # 파싱 불가도 열지 않는다


def test_lineage_block_agrees_with_file_line_on_unverified_owner(monkeypatch):
    """[P1] 두 표시면이 **같은 술어**를 쓴다 — 요약이 파일 라인의 fail-closed 를 되돌리면 안 된다.

    종전 요약 코드는 `not e.get("uploader")` 라 소유 미상 행을 "you can extend it" 으로 열었다.
    """
    rows = [
        _row(10, "report.sql", uploader=10, version=1),
        _row(20, "report.sql", uploader=0, version=1, role="assistant",
             created="2026-08-13 18:25", branch_of=10),
    ]
    out = _build(rows, [10, 20], monkeypatch, account_id=10)
    blk = _lineage_block(out)
    assert "lineage owner unverified — READ-ONLY for you" in blk
    assert "your lineage — you can extend it" not in blk
    # 파일 라인도 같은 결론이어야 한다.
    line = next(ln for ln in out.splitlines() if "attachment_id=20" in ln)
    assert "(owner unverified)" in line


def test_update_directive_defers_target_choice_to_ownership_labels():
    """[P1] 전역 지침이 대상을 '내 것으로 표시된 파일' 로 제한한다(가드보다 넓지 않게)."""
    d = agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    # §18.8 (b) 재설계의 정확한 범위(codex 라운드 6 [P2] 정정): 재현하지 않는 것은 **소유권 판정**
    # 이다 — "누구 것이면 갱신 가능" 을 프롬프트가 흉내내면 저장 가드와 어긋난다. 반면 **kind 사실**
    # (바이너리는 애초에 버전이 없다)은 모델이 헛시도하지 않도록 한 번 진술한다. 즉 금지되는 것은
    # allowlist/denylist 형태의 **소유 집합 재현**이고, kind 규칙 진술은 그 대상이 아니다.
    assert "the `update_attachment` tool, not you" in d
    assert "relay that reason to the user" in d
    assert "only text/csv/sql files can get a new version" in d.lower(), "kind 규칙이 drift-내성 표면에 있어야 함"
    assert "only the ones ATTACHED FILES shows as yours" not in d, "allowlist 문구 회귀(과잉 차단)"
    assert "No marker means it is yours to update" not in d, "denylist 문구 회귀(과잉 주장)"


def test_new_directive_trigger_is_narrowed_at_the_top():
    """[P2] 발동 조건 **자체**가 좁아야 한다 — 절 끝의 경계만으로는 두 지침이 동시에 발동한다."""
    d = agent_core._ATTACHMENT_NEW_DELIVERY_DIRECTIVE
    assert "that is NOT already listed in ATTACHED FILES" in d
    # 무조건 발동하던 종전 문구가 되살아나면 회귀.
    assert "If the user asks you to deliver a script/query/file you produced **as a downloadable" not in d


def test_update_tool_description_defers_to_ownership_labels():
    """[P1] 도구 설명도 '참조 가능한 전부' 가 아니라 소유 라벨에 위임한다."""
    import modules.tools as tools

    desc = next(
        t["function"]["description"] for t in tools._ATTACHMENT_TOOL_DEFS
        if t["function"]["name"] == "update_attachment"
    )
    assert "갱신 허용 여부는 이 도구가 판정한다" in desc
    assert "허용 집합을 네가 미리 " in desc, "허용 집합 열거 대신 '추측 말고 호출' 계약"
    assert "사유를 사용자에게 그대로 전달" in desc
    assert "텍스트가 아닌 kind 는 거부되며" not in desc, "허용 집합 열거 회귀"
    assert "이 대화에서 참조 가능한 텍스트/CSV 첨부" not in desc, "과잉 주장 회귀"
    assert "ATTACHED FILES 에서 네 것으로 표시된" not in desc, "allowlist 문구 회귀(과잉 차단)"
    assert "표식이 없으면 갱신 가능하다" not in desc, "denylist 문구 회귀(과잉 주장)"


def test_update_instructions_are_injected_once_not_per_file(monkeypatch):
    """[P2] 갱신 방법은 첨부 수와 무관하게 **한 번**만 실린다(상한 200건에서 토큰 폭증 방지)."""
    rows = [
        _row(300 + i, f"gen_{i}.sql", uploader=10, version=1, role="assistant")
        for i in range(6)
    ]
    out = _build(rows, [r[0] for r in rows], monkeypatch, account_id=10)
    assert out.count("update_attachment(attachment_id=<the id on that line>)") == 1
    assert out.count("🤖AI-owned") == len(rows) + 1  # 각 파일 라벨 + 범례 헤더 1


def test_legend_absent_when_no_assistant_attachment(monkeypatch):
    """범례는 라벨이 실제로 붙은 턴에만 렌더한다(사용자 첨부만이면 0 토큰)."""
    out = _build([_row(70, "u.sql", uploader=10, version=1)], [70], monkeypatch, account_id=10)
    assert "🤖AI-owned" not in out


def test_one_to_one_user_upload_has_no_ownership_marker(monkeypatch):
    """자체 확인 라운드 적발의 **근거 사실** 고정 — 1:1 에는 소유 표식이 붙지 않는다.

    `👤uploaded-by=you` 는 타 업로더가 있을 때만 렌더된다(`_has_other_uploader`). 그래서 갱신 대상
    규정을 allowlist("네 것으로 표시된 것만")로 쓰면 1:1 대화(라이브 348/383)에서 사용자 자신의
    파일조차 대상 밖으로 읽힌다. 이 테스트가 깨지면 지침 문구의 전제가 바뀐 것이므로 문구도 함께
    재검토해야 한다.
    """
    out = _build([_row(60, "mine.sql", uploader=10, version=1)], [60], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=60" in ln)
    assert "uploaded-by" not in line, "1:1 에서는 업로더 라벨이 붙지 않는다(전제)"
    assert "READ-ONLY" not in line


# ── codex 확인 라운드(4R) 흡수: 술어 복제 제거 + 테스트 사각 메우기 ──────────────────────


# provenance gate 의 소유 미상 축은 사용자 승인(2026-08-26)으로 이 cycle 에서 **닫았다**.
# 그 계약(fail-closed · 과차단 방지 2축 · 사유 정확성)은 전용 파일이 전수로 고정한다:
#   tests/test_attach_provenance_unknown_owner.py


def test_label_makes_no_updatability_claim_for_non_text_kind(monkeypatch):
    """[P2] 라벨은 kind 를 보지 않는다 — 그래서 **갱신 가능성을 주장하지 않는 것**이 계약이다.

    종전 라벨은 `(yours) → update_attachment` 진입점을 kind 무관하게 붙여, 저장 가드가 text/csv 만
    허용한다는 사실과 어긋났다. 재설계 후 라벨은 사실만 싣고 kind 규칙은 지침이 한 번 말한다.
    """
    rows = [(42, "conv-x", "book.xlsx", "xlsx", "application/vnd.ms-excel", 100, "small",
             "uploaded", json.dumps({}), None, 1, "assistant", 10,
             datetime.strptime("2026-08-13 18:20", "%Y-%m-%d %H:%M"))]
    out = _build(rows, [42], monkeypatch, account_id=10)
    line = next(ln for ln in out.splitlines() if "attachment_id=42" in ln)
    assert "🤖AI-owned v1 (yours)" in line
    assert "update_attachment" not in line, "행이 진입점을 주장하면 kind 불일치가 되살아난다"
    # kind 규칙은 drift-내성 지침에 있어야 한다(본문에만 있으면 운영자 row 가 삼킨다).
    assert "binary kinds (xlsx/pdf/image)" in agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    # 범례의 진입점도 kind 조건을 달아야 한다(kind 무관 진입점 주장 회귀 방지).
    assert "for a text/csv file, raise its version" in out
    assert "Binary kinds cannot be versioned at all" in out


def test_new_directive_distinguishes_unlisted_from_nonexistent():
    """[P2] '목록에 없음' ≠ '존재하지 않음' — 그 동치 가정이 재첨부 지시와 충돌했다."""
    d = agent_core._ATTACHMENT_NEW_DELIVERY_DIRECTIVE
    assert "Not listed ≠ does not exist" in d
    assert "ask the user to re-attach it" in d
    assert "no attachment of its own anywhere in this conversation" in d


def test_legend_does_not_assert_impossibility(monkeypatch):
    """재설계 계약: 범례도 '불가' 를 단정하지 않는다(그 단정이 곧 술어 복제였다)."""
    rows = [
        _row(50, "a.sql", uploader=10, version=1, role="assistant"),
        _row(51, "b.sql", uploader=99, version=1, role="assistant"),
    ]
    out = _build(rows, [50, 51], monkeypatch, account_id=10)
    assert "provenance facts, not your lineage" in out
    assert "`update_attachment` decides" in out
    assert "CANNOT create a new version" not in out

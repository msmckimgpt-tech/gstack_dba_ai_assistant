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

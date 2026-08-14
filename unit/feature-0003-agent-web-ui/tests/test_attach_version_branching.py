"""REQ-20260814-attach-version-branching — assistant 수정본의 별도 계보 분기 계약.

사용자 결정(2026-08-14): assistant 가 만든 수정본을 사용자 계보에 v+1 로 편입하지 않고
**별도 root 체인의 v1 로 분기**한다. 사용자 계보와 그 최신본은 건드리지 않는다.

왜: 종전에는 한 계보에 사람 버전과 AI 버전이 섞이고, AI 수정본이 사용자 최신본을 supersede 해
목록에서 밀어냈다. 사용자는 "내가 올린 최신" 을 잃고, assistant 도 "누구 기준 최신" 을 구분하지
못했다. 스키마는 늘리지 않고(UNIQUE(Root,Version) 불변) MetaJson 의 분기 지점으로 트리를 복원한다.
"""
from __future__ import annotations

import inspect

import app
from routers import attachments as _attachments_router


class _CaptureCursor:
    def __init__(self, sink, rows=None, dictionary=False):
        self._sink = sink
        self._rows = rows or []
        self._dict = dictionary

    def execute(self, sql, params=None):
        self._sink.append((" ".join(str(sql).split()), params))

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class _CaptureConn:
    def __init__(self, sink, rows=None):
        self._sink = sink
        self._rows = rows or []

    def cursor(self, dictionary=False):
        return _CaptureCursor(self._sink, self._rows, dictionary)


# ── 계보 head 조회(시간순 축) ──────────────────────────────────────────────

def test_lineage_heads_query_scopes_conversation_and_filename():
    """계보 head 조회는 대화 + 파일명으로 스코프하고 **head 만**(SupersededAt IS NULL) 가져온다.

    스코프가 빠지면 타 대화의 동명 파일이 비교 후보로 새어든다(IDOR 축).
    """
    sink: list = []
    rows = [{"Id": 20, "RootAttachmentId": None, "AccountId": 50, "CreatedByRole": "assistant",
             "VersionNumber": 1, "OriginalFilename": "r.sql", "CreatedAt": None, "MetaJson": "{}"}]
    out = app._load_filename_lineage_heads(_CaptureConn(sink, rows), "conv-x", "r.sql")
    assert len(out) == 1 and out[0]["Id"] == 20
    sql, params = sink[0]
    assert "ConversationId = %s" in sql and "OriginalFilename = %s" in sql
    assert "SupersededAt IS NULL" in sql, "head 가 아닌 구버전까지 오면 계보 수가 부풀려진다"
    assert "DeletedAt IS NULL" in sql and "DeletePending = 0" in sql
    assert "ORDER BY CreatedAt DESC" in sql, "시간순 축이므로 최신 우선 정렬"
    assert params[0] == "conv-x" and params[1] == "r.sql"


def test_lineage_heads_returns_empty_on_missing_args():
    """대화/파일명이 없으면 조회하지 않는다(전량 스캔 방지)."""
    sink: list = []
    assert app._load_filename_lineage_heads(_CaptureConn(sink), "", "r.sql") == []
    assert app._load_filename_lineage_heads(_CaptureConn(sink), "conv-x", "") == []
    assert sink == [], "인자가 없으면 쿼리 자체를 던지지 않는다"


def test_lineage_heads_fails_soft():
    """조회 실패는 빈 목록 — 비교 축 하나가 죽어도 버전 조회 자체는 계속돼야 한다."""
    class _Boom:
        def cursor(self, dictionary=False):
            raise RuntimeError("db down")

    assert app._load_filename_lineage_heads(_Boom(), "conv-x", "r.sql") == []


# ── 분기 판정 (구조 잠금) ──────────────────────────────────────────────────
# materialize 경로는 MinIO·audit·dual-write 를 함께 태워 fake 로 전 구간을 돌리기 어렵다.
# 대신 분기 계약이 코드에서 사라지면 FAIL 하도록 소스를 잠근다(§16.7 G10 동형).

def _materialize_src() -> str:
    return inspect.getsource(app._materialize_assistant_attachment_edits)


def test_branch_decision_is_driven_by_source_role():
    """source 가 사람 첨부면 분기, assistant 계보면 연장 — 판정 축이 CreatedByRole 이어야 한다."""
    src = _materialize_src()
    assert "_branch_from_user_chain" in src
    assert 'CreatedByRole' in src and '!= "assistant"' in src


def test_branch_starts_new_root_chain_at_v1():
    """분기는 새 계보의 v1 이다 — RootAttachmentId 는 NULL 로 들어가야 자기 자신이 root 가 된다."""
    src = _materialize_src()
    assert "next_version = 1" in src
    assert "(root_id or None)" in src, "root_id=0 이 그대로 INSERT 되면 체인이 깨진다"


def test_branch_does_not_supersede_user_chain():
    """**핵심**: 분기일 때 사용자 계보를 supersede 하지 않는다.

    이 가드가 빠지면 AI 수정본이 사용자 최신본을 목록에서 밀어낸다 — 계보를 나눈 목적의 정반대다.
    """
    src = _materialize_src()
    assert "_supersede_root_id" in src
    assert "if _supersede_root_id:" in src, "supersede 가 무조건 실행되면 분기 의미가 없다"
    body = src.split("if _supersede_root_id:", 1)[1]
    assert "SET SupersededAt" in body, "연장 경로에서는 여전히 구버전을 꺼야 한다"


def test_branch_records_origin_for_tree_reconstruction():
    """스키마를 늘리지 않으므로 MetaJson 의 분기 지점이 트리 복원의 유일한 단서다."""
    src = _materialize_src()
    assert "branch_of_attachment_id" in src
    assert "branch_of_root_id" in src


def test_dual_write_mirrors_new_row_on_branch():
    """분기 시 체인 조회 대상이 없으므로(root_id=0) 새 row 만 미러해야 한다."""
    src = _materialize_src()
    seg = src.split("dual_write_enabled", 1)[1]
    assert "if _supersede_root_id:" in seg, "분기에서 root_id=0 으로 체인을 조회하면 안 된다"
    assert "mirror_attachments" in seg


# ── §18.8 적대 리뷰 반영 축 ────────────────────────────────────────────────

def test_user_reupload_never_joins_an_ai_lineage():
    """**[P1]**: 사용자 재업로드는 사용자 계보에만 편입된다.

    역할을 가리지 않으면 같은 파일명의 AI head 가 Id 순으로 먼저 뽑혀, 사용자의 다음 업로드가
    AI 계보의 v2 가 되고 그 head 를 supersede 한다 — 한 번의 재업로드로 계보 분리가 무너진다.
    """
    sink: list = []
    app._find_latest_same_name_attachment(_CaptureConn(sink, [{"Id": 1}]), "conv-x", 7, "r.sql")
    sql, _ = sink[0]
    assert "CreatedByRole" in sql and "<> 'assistant'" in sql, \
        "동명 head 선택이 역할을 가리지 않으면 AI 계보로 편입된다"


def test_lineage_heads_collapse_to_one_per_root():
    """**[P1]**: 같은 root 에 live head 가 둘 남아도 계보는 하나로 센다.

    업로드 경로가 INSERT commit 뒤 supersede 하고 그 실패를 삼키므로(기존 결함) 한 체인에 head 가
    둘 남을 수 있다. 그대로 반환하면 한 계보를 둘로 오인해 "AI 가 만든 다른 버전이 있다" 는 거짓
    사실이 프롬프트·UI 로 나간다.
    """
    rows = [
        {"Id": 12, "RootAttachmentId": 10, "AccountId": 7, "CreatedByRole": "user",
         "VersionNumber": 3, "OriginalFilename": "r.sql", "CreatedAt": None, "MetaJson": "{}"},
        {"Id": 11, "RootAttachmentId": 10, "AccountId": 7, "CreatedByRole": "user",
         "VersionNumber": 2, "OriginalFilename": "r.sql", "CreatedAt": None, "MetaJson": "{}"},
        {"Id": 20, "RootAttachmentId": None, "AccountId": 7, "CreatedByRole": "assistant",
         "VersionNumber": 1, "OriginalFilename": "r.sql", "CreatedAt": None, "MetaJson": "{}"},
    ]
    out = app._load_filename_lineage_heads(_CaptureConn([], rows), "conv-x", "r.sql")
    assert [r["Id"] for r in out] == [12, 20], "같은 root(10) 는 최신 1건만, AI 계보는 별개"


# ── REQ-20260814-attach-version-tree-ui: 계보 간(시간순) diff 인가 계약 ──────

def test_cross_lineage_diff_authorizes_each_side_independently():
    """계보 간 비교는 **양쪽을 각각 인가**한다.

    기준 첨부의 게이트를 통과했다는 사실이 체인 밖 다른 계보의 접근권을 함의하지 않는다.
    여기서 기준 하나만 검사하면 임의 attachment_id 두 개의 본문을 나란히 여는 경로가 된다.
    """
    src = inspect.getsource(_attachments_router.get_attachment_version_diff)
    # `if cross_lineage:` 는 소스에 여러 번 나온다(파라미터 파싱 · 본문 · 헤더 정정).
    # 위치로 고르면 코드가 늘 때마다 조용히 다른 블록을 검사하게 된다 — **내용으로** 고른다.
    seg = next(b for b in src.split("if cross_lineage:") if "from_att_id)" in b)
    assert "for _side in (left, right)" in seg
    assert "_account_can_access_attachment" in seg


def test_cross_lineage_diff_is_scoped_to_same_conversation_and_filename():
    """같은 대화·같은 파일명으로 스코프한다 — 범용 '아무 첨부 2개 비교' 경로가 되면 안 된다."""
    src = inspect.getsource(_attachments_router.get_attachment_version_diff)
    # `if cross_lineage:` 는 소스에 여러 번 나온다(파라미터 파싱 · 본문 · 헤더 정정).
    # 위치로 고르면 코드가 늘 때마다 조용히 다른 블록을 검사하게 된다 — **내용으로** 고른다.
    seg = next(b for b in src.split("if cross_lineage:") if "from_att_id)" in b)
    assert "ConversationId" in seg and "같은 대화" in seg
    assert "OriginalFilename" in seg and "같은 파일" in seg


def test_cross_lineage_diff_rejects_same_attachment():
    """같은 첨부 두 번은 비교가 아니다(계보 내 축의 '같은 버전' 거부와 동형)."""
    src = inspect.getsource(_attachments_router.get_attachment_version_diff)
    assert "from_att_id == to_att_id" in src


def test_version_axis_contract_is_unchanged():
    """기존 계보 내 축(from_version/to_version)은 그대로 — 무회귀."""
    src = inspect.getsource(_attachments_router.get_attachment_version_diff)
    assert "from_version" in src and "to_version" in src
    assert "_load_attachment_version_chain" in src

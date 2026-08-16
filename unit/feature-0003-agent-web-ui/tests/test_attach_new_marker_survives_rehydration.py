"""FR-attach-change-signal-client-only (프론트 축) — 신규 첨부 표식이 재수화를 살아남는가.

conv-audit 2026-08-14: `_loadConversationAttachments` 는 대화 진입·첨부 패널 mutation 때 버킷을
서버 목록으로 **통째 재구성**하는데, 종전엔 모든 항목을 `source:"session"` 으로 덮었다. 그래서
방금 올린 파일의 ★신규 표식이 사라지고, 다음 전송의 `new_attachment_ids` 가 비어
프롬프트에서 갱신 파일이 "◆세션(이전 세션 첨부)" 로 오라벨됐다(60일 실측 14 job / 14 대화).

여기서 잠그는 것은 **두 계약의 쌍**이다 — 한쪽만 있으면 각각 다른 방향으로 깨진다:
  P1 재수화가 **아직 전송하지 않은** 신규 표식을 보존한다(유실 방지).
  P2 전송 성공 시 `new → session` 전환은 그대로다(과표시 방지) — 이게 없으면 P1 때문에
     같은 파일이 매 턴 ★신규 로 실려 "이번 턴에 올라왔다" 는 거짓 사실이 반복된다.

한계(정직): 이 파일은 소스 배선을 잠그는 **구조 가드**이지 런타임 동작 증명이 아니다. 실제
브라우저에서의 표식 보존은 PB-0008 라이브 확인 대상이다. 서버측에는 독립 봉인이 따로 있다
(`agent_core._derive_server_new_attachment_ids` — 새로고침으로 버킷 자체가 사라지는 경우를 덮는다).
"""
from __future__ import annotations

import pathlib
import re

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"


def _composer_source_without_comments() -> str:
    """주석을 뺀 composer.js — 설명문의 단어가 배선 단언을 vacuous 하게 통과시키지 않도록."""
    js = (_STATIC / "app" / "composer.js").read_text(encoding="utf-8")
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    return re.sub(r"(?<![:/])//[^\n\"'`]*$", "", js, flags=re.M)


def _function_body(js: str, name: str) -> str:
    """`async function <name>(` 부터 다음 top-level 함수 선언 직전까지."""
    start = js.index(f"function {name}(")
    rest = js[start + 1:]
    nxt = re.search(r"^(?:async\s+)?function\s+\w+\(", rest, flags=re.M)
    return rest[: nxt.start()] if nxt else rest


def test_p1_rehydration_preserves_unsent_new_markers():
    """재수화가 모든 항목을 무조건 session 으로 덮으면 ★신규 가 유실된다."""
    body = _function_body(_composer_source_without_comments(), "_loadConversationAttachments")
    assert 'source: "session"' not in body, (
        "재수화가 여전히 무조건 session 으로 덮는다 — 신규 표식이 유실된다"
    )
    assert 'source: keepNewIds.has(Number(a.id)) ? "new" : "session"' in body, (
        "재수화가 기존 신규 표식을 조건부로 보존하지 않는다"
    )
    # 보존 대상은 **서버 목록 재구성 이전**의 버킷에서 뽑아야 한다 — 재구성 뒤에 뽑으면 항상 빈 집합.
    assert body.index("keepNewIds") < body.index("bucket.items = bucket.items.filter"), (
        "보존 집합을 버킷 재구성 **뒤**에 계산한다 — 항상 비어 무의미하다"
    )


def test_p2_send_success_still_demotes_new_to_session():
    """전송 후 강등이 사라지면 P1 이 같은 파일을 매 턴 ★신규 로 만든다(거짓 사실 반복)."""
    js = _composer_source_without_comments()
    assert 'it.source = "session";' in js and 'it.source !== "session"' in js, (
        "전송 성공 시 new → session 강등이 사라졌다 — 신규 표식이 영구화된다"
    )


def test_p2b_lazy_create_demotes_the_effective_bucket_not_only_the_sentinel():
    """강등이 sentinel 버킷만 보면 lazy-create 첨부가 **영구 ★신규** 로 남는다.

    §18.8 codex [P1]→[P2](코드 판독으로 적발). 새 대화의 첨부는 발급된 early-cid 버킷으로
    옮겨 간다 — 업로드 시점 발급(`_uploadAttachment`)·전송 시점 발급
    (`_flushStagedAttachmentsToCid`) **두 경로 모두**. sentinel 키만 강등하면 실제 파일이 든
    버킷이 `new` 로 남고, P1 보존과 겹쳐 그 파일이 **매 턴** ★신규로 재전송된다.
    그래서 강등의 정본은 **서버가 응답한 conversation_id** 다 — 이 요청이 실제로 어느 대화로
    갔는지는 서버만 확정한다. 보존(P1)과 강등(P2)은 *같은 키* 위에서만 쌍으로 성립한다.
    """
    js = _composer_source_without_comments()
    body = _function_body(js, "sendPrompt")
    m = re.search(r"_clearKeys\s*=\s*\[(.*?)\];", body, flags=re.S)
    assert m, "전송 후 강등 대상 목록(_clearKeys)을 찾지 못했다"
    keys = m.group(1)
    assert "payload.conversation_id" in keys, (
        "강등 대상이 서버가 확정한 conversation_id 를 포함하지 않는다 — early-cid 버킷의 첨부가 "
        "`new` 로 남아 이후 모든 턴에 ★신규 로 재전송된다"
    )
    assert "askKey" in keys, "early-cid 전송 시점 발급 경로가 강등 대상에서 빠졌다"
    # 응답 시점의 **활성 대화**를 강등 대상에 넣으면 안 된다(§18.8 codex round4 [P1]) —
    # A 의 응답을 기다리는 사이 B 로 옮겨 올린 파일의 ★신규를 A 의 응답이 지운다.
    assert "state.activeConversationId" not in keys, (
        "강등 대상이 이 요청에 고정되지 않았다 — 다른 대화의 미전송 신규 표식을 훼손한다"
    )


def test_p2c_demotes_only_the_ids_this_request_actually_sent():
    """§18.8 codex round5 [P1]: 버킷의 `new` 를 통째로 내리면, 응답을 기다리는 사이 같은 대화에
    새로 올린 파일까지 '전송됨' 으로 강등된다. 그 파일은 실제로는 아직 안 보내졌으므로 다음
    요청의 `new_attachment_ids` 에서 빠지고(재수화 보존도 `session` 을 유지), 봉인하려던
    미인지가 바로 그 파일에서 되살아난다. 강등은 **전송 스냅샷의 id** 로만 한다."""
    body = _function_body(_composer_source_without_comments(), "sendPrompt")
    assert "_sentNewIds" in body and "askBody.new_attachment_ids" in body, (
        "강등이 전송 스냅샷 기준이 아니다"
    )
    assert "_sentNewIds.has(Number(it.id))" in body, (
        "버킷의 모든 신규 표식을 무조건 강등한다 — 요청에 실리지 않은 파일까지 잃는다"
    )


def test_p3_ask_payload_still_derives_new_ids_from_marker():
    """`new_attachment_ids` 가 표식(source)에서 나온다는 전제 자체가 유지되는지."""
    js = _composer_source_without_comments()
    assert "askBody.new_attachment_ids" in js
    assert 'it.source !== "session"' in js, (
        "전송 payload 가 더 이상 신규 표식을 기준으로 만들어지지 않는다"
    )

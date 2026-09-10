"""assistant 답변의 첨부 쓰기 블록 후처리 — **경로 공용 정본**.

## 무엇인가

assistant 가 답변에 ```` ```attachment-edit ```` / ```` ```attachment-new ```` 블록을 실으면
그 내용은 채팅 본문이 아니라 **다운로드 첨부**(원본의 새 버전 / 새 파일)가 되어야 한다.
그 시퀀스가 여기 있다:

    materialize edit → materialize new → 도구 전달분 바인딩 → strip → 미전달 고지 → content 갱신

## 왜 shared 인가

이 시퀀스는 ask-worker 경로(`modules/ask.py`)에만 살아 있었고, 브리지 경로
(`routers/ai_tools.py`)에는 **아예 없었다**. 없는 쪽에서 사용자가 겪은 것은 거짓 성공이다 —
개인 AI 는 관례대로 블록을 만들어 냈는데 서버가 처리하지 않아 파일은 v1 그대로인 채 답변만
"수정했습니다" 라고 말했다(라이브 실측 2026-08-28, 첨부 1246).

두 번째 구현을 쓰는 대신 한 벌로 합친다. 저장 가드(소유권·kind·용량·확장자 allowlist)는
materialize 안에 있고, 구현이 갈리면 그 가드도 갈린다 — **갈리는 순간 느슨한 쪽이 사용자가
보는 진실이 된다.** 쓰기 경계는 답변을 만든 주체가 안이든 밖이든 같아야 한다.

## 왜 `ops` 를 받는가

실제 저장·strip 원시연산은 web 층(`app`)에 있다. 여기서 `import app` 을 모듈 최상단에 두면
이 파일이 web 전체를 끌고 오고, worker 테스트가 쓰는 가벼운 fake 주입도 불가능해진다.
`ops` 는 그 원시연산 6종을 가진 네임스페이스다 — 생략하면 지연 `import app`.
"""
from __future__ import annotations

import logging
from typing import Any

__all__ = ["count_attachment_block_fences", "apply_assistant_attachment_blocks"]


class AttachmentWriteBudget:
    """한 후처리의 저장 시도를 제한한다. 실패한 쓰기도 예약량을 반환하지 않는다."""

    def __init__(self, count: int, size_bytes: int):
        self.count = max(0, int(count))
        self.size_bytes = max(0, int(size_bytes))
        self.attempted_count = 0
        self.used_count = 0
        self.used_bytes = 0

    def start(self) -> str:
        if self.attempted_count >= self.count:
            return f"한 답변의 첨부 개수 상한({self.count}개)을 초과했습니다."
        self.attempted_count += 1
        return ""

    def check(self, size_bytes: int) -> str:
        if self.used_count >= self.count:
            return f"한 답변의 첨부 개수 상한({self.count}개)을 초과했습니다."
        if self.used_bytes + size_bytes > self.size_bytes:
            return f"한 답변의 첨부 합계 용량 상한({self.size_bytes} bytes)을 초과했습니다."
        return ""

    def reserve(self, size_bytes: int) -> str:
        reason = self.check(size_bytes)
        if not reason:
            self.used_count += 1
            self.used_bytes += size_bytes
        return reason


def count_attachment_block_fences(text: str) -> tuple[int, int]:
    """답변에서 **실제로 열리는** attachment 블록 fence 수 → `(edit, new)`.

    단순 substring 카운트를 쓰면 답변이 **예시로 인용한** ```` ```attachment-edit ```` 까지 세어
    정상 전달에도 "전달 실패" 문단이 붙는다(거짓 경고). 두 축을 조인다:

    - **줄머리 fence 만** 센다(들여쓴 것은 블록이 아니다).
    - **바깥 fence 안의 인용은 제외** — ```` ```markdown ```` 안에서 열 0 으로 적은 것은 예시다.
      ```` 이상 backtick 과 `~~~` 도 fence 이므로 열림/닫힘을 함께 추적한다.
    """
    edit_n = new_n = 0
    open_tag: str | None = None
    for line in str(text or "").splitlines():
        if line.startswith("```"):
            n = len(line) - len(line.lstrip("`"))
        elif line.startswith("~~~"):
            n = len(line) - len(line.lstrip("~"))
        else:
            continue
        tag = line[n:].strip()
        if open_tag is None:
            if tag.startswith("attachment-edit"):
                edit_n += 1
            elif tag.startswith("attachment-new"):
                new_n += 1
            open_tag = tag or ""          # 여는 fence(언어 표기 유무 무관)
        elif not tag:
            open_tag = None               # 닫는 fence
    return edit_n, new_n


def _count_expected_blocks(ops: Any, content: str) -> tuple[int, int]:
    """이 답변에서 **materialize 가 시도할** 블록 수 → `(edit, new)`.

    ## 왜 fence 를 세지 않는가 (codex 적대 리뷰 P1, 2026-08-28)

    `count_attachment_block_fences` 는 markdown 의미론을 따라 **들여쓴 fence 와 바깥 fence
    안의 인용을 블록이 아니라고** 본다. 그런데 실제 파서(`_attachment_*_block_spans`)는
    `ln.strip().startswith(tag)` 라 **그것들도 블록으로 연다**. 둘이 갈리면 미전달 계수의
    기준이 실제 저장 시도와 어긋나, 파일은 만들어졌는데(또는 만들다 실패했는데) 답변은
    아무 말도 하지 않는 침묵 경로가 생긴다.

    기준은 **파서**다 — 그것이 실제로 무엇을 만들려 했는지가 유일하게 옳은 분모다.
    파서를 부를 수 없는 환경(가벼운 fake)에서는 fence 계수로 물러난다: 그 값은 파서가
    여는 집합의 **부분집합**이라 과대계상(=거짓 실패 문구)은 만들지 않는다.
    """
    try:
        edits = ops._attachment_edit_block_spans(content) or []
        news = ops._attachment_new_block_spans(content) or []
        return len(edits), len(news)
    except Exception:
        return count_attachment_block_fences(content)


def apply_assistant_attachment_blocks(conn, *, account: dict[str, Any], conversation_id: str,
                                      message_id: int, answer: str,
                                      failed: bool = False,
                                      tool_attachment_ids: "list[int] | tuple" = (),
                                      ops: Any = None, request: Any = None) -> dict[str, Any]:
    """첨부 쓰기 블록을 실제 첨부로 만들고 답변 본문을 정리한다.

    ## 계약

    - `failed=True`(실패·취소 run)면 materialize 를 건너뛴다. 그 경로엔 이미 오류가 표면화돼
      있어 미전달 고지까지 겹치면 같은 사실을 두 번 다르게 말하게 된다. **strip 은 한다** —
      실패했다고 파일 전문을 채팅에 쏟아 두지 않는다.
    - 실패는 답변 전달을 막지 않는다(fail-soft). 대신 **조용히 넘어가지도 않는다**: 블록 수
      대비 실제 생성 수가 모자라면 사유(있으면)와 건수를 답변에 덧붙여 본문의 성공 서술을
      정정한다. 사유를 모르는 경로(파싱 실패·캡 초과·저장 계층 오류)도 건수는 밝힌다.
    - content 갱신에 성공했을 때만 `answer_persisted=True` — 호출자가 자기 사본(result_json·
      회수 store)을 교체할지 그것으로 판단한다. 아니면 DB 메시지와 갈린다.

    Returns: `{"answer", "edited", "created", "skipped", "undelivered", "changed",
    "answer_persisted"}`.
    """
    log = logging.getLogger(__name__)
    if ops is None:                       # 지연 import — 이 모듈이 web 전체를 끌고 오지 않는다
        import app as ops                 # type: ignore[no-redef]

    out: dict[str, Any] = {
        "answer": answer, "edited": [], "created": [], "skipped": [],
        "undelivered": 0, "changed": False, "answer_persisted": False,
    }
    content = str(answer or "")
    tool_ids = [int(i) for i in (tool_attachment_ids or [])]
    if not content:
        return out
    message_saved = int(message_id or 0) > 0
    if not tool_ids and ("attachment-edit" not in content) and ("attachment-new" not in content):
        return out                        # 흔한 경로 — 비용 0

    edited: list = []
    created: list = []
    skipped: list[str] = []
    block_edited_n = 0
    if not failed and message_saved:
        budget = AttachmentWriteBudget(ops._ASSISTANT_EDIT_COUNT_CAP,
                                       ops._ASSISTANT_ATTACHMENT_TOTAL_SIZE_CAP_BYTES)
        try:
            edited = ops._materialize_assistant_attachment_edits(
                conn, account=account, conversation_id=conversation_id, answer=content,
                message_id=int(message_id), request=request, skipped=skipped, budget=budget) or []
            # 도구 전달분을 합치기 **전에** 블록 경로가 만든 수를 잡는다 — 합본으로 재면
            # "도구로 1건 전달 + 블록 1건 실패" 가 상쇄돼 경고가 사라진다.
            block_edited_n = len(edited)
            remaining = max(0, int(ops._ASSISTANT_EDIT_COUNT_CAP) - len(edited))
            created = ops._materialize_assistant_attachment_new(
                conn, account=account, conversation_id=conversation_id, answer=content,
                message_id=int(message_id), request=request, remaining_count=remaining,
                skipped=skipped, budget=budget) or []
        except Exception:
            log.error("첨부 materialize 실패 conv=%s msg=%s — 답변 전달은 계속",
                      conversation_id, message_id, exc_info=True)

    # 도구로 전달된 첨부를 답변 메시지에 바인딩 — 말풍선 칩 노출의 전제.
    if tool_ids and message_saved:
        try:
            bound = ops._bind_tool_delivered_attachments(
                conn, conversation_id=conversation_id, account_id=int(account.get("id") or 0),
                attachment_ids=tool_ids, message_id=int(message_id)) or []
            if bound:
                edited = list(bound) + list(edited)
            else:
                log.warning("도구 전달 첨부 %d건 바인딩 결과 0 — 칩 미노출 가능", len(tool_ids))
        except Exception:
            log.error("도구 전달 첨부 바인딩 실패 — 사용자 말풍선에 칩이 뜨지 않는다", exc_info=True)

    try:
        stripped = ops._strip_attachment_new_blocks(
            ops._strip_attachment_edit_blocks(content, edited), created)
    except Exception:
        log.error("첨부 블록 strip 실패 conv=%s — 원문 유지", conversation_id, exc_info=True)
        out.update(edited=edited, created=created, skipped=skipped)
        return out

    edit_fences, new_fences = _count_expected_blocks(ops, content)
    undelivered = max(0, edit_fences - block_edited_n) + max(0, new_fences - len(created))
    if not message_saved and not failed:
        skipped.extend(["답변 저장을 확인하지 못해 첨부를 연결하지 못했습니다."] * max(undelivered, bool(tool_ids)))
    if not failed and (skipped or undelivered):
        uniq: list[str] = []
        for reason in skipped:
            reason = str(reason).strip()
            if reason and reason not in uniq:
                uniq.append(reason)
        note = "\n\n> ⚠️ **첨부 전달 실패** — 아래 파일은 새 버전으로 저장되지 않았습니다.\n"
        if uniq:
            note += "".join(f">   · {r}\n" for r in uniq[:5])
            if len(uniq) > 5:
                note += f">   · … 외 {len(uniq) - 5}건\n"
        unexplained = max(0, undelivered - len(skipped))
        if unexplained:
            note += f">   · 사유 미상 {unexplained}건 — 파일 블록 형식 또는 저장 처리에 문제가 있습니다.\n"
        note += "> 위 답변에 갱신했다는 서술이 있어도 이 파일들은 전달되지 않았습니다."
        stripped = stripped.rstrip() + note
        log.warning("첨부 전달 실패 conv=%s — 사유있음 %d · 사유미상 %d "
                    "(블록 edit=%d/new=%d, 생성 edit=%d/new=%d)",
                    conversation_id, len(uniq), unexplained,
                    edit_fences, new_fences, block_edited_n, len(created))

    out.update(edited=edited, created=created, skipped=skipped,
               undelivered=undelivered, answer=stripped, changed=(stripped != content))
    if stripped != content and message_saved:
        try:
            out["answer_persisted"] = bool(ops._update_assistant_message_content(
                conn, conversation_id, int(message_id), stripped))
        except Exception:
            log.warning("첨부 strip content 갱신 실패 conv=%s msg=%s",
                        conversation_id, message_id, exc_info=True)
    return out

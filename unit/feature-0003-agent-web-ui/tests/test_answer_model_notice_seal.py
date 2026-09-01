"""답변에 모델·추론등급 고지가 실리지 않는다 — **서버가 집행한다**.

## 이 테스트가 잠그는 사고 (라이브 실측 2026-09-01)

브리지 답변 끝에 이런 줄이 붙어 있었다:

    > 이 답변은 claude 의 모델 opus · 추론등급 xhigh 로 생성했습니다.

이 문장을 만들던 곳은 러너(`bridge_agent.py`)이고 **정본에서는 2026-08-31 에 이미 지웠다**
(커밋 `82f3a160`, 사용자 결정). 라이브 배포본에도 그 커밋이 들어가 있었다. 그런데 같은 문구가
이틀 뒤인 09-01 11:05 제출분(`WebAiTasks` #80)에 그대로 실렸다.

원인은 **러너가 서버 배포 대상이 아니라는 것**이다. 러너는 각 사용자 머신에 설치된 사본이고
(실측: `~/.mysql-ai-bridge/bridge_agent.py`, 08-31 16:55 설치 — 제거 커밋 이전본), 서버를 아무리
배포해도 그 머신이 다시 받아 가기 전까지는 옛 코드가 돈다. 러너를 쓰지 않는 등록형 AI 는 애초에
그 코드를 지나지 않으므로 자기 판단으로 같은 문장을 쓸 수도 있다.

그래서 집행을 **서버의 단일 문**(`submit_answer`)으로 옮겼다. 여기가 답변이 대화로 가는 유일한
경로이므로(`_deliver_web_bridge_answer` 호출처는 이 함수 하나뿐), 한 번 걷어내면 구버전 러너·
등록형 AI·AI 자발 부착이 같은 지점에서 닫힌다.

## 이 스위트가 특별히 지키는 두 설계 결정

**① 범위는 답변 말미다(펜스를 세지 않는다).** 초안은 코드 펜스를 토글해 「안/밖」 을 갈랐는데,
적대 리뷰가 두 방향으로 깨뜨렸다 — 닫히지 않은 펜스 하나면 봉인이 통째로 뚫리고(AI 출력이
코드블록 도중 잘리는 것은 흔하다), 4-백틱 중첩 펜스에서는 반대로 블록 **안의 내용을 지웠다**.
지금은 말미 `_NOTICE_TAIL_LINES` 줄만 본다.

**② 정규식은 문장 골격 전체다(어휘 조각이 아니다).** 초안은 `모델`·`추론등급` 어휘만 봐서
`모델링`·`논리 모델` 에 부분일치했고, 더 나쁘게는 **미반영 사실을 자기 말로 쓴 문장**까지
삼켰다 — 지키려던 계약이 같은 정규식에서 깨지는 형태였다.

## 왜 두 겹으로 보는가

`_strip_model_notice` 를 직접 부르는 검사만 두면 **헬퍼는 옳은데 진입점이 그것을 안 쓰는** 상태를
통과시킨다(이 저장소가 반복해서 겪은 형태). 그래서 아래 절반은 `submit_answer` 를 가짜 DB·가짜
전달 함수로 **실제 구동**해서, 저장본(`WebAiTasks.Answer`)과 대화 전달본 **양쪽**에 고지가 없음을
확인한다 — 소비처가 넷(저장·전달·원장 바이트수·제목)이라 한 곳만 보면 나머지가 갈릴 수 있다.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import time

import pytest

import routers.ai_tools as ai_tools


_BODY = "테이블 3개를 확인했습니다.\n\n결론: 인덱스가 없습니다."

#: 러너가 실제로 만드는 미반영 고지 (`bridge_agent.py` 의 고정 문구).
_UNMET = ("> 참고: 요청하신 모델 opus · 추론등급 xhigh 은(는) 이 AI 에서 쓸 수 없어"
          " 기본 설정으로 답했습니다.")


# ── 걷어내야 하는 형태 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("notice", [
    # 러너가 만드는 세 형태 (모델만 · 등급만 · 둘 다).
    "> 이 답변은 claude 의 모델 opus · 추론등급 xhigh 로 생성했습니다.",
    "> 이 답변은 claude 의 모델 haiku 로 생성했습니다.",
    "> 이 답변은 claude 의 추론등급 xhigh 로 생성했습니다.",
    # 런타임 이름은 러너가 신고하는 값이라 서버가 열거하지 않는다.
    "> 이 답변은 codex 의 모델 gpt-5.6-sol · 추론등급 high 로 생성했습니다.",
    "> 이 답변은 ollama 의 모델 qwen3 로 생성했습니다.",
    # 러너 밖 AI 가 자기 판단으로 쓸 때의 변형 — 접두·공백·종결이 흔들린다.
    "이 답변은 gemini 의 모델 flash 로 생성했습니다.",
    "이 답변은 gemini 의 모델 flash 로 생성했습니다",          # 마침표 없음
    ">> 이 답변은 claude 의 모델 opus 로 생성했습니다.",        # 중첩 인용
    "- > 이 답변은 claude 의 모델 opus 로 생성했습니다.",       # 목록 + 인용
    "  이 답변은 claude 의 모델 opus 로 생성했습니다.",         # 들여쓰기
    "> 이 답변은　claude 의 모델 opus 로 생성했습니다.",        # 전각 공백 U+3000
    "> 이 답변은 claude의 모델 opus 로 생성했습니다.",          # 조사 붙여쓰기
    "> 이 답변은 claude 의 모델 opus 로 생성했습니다.\r",       # CRLF 잔여 \r
])
def test_notice_line_is_stripped(notice):
    got = ai_tools._strip_model_notice(f"{_BODY}\n\n{notice}")
    assert got == _BODY, f"걷히지 않았다: {notice!r}"


# ── 걷어내면 안 되는 것 ─────────────────────────────────────────────────────

def test_unmet_notice_alone_survives():
    """「고른 값이 반영되지 않았다」는 **다른 사실**이라 남는다 (사용자 결정 2026-08-31·09-01).

    화면 어디에도 드러나지 않으므로 답변이 유일한 통로다. 모델 이름이 문장 안에 있다는 이유로
    함께 지우면, 사용자는 고르지 않은 기본 모델의 답을 자기가 고른 모델의 답으로 읽는다.

    ⚠ 이 케이스만으로는 정규식의 과잉을 못 잡는다 — 미반영 고지에는 `생성했습니다` 가 없어
    빠른 길에서 되돌아온다. 그 축은 아래 `…_mixed…` 와 `…_paraphrased…` 가 본다.
    """
    got = ai_tools._strip_model_notice(f"{_BODY}\n\n{_UNMET}")
    assert got == f"{_BODY}\n\n{_UNMET}"


def test_mixed_notices_keep_only_unmet():
    """둘이 섞여 오면 갈라낸다 — **정규식의 과잉을 실제로 잡는 케이스**.

    빠른 길을 지나 정규식까지 도달하므로, 어휘만 보고 지우는 구현은 여기서 미반영 고지까지
    삼켜 실패한다.
    """
    applied = "> 이 답변은 claude 의 추론등급 xhigh 로 생성했습니다."
    got = ai_tools._strip_model_notice(f"{_BODY}\n\n{_UNMET}\n\n{applied}")
    assert "기본 설정으로 답했습니다" in got, "미반영 고지까지 삼켰다"
    assert "로 생성했습니다" not in got
    assert "인덱스가 없습니다" in got


@pytest.mark.parametrize("line", [
    # 미반영 사실을 **자기 말로** 쓴 문장 — 러너 고정 문구가 아니어도 살아야 한다.
    # 이 경로를 닫으려고 서버 집행을 도입했는데 같은 정규식이 그것을 지우면 자멸이다.
    "> 이 답변은 요청하신 모델 opus 대신 기본 모델로 생성했습니다.",
    # 축 이름의 부분일치 (`모델링` · `논리 모델`).
    "이 답변은 모델링 도구로 생성했습니다.",
    "이 답변은 논리 모델 기준으로 생성했습니다.",
    # 축 자체가 없는 문장.
    "이 답변은 2026-08-30 백업본으로 생성했습니다.",
])
def test_lookalike_sentences_survive(line):
    src = f"{_BODY}\n\n{line}"
    assert ai_tools._strip_model_notice(src) == src, f"과잉 제거: {line!r}"


def test_inline_mention_inside_a_sentence_is_kept():
    """줄 전체가 고지일 때만 걷는다 — 문장 중간의 언급까지 지우면 본문이 잘린다."""
    src = f"{_BODY} 참고로 이 답변은 claude 의 모델 opus 로 생성했습니다. 다음 단계는 …"
    assert ai_tools._strip_model_notice(src) == src


def test_answer_without_notice_is_returned_unchanged():
    """빠른 길 — 거의 모든 답변이 여기서 끝난다(불필요한 재조립으로 본문을 흔들지 않는다)."""
    src = "SELECT 1;\n\n결과는 1 입니다.\n"
    assert ai_tools._strip_model_notice(src) is src


def test_no_match_returns_the_original_object():
    """빠른 길을 지나더라도 **걷은 것이 없으면** 원문 그대로다.

    재조립하면 선행 들여쓰기 코드블록(4칸)이 문단으로 바뀌거나 후행 개행이 사라진다 — 아무것도
    제거하지 않은 입력이 바뀌는 것은 그 자체로 결함이다(적대 리뷰 P2-1).
    """
    src = "    SELECT 1\n\n이 답변은 논리 모델 기준으로 생성했습니다.\n\n"
    assert ai_tools._strip_model_notice(src) is src


def test_leading_indentation_is_preserved_when_stripping():
    """걷을 때도 **앞쪽**은 건드리지 않는다 — 4칸 들여쓰기 코드블록이 문단이 되면 안 된다."""
    src = ("    SELECT 1\n\n본문입니다.\n\n"
           "> 이 답변은 claude 의 모델 opus 로 생성했습니다.")
    got = ai_tools._strip_model_notice(src)
    assert got.startswith("    SELECT 1"), "선행 공백이 사라졌다"
    assert "로 생성했습니다" not in got


# ── 범위 계약 (말미만 본다) ─────────────────────────────────────────────────

def test_notice_far_above_the_tail_is_left_alone():
    """본문 한복판의 같은 문장은 **범위 밖**이다 — 예시 인용을 지키는 쪽의 계약."""
    filler = "\n".join(f"{i}번째 줄입니다." for i in range(20))
    src = (f"{filler}\n> 이 답변은 claude 의 모델 opus 로 생성했습니다.\n{filler}")
    assert ai_tools._strip_model_notice(src) == src


def test_unclosed_code_fence_does_not_leak_the_notice():
    """**닫히지 않은 펜스로 봉인이 뚫리지 않는다** (적대 리뷰 P1-3).

    AI 출력이 코드블록 도중 잘리고 CLI 가 exit 0 이면 러너는 `ok=True` 로 보고 고지를 덧붙인다.
    펜스를 세는 구현에서는 그 고지가 「열린 채 끝난 펜스 안」이 되어 그대로 통과했다 — 이 패치가
    막으려던 사고가 그대로 재발하는 형태였다.
    """
    src = ("다음 쿼리로 확인했습니다.\n\n```sql\nSELECT COUNT(*) FROM Orders\n"
           "WHERE CreatedAt >= '2026-08-01'\n\n"
           "> 이 답변은 claude 의 모델 opus · 추론등급 xhigh 로 생성했습니다.")
    got = ai_tools._strip_model_notice(src)
    assert "로 생성했습니다" not in got, "닫히지 않은 펜스가 봉인을 뚫었다"
    assert "SELECT COUNT(*)" in got, "본문까지 잘렸다"


def test_nested_backtick_fence_content_is_not_destroyed():
    """4-백틱 중첩 펜스 **안의 내용을 지우지 않는다** (적대 리뷰 P1-2).

    ```` ``` ```` 를 보여주는 정석 마크다운이다. 펜스를 토글하던 구현은 여기서 상태가 뒤집혀
    코드블록 안을 비웠다 — 답변 데이터 손상이다. 지금은 펜스를 세지 않고, 이 인용은 말미
    범위보다 위에 있으므로 온전히 남는다.
    """
    src = ("문구는 이렇게 생겼습니다:\n\n````markdown\n```\n"
           "> 이 답변은 claude 의 모델 opus 로 생성했습니다.\n```\n````\n\n"
           "위 형태를 걷어냅니다.\n확인이 끝났습니다.\n마무리합니다.\n"
           "추가 설명입니다.\n끝.")
    got = ai_tools._strip_model_notice(src)
    assert "> 이 답변은 claude 의 모델 opus 로 생성했습니다." in got, "인용까지 지웠다"
    assert got.count("```") == src.count("```"), "펜스 구조가 깨졌다"


def test_notice_only_answer_is_not_emptied():
    """본문은 정리 결과가 비면 **정리하지 않는다** (적대 리뷰 P2-3).

    빈 답변으로 만들면 위쪽 검사가 400 을 돌려주고, 그 task 는 점유된 채 lease 만료까지 대기
    말풍선으로 남는다. 병리적 제출이지만 사용자가 무언가를 보는 쪽이 낫다.
    """
    src = "> 이 답변은 claude 의 모델 opus 로 생성했습니다."
    assert ai_tools._strip_model_notice(src) == src


def test_allow_empty_drops_a_notice_only_value():
    """제목 축은 그 예외를 끈다 — 한 줄이라 걷으면 항상 비고, 빈 제목은 무해하다.

    본문 규칙(`비면 원문`)을 제목에 그대로 쓰면 봉인이 **제목에서만** 뚫린다(실제로 이 테스트가
    그 상태를 잡아 `allow_empty` 가 생겼다).
    """
    src = "이 답변은 claude 의 모델 opus 로 생성했습니다."
    assert ai_tools._strip_model_notice(src, allow_empty=True) == ""


# ── 성능 (async 핸들러 안에서 동기로 돈다) ──────────────────────────────────

@pytest.mark.parametrize("size", [30_000, 180_000])
def test_pathological_single_line_is_bounded(size):
    """아주 긴 **한 줄**이 이벤트 루프를 세우지 않는다 (적대 리뷰 P1-1).

    종전 초안(lazy 이중 `[^\\n]*?`)은 같은 입력 180KB 에 36초를 실측했다. 지금은 정규식에 lazy
    중첩이 없고, 그와 별개로 줄 길이 상한(`_NOTICE_MAX_LINE`)이 비용을 상수로 묶는다.
    """
    hostile = "이 답변은 " + "모델 " * (size // 6) + "로 생성했습니다"
    t0 = time.perf_counter()
    ai_tools._strip_model_notice(hostile)
    assert time.perf_counter() - t0 < 0.5, "정리 비용이 입력 길이를 따라 폭발한다"


def test_long_notice_like_line_is_skipped_by_length_guard():
    """상한을 넘는 줄은 아예 검사하지 않는다 — 고지는 100자 안팎이다."""
    long_line = ("> 이 답변은 claude 의 모델 " + "x" * _guard_len() +
                 " 로 생성했습니다.")
    src = f"{_BODY}\n\n{long_line}"
    assert ai_tools._strip_model_notice(src) == src


def _guard_len() -> int:
    return ai_tools._NOTICE_MAX_LINE


# ── 진입점 배선 (submit_answer 실제 구동) ────────────────────────────────────


class _FakeRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return json.loads(json.dumps(self._payload))


class _FakeCursor:
    """`UPDATE WebAiTasks … SET Answer=%s` 의 파라미터를 잡아 둔다."""

    def __init__(self, sink):
        self._sink = sink
        self.rowcount = 1

    def execute(self, sql, params=None):
        self._sink.append((sql, params))

    def fetchone(self):
        return None

    def close(self):
        pass


class _FakeConn:
    def __init__(self, sink):
        self._sink = sink

    def cursor(self):
        return _FakeCursor(self._sink)

    def commit(self):
        pass

    def rollback(self):
        pass


def _run_submit(monkeypatch, answer: str, title: str = "") -> dict:
    """`submit_answer` 를 실제로 구동하고 소비처별 값을 돌려준다."""
    sink: list = []
    seen: dict = {}

    monkeypatch.setattr(ai_tools, "_load_task", lambda *a, **k: {
        "task_id": "t_x", "status": "open", "conversation_id": 7,
        "kind": "chat", "datasource_key": None, "product_id": None})
    monkeypatch.setattr(ai_tools, "_sibling_tasks", lambda *a, **k: [])
    monkeypatch.setattr(ai_tools, "_conversation_access_denied", lambda *a, **k: None)
    monkeypatch.setattr(ai_tools, "_record_bridge_activity", lambda *a, **k: None)
    monkeypatch.setattr(ai_tools, "_safe_record", lambda *a, **k: None)
    monkeypatch.setattr(ai_tools, "_pg", lambda: None)
    monkeypatch.setattr(ai_tools._ledger, "record",
                        lambda *a, **k: seen.update(ledger_bytes=k.get("bytes_out")))

    def _deliver(conn, task_id, account, body, *, title="", **kw):
        seen["delivered"] = body
        seen["title"] = title
        return True

    monkeypatch.setattr(ai_tools, "_deliver_web_bridge_answer", _deliver)

    payload = {"task_id": "t_x", "answer": answer, "source_tasks": ["t_x"]}
    if title:
        payload["title"] = title
    res = asyncio.run(ai_tools.submit_answer(
        _FakeRequest(payload),
        ctx={"account": {"id": 1, "username": "admin"}, "client_id": "c1"},
        conn=_FakeConn(sink)))
    assert res.status_code == 200, res.body

    for sql, params in sink:
        if "UPDATE WebAiTasks" in sql and params:
            seen["stored"] = str(params[0])
    assert seen.get("stored"), "저장 UPDATE 를 잡지 못했다 — 보려는 경로가 바뀌었다"
    return seen


def test_submit_answer_strips_notice_on_every_consumer(monkeypatch):
    """저장본·대화 전달본·원장 바이트수 **전부**에서 고지가 사라진다.

    한쪽만 보면 나머지가 갈린다 — 화면(전달본)만 깨끗하고 저장본에 남으면 그 답변은 나중에
    요약·검색 경로로 우리 컨텍스트에 되돌아온다.
    """
    seen = _run_submit(
        monkeypatch,
        f"{_BODY}\n\n> 이 답변은 claude 의 모델 opus · 추론등급 xhigh 로 생성했습니다.")
    assert "로 생성했습니다" not in seen["stored"], "저장본에 고지가 남았다"
    assert "로 생성했습니다" not in seen["delivered"], "대화 전달본에 고지가 남았다"
    assert "인덱스가 없습니다" in seen["stored"], "본문까지 잘렸다"
    # 원장은 **저장된 것**의 크기를 적어야 한다 — 정리 전 길이를 적으면 기록이 거짓이 된다.
    assert seen["ledger_bytes"] == len(_BODY.encode("utf-8"))


def test_submit_answer_keeps_unmet_notice(monkeypatch):
    """진입점을 지나도 미반영 고지는 살아남는다 (제거 범위가 넓어지지 않았다).

    빠른 길에 가리지 않도록 **두 고지를 함께** 넣는다 — 미반영만 넣으면 정규식에 닿지도 않아
    "범위가 안 넓어졌다" 를 실제로 확인한 것이 아니다.
    """
    seen = _run_submit(
        monkeypatch,
        f"{_BODY}\n\n{_UNMET}\n\n> 이 답변은 claude 의 모델 opus 로 생성했습니다.")
    for where in ("stored", "delivered"):
        assert "기본 설정으로 답했습니다" in seen[where], f"{where} 에서 미반영 고지가 사라졌다"
        assert "로 생성했습니다" not in seen[where], f"{where} 에 고지가 남았다"


def test_submit_answer_seals_the_title(monkeypatch):
    """제목도 같은 봉인을 지난다 — 사용자 대면 표면은 본문만이 아니다 (적대 리뷰 P2-4)."""
    seen = _run_submit(
        monkeypatch, _BODY,
        title="이 답변은 claude 의 모델 opus 로 생성했습니다.")
    assert "로 생성했습니다" not in seen["title"], "대화 제목에 고지가 박힌다"


# ── 러너 정본 회귀 잠금 ──────────────────────────────────────────────────────

def test_runner_source_does_not_reintroduce_the_notice():
    """러너 정본은 이 문장을 **만들지 않는다** — 서버 집행이 생겼다고 되돌리지 않는다.

    두 겹인 이유: 만들지 않는 것이 먼저고(러너), 이미 퍼진 사본과 등록형 AI 를 닫는 것이
    나중이다(서버). 서버가 지운다는 이유로 러너가 다시 붙이기 시작하면, 러너를 쓰지 않는
    경로의 고지 유무가 서버 정규식 하나에만 매달리게 된다.

    검사 범위는 **파일 전체**다 — `handle_one` 만 보면 생성이 다른 함수로 옮겨간 재도입을
    통과시킨다(적대 리뷰 P2-5).
    """
    unit = pathlib.Path(__file__).resolve().parents[2]
    srcs = [unit / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py",
            unit / "feature-0003-agent-web-ui" / "src" / "static" / "agent"
            / "bridge_agent.py"]
    for src in srcs:
        text = src.read_text(encoding="utf-8")
        offenders = [ln for ln in text.split("\n")
                     if "로 생성했습니다" in ln and not ln.lstrip().startswith("#")]
        assert not offenders, f"{src.name} 이 고지를 다시 만든다: {offenders[:2]}"


def test_runner_copies_stay_identical():
    """두 사본은 **같은 파일**이어야 한다 — 갈리면 사용자가 받는 러너가 정본이 아니게 된다."""
    unit = pathlib.Path(__file__).resolve().parents[2]
    a = (unit / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_bytes()
    b = (unit / "feature-0003-agent-web-ui" / "src" / "static" / "agent"
         / "bridge_agent.py").read_bytes()
    assert a == b, "러너 정본과 서빙 사본이 갈렸다"

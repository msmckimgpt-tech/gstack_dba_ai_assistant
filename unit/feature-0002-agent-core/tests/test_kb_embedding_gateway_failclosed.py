"""local-llm-decommission 후속 — 임베딩 경로의 fail-closed 계약 (codex 적대 리뷰 P1·P2, 2026-09-07).

## 왜 필요한가

`local-llm-decommission`(2026-09-07)이 `kb_embedding_worker` 에서 `LOCAL_LLM_API_KEY/BASE`
fallback 을 제거했다. 그 제거 자체는 옳았으나 **두 개의 구멍을 남겼고 적대 리뷰가 잡았다**:

- **P1** `base_url` 미지정 → OpenAI SDK 기본값 `https://api.openai.com/v1`. 즉 KEY 만 있고
  URL 이 없는 구성에서 **게이트웨이 자격증명과 KB 텍스트가 OpenAI 로 나간다.**
  `docs/SECURITY.md`(CHG-20260522-0006)는 "LLM 호출 entry 는 게이트웨이만 허용" 이고
  OpenAI direct 경로를 의도적으로 폐기했으므로, 이 무지정 상태는 그 결정을 조용히 우회한다.
- **P2** `AGENT_KB_EMBEDDING_MODEL` 기본값이 빈 값이 됐는데 `AGENT_KB_EMBEDDING_AUTO` 는 여전히
  기본 활성이라, insight-worker 백필 데몬이 `INTERVAL_SEC` 마다 **빈 모델명으로** 임베딩을
  시도한다. 쿼리 임베딩만 `_embed_query_vector` 에서 no-op 이 됐고 백필 경로는 그 방어를
  공유하지 않았다 (§16.7 G8-a — 결정을 일부 경로에만 반영).

두 계약을 여기서 잠근다. 이 파일은 **순수 함수 계약**이 아니라 *실제 진입점*(`call_openai_embeddings`,
`run_embedding_pass`)을 대상으로 하므로 배선 사각(§16.7 G14-e)이 생기지 않는다.
"""
import sys
import pathlib

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scripts import kb_embedding_worker as W  # noqa: E402


# ── P1: 게이트웨이 URL·KEY paired 요구 ────────────────────────────────────────

@pytest.mark.parametrize(
    "key,base,missing_token",
    [
        ("k", "", "BEDROCK_GATEWAY_URL"),          # ← P1 의 정확한 형태
        ("", "http://bedrock-gateway:8080/v1", "BEDROCK_GATEWAY_API_KEY"),
        ("", "", "BEDROCK_GATEWAY_URL"),
    ],
)
def test_embedding_client_requires_both_gateway_settings(monkeypatch, key, base, missing_token):
    """한쪽만 설정된 구성에서는 **클라이언트를 만들기 전에** 실패한다.

    핵심은 "실패한다" 가 아니라 **OpenAI 기본 endpoint 로 나가지 않는다** 다.
    따라서 `OpenAI` 생성자가 호출되면 그 자체로 계약 위반이다.
    """
    monkeypatch.setenv("BEDROCK_GATEWAY_API_KEY", key)
    monkeypatch.setenv("BEDROCK_GATEWAY_URL", base)

    called = []

    class _Boom:
        def __init__(self, *a, **kw):
            called.append(kw)
            raise AssertionError(
                f"OpenAI 클라이언트가 생성됐다 — base_url={kw.get('base_url')!r}. "
                "게이트웨이 설정이 불완전하면 생성 전에 차단돼야 한다(P1)."
            )

    import openai as _openai
    monkeypatch.setattr(_openai, "OpenAI", _Boom)

    with pytest.raises(RuntimeError) as ei:
        W.call_openai_embeddings(["텍스트"], "titan-embed", 5, 1)
    assert missing_token in str(ei.value), str(ei.value)
    assert called == [], "클라이언트가 생성되면 안 된다"


def test_embedding_client_passes_explicit_base_url(monkeypatch):
    """양쪽이 설정되면 `base_url` 을 **명시 전달**한다 (SDK 기본값에 맡기지 않는다)."""
    monkeypatch.setenv("BEDROCK_GATEWAY_API_KEY", "k")
    monkeypatch.setenv("BEDROCK_GATEWAY_URL", "http://bedrock-gateway:8080/v1")

    seen = {}

    class _Resp:
        data = [type("D", (), {"embedding": [0.1, 0.2]})()]

    class _Client:
        def __init__(self, **kw):
            seen.update(kw)
            self.embeddings = self

        def create(self, **kw):
            return _Resp()

    import openai as _openai
    monkeypatch.setattr(_openai, "OpenAI", _Client)

    out = W.call_openai_embeddings(["텍스트"], "titan-embed", 5, 1)
    assert out == [[0.1, 0.2]]
    assert seen.get("base_url") == "http://bedrock-gateway:8080/v1", seen
    assert seen.get("api_key") == "k"


# ── P2: 모델 미설정 시 백필 no-op ─────────────────────────────────────────────

def test_backfill_is_noop_when_model_unset(monkeypatch):
    """`AGENT_KB_EMBEDDING_MODEL` 이 빈 값이면 백필이 **DB 도 게이트웨이도 건드리지 않는다**.

    `AGENT_KB_EMBEDDING_AUTO` 가 기본 활성이라, 이 가드가 없으면 데몬이 매 tick 마다
    빈 모델명으로 요청을 반복한다.
    """
    monkeypatch.setattr(W, "get_settings", lambda: {
        "model": "", "batch_size": 25, "timeout": 300, "max_attempts": 3,
    })

    def _no_conn():
        raise AssertionError("모델 미설정인데 PG 연결을 열었다 — 진입 자체가 막혀야 한다(P2)")

    def _no_embed(*a, **kw):
        raise AssertionError("모델 미설정인데 임베딩을 호출했다(P2)")

    monkeypatch.setattr(W, "open_pg_conn", _no_conn)
    monkeypatch.setattr(W, "call_openai_embeddings", _no_embed)

    rep = W.run_embedding_pass(max_rows=10)
    assert rep["processed"] == 0
    assert rep["failed"] == 0
    assert rep.get("skipped") == "embedding-model-unset", rep
    # 비활성은 실패가 아니다 — error 를 실으면 caller 가 매 tick 경고를 쌓는다.
    assert not rep.get("error"), rep


def test_backfill_still_runs_when_model_set(monkeypatch):
    """가드가 **정상 경로를 막지 않는다** (§16.7 G9-c — 차단 로직의 정상 경로 실측)."""
    monkeypatch.setattr(W, "get_settings", lambda: {
        "model": "titan-embed", "batch_size": 2, "timeout": 300, "max_attempts": 1,
    })
    monkeypatch.setattr(W, "open_pg_conn", lambda: object())
    batches = [[("h1", "t1")], []]
    monkeypatch.setattr(W, "fetch_pending_batch", lambda conn, n: batches.pop(0) if batches else [])
    monkeypatch.setattr(W, "call_openai_embeddings", lambda t, m, to, ma: [[0.1]] * len(t))
    monkeypatch.setattr(W, "update_embeddings", lambda conn, h, e, m: len(h))
    monkeypatch.setattr(W, "count_pending", lambda conn: 0)

    rep = W.run_embedding_pass(max_rows=10)
    assert rep["processed"] == 1, rep
    assert rep.get("skipped") is None, rep

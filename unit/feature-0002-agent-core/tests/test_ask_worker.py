"""ask-worker 순수 로직 단위 테스트 (TASK-0169).

payload round-trip / result slim / config 기본값. 실 DB·실행 불필요.
"""
from __future__ import annotations


def test_payload_to_kwargs_round_trip():
    import modules.ask as ask
    payload = {
        "user_message": "select 1",
        "conversation_id": "conv-1",
        "model": "edge",
        "product_id": 3,
        "role_id": 2,
        "account_id": 99,            # payload 안 값은 무시되고 인자 account_id 우선
        "allowed_schemas": ["dbgame"],
        "product_mode": "pinned",
        "attachment_ids": [1, 2],
        "new_attachment_ids": [2],
        "image_inline_path": "/shared/ask-inline/img.json",
        "text_inline_path": None,
    }
    kw = ask._payload_to_kwargs(payload, account_id=42, run_id="run-7")
    assert kw["user_message"] == "select 1"
    assert kw["conversation_id"] == "conv-1"
    assert kw["model"] == "edge"
    assert kw["account_id"] == 42           # 인자 우선
    assert kw["allowed_schemas"] == ["dbgame"]
    assert kw["attachment_ids"] == [1, 2]
    assert kw["image_inline_path"] == "/shared/ask-inline/img.json"
    assert kw["text_inline_path"] is None
    assert kw["output_mode"] == "json"      # 항상 json
    assert kw["run_id"] == "run-7"          # 주입 run_id
    # conv_file / temperature / api_key 는 전달 안 함(worker 재계산/무시).
    assert "conv_file" not in kw
    assert "temperature" not in kw


def test_payload_to_kwargs_defaults_for_missing():
    import modules.ask as ask
    kw = ask._payload_to_kwargs({}, account_id=1, run_id="r")
    assert kw["user_message"] == ""
    assert kw["conversation_id"] is None
    assert kw["product_mode"] == "pinned"
    assert kw["attachment_ids"] == []
    assert kw["new_attachment_ids"] == []


def test_slim_result_keeps_shape_fields():
    import modules.ask as ask
    full = {
        "answer": "42", "conversation_id": "c", "run_id": "r",
        "executed_sql": "select 1", "result_csv_paths": ["/a.csv"],
        "rationale": "because", "error": "", "steps": [{"i": 1}],
        "internal_junk": {"big": "x" * 1000},  # 보존 대상 아님
    }
    slim = ask._slim_result(full)
    assert slim["answer"] == "42"
    assert slim["steps"] == [{"i": 1}]          # 응답 shape 패리티
    assert slim["result_csv_paths"] == ["/a.csv"]
    assert "internal_junk" not in slim


def test_slim_result_handles_non_dict():
    import modules.ask as ask
    out = ask._slim_result(None)
    assert "error" in out


def test_config_ask_worker_defaults():
    import shared.config as cfg
    # 실행모델 flag 는 유효한 값이어야 한다. 코드 default 는 inprocess(os.getenv 의 2번째
    # 인자)이나 .env 로 override 가능하며, 라이브 cutover 후엔 worker 로 설정돼 있을 수 있다
    # (TASK-0169). 따라서 특정 값이 아니라 유효 집합 membership 을 단언한다 — make test 가
    # 라이브 .env(env_file)를 로드하므로 `== "inprocess"` 고정은 cutover 후 false-positive.
    assert cfg.AGENT_ASK_EXECUTION_MODE in ("inprocess", "worker")
    # stale 임계는 run_timeout(agent_core 와 동일 공식) 보다 커야 false-positive
    # requeue 가 없다(BLOCKER 3/E 정합). AGENT_TIMEOUT_SEC 를 키운 배포에서도 성립해야 함.
    run_timeout = max(cfg.AGENT_TIMEOUT_SEC * 3, max(1, int(cfg.AGENT_EARLY_FINALIZE_MS / 1000)))
    assert cfg.AGENT_ASK_WORKER_STALE_SEC > run_timeout
    # heartbeat 주기는 stale 보다 충분히 작아야 한다.
    assert cfg.AGENT_ASK_WORKER_HEARTBEAT_SEC < cfg.AGENT_ASK_WORKER_STALE_SEC
    assert cfg.AGENT_ASK_WORKER_ATTEMPTS_CAP >= 1


def test_run_agent_accepts_run_id_param():
    # run_agent 시그니처에 run_id 주입 인자가 추가됐는지(worker correlate).
    import inspect
    import agent_core
    sig = inspect.signature(agent_core.run_agent)
    assert "run_id" in sig.parameters
    sig2 = inspect.signature(agent_core._run_agent_core)
    assert "run_id" in sig2.parameters

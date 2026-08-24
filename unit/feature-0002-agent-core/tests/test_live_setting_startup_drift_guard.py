"""conv-audit FR-live-cap-derived-from-startup-snapshot — "live 설정을 startup 스냅샷으로 읽어
파생하는" 부류의 부정합을 **구조적으로** 막는 회귀 가드.

배경(2026-08-24 전수 점검):
  `runtime_settings` 스펙의 `apply_mode="live"` 값은 관리 콘솔에서 바꾸면 즉시 반영된다.
  그런데 `shared/config.py` 는 그 중 일부를 `_startup_int()` 로 **기동 시 1회** 읽어 상수에
  넣는다. 그 상수를 다시 **다른 임계의 파생 소스**로 쓰면, 소비처가 live 를 읽는 순간 두 값이
  갈라진다 — 그리고 그 갈라짐은 조용하다(어디서도 에러가 나지 않는다).

  실제로 두 건이 그렇게 터졌다:
    · `AGENT_ASK_WORKER_STALE_SEC` = `max(cfg.AGENT_TIMEOUT_SEC*3, …)+180`(**startup**) vs
      `agent_core.run_timeout_sec` = `_rts.get_int("AGENT_TIMEOUT_SEC")*3`(**live**)
      → 콘솔에서 상한을 올리면 회수 임계만 옛 값 → **살아있는 정상 run 을 sweeper 가 회수**.
    · `WEB_PROGRESS_STALE_TIMEOUT_SECONDS` = 1200 상수 vs per-attempt 상한 live 1800
      → 정상 대기를 "작업 중단" 으로 오표시(`FR-stale-threshold-below-llm-attempt-cap`).

  개별 수정만으로는 재발한다 — 다음 사람이 같은 형태를 또 쓴다. 그래서 **패턴 자체**를 잠근다.

여기서 고정하는 계약:
  T1 config.py 모듈 레벨에서 **live-스펙 startup 상수를 참조해 다른 상수를 만드는 대입**이 없다.
     (AST 검사 — 문자열 grep 이 아니라 실제 참조 구조를 본다.)
  T2 live 스펙 키를 `_startup_int` 로 읽는 목록은 **근거가 기록된 allowlist** 안에만 있다.
  T3 `AGENT_ASK_WORKER_STALE_SEC` 는 run 길이·per-attempt 상한과 무관하다(heartbeat 파생).
  T4 `modules/llm.py` 는 startup 상수를 timeout 으로 **명시 전달**하지 않는다(전부 live fallback).

`make test` (agent 이미지, --no-deps) 에서 DB 없이 소스·스펙만으로 실행된다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from shared import config as cfg
from shared import runtime_settings as rts

_CONFIG_PATH = Path(cfg.__file__)


@pytest.fixture(autouse=True)
def _isolate_stale_state(monkeypatch):
    """§18.8 codex [P2]: env override 와 high-water 는 **프로세스 상태**다 — 테스트마다 격리.

    격리하지 않으면 (a) 실행 환경에 `AGENT_ASK_WORKER_STALE_SEC` 가 설정돼 있으면 파생 경로를
    타지 않아 단조성 단언이 **비결정적으로** 깨지고(vacuous/flaky) (b) 앞 테스트가 올린
    high-water 가 뒤 테스트의 기대를 무너뜨린다.
    """
    monkeypatch.setattr(cfg, "_ASK_STALE_ENV_OVERRIDE", "", raising=False)
    monkeypatch.setattr(cfg, "_ask_stale_high_water", 0, raising=False)
    yield


def _live_spec_keys() -> set[str]:
    out: set[str] = set()
    for spec in rts.list_specs():
        d = spec if isinstance(spec, dict) else {}
        if d.get("apply_mode") == "live" and d.get("key"):
            out.add(str(d["key"]))
    return out


def _startup_int_keys(src: str) -> set[str]:
    return set(re.findall(r'_startup_int\(\s*"([A-Z0-9_]+)"', src))


# apply_mode=live 인데 startup 상수로도 읽히는 키 — **상수 자체의 존재는 허용**하되 근거를 남긴다.
# 규칙: 여기 등재된 키의 startup 상수는 "재배포 경계 반영이 무해한 경로"(저수준 DB 연결 설정 등)
# 에만 쓰고, **판정·임계의 파생 소스로 쓰지 않는다**(그건 T1 이 막는다).
_ALLOWED_LIVE_AS_STARTUP = {
    # 저수준 DB 연결 설정(`modules/utils.py` connection_timeout · `shared/db.py` 쿼리 예산 폴백)에
    # 재사용된다. 그 경로는 재배포 시 반영돼도 무해하다(스펙 description 이 그 비대칭을 명시).
    # 런타임 판정은 전부 `_rts.get_int("AGENT_TIMEOUT_SEC")` 를 쓴다.
    "AGENT_TIMEOUT_SEC",
    # 실소비처 0 — 유일한 사용처 `modules/mcp_client.py` 가 live 를 직접 읽는다. export 잔재.
    "MCP_TIMEOUT_SEC",
}


# ── T1: live-스펙 startup 상수를 파생 소스로 쓰는 모듈-레벨 대입 금지 ──────────────
def test_no_module_level_derivation_from_live_startup_constant():
    src = _CONFIG_PATH.read_text(encoding="utf-8")
    live = _live_spec_keys()
    suspects = live & _startup_int_keys(src)
    assert suspects, "테스트 전제 붕괴 — live 스펙과 startup 읽기의 교집합이 사라졌다(가드 vacuous)"

    tree = ast.parse(src)
    lines = src.splitlines()

    # §18.8 codex [P2]: 모듈 레벨만 보면 함수 안 `return AGENT_TIMEOUT_SEC * 3` 을 놓친다 —
    # 함수 안이어도 startup 상수는 여전히 startup 값이다. 그래서 함수 본문까지 검사하되
    # **fail-open 폴백은 제외**한다: live 조회가 실패했을 때 기동 스냅샷으로 되돌아가는 것은
    # 의도된 설계이고(그 경로가 없으면 설정 가용성이 판정을 막는다) 항상 `except` 안에 있다.
    exempt: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler):
            for sub in ast.walk(n):
                exempt.add(id(sub))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)):
            continue
        value = node.value
        if value is None:
            continue
        for sub in ast.walk(value):
            if not (isinstance(sub, ast.Name) and sub.id in suspects):
                continue
            if id(sub) in exempt:
                continue        # fail-open 폴백
            src_line = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
            if "drift-ok:" in src_line:
                continue        # 비-판정 용도 명시 예외(사유를 같은 줄에 적는다)
            if isinstance(node, ast.Return):
                offenders.append(f"return <- {sub.id} (line {node.lineno})")
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            # 자기 정의부(`AGENT_TIMEOUT_SEC = _startup_int("AGENT_TIMEOUT_SEC", …)`)는 제외.
            if names and names != [sub.id]:
                offenders.append(f"{names} <- {sub.id} (line {node.lineno})")
    assert not offenders, (
        "live 설정의 startup 스냅샷을 파생 소스로 쓰고 있다 — 소비처가 live 를 읽으면 조용히 "
        "어긋난다. live 조회로 바꾸거나, 판정과 무관한 용도라면 그 줄에 `# drift-ok: <사유>` 를 "
        f"달 것: {offenders}"
    )


# ── T2: allowlist 밖의 live×startup 조합 금지 ─────────────────────────────────────
def test_live_spec_read_as_startup_is_allowlisted():
    src = _CONFIG_PATH.read_text(encoding="utf-8")
    unexpected = sorted((_live_spec_keys() & _startup_int_keys(src)) - _ALLOWED_LIVE_AS_STARTUP)
    assert not unexpected, (
        "apply_mode=live 인 설정을 _startup_int 로 읽는 신규 키가 생겼다. 콘솔 변경을 추종하지 "
        "못하므로 (a) live 조회로 바꾸거나 (b) 무해한 이유를 _ALLOWED_LIVE_AS_STARTUP 에 근거와 "
        f"함께 등재할 것: {unexpected}"
    )


# ── T3: 회수 임계가 live 상한과 함께 움직인다(소스 일치) ─────────────────────────
def test_ask_worker_stale_follows_live_cap(monkeypatch):
    """콘솔에서 상한을 올리면 회수 임계도 **같은 호출에서** 커져야 한다.

    종전에는 임계가 import 시점 스냅샷이라, 상한을 올리면 run 예산(live×3)만 커지고 임계는
    옛 값에 남아 **살아있는 정상 run 을 sweeper 가 회수**할 수 있었다.
    """
    from shared import runtime_settings as _rts

    def _cap(v):
        monkeypatch.setattr(_rts, "get_int", lambda _k, _v=v: _v)
        return cfg.effective_ask_worker_stale_sec()

    small, large = _cap(60), _cap(1800)
    assert large > small, f"상한 60→1800 인데 회수 임계가 안 커졌다({small} → {large})"
    # run 예산(live×3)보다 커야 false-positive 회수가 없다 — 종전 계약을 값으로 보존.
    for cap in (60, 300, 900, 1800, 3600):
        eff = _cap(cap)
        run_est = max(cap * 3, max(1, int(cfg.AGENT_EARLY_FINALIZE_MS / 1000)))
        assert eff > run_est, f"cap={cap}: 임계 {eff} <= run 예산 {run_est} — 살아있는 run 회수"


def test_ask_worker_stale_has_floor_and_fail_open(monkeypatch):
    from shared import runtime_settings as _rts

    monkeypatch.setattr(_rts, "get_int", lambda _k: 5)     # 스펙 최소
    assert cfg.effective_ask_worker_stale_sec() >= cfg._ASK_STALE_FLOOR_SEC
    # 조회 실패도 fail-open(예외 전파 없음).
    def _boom(_k):
        raise RuntimeError("snapshot gone")
    monkeypatch.setattr(_rts, "get_int", _boom)
    assert cfg.effective_ask_worker_stale_sec() >= cfg._ASK_STALE_FLOOR_SEC


def test_cap_drop_does_not_shrink_reclaim_threshold(monkeypatch):
    """§18.8 codex [P1]: 큰 예산으로 시작된 run 이 낮아진 임계로 조기 회수되지 않는다.

    run 예산은 시작 시점 고정인데 회수 임계만 즉시 작아지면, cap 1800 에서 시작한 5,400s run 이
    cap 60 으로 내린 순간 600s 임계로 회수된다.
    """
    from shared import runtime_settings as _rts

    monkeypatch.setattr(_rts, "get_int", lambda _k: 1800)
    high = cfg.effective_ask_worker_stale_sec()
    monkeypatch.setattr(_rts, "get_int", lambda _k: 60)
    assert cfg.effective_ask_worker_stale_sec() == high, "상한 하락을 즉시 따라가 조기 회수 가능"


# ── §18.8 codex [P1]: env override 가 안전 하한을 우회하지 않는다 ─────────────────
@pytest.mark.parametrize("raw", ["-1", "0", "-3600"])
def test_nonpositive_env_override_is_rejected(monkeypatch, raw):
    """`-1` 이 통과하면 SQL cutoff 가 미래가 되어 정상 running job 전부를 즉시 stale 판정한다."""
    from shared import runtime_settings as _rts

    monkeypatch.setattr(_rts, "get_int", lambda _k: 300)
    monkeypatch.setattr(cfg, "_ASK_STALE_ENV_OVERRIDE", raw, raising=False)
    eff = cfg.effective_ask_worker_stale_sec()
    assert eff > 0, f"override {raw!r} → {eff} (비양수 임계는 정상 job 을 전부 회수한다)"
    assert eff >= cfg._ASK_STALE_FLOOR_SEC, f"override {raw!r} 가 파생 폴백을 타지 않았다: {eff}"


@pytest.mark.parametrize("raw", ["", "abc", "12x"])
def test_malformed_env_override_falls_back(monkeypatch, raw):
    from shared import runtime_settings as _rts

    monkeypatch.setattr(_rts, "get_int", lambda _k: 300)
    monkeypatch.setattr(cfg, "_ASK_STALE_ENV_OVERRIDE", raw, raising=False)
    assert cfg.effective_ask_worker_stale_sec() >= cfg._ASK_STALE_FLOOR_SEC


def test_positive_env_override_is_honored_with_heartbeat_floor(monkeypatch):
    """운영자가 명시한 양수는 존중하되, heartbeat 지연만으로 오회수되는 값은 끌어올린다."""
    monkeypatch.setattr(cfg, "_ASK_STALE_ENV_OVERRIDE", "4321", raising=False)
    assert cfg.effective_ask_worker_stale_sec() == 4321
    monkeypatch.setattr(cfg, "_ASK_STALE_ENV_OVERRIDE", "1", raising=False)
    hb_min = max(3, int(cfg.AGENT_ASK_WORKER_HEARTBEAT_SEC) * 3)
    assert cfg.effective_ask_worker_stale_sec() == hb_min


def test_stale_judgement_paths_use_live_function_not_constant():
    """(소스 잠금) 판정 경로는 상수가 아니라 live 함수를 쓴다.

    상수를 다시 끌어다 쓰면 이 cycle 이 없앤 어긋남이 그대로 되살아난다. 로그 표시 같은
    비-판정 용도만 상수를 써도 되지만, `stale_seconds=`/`max_wait` 처럼 판정에 들어가는
    자리는 함수여야 한다.
    """
    from modules import ask as ask_mod

    ask_src = Path(ask_mod.__file__).read_text(encoding="utf-8")
    assert "stale_seconds=int(effective_ask_worker_stale_sec())" in ask_src
    assert "stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC)" not in ask_src

    # §18.8 codex [P2]: 파일 부재를 조용히 통과시키면 경로가 바뀐 날 가드가 사라진다 →
    # 존재 자체를 단언하고, 못 찾으면 실패로 알린다(가드 vacuous 방지).
    web = _CONFIG_PATH.parent.parent / "unit/feature-0003-agent-web-ui/src/routers/_conv_store.py"
    assert web.exists(), f"web 소비처를 찾지 못했다 — 경로 변경 시 이 가드를 함께 갱신할 것: {web}"
    web_src = web.read_text(encoding="utf-8")
    assert "stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC)" not in web_src
    assert "max_wait = int(AGENT_ASK_WORKER_STALE_SEC)" not in web_src
    assert "effective_ask_worker_stale_sec()" in web_src


# ── T4: llm.py 는 startup 상수를 timeout 으로 명시 전달하지 않는다 ────────────────
def test_llm_module_passes_no_startup_constant_as_timeout():
    from modules import llm as llm_mod

    src = Path(llm_mod.__file__).read_text(encoding="utf-8")
    bad = re.findall(r"_openai_request_timeout\(\s*AGENT_TIMEOUT_SEC\s*\)", src)
    assert not bad, (
        "startup 상수를 per-request timeout 으로 명시 전달하고 있다 — 인자를 생략하면 "
        f"live fallback 이라 콘솔 조정이 반영된다(feature-0018 계약): {len(bad)}건"
    )

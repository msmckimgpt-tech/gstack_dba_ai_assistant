"""bin/refresh-claude-oauth-token.sh — 사용량-소진 게이트 회귀 잠금.

배경 (CHG-20260807-oauth-exhaustion-gate):
    2026-08-07 claude-corp 의 7일(주간) 쿼터가 100% 소진됐다(`anthropic-ratelimit-unified-7d-status
    =rejected`, `retry-after` ≈ 2.04일). 자격증명 **파일**은 멀쩡하므로 정적 검사는 계속 통과했고,
    30분 cron 이 소진 계정을 1순위 slot(ANTHROPIC_API_KEY)에 재주입해 "게이트가 root 로 옮겨오지
    않는" 상태가 리셋까지 고착됐다. 그 사이 모든 LLM 호출은 소진 계정으로 먼저 나가 429 를 받고
    (num_retries=1 → 2회) root 로 우회했고, root 폴백이 없는 alias(bare sonnet/opus)는 전면 실패했다.

본 스위트가 잠그는 계약:
    G1 게이트 off  — 정적-검사-전용(2026-07-07~2026-08-06) 동작 완전 보존.
    G2 heartbeat   — 최근 판정이 있으면 라이브 probe 0회, RECHECK_SEC 경과 시에만 1회
                     (30분마다 찔러 claude-corp 5h 윈도우를 재고정하던 회귀 차단).
    G3 소진 검출   — 1-probe → 429 면 그 계정을 건너뛰고 root 승격 +
                     `anthropic-ratelimit-unified-reset` 을 우회 만료로 캐시.
    G4 flapping 0  — 캐시가 유효한 동안엔 probe 없이 계속 우회(로그가 깨끗해져도 되돌아가지 않음).
    G5 자동 복귀   — 캐시 만료 후 1-probe 가 200 이면 원 1순위로 복귀 + 캐시 제거.
    G6 fail-open   — 네트워크/미분류 오류는 "소진"으로 오판하지 않는다(2026-07-30 DNS 34분 단절
                     사고 재발 차단 — 도달성 장애 ≠ 사용량 소진).
    G7 root slot   — ANTHROPIC_API_KEY_ROOT 는 고정 배선이라 게이트 미적용(항상 root 토큰).
    G8 --check     — 라이브 probe·.env·상태파일 전부 무변경.
    G9 clamp       — 우회 만료는 [min, max] cooldown 으로 클램프(헤더 이상값 방어).
"""

import json
import os
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = REPO_ROOT / "bin" / "refresh-claude-oauth-token.sh"


# ── 가짜 Anthropic /v1/messages ────────────────────────────────────────────────
class _ProbeServer:
    """스크립트의 라이브 probe 를 받아내는 최소 HTTP 서버.

    `script` 로 응답 시퀀스를 지정한다(각 항목 = (status, headers)). 호출 횟수는 `calls`.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler 규약
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length)
                outer.calls.append({
                    "authorization": self.headers.get("authorization", ""),
                    "body": json.loads(raw or b"{}"),
                })
                idx = min(len(outer.calls) - 1, len(outer._responses) - 1)
                status, headers = outer._responses[idx]
                payload = b'{"content":[{"type":"text","text":"pong"}]}' if status == 200 \
                    else b'{"type":"error","error":{"type":"rate_limit_error"}}'
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, str(v))
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_a):  # 테스트 출력 오염 방지
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def url(self):
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1/messages"


# ── 하네스 ────────────────────────────────────────────────────────────────────
def _write_cred(cred_root: Path, account: str, token: str, *, ttl_sec: int = 7200):
    d = cred_root / account
    d.mkdir(parents=True, exist_ok=True)
    (d / ".credentials.json").write_text(json.dumps({
        "claudeAiOauth": {
            "accessToken": token,
            "refreshToken": "refresh-" + token,
            "expiresAt": int((time.time() + ttl_sec) * 1000),
            "scopes": ["user:inference"],
        }
    }))


@pytest.fixture()
def env(tmp_path):
    """격리된 repo/credentials/mock-docker 를 갖춘 스크립트 실행 환경."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.bedrock").write_text(
        "AWS_REGION=ap-northeast-2\nANTHROPIC_API_KEY=stale-primary\nANTHROPIC_API_KEY_ROOT=stale-root\n")
    (repo / "docker-compose.yml").write_text("services: {}\n")

    cred_root = tmp_path / "creds"
    _write_cred(cred_root, "claude-corp", "tok-corp")
    _write_cred(cred_root, "root", "tok-root")

    # `docker compose logs` 출력(=게이트 trigger 조건 (a))과 `up -d` 를 흉내내는 mock.
    binstub = tmp_path / "bin"
    binstub.mkdir()
    docker = binstub / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "${1:-}" = "compose" ]; then\n'
        '  for a in "$@"; do [ "$a" = "logs" ] && { printf "%s\\n" "${MOCK_GATEWAY_LOGS:-}"; exit 0; }; done\n'
        "fi\n"
        'printf "%s\\n" "$@" >> "$MOCK_DOCKER_CALLS"\n'
        "exit 0\n")
    docker.chmod(0o755)

    return {
        "tmp": tmp_path,
        "repo": repo,
        "env_file": repo / ".env.bedrock",
        "cred_root": cred_root,
        "state_file": tmp_path / "state" / "exhaustion.json",
        "docker_calls": tmp_path / "docker-calls.txt",
        "binstub": binstub,
    }


# 하네스는 CLAUDE_OAUTH_* 를 **전부 고정**한다 — 운영자 셸에 남은 override 가 스위트를
# 조용히 다른 계약으로 통과시키는 vacuous pass 를 막는다. 케이스별 변경은 _run(**extra) 로만.
_PINNED = {
    "CLAUDE_OAUTH_EXHAUSTION_GATE": "1",
    "CLAUDE_OAUTH_ACCOUNTS": "claude-corp root",
    "CLAUDE_OAUTH_MIN_TTL": "300",
    "CLAUDE_OAUTH_FORCE_PROBE": "0",
    "CLAUDE_OAUTH_OBS_WINDOW": "35m",
    "CLAUDE_OAUTH_PROBE_MODEL": "claude-haiku-4-5",
    "CLAUDE_OAUTH_PROBE_MAX_COOLDOWN": "691200",
    "CLAUDE_OAUTH_PROBE_MIN_COOLDOWN": "300",
    "CLAUDE_OAUTH_GATE_RECHECK_SEC": "3600",
}


def _run(env, *args, probe_url="http://127.0.0.1:1/v1/messages", gateway_logs="", **extra):
    e = dict(os.environ)
    e.pop("CLAUDE_OAUTH_ACCOUNT", None)  # 단일-계정 강제가 남아 있으면 폴백 계약 자체가 무의미
    e.update(_PINNED)
    e.update({
        "PATH": f'{env["binstub"]}:{os.environ["PATH"]}',
        "CLAUDE_OAUTH_REPO": str(env["repo"]),
        "CLAUDE_OAUTH_CRED_ROOT": str(env["cred_root"]),
        "CLAUDE_OAUTH_STATE_FILE": str(env["state_file"]),
        "CLAUDE_OAUTH_PROBE_URL": probe_url,
        "CLAUDE_OAUTH_PROBE_TIMEOUT": "5",
        "MOCK_GATEWAY_LOGS": gateway_logs,
        "MOCK_DOCKER_CALLS": str(env["docker_calls"]),
    })
    e.update({k: str(v) for k, v in extra.items()})
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=e, timeout=90)


def _env_val(env, key):
    for line in env["env_file"].read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    return None


def _state(env):
    return json.loads(env["state_file"].read_text()) if env["state_file"].exists() else {}


_RL_HEADERS = {
    "anthropic-ratelimit-unified-status": "rejected",
    "anthropic-ratelimit-unified-5h-status": "allowed",
    "anthropic-ratelimit-unified-7d-status": "rejected",
    "anthropic-ratelimit-unified-7d-utilization": "1.0",
    "anthropic-ratelimit-unified-representative-claim": "seven_day",
    "retry-after": "176528",
}


def _rl_headers(reset_epoch):
    h = dict(_RL_HEADERS)
    h["anthropic-ratelimit-unified-reset"] = str(int(reset_epoch))
    return h


# ── G1: 게이트 off = 정적-검사-전용 동작 보존 ──────────────────────────────────
def test_gate_disabled_keeps_static_only_behaviour(env):
    with _ProbeServer([(429, _rl_headers(time.time() + 3600))]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom",
                 CLAUDE_OAUTH_EXHAUSTION_GATE="0")
        assert r.returncode == 0, r.stderr
        assert srv.calls == [], "게이트 off 인데 라이브 probe 가 발생했다"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"
    assert not env["state_file"].exists()


# ── G2: heartbeat — 최근 판정이 있으면 probe 0회, 간격 경과 시에만 1회 ────────
def test_recent_verdict_means_zero_live_probe(env):
    """최근 판정이 있으면 라이브 probe 를 하지 않는다 (30분마다 찌르던 회귀 차단)."""
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    env["state_file"].write_text(json.dumps({
        "claude-corp": {"until": 0, "checked": int(time.time()) - 60, "detail": "HTTP 200"},
        "root": {"until": 0, "checked": int(time.time()) - 60, "detail": "HTTP 200"}}))
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")  # 게이트웨이 로그도 깨끗
        assert r.returncode == 0, r.stderr
        assert srv.calls == [], "최근 판정이 있는데 probe 가 나갔다 — 5h 윈도우 재고정 회귀"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"
    assert "게이트 재확인 불요" in r.stderr


def test_heartbeat_disabled_means_zero_live_probe(env):
    """RECHECK_SEC=0 이면 heartbeat 가 완전히 꺼진다(운영자 킬스위치)."""
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert srv.calls == []
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"


def test_heartbeat_fires_once_interval_elapsed(env):
    """마지막 판정이 오래됐으면 heartbeat 로 1-probe — 로그가 무증상이어도 소진을 잡는다.

    라이브 실측(2026-08-07): claude-corp 429 여도 litellm 이 root 로 성공 폴백하면
    게이트웨이 로그엔 `200 OK` 만 남는다. 로그 grep 만으로는 이 상태를 영영 못 잡으므로
    heartbeat 가 주 신호여야 한다.
    """
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    env["state_file"].write_text(json.dumps({
        "claude-corp": {"until": 0, "checked": int(time.time()) - 7200, "detail": "HTTP 200"}}))
    reset = int(time.time()) + 172800
    with _ProbeServer([(429, _rl_headers(reset)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="",  # 로그 완전 무증상
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=3600)
        assert r.returncode == 0, r.stderr
        assert srv.calls[0]["authorization"] == "Bearer tok-corp"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root", \
        "로그 무증상 소진을 heartbeat 가 잡지 못했다 — 게이트가 root 로 옮겨오지 않는다"
    assert _state(env)["claude-corp"]["until"] == reset


# ── G3: 소진 검출 → root 승격 + reset 헤더를 우회 만료로 캐시 ─────────────────
def test_exhausted_primary_hands_over_to_root(env):
    reset = int(time.time()) + 172800  # 7d reset ≈ 2일 뒤
    # 1st = claude-corp(429 소진), 2nd = 승격된 root(200) — 오류가 관측된 창에서는 후보마다 1-probe.
    with _ProbeServer([(429, _rl_headers(reset)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: rate_limit_error")
        assert r.returncode == 0, r.stderr
        assert [c["authorization"] for c in srv.calls] == ["Bearer tok-corp", "Bearer tok-root"]
        assert srv.calls[0]["body"]["max_tokens"] == 16, "probe 는 최소 비용 ping 이어야 한다"

    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root", "1순위 slot 이 root 로 옮겨오지 않았다"
    assert _env_val(env, "ANTHROPIC_API_KEY_ROOT") == "tok-root"
    st = _state(env)
    assert st["claude-corp"]["until"] == reset
    assert "7d=rejected" in st["claude-corp"]["detail"]
    assert st["root"]["until"] == 0, "승격된 root 는 소진 상태가 아니어야 한다"
    # 토큰이 바뀌었으므로 게이트웨이 재생성 1회
    assert "--force-recreate" in env["docker_calls"].read_text()


# ── G4: 캐시가 유효한 동안엔 probe 없이 계속 우회 (flapping 0) ────────────────
def test_cached_exhaustion_skips_without_probe(env):
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    until = int(time.time()) + 3600
    env["state_file"].write_text(json.dumps({
        "claude-corp": {"until": until, "detail": "429 7d=rejected(1.0)", "checked": int(time.time())}}))

    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")  # 로그는 이미 깨끗해진 상태
        assert r.returncode == 0, r.stderr
        assert all(c["authorization"] != "Bearer tok-corp" for c in srv.calls), \
            "유효한 소진 캐시가 있는데 그 계정으로 probe 가 나갔다"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root"
    assert "사용량 소진 캐시" in r.stderr
    assert _state(env)["claude-corp"]["until"] == until  # 캐시 무변경


# ── G5: 캐시 만료 후 200 이면 원 1순위로 자동 복귀 ────────────────────────────
def test_recovery_after_cooldown_promotes_back(env):
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    env["state_file"].write_text(json.dumps({
        "claude-corp": {"until": int(time.time()) - 5, "detail": "429 7d=rejected(1.0)", "checked": 0}}))

    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")  # 로그 깨끗해도 캐시 만료면 복구 확인 1회
        assert r.returncode == 0, r.stderr
        assert len(srv.calls) == 1, "캐시 만료 시 복구 확인 probe 1회여야 한다"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"
    assert "사용량 회복 확인" in r.stderr
    assert _state(env)["claude-corp"]["until"] == 0, "복귀했는데 소진 캐시가 남아 있다"


# ── G6: 네트워크/미분류 오류는 소진으로 오판하지 않는다 (fail-open) ───────────
@pytest.mark.parametrize("mode", ["http_500", "unreachable"])
def test_unclassified_failure_is_fail_open(env, mode):
    if mode == "http_500":
        with _ProbeServer([(500, {})]) as srv:
            r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom")
    else:
        # 도달 불가 포트 = 2026-07-30 게이트웨이 DNS 단절 상황의 대리 재현
        r = _run(env, probe_url="http://127.0.0.1:1/v1/messages",
                 gateway_logs="litellm.RateLimitError: boom")
    assert r.returncode == 0, r.stderr
    assert "판정 보류" in r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp", "도달성 장애를 소진으로 오판해 계정을 옮겼다"
    entry = _state(env)["claude-corp"]
    assert entry["until"] == 0, "판정 보류인데 우회(소진) 상태를 기록했다"
    assert entry["detail"].startswith("보류:")


# ── G7: root slot 은 고정 배선 — 게이트 미적용 ────────────────────────────────
def test_root_slot_is_never_gated(env):
    """1순위 후보가 전부 소진돼도 ANTHROPIC_API_KEY_ROOT 는 root 토큰을 유지한다."""
    reset = int(time.time()) + 7200
    with _ProbeServer([(429, _rl_headers(reset)), (429, _rl_headers(reset))]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom")
        assert r.returncode == 0, r.stderr
        # claude-corp 429 → root 도 후보라 1회 더 probe → 429 → 전원 소진
        assert len(srv.calls) == 2
    assert _env_val(env, "ANTHROPIC_API_KEY_ROOT") == "tok-root"
    # 전원 소진이면 게이트를 무시하고 정적 1순위 유지(주입 중단으로 stale 토큰을 남기지 않는다)
    assert "후보 전원 사용량 소진" in r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"


# ── G8: --check 는 라이브 probe·.env·상태파일 전부 무변경 ────────────────────
def test_check_mode_is_side_effect_free(env):
    before = env["env_file"].read_text()
    with _ProbeServer([(429, _rl_headers(time.time() + 3600))]) as srv:
        r = _run(env, "--check", probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom")
        assert r.returncode == 0, r.stderr
        assert srv.calls == [], "--check 인데 라이브 probe 가 발생했다"
    assert env["env_file"].read_text() == before
    assert not env["state_file"].exists()
    assert not env["docker_calls"].exists()
    assert "[check]" in r.stderr


# ── G9: 우회 만료 clamp — 헤더 이상값 방어 ───────────────────────────────────
@pytest.mark.parametrize(
    "reset_offset,max_cooldown,expect_max",
    [(10 ** 7, 3600, True),   # reset 이 상한을 넘으면 상한으로 클램프
     (1, 3600, False)],       # reset 이 하한보다 가까우면 하한으로 클램프
)
def test_cooldown_is_clamped(env, reset_offset, max_cooldown, expect_max):
    now = int(time.time())
    with _ProbeServer([(429, _rl_headers(now + reset_offset)),
                       (429, _rl_headers(now + reset_offset))]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom",
                 CLAUDE_OAUTH_PROBE_MAX_COOLDOWN=max_cooldown, CLAUDE_OAUTH_PROBE_MIN_COOLDOWN=300)
        assert r.returncode == 0, r.stderr
    until = _state(env)["claude-corp"]["until"]
    if expect_max:
        assert now + max_cooldown - 5 <= until <= now + max_cooldown + 5
    else:
        assert now + 300 - 5 <= until <= now + 300 + 5


# ── 정적 검사 회귀: 만료 임박 계정은 게이트 이전에 걸러진다 ────────────────────
def test_static_expiry_still_filters_before_gate(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=60)  # MIN_TTL(300) 미만
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom")
        assert r.returncode == 0, r.stderr
        # 정적 검사에서 이미 탈락 → 그 계정으로는 probe 하지 않는다
        assert all(c["authorization"] != "Bearer tok-corp" for c in srv.calls)
    assert "토큰 만료/임박" in r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root"


# ── 스크립트 자체 무결성 ──────────────────────────────────────────────────────
def test_script_syntax_is_valid():
    assert shutil.which("bash"), "bash 필요"
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

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
        self.overflow = 0   # 시나리오가 정의하지 않은 잉여 probe 수
        self.errors = []    # 핸들러 내부 예외 — 조용히 '연결 끊김'으로 위장되면 안 된다
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler 규약
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length)
                outer.calls.append({
                    "authorization": self.headers.get("authorization", ""),
                    "anthropic-beta": self.headers.get("anthropic-beta", ""),
                    "user-agent": self.headers.get("user-agent", ""),
                    "body": json.loads(raw or b"{}"),
                })
                # 종전엔 마지막 응답을 무한 반복해 **잉여 probe 가 보이지 않았다**(적대 리뷰).
                # 시나리오가 정의한 횟수를 넘으면 599 로 튀게 해 테스트가 알아채도록 한다.
                idx = len(outer.calls) - 1
                if idx >= len(outer._responses):
                    outer.overflow += 1
                    self.send_response(599)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return
                spec = outer._responses[idx]
                status, headers = spec[0], dict(spec[1])
                payload = spec[2] if len(spec) > 2 else (
                    b'{"content":[{"type":"text","text":"pong"}]}' if status == 200
                    else b'{"type":"error","error":{"type":"rate_limit_error"}}')
                delay = float(headers.pop("x-test-delay", 0) or 0)
                if delay:
                    time.sleep(delay)
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, str(v))
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):  # noqa: N802 — 302 이후 urllib 은 POST 를 GET 으로 바꾼다
                outer.calls.append({
                    "method": "GET",
                    "authorization": self.headers.get("authorization", ""),
                    "anthropic-beta": self.headers.get("anthropic-beta", ""),
                    "body": {},
                })
                payload = b'{"content":[{"type":"text","text":"pong"}]}'
                self.send_response(200)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except Exception as exc:  # noqa: BLE001
                    outer.errors.append(repr(exc))
                    raise

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
        assert self.overflow == 0, f"시나리오보다 probe 가 {self.overflow}회 더 나갔다"
        assert not self.errors, f"가짜 엔드포인트가 죽었다(테스트가 vacuous 하게 통과할 수 있다): {self.errors}"

    @property
    def url(self):
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1/messages"


# ── 하네스 ────────────────────────────────────────────────────────────────────
def _write_cred(cred_root: Path, account: str, token: str, *, ttl_sec: int = 7200,
                refresh_token=None, refresh_ttl_sec: int = 30 * 86400, extra=None):
    d = cred_root / account
    d.mkdir(parents=True, exist_ok=True)
    doc = {
        "claudeAiOauth": {
            "accessToken": token,
            "refreshToken": "refresh-" + token if refresh_token is None else refresh_token,
            "expiresAt": int((time.time() + ttl_sec) * 1000),
            "refreshTokenExpiresAt": int((time.time() + refresh_ttl_sec) * 1000),
            "scopes": ["user:inference", "user:profile"],
            "subscriptionType": "max",
        },
        "organizationUuid": "org-keep-me",
    }
    if extra:
        doc["claudeAiOauth"].update(extra)
    f = d / ".credentials.json"
    f.write_text(json.dumps(doc))
    f.chmod(0o600)


def _cred(env, account):
    return json.loads((env["cred_root"] / account / ".credentials.json").read_text())


class _TokenServer(_ProbeServer):
    """가짜 OAuth 토큰 엔드포인트. 응답 스펙은 _ProbeServer 와 동일한 (status, headers[, body])."""

    @property
    def url(self):
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1/oauth/token"


def _token_body(access="new-access", refresh="new-refresh", expires_in=28800, scope=None):
    d = {"access_token": access, "expires_in": expires_in}
    if refresh is not None:
        d["refresh_token"] = refresh
    if scope is not None:
        d["scope"] = scope
    return json.dumps(d).encode()


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
    "CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC": "1800",
    "CLAUDE_OAUTH_AUTO_ROTATE": "1",
    "CLAUDE_OAUTH_ROTATE_LEAD_SEC": "3600",
    "CLAUDE_OAUTH_ROTATE_KEEP_BACKUPS": "5",
    "CLAUDE_OAUTH_CLIENT_ID": "test-client-id",
}


def _run(env, *args, probe_url="http://127.0.0.1:1/v1/messages", gateway_logs="",
         token_url="http://127.0.0.1:1/v1/oauth/token", **extra):
    e = dict(os.environ)
    e.pop("CLAUDE_OAUTH_ACCOUNT", None)  # 단일-계정 강제가 남아 있으면 폴백 계약 자체가 무의미
    e.update(_PINNED)
    e.update({
        "PATH": f'{env["binstub"]}:{os.environ["PATH"]}',
        "CLAUDE_OAUTH_REPO": str(env["repo"]),
        "CLAUDE_OAUTH_CRED_ROOT": str(env["cred_root"]),
        "CLAUDE_OAUTH_STATE_FILE": str(env["state_file"]),
        "CLAUDE_OAUTH_PROBE_URL": probe_url,
        "CLAUDE_OAUTH_TOKEN_URL": token_url,
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


def _burst_headers(retry_after=5):
    """5h RPM/버스트 캡 — 7d 는 멀쩡하고 쿨다운이 짧다. 강등 대상이 아니다."""
    return {
        "anthropic-ratelimit-unified-status": "rejected",
        "anthropic-ratelimit-unified-5h-status": "rejected",
        "anthropic-ratelimit-unified-5h-utilization": "1.0",
        "anthropic-ratelimit-unified-7d-status": "allowed",
        "anthropic-ratelimit-unified-7d-utilization": "0.4",
        "anthropic-ratelimit-unified-representative-claim": "five_hour",
        "retry-after": str(retry_after),
    }


def _seed(env, **accounts):
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    env["state_file"].write_text(json.dumps(accounts))


def _fresh(offset=-60):
    return {"until": 0, "checked": int(time.time()) + offset, "detail": "HTTP 200"}


def _rl_headers(reset_epoch):
    """실측 헤더 모양 — reset 과 retry-after 는 같은 시각을 가리킨다(2026-08-07 라이브 캡처)."""
    h = dict(_RL_HEADERS)
    h["anthropic-ratelimit-unified-reset"] = str(int(reset_epoch))
    h["retry-after"] = str(max(1, int(reset_epoch) - int(time.time())))
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
    # heartbeat 를 끄고 캐시-만료 트리거(b)만 남긴다. 종전 이 테스트는 `checked: 0` 이라
    # heartbeat 가 probe 를 냈고, (b) 를 삭제해도 통과했다(적대 리뷰 mutation M22 생존).
    now = int(time.time())
    _seed(env, **{"claude-corp": {"until": now - 5, "detail": "429 7d=rejected(1.0)", "checked": now - 10},
                  "root": _fresh()})

    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
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
     (60, 3600, False)],      # reset 이 하한보다 가까우면 하한으로 클램프
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


# ── 버스트 429 는 강등하지 않는다 (gate-hardening, 적대 리뷰 P1) ──────────────
def test_burst_429_does_not_demote(env):
    """5h RPM 캡 같은 단발 429 로 계정을 옮기면 2계정 체인이 1계정으로 붕괴한다.

    종전엔 모든 429 를 소진으로 보고 `retry-after=5s` 를 min_cooldown(300s)으로 끌어올려
    강등했다 → 두 slot 이 같은 root 토큰이 되고, 강등/복귀마다 게이트웨이 force-recreate.
    """
    _seed(env, **{"root": _fresh()})
    with _ProbeServer([(429, _burst_headers(retry_after=5))]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
        assert len(srv.calls) == 1

    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp", "버스트 429 로 계정을 강등했다"
    assert _env_val(env, "ANTHROPIC_API_KEY") != _env_val(env, "ANTHROPIC_API_KEY_ROOT"), \
        "두 slot 이 같은 토큰이 되어 2계정 폴백 체인이 붕괴했다"
    assert _state(env)["claude-corp"]["until"] == 0
    assert "일시적" in r.stderr


def test_long_429_without_7d_rejection_still_demotes(env):
    """7d 가 allowed 여도 헤더가 말하는 쿨다운이 길면(≥ MIN_DEMOTE) 강등한다."""
    _seed(env, **{"root": _fresh()})
    with _ProbeServer([(429, _burst_headers(retry_after=7200)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root"
    assert _state(env)["claude-corp"]["until"] > int(time.time()) + 3600


# ── 게이트웨이 로그 트리거 (c) 를 격리 — 종전 8개 호출부가 장식이었다 ─────────
def test_gateway_log_trigger_fires_probe(env):
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="litellm.RateLimitError: boom",
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(srv.calls) == 1, "게이트웨이 오류 관측이 probe 를 내지 않았다"
    assert "[관측]" in r.stderr and "RateLimitError 1건" in r.stderr


def test_clean_gateway_log_fires_nothing(env):
    """(c) 의 음성 대조군 — 로그가 깨끗하면 probe 0."""
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="INFO 200 OK",
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert srv.calls == []
    assert "[관측]" not in r.stderr


# ── FORCE_PROBE (d) ───────────────────────────────────────────────────────────
def test_force_probe_overrides_all_gates(env):
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _ProbeServer([(200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="",
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0, CLAUDE_OAUTH_FORCE_PROBE=1)
        assert r.returncode == 0, r.stderr
        assert len(srv.calls) == 1, "FORCE_PROBE=1 이 무시됐다"


# ── 401/403 — 정적 검사가 못 보는 '취소된 토큰' 방어선 ────────────────────────
@pytest.mark.parametrize("code", [401, 403])
def test_revoked_token_is_skipped(env, code):
    _seed(env, **{"root": _fresh()})
    now = int(time.time())
    with _ProbeServer([(code, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
        assert len(srv.calls) == 1
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root", "취소된 토큰이 주입됐다"
    until = _state(env)["claude-corp"]["until"]
    assert now + 850 <= until <= now + 950


# ── 쿨다운 헤더 파싱: retry-after 단독 / 헤더 없음 / 과거 reset / ms reset ────
@pytest.mark.parametrize("headers,expect_offset", [
    ({"retry-after": "7200"}, 7200),                                  # retry-after 단독
    ({}, 3600),                                                       # 헤더 없음 → 기본 1h
])
def test_cooldown_from_retry_after_and_default(env, headers, expect_offset):
    _seed(env, **{"root": _fresh()})
    h = dict(headers); h["anthropic-ratelimit-unified-7d-status"] = "rejected"
    now = int(time.time())
    with _ProbeServer([(429, h), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    until = _state(env)["claude-corp"]["until"]
    assert now + expect_offset - 10 <= until <= now + expect_offset + 10


def test_stale_reset_header_falls_back_to_retry_after(env):
    """`unified-reset` 이 과거(시계 스큐)면 같은 응답의 retry-after 를 써야 한다.

    종전엔 reset 이 파싱만 되면 무조건 이겨서, 2일짜리 소진이 300s 최소 쿨다운으로
    떨어지고 30분마다 재승격/재강등 + 게이트웨이 recreate 를 반복했다.
    """
    now = int(time.time())
    _seed(env, **{"root": _fresh()})
    h = _rl_headers(now - 90)          # 과거 epoch
    h["retry-after"] = "176528"
    with _ProbeServer([(429, h), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    until = _state(env)["claude-corp"]["until"]
    assert now + 176000 <= until <= now + 177000, f"stale reset 을 걸러내지 못했다: until-now={until-now}"


def test_millisecond_reset_header_is_corrected(env):
    """reset 이 ms 로 오면 상한(8일)에 박혀 회복 probe 가 사라졌다 — ms 보정 확인."""
    now = int(time.time())
    _seed(env, **{"root": _fresh()})
    h = _rl_headers((now + 7200) * 1000)
    del h["retry-after"]
    with _ProbeServer([(429, h), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    until = _state(env)["claude-corp"]["until"]
    assert now + 7000 <= until <= now + 7400, f"ms epoch 보정 실패: until-now={until-now}"


# ── fail-open 이 heartbeat 를 우회해 매 실행 probe 하지 않는다 ────────────────
def test_fail_open_at_cooldown_expiry_does_not_probe_every_run(env):
    """만료 시점 probe 가 네트워크 오류면, 다음 실행은 heartbeat 간격을 지켜야 한다.

    종전엔 과거 `until` 이 남아 `until > 0` 만으로 매 cron 실행이 probe 했다.
    """
    now = int(time.time())
    _seed(env, **{"claude-corp": {"until": now - 5, "checked": now - 10, "detail": "429"},
                  "root": _fresh()})
    # 1회차: 도달 불가 → fail-open
    r1 = _run(env, probe_url="http://127.0.0.1:1/v1/messages", gateway_logs="",
              CLAUDE_OAUTH_GATE_RECHECK_SEC=3600)
    assert r1.returncode == 0, r1.stderr
    assert "판정 보류" in r1.stderr
    # 2회차: heartbeat 미도래 → probe 0 이어야 한다
    with _ProbeServer([(200, {})]) as srv:
        r2 = _run(env, probe_url=srv.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=3600)
        assert r2.returncode == 0, r2.stderr
        assert srv.calls == [], "fail-open 후 매 실행 probe 가 나갔다"


# ── 전원 소진이면 가장 빨리 회복되는 계정을 남긴다 ────────────────────────────
def test_all_exhausted_keeps_soonest_recovering(env):
    now = int(time.time())
    _seed(env, **{"claude-corp": {"until": now + 176000, "checked": now, "detail": "429 7d"},
                  "root": {"until": now + 600, "checked": now, "detail": "429 5h"}})
    r = _run(env, gateway_logs="")
    assert r.returncode == 0, r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root", "2일 뒤 회복하는 계정을 남겼다"
    assert "가장 빨리 회복되는" in r.stderr


# ── probe 형태 (비용·OAuth 호환) ──────────────────────────────────────────────
def test_probe_shape_is_pinned(env):
    _seed(env, **{"root": _fresh()})
    with _ProbeServer([(429, _rl_headers(int(time.time()) + 172800)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
        c = srv.calls[0]
    assert c["body"]["max_tokens"] == 16
    assert c["body"]["model"] == "claude-haiku-4-5"
    assert c["body"]["system"][0]["text"].startswith("You are Claude Code")
    assert c["anthropic-beta"] == "oauth-2025-04-20", "OAuth 토큰 추론에 필요한 beta 헤더가 빠졌다"


# ── 안전장치: 사용 가능 계정 0 → .env·컨테이너 무변경 + exit 1 ────────────────
def test_no_usable_account_exits_1_without_touching_anything(env):
    for acct in ("claude-corp", "root"):
        (env["cred_root"] / acct / ".credentials.json").unlink()
    before = env["env_file"].read_text()
    r = _run(env, gateway_logs="")
    assert r.returncode == 1, r.stderr
    assert env["env_file"].read_text() == before
    assert not env["docker_calls"].exists()


# ── recreate 는 토큰이 실제로 바뀐 경우에만 ───────────────────────────────────
def test_recreate_only_when_token_changed(env):
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    r1 = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
    assert r1.returncode == 0, r1.stderr
    assert env["docker_calls"].read_text().count("--force-recreate") == 1
    r2 = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
    assert r2.returncode == 0, r2.stderr
    assert env["docker_calls"].read_text().count("--force-recreate") == 1, "변경 없는데 재생성했다"
    assert "토큰 변경 없음" in r2.stderr


# ── 상태 파일 견고성 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("payload", ['{"claude-corp": "pwned"}',
                                     '{"claude-corp": [1,2,3]}',
                                     '{"claude-corp": {"until": "abc", "checked": null}}'])
def test_malformed_state_entry_does_not_break_primary_slot(env, payload):
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    env["state_file"].write_text(payload)
    with _ProbeServer([(200, {}), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
        assert srv.overflow == 0
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp", \
        "손상된 상태 항목이 1순위 slot 갱신을 멈췄다"


def test_unwritable_state_dir_does_not_block_injection(env):
    r = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0,
             CLAUDE_OAUTH_STATE_FILE="/proc/nowhere/exhaustion.json")
    assert r.returncode == 0, r.stderr
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"


# ── 보안: 파일 권한 ───────────────────────────────────────────────────────────
def test_secrets_are_not_world_readable(env):
    _seed(env, **{"root": _fresh()})
    with _ProbeServer([(429, _rl_headers(int(time.time()) + 172800)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    assert oct(env["env_file"].stat().st_mode)[-3:] == "600", ".env.bedrock 이 world-readable 이다"
    assert oct(env["state_file"].stat().st_mode)[-3:] == "600"


def test_probe_detail_redacts_tokens_and_control_chars(env):
    """엔드포인트가 돌려준 본문이 그대로 상태파일·로그로 새지 않는다.

    종전 버전은 기본 500 본문에 토큰이 없어 scrub 을 통째로 지워도 통과했다(vacuous pass) —
    적대 리뷰 mutation 으로 확인. 이제 서버가 토큰 모양 문자열·제어문자·장문을 실어 보낸다.
    """
    _seed(env, **{"root": _fresh()})
    leak = (b'{"error":"sk-ant-oat01-LEAKEDSECRET0123456789 \x07ctl \x00nul'
            + b'A' * 400 + b'"}')
    with _ProbeServer([(401, {}, leak)]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
    detail = _state(env)["claude-corp"]["detail"]
    assert "LEAKEDSECRET" not in detail, f"토큰 모양 문자열이 상태파일에 남았다: {detail!r}"
    assert "sk-ant-<redacted>" in detail
    assert "\x07" not in detail and "\x00" not in detail, f"제어문자가 남았다: {detail!r}"
    assert len(detail) <= 210
    assert "LEAKEDSECRET" not in r.stderr, "stderr(=/tmp/refresh-oauth.log)로도 새면 안 된다"


# ── 보안: 상태 파일 디렉토리 권한 + 심링크 미추종 ─────────────────────────────
def test_state_dir_is_private_and_tmp_does_not_follow_symlink(env):
    victim = env["tmp"] / "victim.txt"
    victim.write_text("DO-NOT-OVERWRITE")
    env["state_file"].parent.mkdir(parents=True, exist_ok=True)
    (env["tmp"] / "state" / "exhaustion.json.tmp").symlink_to(victim)

    _seed(env, **{"root": _fresh()})
    with _ProbeServer([(429, _rl_headers(int(time.time()) + 172800)), (200, {})]) as srv:
        r = _run(env, probe_url=srv.url, gateway_logs="")
        assert r.returncode == 0, r.stderr

    assert victim.read_text() == "DO-NOT-OVERWRITE", "고정 .tmp 이름이 심링크를 따라가 임의 파일을 덮어썼다"
    assert not env["state_file"].is_symlink()
    assert oct(env["state_file"].parent.stat().st_mode)[-3:] == "700"


# ── 보안: probe 는 리다이렉트를 따라가지 않는다 (Authorization 유출 차단) ─────
def test_probe_does_not_follow_redirects(env):
    """3xx 를 따라가면 urllib 은 Authorization 헤더를 **다른 호스트로도** 재전송한다."""
    collector = _ProbeServer([(200, {})])
    with collector:
        redirector = _ProbeServer([(302, {"location": collector.url})])
        with redirector:
            _seed(env, **{"root": _fresh()})
            r = _run(env, probe_url=redirector.url, gateway_logs="")
            assert r.returncode == 0, r.stderr
            assert len(redirector.calls) == 1
        assert collector.calls == [], "리다이렉트를 따라가 토큰이 다른 호스트로 전송됐다"

    assert "판정 보류" in r.stderr, "3xx 는 판정 보류(fail-open)여야 한다"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"


# ── 개행/제어문자가 섞인 토큰은 .env 를 깨뜨리기 전에 거부한다 ────────────────
def test_token_with_newline_is_rejected_before_writing_env(env):
    """토큰에 개행이 있으면 .env.bedrock 이 여러 줄로 깨져 다른 키를 덮어쓴다."""
    _write_cred(env["cred_root"], "claude-corp", "tokA\nANTHROPIC_API_KEY_ROOT=pwned")
    before = env["env_file"].read_text()
    r = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
    assert r.returncode != 0, "제어문자 토큰을 그대로 주입했다"
    assert env["env_file"].read_text() == before, ".env.bedrock 이 오염됐다"
    assert "pwned" not in env["env_file"].read_text()


# ── recreate 실패는 sentinel 로 남아 다음 실행이 재시도한다 ───────────────────
def test_failed_recreate_is_retried_next_run(env):
    """종전엔 recreate 실패 후 다음 실행이 CHANGED=0 으로 skip 해 **영구히** 재시도하지 않았다.

    .env 는 새 토큰인데 컨테이너는 옛 토큰 → 만료 후 전량 401.
    """
    docker = env["binstub"] / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "${1:-}" = "compose" ]; then\n'
        '  for a in "$@"; do [ "$a" = "logs" ] && { printf "%s\\n" "${MOCK_GATEWAY_LOGS:-}"; exit 0; }; done\n'
        "fi\n"
        'printf "%s\\n" "$@" >> "$MOCK_DOCKER_CALLS"\n'
        'exit "${MOCK_DOCKER_UP_RC:-0}"\n')
    docker.chmod(0o755)
    sentinel = env["repo"] / ".env.bedrock.needs-recreate"

    r1 = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0, MOCK_DOCKER_UP_RC=1)
    assert r1.returncode == 1, "recreate 실패가 성공으로 보고됐다"
    assert sentinel.exists(), "재시도 sentinel 이 남지 않았다"
    assert "재생성 실패" in r1.stderr

    # 토큰은 그대로(CHANGED=0)지만 sentinel 이 있으므로 재시도해야 한다.
    r2 = _run(env, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0, MOCK_DOCKER_UP_RC=0)
    assert r2.returncode == 0, r2.stderr
    assert not sentinel.exists()
    assert env["docker_calls"].read_text().count("--force-recreate") == 2, "재시도하지 않았다"


# ═══ access token 자동 회전 (auto-rotate 2026-08-11, 사용자 승인) ══════════════
# R1 만료 임박이면 refreshToken 으로 선제 회전하고 새 토큰을 주입한다.
# R2 여유가 있으면 회전하지 않는다(토큰 엔드포인트 무접촉).
# R3 회전 실패(네트워크·4xx)는 자격증명 파일을 **건드리지 않는다**.
# R4 회전형 refresh token 을 원자적으로 영속화하고, 다른 필드·소유자·모드를 보존한다.
# R5 lock 이 잡혀 있으면(CLI 가 회전 중) 건드리지 않는다.
# R6 lock 획득 뒤 파일이 바뀌었으면(남이 이미 회전) 포기한다.
# R7 refresh token 자체가 만료됐으면 시도하지 않는다.
# R8 킬스위치.

def _expiring(env, acct="claude-corp", **kw):
    """만료 임박(=lead 안쪽) 자격증명으로 교체."""
    _write_cred(env["cred_root"], acct, "tok-" + acct.split("-")[-1], ttl_sec=600, **kw)


def test_rotate_refreshes_token_near_expiry_and_injects_it(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)   # lead(3600) 안쪽
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(access="rotated-corp"))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1, "만료 임박인데 회전하지 않았다"
        body = ts.calls[0]["body"]
        assert body["grant_type"] == "refresh_token"
        assert body["refresh_token"] == "refresh-tok-corp"
        assert body["client_id"] == "test-client-id"
        assert body["scope"] == "user:inference user:profile"
    o = _cred(env, "claude-corp")["claudeAiOauth"]
    assert o["accessToken"] == "rotated-corp"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "rotated-corp", "회전된 토큰이 주입되지 않았다"
    assert "자동 회전" in r.stderr


def test_rotate_skipped_when_ttl_is_comfortable(env):
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})   # 기본 TTL 7200 > lead 3600
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == [], "여유가 있는데 회전을 시도했다"
    assert _cred(env, "claude-corp")["claudeAiOauth"]["accessToken"] == "tok-corp"


@pytest.mark.parametrize("mode", ["http_400", "unreachable", "no_access_token"])
def test_rotate_failure_never_touches_credentials(env, mode):
    # MIN_TTL(300) 미만으로 둔다 — 회전에 실패하면 정적 검사가 걸러 폴백이 받아야 한다.
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=120)
    before = (env["cred_root"] / "claude-corp" / ".credentials.json").read_text()
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    if mode == "unreachable":
        r = _run(env, token_url="http://127.0.0.1:1/v1/oauth/token", gateway_logs="",
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
    else:
        resp = (400, {}, b'{"error":"invalid_grant"}') if mode == "http_400" \
            else (200, {}, b'{"expires_in":100}')
        with _TokenServer([resp]) as ts:
            r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
            assert len(ts.calls) == 1
    assert r.returncode == 0, r.stderr
    after = (env["cred_root"] / "claude-corp" / ".credentials.json").read_text()
    assert after == before, "회전 실패인데 자격증명 파일이 바뀌었다"
    assert "회전 생략" in r.stderr
    # 회전 못 한 계정은 정적 검사(만료 임박)로 걸러지고 폴백이 받는다
    assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-root"


def test_rotate_persists_new_refresh_token_and_preserves_everything_else(env):
    _expiring(env)
    path = env["cred_root"] / "claude-corp" / ".credentials.json"
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(access="A2", refresh="R2", expires_in=28800,
                                             scope="user:inference user:profile"))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr

    doc = _cred(env, "claude-corp")
    o = doc["claudeAiOauth"]
    assert o["accessToken"] == "A2"
    assert o["refreshToken"] == "R2", "회전형 refresh token 을 영속화하지 않으면 다음 회전이 죽는다"
    assert doc["organizationUuid"] == "org-keep-me", "다른 필드가 유실됐다"
    assert o["subscriptionType"] == "max"
    assert int(o["expiresAt"] / 1000) - int(time.time()) > 28000, "expiresAt 이 갱신되지 않았다"
    assert oct(path.stat().st_mode)[-3:] == "600"
    baks = sorted((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*"))
    assert len(baks) == 1, "교체 직전본 백업이 없다"
    assert json.loads(baks[0].read_text())["claudeAiOauth"]["accessToken"] == "tok-corp"
    assert oct(baks[0].stat().st_mode)[-3:] == "600"
    assert not list((env["cred_root"] / "claude-corp").glob(".credentials-*.tmp")), "임시 파일이 남았다"


def test_rotate_yields_to_existing_lock(env):
    _expiring(env)
    lock = env["cred_root"] / "claude-corp" / ".credentials.json.rotate.lock"
    lock.write_text("99999")
    before = (env["cred_root"] / "claude-corp" / ".credentials.json").read_text()
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == [], "다른 프로세스가 회전 중인데 끼어들었다"
    assert (env["cred_root"] / "claude-corp" / ".credentials.json").read_text() == before
    assert lock.exists(), "남의 lock 을 지웠다"
    assert "lock_busy" in r.stderr


def test_stale_lock_is_reclaimed(env):
    _expiring(env)
    lock = env["cred_root"] / "claude-corp" / ".credentials.json.rotate.lock"
    lock.write_text("1")
    os.utime(lock, (time.time() - 3600, time.time() - 3600))   # 죽은 프로세스 잔재
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(access="A3"))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1, "stale lock 때문에 영구히 회전 못 하면 안 된다"
    assert _cred(env, "claude-corp")["claudeAiOauth"]["accessToken"] == "A3"
    assert not lock.exists(), "회전 후 lock 을 해제하지 않았다"


def test_expired_refresh_token_is_not_attempted(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600, refresh_ttl_sec=-60)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == [], "만료된 refresh token 으로 요청했다(불필요한 invalid_grant 유발)"
    assert "refresh_token_expired" in r.stderr


def test_missing_refresh_token_is_not_attempted(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600, refresh_token="")
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == []
    assert "no_refresh_token" in r.stderr


def test_auto_rotate_kill_switch(env):
    _expiring(env)
    before = (env["cred_root"] / "claude-corp" / ".credentials.json").read_text()
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_AUTO_ROTATE=0,
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == []
    assert (env["cred_root"] / "claude-corp" / ".credentials.json").read_text() == before


def test_backup_retention_is_bounded(env):
    d = env["cred_root"] / "claude-corp"
    for i in range(7):
        (d / f".credentials.json.bak-{1700000000 + i}").write_text("{}")
    _expiring(env)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_ROTATE_KEEP_BACKUPS=3,
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert len(list(d.glob(".credentials.json.bak-*"))) == 3, "백업이 무한 증식한다"


def test_rotate_aborts_when_another_process_already_rotated(env):
    """lock 획득 사이에 CLI 가 먼저 회전했으면 포기한다.

    이 재확인이 없으면 두 프로세스가 같은 refresh token 으로 각각 회전을 시도하고, 늦은 쪽이
    이미 죽은 refresh token 을 써서 `invalid_grant` 를 받는다 — CLI 는 그때 자격증명을 통째로
    비운다(2026-08-09 claude-corp 이 그렇게 로그아웃됐다). `CLAUDE_OAUTH_ROTATE_RACE_DELAY_SEC`
    로 그 창을 인위적으로 열어 재현한다.
    """
    _expiring(env)
    cred = env["cred_root"] / "claude-corp" / ".credentials.json"
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})

    def _cli_rotates_first():
        time.sleep(0.8)
        _write_cred(env["cred_root"], "claude-corp", "rotated-by-cli", ttl_sec=28800)

    with _TokenServer([(200, {}, _token_body(access="rotated-by-us"))]) as ts:
        t = threading.Thread(target=_cli_rotates_first, daemon=True)
        t.start()
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0,
                 CLAUDE_OAUTH_ROTATE_RACE_DELAY_SEC=2)
        t.join(timeout=5)
        assert r.returncode == 0, r.stderr
        assert ts.calls == [], "남이 이미 회전했는데 죽은 refresh token 으로 또 요청했다"

    o = json.loads(cred.read_text())["claudeAiOauth"]
    assert o["accessToken"] == "rotated-by-cli", "남의 회전 결과를 덮어썼다"
    assert "race_resolved" in r.stderr
    assert not list((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*")), \
        "포기했는데 백업을 남겼다(=파일을 건드렸다)"


def test_rotate_sends_cli_user_agent(env):
    """토큰 엔드포인트는 Cloudflare UA 지문 검사를 한다 — 기본 urllib UA 면 1010 으로 끊긴다.

    2026-08-11 실측: `Python-urllib/*` → HTTP 403 Cloudflare Error 1010(앱 미도달),
    `Claude-User (claude-code/<ver>)` → 400 invalid_grant(정상 도달).
    """
    _expiring(env)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        ua = ts.calls[0]["user-agent"]
    assert ua.startswith("Claude-User (claude-code/"), f"CLI UA 가 아니다: {ua!r}"
    assert "urllib" not in ua.lower()


# ═══ 적대 리뷰(2026-08-11 패널) 반영 회귀 ═══════════════════════════════════════
def test_check_mode_never_rotates(env):
    """`--check` 는 부작용 0 계약이다 — 회전은 파일을 쓰고 일회성 refresh token 을 태운다.

    종전 구현은 `--check` 에서도 실제로 회전했다(적대 리뷰 P1). 인시던트 진단 중 운영자가
    무심코 부르는 명령이라 위험이 크다.
    """
    _expiring(env)
    before = (env["cred_root"] / "claude-corp" / ".credentials.json").read_text()
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, "--check", token_url=ts.url, gateway_logs="")
        assert r.returncode == 0, r.stderr
        assert ts.calls == [], "--check 인데 refresh token 을 소모했다"
    assert (env["cred_root"] / "claude-corp" / ".credentials.json").read_text() == before
    assert not list((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*"))


@pytest.mark.parametrize("payload", [b'[1,2,3]', b'null', b'{"access_token":123}',
                                     b'{"access_token":"A","scope":["not","a","string"]}',
                                     b'not json at all'])
def test_malformed_token_response_cannot_kill_slot_selection(env, payload):
    """회전 중 어떤 예외도 선택 로직을 죽이면 안 된다.

    죽으면 bash 의 `SEL="$(...)" || SEL=""` 가 삼켜 1순위 slot 이 조용히 갱신 정지한다
    (exit 0). 적대 리뷰 P1 — 서버가 돌려주는 응답만으로 재현됐다.
    """
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, payload)]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert "Traceback" not in r.stderr, f"선택 로직이 예외로 죽었다:\n{r.stderr[-600:]}"
    assert "(none)" not in r.stderr, "1순위 slot 이 갱신 정지했다"
    # 응답이 쓰레기여도 slot 은 살아 있어야 한다 — 회전 결과(정상 access_token) 또는 기존 토큰.
    assert _env_val(env, "ANTHROPIC_API_KEY") in ("tok-corp", "A"), _env_val(env, "ANTHROPIC_API_KEY")


def test_missing_expires_in_never_persists_a_past_expiry(env):
    """expires_in 이 없어도 방금 받은 토큰을 '만료됨' 으로 기록하면 안 된다.

    종전엔 과거 값을 되써서 (a) 멀쩡한 토큰이 정적 검사에서 탈락하거나 (b) 매 실행 재회전 +
    게이트웨이 재생성 폭풍이 됐다(적대 리뷰 P1, 둘 다 실증됨).
    """
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, b'{"access_token":"A-NEW"}')]) as ts:
        r1 = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r1.returncode == 0, r1.stderr
        assert len(ts.calls) == 1
    o = _cred(env, "claude-corp")["claudeAiOauth"]
    assert int(o["expiresAt"] / 1000) - int(time.time()) > 3600, "과거 만료를 되썼다"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "A-NEW"
    # 2회차: 이미 여유가 생겼으므로 재회전하지 않는다(= 재생성 폭풍 없음)
    with _TokenServer([(200, {}, _token_body())]) as ts2:
        r2 = _run(env, token_url=ts2.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r2.returncode == 0, r2.stderr
        assert ts2.calls == [], "매 실행 재회전한다"
    assert env["docker_calls"].read_text().count("--force-recreate") == 1


def test_already_expired_access_token_is_recovered(env):
    """동기가 된 사건 그 자체 — 밤사이 만료된 토큰을 회전해 되살린다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=-3600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(access="REVIVED"))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert _env_val(env, "ANTHROPIC_API_KEY") == "REVIVED", "만료된 토큰을 되살리지 못했다"


@pytest.mark.skipif(os.geteuid() != 0,
                    reason="다른 uid 로 chown 하려면 root 필요 — 운영 cron 은 root 로 돈다")
def test_rotation_preserves_file_owner(env):
    """root 로 돌지만 파일 주인은 계정 사용자다 — root 소유로 바꾸면 그 CLI 로그인이 깨진다."""
    import pwd
    uid = pwd.getpwnam("nobody").pw_uid
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    f = env["cred_root"] / "claude-corp" / ".credentials.json"
    os.chown(f, uid, -1)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert f.stat().st_uid == uid, "회전 후 파일 주인이 바뀌었다(계정 CLI 로그인 파손)"
    bak = list((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*"))
    assert bak and bak[0].stat().st_uid == uid


def test_credentials_replace_is_atomic(env):
    """교체는 rename 이어야 한다 — 제자리 덮어쓰기는 중간에 잘린 파일을 노출한다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    f = env["cred_root"] / "claude-corp" / ".credentials.json"
    ino = f.stat().st_ino
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
    assert f.stat().st_ino != ino, "os.replace 가 아니라 제자리 쓰기였다(원자성 없음)"


def test_no_backup_written_when_rotation_yields_nothing(env):
    """응답에 access_token 이 없으면 파일을 **아예** 건드리지 않는다(백업도 없다)."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, b'{"expires_in":100}')]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
    assert not list((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*"))


def test_backup_path_symlink_is_not_followed(env):
    """root 가 비특권 계정 소유 디렉토리에 쓴다 — .bak 경로 심링크를 따라가면 임의 파일 덮어쓰기."""
    victim = env["tmp"] / "victim-root-owned.txt"
    victim.write_text("DO-NOT-OVERWRITE")
    d = env["cred_root"] / "claude-corp"
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    now = int(time.time())
    for t in range(now, now + 8):                      # 예측 가능한 시각을 전부 선점
        for suffix in ("", "-000000"):
            try:
                (d / f".credentials.json.bak-{t}{suffix}").symlink_to(victim)
            except FileExistsError:
                pass
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
    assert victim.read_text() == "DO-NOT-OVERWRITE", "심링크를 따라가 임의 파일을 덮어썼다"
    assert _cred(env, "claude-corp")["claudeAiOauth"]["accessToken"] == "new-access", \
        "심링크 방해로 회전 자체가 실패하면 안 된다(백업은 best-effort)"


def test_symlinked_credentials_file_is_refused(env):
    real = env["tmp"] / "elsewhere.json"
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    f = env["cred_root"] / "claude-corp" / ".credentials.json"
    f.rename(real)
    f.symlink_to(real)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert ts.calls == []
    assert "credentials_is_symlink" in r.stderr


def test_rotation_failure_backs_off(env):
    """엔드포인트가 계속 실패하면 30분마다 무한 재시도하지 않는다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(429, {}, b'{"error":"rate_limited"}')]) as ts:
        r1 = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r1.returncode == 0, r1.stderr
        assert len(ts.calls) == 1
    assert _state(env)["rotate:claude-corp"]["next"] > int(time.time())
    with _TokenServer([(200, {}, _token_body())]) as ts2:
        r2 = _run(env, token_url=ts2.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r2.returncode == 0, r2.stderr
        assert ts2.calls == [], "backoff 중인데 또 때렸다"
    assert "backoff" in r2.stderr


def test_token_endpoint_error_body_is_scrubbed(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    leak = b'{"error":"sk-ant-ort01-LEAKEDREFRESH0123456789 \x07ctl"}'
    with _TokenServer([(400, {}, leak)]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
    assert "LEAKEDREFRESH" not in r.stderr, "토큰 모양 문자열이 로그로 샜다"
    assert "LEAKEDREFRESH" not in json.dumps(_state(env))


def test_keep_backups_zero_keeps_nothing(env):
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    d = env["cred_root"] / "claude-corp"
    for i in range(3):                       # 기존 백업이 있어야 prune 계약이 검증된다
        (d / f".credentials.json.bak-{1700000000 + i}").write_text("{}")
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body())]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_ROTATE_KEEP_BACKUPS=0,
                 CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert not list((env["cred_root"] / "claude-corp").glob(".credentials.json.bak-*")), \
        "0=보관 안 함인데 오히려 전부 남겼다"


def test_lost_update_during_http_window_is_discarded(env):
    """HTTP 왕복 동안 CLI 가 쓴 결과를 우리 스냅샷으로 덮어쓰면 안 된다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})

    def _cli_writes_midflight():
        time.sleep(1.2)      # 요청 전 재확인(즉시)은 지나고, 응답(3s) 전에 들어온다
        _write_cred(env["cred_root"], "claude-corp", "rotated-by-cli", ttl_sec=28800)

    # 서버가 3초 늦게 응답하는 동안 CLI 가 쓴다 — 이 창은 '요청 전' 재확인으로는 못 막고
    # **요청 직후** 재확인만이 막는다.
    with _TokenServer([(200, {"x-test-delay": "3"}, _token_body(access="rotated-by-us"))]) as ts:
        t = threading.Thread(target=_cli_writes_midflight, daemon=True)
        t.start()
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0,
                 CLAUDE_OAUTH_PROBE_TIMEOUT=20)
        t.join(timeout=10)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert _cred(env, "claude-corp")["claudeAiOauth"]["accessToken"] == "rotated-by-cli", \
        "남의 회전 결과를 덮어썼다(lost update)"


def test_narrowed_scope_is_not_persisted(env):
    """서버가 좁혀 돌려준 scope 를 저장하면(RFC 6749 §5.1 허용) 다음 회전이 그 좁은 scope 로
    나가 되돌릴 수 없다 — scope 는 요청 입력일 뿐이므로 영속화하지 않는다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    before = _cred(env, "claude-corp")["claudeAiOauth"]["scopes"]
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(scope="user:inference"))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert _cred(env, "claude-corp")["claudeAiOauth"]["scopes"] == before, "scope 가 잠식됐다"


def test_write_failure_after_successful_post_cannot_kill_slot_selection(env):
    """POST 성공 후 쓰기 단계에서 예외가 나도 선택 로직은 살아야 한다.

    refresh token 은 이미 소모됐다 — 여기서 selector 가 죽으면 slot 이 통째로 정지한다.
    """
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    f = env["cred_root"] / "claude-corp" / ".credentials.json"
    if subprocess.run(["chattr", "+i", str(f)], capture_output=True).returncode != 0:
        pytest.skip("chattr +i 미지원 파일시스템 — 쓰기 실패를 재현할 수 없다")
    try:
        _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
        with _TokenServer([(200, {}, _token_body())]) as ts:
            r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
            assert len(ts.calls) == 1
        assert "Traceback" not in r.stderr, f"쓰기 실패가 selector 를 죽였다:\n{r.stderr[-500:]}"
        assert "(none)" not in r.stderr, "1순위 slot 이 갱신 정지했다"
        assert _env_val(env, "ANTHROPIC_API_KEY") == "tok-corp"
    finally:
        subprocess.run(["chattr", "-i", str(f)], capture_output=True)


def test_absurd_expires_in_is_clamped(env):
    """비정상적으로 큰 expires_in 은 epoch 연산·표시에서 예외가 된다 — 그 예외는 파일을 이미
    바꾼 뒤에 터지므로 기본 TTL 로 클램프한다."""
    _write_cred(env["cred_root"], "claude-corp", "tok-corp", ttl_sec=600)
    _seed(env, **{"claude-corp": _fresh(), "root": _fresh()})
    with _TokenServer([(200, {}, _token_body(access="A-CLAMP", expires_in=10 ** 18))]) as ts:
        r = _run(env, token_url=ts.url, gateway_logs="", CLAUDE_OAUTH_GATE_RECHECK_SEC=0)
        assert r.returncode == 0, r.stderr
        assert len(ts.calls) == 1
    assert "Traceback" not in r.stderr, r.stderr[-400:]
    remaining = int(_cred(env, "claude-corp")["claudeAiOauth"]["expiresAt"] / 1000) - int(time.time())
    assert 28000 < remaining < 30000, f"클램프되지 않았다: {remaining}s"
    assert _env_val(env, "ANTHROPIC_API_KEY") == "A-CLAMP"

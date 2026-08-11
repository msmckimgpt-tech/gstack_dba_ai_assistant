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
                status, headers = spec[0], spec[1]
                payload = spec[2] if len(spec) > 2 else (
                    b'{"content":[{"type":"text","text":"pong"}]}' if status == 200
                    else b'{"type":"error","error":{"type":"rate_limit_error"}}')
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
    "CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC": "1800",
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

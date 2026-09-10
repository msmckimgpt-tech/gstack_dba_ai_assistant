"""CLI **자체 모델 카탈로그** 경로 (사용자 요청 2026-09-07).

## 왜 이 경로가 생겼나

사용자 요청: *"공식 웹사이트 등에서 해당 목록을 즉시 얻을 수 있다면, 그렇게 진행하는 부분도
검토해주세요."* — 찾아보니 웹사이트보다 나은 것이 **CLI 안에** 있었다.
`codex debug models` = 「Render the raw model catalog as JSON」(`codex debug --help`).

같은 머신 실측 (2026-09-07):

| 경로 | 시간 | 결과 |
|---|---|---|
| `codex debug models` | **0.23초** | 노출 모델 7종 + 등급 4단계 |
| 능력 질의(가드+extras) | 22.7초 | **`models: []`** — 「모델은 못 고른다」 |
| 가드 없이 · 모델축만 · 원장 확인 | 200~603초 | 전부 **타임아웃** |

## 무엇을 잠그는가

1. 카탈로그 출력이 능력으로 옮겨진다 — 노출(`visibility`) 필터·우선순위 순서·등급 교집합.
2. **출력이 커도 잘리지 않는다.** 첫 구현이 정확히 여기서 죽었다(아래 회귀 참조).
3. 카탈로그가 **캐시를 이긴다** — 아끼면 낡은 목록이 그 머신에서 계속 정본이 된다.
4. 카탈로그 결과는 **로컬 캐시에 남지 않는다** — 다음 기동이 다시 읽어 항상 최신이다.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_catalog", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ba():
    return _load_runner()


def _model(slug, *, vis="list", prio=1, efforts=("low", "medium", "high", "xhigh"),
           name=None, filler=0):
    """실측 `codex debug models` 항목의 축약. `filler` 로 프롬프트 전문 부피를 흉내 낸다."""
    out = {
        "slug": slug,
        "display_name": name or slug.upper(),
        "visibility": vis,
        "priority": prio,
        "supported_reasoning_levels": [{"effort": e, "description": ""} for e in efforts],
    }
    if filler:
        out["model_messages"] = {"persistent_instructions": "가" * filler}
    return out


def _catalog(*models) -> str:
    return json.dumps({"models": list(models)}, ensure_ascii=False)


class _Proc:
    def __init__(self, out="", rc=0, err=""):
        self.stdout, self.returncode, self.stderr = out, rc, err


def _fake_run(ba, monkeypatch, payload, rc=0):
    seen: list = []

    def _run(cmd, **_k):
        seen.append(list(cmd))
        return _Proc(out=payload, rc=rc)

    monkeypatch.setattr(ba.subprocess, "run", _run)
    return seen


# ── 1. 파싱 계약 ────────────────────────────────────────────────────────────


def test_catalog_becomes_capabilities(ba, monkeypatch):
    """노출 모델만·CLI 가 정한 순서로·등급은 **교집합**."""
    seen = _fake_run(ba, monkeypatch, _catalog(
        _model("gpt-5.6-sol", prio=6, efforts=("low", "medium", "high", "xhigh", "max", "ultra")),
        _model("gpt-6-astra", prio=1, efforts=("low", "medium", "high", "xhigh", "max", "ultra")),
        _model("gpt-reserve", prio=3, vis="hide"),
        _model("gpt-5.5", prio=12, efforts=("low", "medium", "high", "xhigh")),
    ))
    got = ba.catalog_runtime_caps("codex")
    assert got is not None, "카탈로그를 능력으로 옮기지 못했다"
    assert [m["value"] for m in got["models"]] == ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.5"], (
        "노출 필터 또는 우선순위 순서가 그 CLI 가 정한 것과 다르다")
    assert [e["value"] for e in got["efforts"]] == ["low", "medium", "high", "xhigh"], (
        "등급이 교집합이 아니다 — 어떤 모델에서는 거부되는 값을 고를 수 있게 된다")
    assert got["source"] == "catalog"
    assert got["model"] == ["-m", "{model}"], "모델을 넘길 인자 형태가 붙지 않았다"
    # ⚠ `subprocess.run` patch 는 **stdlib 모듈 전역**이라, 앞선 테스트가 남긴 배경 스레드
    #   (생존 확인 등)의 호출도 여기 섞인다. 「첫 호출」을 단정하면 그 잡음에 흔들리므로
    #   «카탈로그 명령이 실제로 나갔는가» 를 본다(이 테스트가 증명하려는 것은 그것이다).
    assert any(c[-2:] == ["debug", "models"] for c in seen), f"카탈로그 명령이 아니다: {seen}"


def test_a_large_catalog_is_not_truncated(ba, monkeypatch):
    """⭐ 회귀 — 출력이 커도 **잘리지 않는다**.

    첫 구현은 `_CAPS_PROBE_MAX_BYTES`(256KB)로 잘랐는데 실측 출력은 **413,777 바이트**였다
    (모델마다 `model_messages` 프롬프트 전문이 실린다). JSON 이 중간에서 끊겨 `json.loads`
    가 실패했고, 이 경로는 **한 번도 성공하지 못한 채** 조용히 폴백했다 — 배선은 있는데
    실행되지 않는 상태(§16.7 G14-e: 존재는 실행이 아니다). 종단 실행에서야
    「카탈로그 출력을 해석하지 못했습니다」 0.198초로 드러났다.
    """
    payload = _catalog(_model("gpt-5.6-sol", filler=200_000),
                       _model("gpt-5.5", prio=2, filler=200_000))
    assert len(payload.encode("utf-8")) > ba._CAPS_PROBE_MAX_BYTES, (
        "이 표본이 종전 상한을 넘지 않으면 이 테스트는 아무것도 증명하지 못한다")
    _fake_run(ba, monkeypatch, payload)
    got = ba.catalog_runtime_caps("codex")
    assert got and [m["value"] for m in got["models"]] == ["gpt-5.6-sol", "gpt-5.5"]


@pytest.mark.parametrize("payload,rc", [
    ("not json at all", 0),
    ('{"models": []}', 0),
    ('{"models": [{"slug": "x", "visibility": "hide"}]}', 0),
    ('{"models": [{"slug": "ok", "visibility": "list"}]}', 1),
])
def test_a_broken_catalog_falls_back_quietly(ba, monkeypatch, payload, rc):
    """포맷 변경·비정상 종료·빈 결과는 **예외가 아니라 None** 이다.

    `debug` 하위명령이라 포맷이 바뀔 수 있다. 여기서 예외가 새면 그 런타임의 협상 스레드가
    죽어 「협상이 조용히 안 끝나는」 상태가 된다 — 이 파일이 지키는 것은 «이 경로가 사라져도
    기능은 죽지 않는다» 이다.
    """
    _fake_run(ba, monkeypatch, payload, rc=rc)
    why: dict = {}
    assert ba.catalog_runtime_caps("codex", reason_out=why) is None
    assert why.get("reason"), "실패했는데 사유가 남지 않았다 — 진단할 근거가 사라진다"


def test_runtimes_without_a_catalog_skip_the_path(ba, monkeypatch):
    """카탈로그 명령이 없는 런타임은 프로세스를 **띄우지도 않는다**."""
    seen = _fake_run(ba, monkeypatch, _catalog(_model("x")))
    assert ba.catalog_runtime_caps("claude") is None
    assert seen == [], "카탈로그가 없는 런타임에서 명령을 실행했다"


def test_one_silent_model_does_not_erase_every_effort_level(ba, monkeypatch):
    """⭐ 등급 교집합의 모수는 **신고한 모델**뿐이다 (적대리뷰 P2 ×2, 2026-09-07).

    카탈로그의 노출 모델 하나가 `supported_reasoning_levels` 를 빠뜨리면(또는 리스트가 아닌
    값이라 타입 가드가 `[]` 로 접으면), 종전 교집합은 그 빈 목록까지 모수에 넣어 **공집합**을
    만들었다. 그러면 그 런타임의 추론 등급 선택기가 통째로 사라지고, 카탈로그가 매 기동
    캐시를 이기므로 그 소실이 영구화된다 — 「덜 주되 항상 맞게」가 「아무것도 안 준다」로
    뒤집힌다. 빈 목록은 「지정할 수 없다」가 아니라 「이 카탈로그가 말하지 않았다」이다.
    """
    _fake_run(ba, monkeypatch, _catalog(
        _model("gpt-6-astra", prio=1, efforts=("low", "medium", "high")),
        {"slug": "gpt-mini", "display_name": "Mini", "visibility": "list", "priority": 2},
        {"slug": "gpt-odd", "display_name": "Odd", "visibility": "list", "priority": 3,
         "supported_reasoning_levels": "not-a-list"},
    ))
    got = ba.catalog_runtime_caps("codex")
    assert got is not None
    assert [m["value"] for m in got["models"]] == ["gpt-6-astra", "gpt-mini", "gpt-odd"]
    assert [e["value"] for e in got["efforts"]] == ["low", "medium", "high"], (
        "등급을 신고하지 않은 모델이 교집합을 공집합으로 만들었다 — 선택기가 통째로 사라진다")


def test_a_catalog_failure_does_not_mask_the_real_reason(ba, monkeypatch):
    """⭐ 카탈로그 실패 사유가 **뒤 사유를 가리지 않는다** (적대리뷰 P2, 2026-09-07).

    카탈로그는 맨 먼저 시도되므로 그 사유를 `reasons[nm]` 에 바로 대입하면, 뒤따르는
    `reasons.setdefault(...)`(남은 시간 부족 · `_probe` 예외)가 통째로 가려진다 — 사용자에게는
    실제 원인 대신 「카탈로그 조회 exit 1」이 표시된다. 이 파일이 반복해 고쳐 온 「실패를 다른
    실패로 위장」의 재생산이다.
    """
    monkeypatch.setattr(ba, "_which_ai", lambda n: "/usr/bin/codex" if n == "codex" else None)
    _fake_run(ba, monkeypatch, "not json", rc=1)           # 카탈로그 실패

    def _boom(*_a, **_k):
        raise RuntimeError("OAuth access token has expired")

    monkeypatch.setattr(ba, "_ask_json", _boom)
    seen: list = []
    monkeypatch.setattr(ba, "note_ai_unusable", lambda msg, **kwargs: seen.append(str(msg)))
    ba.detect_runtimes(only="codex", cached=None, probe=True)
    assert seen, "실패를 사용자 축으로 알리지 않았다"
    assert "OAuth access token has expired" in seen[-1], (
        f"카탈로그 사유가 실제 원인을 가렸다: {seen[-1]}")


def test_a_winning_catalog_keeps_the_existing_disk_cache(ba, monkeypatch):
    """⭐ 카탈로그가 이겨도 **디스크 캐시를 지우지 않는다** (적대리뷰 P2 ×2, 2026-09-07).

    `catalog` 은 캐시 금지 출처라 `_detail` 에서 빠지는데, `_publish_caps` 가 「`_detail` 에
    없는 키는 지운다」로 `caps` 에서 pop 하고 `save_conf` 가 파일을 통째로 재작성한다 —
    그 머신의 기존 probe 캐시가 **삭제된다**. 그 뒤 `debug models` 없는 빌드로 내려가면
    되돌아갈 캐시가 없어 매 기동 LLM 질의로 떨어진다. 캐시는 이번 회차의 후보가 아니라
    다음 기동의 안전망이다.
    """
    monkeypatch.setattr(ba, "_which_ai", lambda n: "/usr/bin/codex" if n == "codex" else None)
    _fake_run(ba, monkeypatch, _catalog(_model("gpt-5.6-sol")))
    prior = {"codex": {"label": "Codex", "source": "cache", "effort_probed": True,
                       "models": [{"value": "gpt-5.1-codex", "label": "옛 세대"}],
                       "efforts": [], "model": ["-m", "{model}"], "effort": None,
                       "argv": ["codex", "exec", "{prompt}"]}}
    detail: dict = {}
    got = ba.detect_runtimes(only="codex", cached=prior, probe=True, detail_out=detail)
    entry = next(r for r in got if r["runtime"] == "codex")
    assert entry["source"] == "catalog" and \
        [m["value"] for m in entry["models"]] == ["gpt-5.6-sol"], "카탈로그가 신고를 이기지 않았다"
    assert detail.get("codex") == prior["codex"], (
        "카탈로그가 이기면서 디스크 캐시를 지웠다 — 다음 기동의 안전망이 사라진다")


# ── 2. 배선 계약 ────────────────────────────────────────────────────────────


def test_catalog_wins_over_the_local_cache(ba, monkeypatch):
    """⭐ 캐시가 있어도 카탈로그를 **다시 읽는다**.

    캐시를 두는 이유는 «비싼 질의를 반복하지 않는다» 인데, 이 경로는 240ms·토큰 0 이라 그
    이유가 성립하지 않는다. 아끼면 몇 달 전 LLM 답이 그 머신에서 계속 정본이 된다 — 이
    경로가 해결하려던 상태(낡은 목록)를 캐시가 그대로 재생산한다.
    """
    monkeypatch.setattr(ba, "_which_ai", lambda n: "/usr/bin/codex" if n == "codex" else None)
    _fake_run(ba, monkeypatch, _catalog(_model("gpt-5.6-sol")))
    stale = {"codex": {"label": "Codex", "source": "cache", "effort_probed": True,
                       "models": [{"value": "gpt-5.1-codex", "label": "옛 세대"}],
                       "efforts": [], "model": ["-m", "{model}"], "effort": None,
                       "argv": ["codex", "exec", "{prompt}"]}}
    detail: dict = {}
    got = ba.detect_runtimes(only="codex", cached=stale, probe=True, detail_out=detail)
    entry = next(r for r in got if r["runtime"] == "codex")
    assert [m["value"] for m in entry["models"]] == ["gpt-5.6-sol"], (
        "캐시의 낡은 목록이 카탈로그를 이겼다")
    assert entry["source"] == "catalog"
    # ⚠ 계약이 갈린다 (적대리뷰 P2, 2026-09-07): **카탈로그 결과는 캐시에 남기지 않되,
    #   이미 있던 캐시는 지우지 않는다.** 앞은 「매번 다시 읽어 항상 최신」이고, 뒤는
    #   「카탈로그가 없는 빌드로 내려갔을 때의 안전망」이다. 초판은 뒤를 보지 않아
    #   `save_conf` 가 파일을 재작성하며 기존 캐시를 지우는 것을 통과시켰다.
    assert detail.get("codex") == stale["codex"], (
        "카탈로그 결과가 캐시를 덮었거나 기존 캐시를 지웠다 — 둘 다 안 된다")


def test_a_failed_catalog_does_not_re_query_a_settled_cache(ba, monkeypatch):
    """⭐ 회귀 — 카탈로그가 **실패해도** 이미 완전한 캐시를 다시 묻지 않는다.

    종전에는 `ask` 가 «캐시 없음 또는 축 미확정» 일 때만 협상을 돌렸으므로 캐시가 완전하면
    LLM 질의가 0회였다. 카탈로그 경로가 `ask` 에 «카탈로그가 있는 런타임» 을 추가하면서,
    그 카탈로그가 실패하는 빌드(구 codex 처럼 `debug models` 를 모르는)에서는 확정된 캐시가
    축 재질의로 흘러 **매 기동마다 LLM 질의를 한 번씩 태운다** — 캐시를 둔 이유를 정면으로
    깨는 회귀다(자기검토 2026-09-07에 적발).
    """
    monkeypatch.setattr(ba, "_which_ai", lambda n: "/usr/bin/codex" if n == "codex" else None)
    _fake_run(ba, monkeypatch, "not json", rc=1)          # 카탈로그 실패
    asked: list = []
    monkeypatch.setattr(ba, "_ask_json",
                        lambda *a, **k: asked.append("asked") or None)
    settled = {"codex": {"label": "Codex", "source": "cache", "effort_probed": True,
                         "models": [{"value": "gpt-5.6-sol", "label": "Sol"}],
                         "efforts": [{"value": "low", "label": "낮음"}],
                         "model": ["-m", "{model}"], "effort": ["-c", "e={effort}"],
                         "argv": ["codex", "exec", "{prompt}"]}}
    got = ba.detect_runtimes(only="codex", cached=settled, probe=True)
    assert asked == [], f"확정된 캐시인데 LLM 에 다시 물었다: {len(asked)}회"
    entry = next(r for r in got if r["runtime"] == "codex")
    assert [m["value"] for m in entry["models"]] == ["gpt-5.6-sol"], "캐시 목록이 사라졌다"
    assert entry["source"] == "cache"


def test_catalog_reruns_even_when_probing_is_otherwise_skipped(ba, monkeypatch):
    """캐시가 **완전한** 런타임도 카탈로그 때문에 협상 대상에 남는다.

    `ask` 계산이 카탈로그를 보지 않으면 위 계약은 코드로만 존재한다 — `_probe` 가 아예
    불리지 않기 때문이다(§16.7 G14-e).
    """
    monkeypatch.setattr(ba, "_which_ai", lambda n: "/usr/bin/codex" if n == "codex" else None)
    seen = _fake_run(ba, monkeypatch, _catalog(_model("gpt-5.6-sol")))
    settled = {"codex": {"label": "Codex", "source": "cache", "effort_probed": True,
                         "models": [{"value": "old", "label": "old"}],
                         "efforts": [{"value": "low", "label": "낮음"}],
                         "model": ["-m", "{model}"], "effort": ["-c", "e={effort}"],
                         "argv": ["codex", "exec", "{prompt}"]}}
    ba.detect_runtimes(only="codex", cached=settled, probe=True)
    assert seen, "완전한 캐시가 있으면 카탈로그를 아예 읽지 않는다"


# ── 3. 서버 원장 축 ─────────────────────────────────────────────────────────


def test_catalog_anchors_the_ledger_like_an_open_enumeration():
    """`catalog` 는 열린 열거와 **같은 급** — 앵커를 세우고 streak 을 0으로 되돌린다.

    카탈로그는 그 CLI 의 출력 그대로라 회차별 흔들림이 없다. 확인(`verified`)처럼 streak 을
    올리면, 확인만 반복돼 제시가 멎는 축(`BASELINE_MAX_VERIFY_STREAK`)에 카탈로그가 걸려
    **가장 믿을 만한 목록이 먼저 꺼진다**.
    """
    import sys
    sys.path.insert(0, str(_UNIT.parent))
    from shared import bridge_caps

    t0 = datetime(2026, 9, 7, tzinfo=timezone.utc)
    rt = [{"runtime": "codex", "label": "Codex",
           "models": [{"value": "gpt-5.6-sol", "label": "Sol"}], "efforts": []}]
    led = bridge_caps.merge_baseline({}, rt, now=t0, sources={"codex": "verified"})
    led = bridge_caps.merge_baseline(led, rt, now=t0 + timedelta(hours=2),
                                     sources={"codex": "verified"})
    assert led["codex"]["verify_streak"] == 2

    at = t0 + timedelta(hours=4)
    led = bridge_caps.merge_baseline(led, rt, now=at, sources={"codex": "catalog"})
    assert led["codex"]["verify_streak"] == 0, "카탈로그가 자기강화 카운터를 되돌리지 않는다"
    assert led["codex"]["probed_at"] == bridge_caps._iso(at), "카탈로그가 앵커를 세우지 않는다"

    # 원장 폴백은 반대다 — 원장을 되받아 원장을 갱신하면 자기강화 루프가 된다.
    later = at + timedelta(hours=2)
    led2 = bridge_caps.merge_baseline(led, rt, now=later, sources={"codex": "baseline"})
    assert led2["codex"]["probed_at"] == led["codex"]["probed_at"], (
        "원장 폴백이 앵커를 갱신했다 — 「앵커된 답이 앵커를 갱신」하는 루프가 열렸다")
    assert led2["codex"]["verify_streak"] == 0
    # ⭐ **만료 축까지 본다** (적대리뷰 P1 ×2, 2026-09-07). 초판은 위 두 줄만 보고 통과했는데,
    #   실제 화석 만료는 `last_used_at` 이 결정한다 — `prune_stale` 의 TTL(14일)이 그 값을
    #   읽기 때문이다. 폴백이 그 값을 매번 밀면 `probed_at`·`verify_streak` 을 얼려 둬도
    #   항목은 **영원히 살아남고**, 그 원장이 다시 폴백으로 화면에 오르는 닫힌 루프가 된다.
    #   즉 초판은 「갱신하지 않는다」를 증명한다고 적고 정작 갱신되는 필드를 보지 않았다.
    assert led2["codex"]["last_used_at"] == led["codex"]["last_used_at"], (
        "원장 폴백이 TTL 축(last_used_at)을 밀었다 — 화석이 영구화된다")


def test_a_baseline_echo_cannot_keep_a_fossil_alive_past_its_ttl():
    """⭐ 위 단정의 **결과**를 만료 지점에서 확인한다 (적대리뷰 P1, 2026-09-07).

    필드 하나를 보는 것과 「그래서 만료되는가」는 다른 사실이다. 실조회가 계속 실패해
    폴백만 도는 러너를 TTL 너머까지 돌려, 그 항목이 실제로 걷혀 나가는지 본다.
    """
    import sys
    sys.path.insert(0, str(_UNIT.parent))
    from shared import bridge_caps

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rt = [{"runtime": "codex", "label": "Codex",
           "models": [{"value": "gpt-5.1-codex", "label": "옛 세대"}], "efforts": []}]
    led = bridge_caps.merge_baseline({}, rt, now=t0, sources={"codex": "probe"})
    assert "codex" in led

    # 폴백만 도는 러너: TTL(14일)의 두 배를 1시간 간격으로 신고한다.
    at = t0
    for _ in range(24 * bridge_caps.BASELINE_TTL_DAYS * 2):
        at = at + timedelta(hours=1)
        led = bridge_caps.merge_baseline(led, rt, now=at, sources={"codex": "baseline"})

    assert bridge_caps.prune_stale(led, now=at) == {}, (
        "원장 폴백만 반복됐는데 항목이 TTL 을 넘겨 살아남았다 — 화석이 영구화된다")

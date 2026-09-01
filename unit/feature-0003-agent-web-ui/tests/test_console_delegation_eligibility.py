"""feature-0043 (TASK-20260901T190000) — **배급 자격 판정**의 행위 계약.

## 왜 이 파일이 생겼나

뮤테이션에서 두 뮤턴트가 **생존**했다:

- `_classify` 의 `runner_can_take` 재질의를 지워도 아무 테스트가 안 죽었다
- 되메우는 선행 분기(`console_jobs` 신고 확인)까지 **함께** 지워도 안 죽었다

두 번째가 중요하다. 첫 번째만 생존했다면 등가 뮤턴트(방어선이 되메운 것)로 볼 수 있었지만,
둘 다 생존했다는 것은 **이 판정에 행위 테스트가 아예 없었다**는 뜻이다. 그리고 이 판정은
「누구에게 작업을 주는가」 — 이 feature 의 중심이다. 자격 없는 러너에 콘솔 작업을 주면
대화용 프레이밍으로 감싸 JSON 산출물이 조용히 망가진다(P0-Z 계열의 원래 실패 모드).

## 이 파일이 잠그는 것

1. `_classify` 가 각 상태에 **맞는 사유**를 낸다 — 사유가 곧 운영자의 조치다.
2. `_classify` 의 `ready` 와 배급 정본 `runner_can_take` 가 **절대 갈리지 않는다**.
   갈리면 화면은 "맡길 수 있다" 고 하는데 워커는 안 맡긴다(또는 그 반대).

⚠ 이 파일은 feature-0003 에 둔다 — `routers._console_llm` 은 feature-0003 의 `src` 가
path 에 있어야 import 되고, feature-0043 의 conftest 는 그것을 의도적으로 올리지 않는다
(두 feature 의 `modules` 패키지가 서로를 가린다).
"""
from __future__ import annotations

import itertools

import pytest

from routers import _console_llm as cl
from shared.bridge_tasks import (
    RUNNER_FEATURE_BATCH_JOBS,
    RUNNER_FEATURE_CONSOLE_JOBS,
    RUNNER_MIN_AGENT_VERSION,
    runner_can_take,
)

_OK_VER = RUNNER_MIN_AGENT_VERSION
_OLD_VER = "2026.01.01"


def _profile(*, listening=True, features=(RUNNER_FEATURE_CONSOLE_JOBS,), version=_OK_VER):
    return {"listening": listening, "features": list(features), "agent_version": version}


@pytest.mark.parametrize("profile,has_token,expected", [
    # 연결이 없는 사람에게 "러너를 갱신하세요" 라고 말하면 그는 갱신할 러너가 없다 —
    # 가장 바깥 원인부터 판정한다는 계약이 곧 사유의 순서다.
    (_profile(), False, cl.DELEGATION_NO_CONNECTION),
    (_profile(listening=False), True, cl.DELEGATION_RUNNER_IDLE),
    (_profile(features=()), True, cl.DELEGATION_UNSUPPORTED),
    (_profile(version=_OLD_VER), True, cl.DELEGATION_OUTDATED),
    (_profile(), True, cl.DELEGATION_READY),
])
def test_classify_names_the_actual_cause(profile, has_token, expected):
    """상태마다 **다른 사유**를 낸다 — 사유가 곧 조치(연결 안내 / 기동 / 갱신)다."""
    assert cl._classify(profile, has_token) == expected


def test_batch_needs_its_own_consent():
    """배경 배치는 콘솔 작업 능력만으로 자격이 생기지 않는다.

    합치면 「할 줄 안다」가 「해도 된다」로 승격된다 — 그 작업은 그 사람이 요청한 적 없고
    그 사람 계정의 사용량을 태운다.
    """
    only_console = _profile()
    assert cl._classify(only_console, True) == cl.DELEGATION_READY
    assert cl._classify(only_console, True, need_batch=True) == cl.DELEGATION_UNSUPPORTED
    with_batch = _profile(features=(RUNNER_FEATURE_CONSOLE_JOBS, RUNNER_FEATURE_BATCH_JOBS))
    assert cl._classify(with_batch, True, need_batch=True) == cl.DELEGATION_READY


def test_classify_ready_never_disagrees_with_the_dispatch_predicate():
    """화면 판정(`_classify`)과 배급 정본(`runner_can_take`)이 **한 조합도 갈리지 않는다**.

    두 곳에 같은 순서를 손으로 적어 둔 구조라, 한쪽만 고쳐지는 날 갈린다. 그 갈림은
    「화면은 맡길 수 있다는데 워커는 안 맡긴다」(또는 그 반대)로 나타나고, 어느 쪽이든
    사용자는 이유를 알 수 없다. 전 조합을 돌려 대조한다.
    """
    feature_sets = [
        (),
        (RUNNER_FEATURE_CONSOLE_JOBS,),
        (RUNNER_FEATURE_BATCH_JOBS,),
        (RUNNER_FEATURE_CONSOLE_JOBS, RUNNER_FEATURE_BATCH_JOBS),
        ("something_else",),
    ]
    combos = itertools.product([True, False], feature_sets, [_OK_VER, _OLD_VER, "", "vNext"],
                               [True, False])
    checked = 0
    for listening, feats, version, need_batch in combos:
        profile = _profile(listening=listening, features=feats, version=version)
        # `has_token=True` 로 고정한다 — 토큰 부재는 러너 자격 이전의 축이라
        # `runner_can_take` 가 아예 보지 않는다(그쪽은 프로필만 받는다).
        screen_ready = cl._classify(profile, True, need_batch=need_batch) == cl.DELEGATION_READY
        dispatch_ready = runner_can_take(profile, need_batch=need_batch)
        assert screen_ready == dispatch_ready, (
            f"판정이 갈렸다 — 화면={screen_ready} 배급={dispatch_ready} "
            f"(listening={listening} features={feats} version={version!r} batch={need_batch})")
        checked += 1
    assert checked == 2 * len(feature_sets) * 4 * 2, "조합이 줄었다 — 검사가 좁아졌는지 확인"


def test_delegation_available_only_on_ready():
    """게이트가 열린 배포(`direct`)에서는 위임하지 않는다 — 종전 직접 경로가 돈다."""
    assert cl.delegation_available({"delegation": cl.DELEGATION_READY}) is True
    for state in (cl.DELEGATION_DIRECT, cl.DELEGATION_NO_CONNECTION, cl.DELEGATION_RUNNER_IDLE,
                  cl.DELEGATION_UNSUPPORTED, cl.DELEGATION_OUTDATED):
        assert cl.delegation_available({"delegation": state}) is False
    assert cl.delegation_available(None) is False

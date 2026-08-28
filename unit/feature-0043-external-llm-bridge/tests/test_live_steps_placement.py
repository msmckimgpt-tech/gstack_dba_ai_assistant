"""feature-0043 — 진행 중 실행 단계가 **말풍선 안에, 자기 run 으로** 그려지는가.

라이브 제보(2026-08-28, 스크린샷):

    [새 질문]
    Assistant  연결된 AI 가 이 질문을 가져갔습니다. 조사·작성 중입니다.
               ▶ 쿼리 결과
               [단계 보기 (21)]        ← ① 직전 답변의 단계 수(이 질문의 단계가 아니다)
    ─────────────────────────────────  ← 말풍선 경계
    내부 동작  질문을 가져왔습니다 …    ← ② 카드가 말풍선 **밖으로** 흘러나옴
    read_task_attachment …
    SQL 실행 …

두 증상은 서로 다른 뿌리에서 나온다.

① `_load_steps_for_message` 는 메시지 meta 에 `run_id` 가 없으면 "그 시각 이전의 가장 최근
   run" 으로 폴백한다. 대기 말풍선에는 각인이 없었으므로 **직전 답변의 run** 이 잡혔다.
② 진행 단계 앵커(`data-bridge-task`)가 말풍선이 아니라 **메시지 행**에 붙어 있었다. 행은
   아바타·메타·말풍선을 담는 바깥 컨테이너라, 거기 append 하면 말풍선 옆 별개 블록이 된다.

여기에 하나 더 — 진행 표시가 **두 축에서 동시에** 그려지고 있었다. `/api/progress` 의 run
폴백이 브리지 run 까지 잡아 내부 경로용 progress-strip 을 깨웠기 때문이다(브리지에는 전용
표시가 이미 있다).
"""
from __future__ import annotations

import ast
import pathlib

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
CONV_STORE = WEB_SRC / "routers" / "_conv_store.py"
CONVS = WEB_SRC / "routers" / "conversations.py"
APP_JS = WEB_SRC / "static" / "app.js"


def _func_source(path: pathlib.Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다")


# ── ① 대기 말풍선은 자기 run 을 가리킨다 ─────────────────────────────────────


def test_placeholder_bubble_imprints_its_own_run_id():
    """각인이 없으면 '이 시각 이전의 최근 run' 폴백이 **직전 답변의 단계**를 붙인다."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    anchor = src.index('"placeholder": True')
    tail = src[anchor:anchor + 800]
    assert '"run_id": task_id' in tail, (
        "대기 말풍선 meta 에 run_id 각인이 없다 — 남의 단계 수가 표시된다")


def test_step_lookup_prefers_the_imprinted_run():
    """각인이 있으면 폴백을 타지 않는다(계약 유지 확인)."""
    src = _func_source(CONV_STORE, "_load_steps_for_message")
    assert 'meta.get("run_id")' in src and "_load_steps_for_run(" in src


# ── ② 앵커는 말풍선 안에 있다 ────────────────────────────────────────────────


def test_live_steps_anchor_is_on_the_bubble_not_the_row():
    """행에 붙이면 카드가 말풍선 밖으로 나온다 — 완료본은 말풍선 안 details 에 들어간다."""
    src = APP_JS.read_text(encoding="utf-8")
    assert "bubble.dataset.bridgeTask" in src, "앵커가 말풍선에 붙지 않는다"
    assert "row.dataset.bridgeTask" not in src, (
        "앵커가 여전히 메시지 행에 붙는다 — 단계가 말풍선 밖으로 흘러나온다")


def test_anchor_is_only_for_placeholder_bubbles():
    """답변으로 덮인 말풍선에까지 앵커가 남으면, 완료본에 진행 카드가 덧그려진다."""
    src = APP_JS.read_text(encoding="utf-8")
    idx = src.index("_bridgeAnchorTask")
    seg = src[idx - 400:idx + 400]
    assert "placeholder" in seg, "placeholder 조건 없이 앵커를 붙인다"


# ── ③ 브리지 run 은 내부 진행 표시를 깨우지 않는다 ──────────────────────────


def test_progress_fallback_excludes_bridge_runs():
    """브리지에는 전용 진행 표시가 있다 — 두 축이 같은 run 을 그리면 자리가 갈린다."""
    src = _func_source(CONV_STORE, "_load_latest_run_id_from_steps")
    assert "_BRIDGE_RUN_ID_LIKE" in src, (
        "브리지 run 이 내부 progress fallback 에 그대로 잡힌다 — "
        "말풍선 밖 progress-strip 이 켜진다")
    assert "run_id NOT LIKE" in src, "제외 조건이 SQL 에 없다"


def test_bridge_run_prefix_matches_the_task_id_generator():
    """접두가 갈리면 제외가 조용히 무효가 된다(생성부와 같은 규칙이어야 한다)."""
    store = CONV_STORE.read_text(encoding="utf-8")
    assert r'_BRIDGE_RUN_ID_LIKE = r"t\_%"' in store
    enqueue = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert 'task_id = "t_" + secrets.token_urlsafe(12)' in enqueue, (
        "task_id 생성 규칙이 바뀌었다 — 제외 패턴도 함께 고쳐야 한다")


def test_ledger_exclusion_is_kept():
    """사후 이관 제외(2026-08-27 회귀 방지)는 그대로 남아야 한다."""
    src = _func_source(CONV_STORE, "_load_latest_run_id_from_steps")
    assert "_BRIDGE_LEDGER_WORK_SOURCE" in src

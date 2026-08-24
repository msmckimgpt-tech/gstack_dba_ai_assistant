#!/usr/bin/env python3
"""PB-0008 계측 — 인라인 이름 변경이 배경 재렌더에 오확정되지 않는지(sidebar-rename-focus).

실 Windows Chrome(CDP relay, `bin/win-browser.py` 브리지)에 붙어 다음을 실측한다:

  A. 폴더 인라인 편집 중 **배경 재렌더**(`renderConversationList()` — AI 응답 진행 중 상태
     갱신처럼 억제할 수 없는 경로의 대표)가 끼어도 ① `PATCH /api/folders/{id}` 가 발사되지
     않고 ② 입력값·커서·포커스가 유지되는가.
  B. 편집 중 **주기 unread 동기화**(7s)가 `/api/conversations` 를 호출하지 않는가(억제).
  C. 대화 항목 우클릭 메뉴에 `이름 변경` 이 있고, 선택 시 **모달 없이** 그 행이 인라인
     텍스트박스로 바뀌며 Enter 로 확정되는가.

네트워크는 `page.on("request")` 로 관측한다 — "확정되지 않았다" 를 화면이 아니라 **요청 유무**로
판정해야 거짓 통과가 없다.

전제:
  1. `python3 bin/win-browser.py doctor` 가 ok.
  2. 검증 대상 URL 에 로그인된 탭이 열려 있을 것.
     미머지 브랜치는 라이브 web 이미지 + 본 worktree 의 `src/static` bind-mount 컨테이너로 띄운다.

실행:
  python3 pb0008_sidebar_rename_focus.py --url-part 18099 --shot-dir <dir>

주의: **창을 전면화(bring_to_front)** 한다 — 비활성 탭은 rAF/타이머가 throttle 돼 편집·렌더
타이밍이 실제와 달라진다.
"""
from __future__ import annotations

import argparse
import json
import time

from playwright.sync_api import sync_playwright

DEFAULT_ENDPOINT = "http://172.26.144.1:9223"


# 편집 중인 입력의 상태 — 값·커서·포커스·연결 여부를 한 번에 읽는다.
READ_EDIT = """
() => {
  const inp = document.querySelector('#conversationList .conv-inline-rename-input');
  if (!inp) return { present: 0 };
  return {
    present: 1,
    value: inp.value,
    selStart: inp.selectionStart,
    selEnd: inp.selectionEnd,
    focused: document.activeElement === inp,
    key: inp.dataset.renameKey || '',
    connected: inp.isConnected ? 1 : 0,
  };
}
"""


def attach(endpoint: str, url_part: str):
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(endpoint)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if url_part in pg.url:
                pg.bring_to_front()
                return pw, browser, pg
    raise SystemExit(f"대상 탭을 찾지 못했습니다 (url_part={url_part})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--url-part", default="18099")
    ap.add_argument("--shot-dir", default="/tmp/pb0008-rename")
    ap.add_argument("--idle-sec", type=float, default=9.0, help="편집 중 배경 동기화 관측 시간")
    ap.add_argument("--phase", default="AB,C", help="수행할 단계 (AB / C / AB,C)")
    args = ap.parse_args()
    phases = {p.strip() for p in args.phase.split(",")}

    pw, browser, pg = attach(args.endpoint, args.url_part)
    out: dict = {"url": pg.url}
    reqs: list[dict] = []
    pg.on("request", lambda r: reqs.append({"m": r.method, "u": r.url, "t": time.time()}))

    def since(mark: float, *, method=None, needle=None):
        return [r for r in reqs
                if r["t"] >= mark
                and (method is None or r["m"] == method)
                and (needle is None or needle in r["u"])]

    try:
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        if "AB" in phases:
            _run_ab(pg, args, out, since)
        if "C" in phases:
            _run_c(pg, args, out, since)
    finally:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        browser.close()
        pw.stop()
    return 0


def _run_ab(pg, args, out, since):
    """A: 편집 중 배경 재렌더가 확정을 만들지 않는가 · B: 배경 동기화 억제와 정상 확정."""
    if True:
        pg.click("#newFolderBtn")           # 생성 직후 인라인 편집 자동 진입
        pg.wait_for_timeout(900)
        st0 = pg.evaluate(READ_EDIT)
        out["A_entered_edit"] = st0

        # 사용자가 이름을 "입력하는 중"(아직 확정 전). 한글은 type() 이 뭉개므로 fill 로 넣는다.
        pg.fill("#conversationList .conv-inline-rename-input", "검증중인 폴더이름")
        pg.evaluate("() => { const i = document.querySelector('#conversationList .conv-inline-rename-input');"
                    " i.focus(); i.setSelectionRange(4, 4); }")
        st1 = pg.evaluate(READ_EDIT)
        out["A_typed"] = st1
        pg.screenshot(path=f"{args.shot_dir}/A1-editing.png")

        mark = time.time()
        # 억제할 수 없는 경로의 대표 — 목록 전량 재구성을 직접 유발한다.
        pg.evaluate("async () => { const m = await import('/static/app/sidebar.js?v=dev');"
                    " m.renderConversationList(); m.renderConversationList(); }")
        pg.wait_for_timeout(500)
        st2 = pg.evaluate(READ_EDIT)
        out["A_after_rerender"] = st2
        out["A_patch_requests"] = since(mark, method="PATCH")
        pg.screenshot(path=f"{args.shot_dir}/A2-after-rerender.png")

        # ── B. 편집 중 배경 동기화 억제 (주기 unread 동기화 7s) ─────────────────
        mark_idle = time.time()
        pg.wait_for_timeout(int(args.idle_sec * 1000))
        out["B_idle_sec"] = args.idle_sec
        out["B_conversations_polls_while_editing"] = since(mark_idle, needle="/api/conversations")
        st3 = pg.evaluate(READ_EDIT)
        out["B_edit_survived_idle"] = st3

        # 확정(Enter) — 정상 경로가 막히지 않았는지(차단 로직의 정상 경로 실측)
        mark_commit = time.time()
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(1500)
        out["B_commit_patch"] = since(mark_commit, method="PATCH", needle="/api/folders")
        out["B_folder_names"] = pg.evaluate(
            "() => Array.from(document.querySelectorAll('#conversationList .conv-folder-name')).map(e => e.textContent.trim())")
        pg.screenshot(path=f"{args.shot_dir}/B1-committed.png")

        # 편집이 끝난 뒤 배경 동기화가 재개되는지
        mark_after = time.time()
        pg.wait_for_timeout(9000)
        out["B_polls_after_edit_done"] = len(since(mark_after, needle="/api/conversations"))

        # 정리 — 검증이 만든 폴더만 삭제
        out["B_cleanup"] = pg.evaluate("""async () => {
          const r = await fetch('/api/folders', { credentials: 'same-origin' });
          const j = await r.json();
          const targets = (j.folders || []).filter(f => String(f.name).includes('검증중인 폴더이름'));
          const res = [];
          for (const f of targets) {
            const d = await fetch(`/api/folders/${f.folder_id}`, { method: 'DELETE', credentials: 'same-origin' });
            res.push({ id: f.folder_id, name: f.name, status: d.status });
          }
          return res;
        }""")


def _run_c(pg, args, out, since):
    """C: 대화 우클릭 메뉴의 '이름 변경' → 모달 없이 인라인 편집 → 확정 → 원복."""
    if True:
        # ── C. 대화 우클릭 → '이름 변경' → 인라인 편집 → 확정 → 원복 ────────────
        pg.reload(wait_until="domcontentloaded")
        # 목록은 /api/conversations 응답 후에 그려진다 — 고정 대기 대신 행이 나타날 때까지 기다린다.
        pg.wait_for_selector("#conversationList .conv-item.is-own", timeout=20000)
        pg.wait_for_timeout(600)
        # 첫 진입 시 오래된 날짜 그룹은 접혀 있어 대화 행이 DOM 에 없다 — 헤더를 펼친다.
        pg.evaluate("""() => {
          const heads = Array.from(document.querySelectorAll('#conversationList .conv-date-group-header.is-collapsed, #conversationList .conv-group-collapsible.is-collapsed'));
          heads.slice(0, 3).forEach((h) => h.click());
        }""")
        pg.wait_for_timeout(700)
        target = pg.evaluate("""() => {
          const el = document.querySelector('#conversationList .conv-item.is-own:not(.is-pending)');
          if (!el) return null;
          return { cid: el.dataset.conversationId,
                   title: (el.querySelector('.conv-item-title') || {}).textContent || '' };
        }""")
        out["C_target"] = target
        if target:
            box = pg.evaluate("""(cid) => {
              const el = document.querySelector(`#conversationList .conv-item[data-conversation-id="${cid}"]`);
              const r = el.getBoundingClientRect();
              return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
            }""", target["cid"])
            pg.mouse.move(box["x"], box["y"])
            pg.mouse.click(box["x"], box["y"], button="right")
            pg.wait_for_timeout(700)
            out["C_menu_items"] = pg.evaluate(
                "() => Array.from(document.querySelectorAll('#convItemMenu .conv-item-menu-item, #convItemMenu > *'))"
                ".map(e => (e.textContent || '').trim()).filter(Boolean)")
            pg.screenshot(path=f"{args.shot_dir}/C1-context-menu.png")

            pg.evaluate("""() => {
              const it = Array.from(document.querySelectorAll('#convItemMenu *'))
                .find(e => (e.textContent || '').trim() === '이름 변경' && e.children.length === 0);
              if (it) it.click();
            }""")
            pg.wait_for_timeout(800)
            out["C_inline_after_menu"] = pg.evaluate(READ_EDIT)
            out["C_modal_open"] = pg.evaluate(
                "() => document.querySelectorAll('.share-mgr-backdrop').length")
            pg.screenshot(path=f"{args.shot_dir}/C2-inline-edit.png")

            new_title = f"{target['title'].strip()[:20]} (rename 검증)"
            pg.fill("#conversationList .conv-inline-rename-input", new_title)
            mark_c = time.time()
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(2000)
            out["C_commit_patch"] = since(mark_c, method="PATCH", needle="/title")
            out["C_title_after"] = pg.evaluate("""(cid) => {
              const el = document.querySelector(`#conversationList .conv-item[data-conversation-id="${cid}"] .conv-item-title`);
              return el ? el.textContent.trim() : null;
            }""", target["cid"])
            pg.screenshot(path=f"{args.shot_dir}/C3-renamed.png")

            # 원복 — 검증이 바꾼 운영 데이터를 되돌린다.
            out["C_restore"] = pg.evaluate("""async ([cid, title]) => {
              const r = await fetch(`/api/conversations/${encodeURIComponent(cid)}/title`, {
                method: 'PATCH', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title }),
              });
              return { status: r.status };
            }""", [target["cid"], target["title"].strip()])

if __name__ == "__main__":
    raise SystemExit(main())

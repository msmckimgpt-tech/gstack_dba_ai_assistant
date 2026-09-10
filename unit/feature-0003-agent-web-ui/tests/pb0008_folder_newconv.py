#!/usr/bin/env python3
"""PB-0008 계측 — 폴더 행 '📝'(이 폴더에서 새 대화) + 관리 메뉴 우클릭 이관(folder-newconv).

실 Windows Chrome(CDP relay, `bin/win-browser.py` 브리지)에 붙어 다음을 실측한다:

  F1. 폴더 행의 가시 트리거가 `.conv-folder-newconv-trigger`('📝')이고 구
      `.conv-folder-menu-trigger`('···')는 **없다**.
  F2. 그 트리거를 **클릭**하면 옵션 메뉴가 뜨지 않고, '새 대화 (작성 중)' 행이 **그 폴더
      안**(폴더 헤더 다음, 다음 폴더 헤더 전)에 나타난다. 폴더가 접히지도 않는다.
  F3. 폴더 헤더 **우클릭**은 관리 메뉴를 열고 항목(이름 변경·하위 폴더 추가·설정)이 그대로다.
      우클릭이 새 대화를 만들지 않는다.
  F4. 첫 메시지를 보내면 생성된 대화가 **그 폴더에 배정**된다 — 서버 `/api/conversations`
      payload 의 `folder_id` 로 판정한다(화면만 보고 판정하지 않는다).
  F5. 폴더 행의 시각 캡처(§16.6 픽셀-클래스 — 이모지 교체는 행 정렬·폭에 영향).

판정은 화면 텍스트가 아니라 **DOM 순서·요소 존재·서버 payload** 로 한다.

전제:
  1. `python3 bin/win-browser.py doctor` 가 ok (없으면 `launch` → `session-login`).
  2. `--url` 은 로그인 세션이 있는 오리진. 기본은 라이브 `https://localhost`.

실행:
  python3 pb0008_folder_newconv.py --url https://localhost --shot-dir <dir>
  python3 pb0008_folder_newconv.py --negative   # 역검증: 구 '···' 계약으로 재면 F1/F2 가 FAIL

정리: 본 스크립트가 만든 폴더와 대화만 삭제한다(--keep 으로 보존 가능).
"""
from __future__ import annotations

import argparse
import json
import time

from playwright.sync_api import sync_playwright

DEFAULT_ENDPOINT = "http://172.26.144.1:9223"
MARK = "pb0008-folder-newconv"

# 사이드바에서 «폴더 헤더 → 그 폴더의 자식들» 순서를 읽는다. 폴더 안/밖 판정은 DOM 순서로만
# 가능하므로(폴더 자식은 별도 컨테이너가 아니라 같은 flat 목록에 들여쓰기로 그려진다),
# 목록 전체를 순서대로 훑어 각 행의 종류를 기록한다.
READ_LIST = """
() => {
  const list = document.getElementById('conversationList');
  if (!list) return { ok: 0 };
  const rows = Array.from(list.children).map((el) => ({
    folderId: el.dataset ? (el.dataset.folderId || '') : '',
    convId: el.dataset ? (el.dataset.conversationId || '') : '',
    pendingSentinel: el.dataset ? (el.dataset.pendingSentinel || '') : '',
    cls: el.className || '',
    padLeft: el.style ? (el.style.paddingLeft || '') : '',
    text: (el.textContent || '').slice(0, 40),
    isFolderHeader: (el.className || '').includes('conv-folder-header'),
    isPendingDraft: (el.className || '').includes('is-pending') && !(el.className || '').includes('is-pending-inflight'),
    isPendingInflight: (el.className || '').includes('is-pending-inflight'),
    collapsed: (el.className || '').includes('is-collapsed'),
  }));
  return { ok: 1, rows };
}
"""

READ_FOLDER_ROW = """
(fid) => {
  const hdr = document.querySelector(`.conv-folder-header[data-folder-id="${fid}"]`);
  if (!hdr) return { present: 0 };
  const nc = hdr.querySelector('.conv-folder-newconv-trigger');
  const old = hdr.querySelector('.conv-folder-menu-trigger');
  const r = hdr.getBoundingClientRect();
  return {
    present: 1,
    hasNewConv: nc ? 1 : 0,
    newConvText: nc ? nc.textContent : '',
    newConvAria: nc ? (nc.getAttribute('aria-label') || '') : '',
    newConvRole: nc ? (nc.getAttribute('role') || '') : '',
    newConvTabIndex: nc ? (nc.getAttribute('tabindex') || '') : '',
    hasOldMenuTrigger: old ? 1 : 0,
    headerHeight: Math.round(r.height * 10) / 10,
    nameEllipsized: (() => {
      const n = hdr.querySelector('.conv-folder-name');
      return n && n.scrollWidth > n.clientWidth ? 1 : 0;
    })(),
  };
}
"""

READ_MENU = """
() => {
  const m = document.getElementById('folderMenu');
  if (!m) return { open: 0 };
  return {
    open: 1,
    folderId: m.dataset ? (m.dataset.folderId || '') : '',
    items: Array.from(m.children).map((c) => (c.textContent || '').trim()),
  };
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://localhost")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--shot-dir", default="/tmp")
    ap.add_argument("--negative", action="store_true",
                    help="역검증 — 구 '···' 계약으로 재서 하네스가 실제로 이 변경을 재는지 확인")
    ap.add_argument("--keep", action="store_true", help="테스트 폴더·대화를 지우지 않는다")
    args = ap.parse_args()

    results: list[tuple[str, bool, str]] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, bool(cond), detail))
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {detail}" if detail else ""))

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(args.endpoint)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.bring_to_front()  # 비활성 탭은 rAF/타이머가 throttle 돼 렌더 타이밍이 실제와 달라진다.
        # client-entry-gate(2026-09-10 배포): 일반 브라우저의 맨 `/` 방문은 `/install` 안내로 보내진다.
        # 이 검증은 «앱이 호스팅하는 공유 화면» 을 재는 것이므로, DQA 앱이 붙일 때와 같은 좌표 신호를
        # 실어 게이트를 통과한다(그 게이트 자체는 이 변경의 범위가 아니다).
        entry = args.url.rstrip("/") + "/?client_port=1&client_nonce=pb0008-folder-newconv"
        page.goto(entry, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        if "/install" in page.url:
            print(f"  FAIL  [게이트] 진입 신호에도 설치 안내로 이동함: {page.url}")
            return 2

        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 진입 신호를 실으면 앱이 로컬 브리지 «연결» 모달을 띄운다(이 검증의 대상이 아니며,
        # 오버레이가 사이드바 클릭을 가로챈다). 사이드바를 만지기 전에 닫아 둔다.
        def dismiss_overlays() -> None:
            for _ in range(3):
                shown = page.evaluate(
                    "() => Boolean(document.getElementById('connectModalOverlay'))")
                if not shown:
                    return
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            # Escape 로 안 닫히면 오버레이만 제거한다(제품 상태를 바꾸지 않는 DOM 수준 회피).
            page.evaluate(
                "() => { const n = document.getElementById('connectModalOverlay'); if (n) n.remove(); }")
        dismiss_overlays()

        # ── 준비: 테스트 폴더 2개 생성(형제 폴더가 있어야 «다른 폴더로 새지 않는다» 를 잰다)
        mk = """
        async (name) => {
          const r = await fetch('/api/folders', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          });
          const j = await r.json();
          return j && j.folder && j.folder.folder_id ? Number(j.folder.folder_id) : 0;
        }
        """
        fid_a = page.evaluate(mk, f"{MARK}-A")
        fid_b = page.evaluate(mk, f"{MARK}-B")
        ok("[준비] 테스트 폴더 2개 생성", fid_a > 0 and fid_b > 0, f"A={fid_a} B={fid_b}")
        if not (fid_a and fid_b):
            return 2
        page.goto(entry, wait_until="domcontentloaded")  # reload 대신 같은 진입 신호로 재적재(게이트 통과 유지)
        page.wait_for_timeout(2500)
        dismiss_overlays()

        # ── F1: 폴더 행의 트리거
        row = page.evaluate(READ_FOLDER_ROW, fid_a)
        ok("[F1] 폴더 행 렌더", row.get("present") == 1)
        want_new = 0 if args.negative else 1
        ok("[F1] ★ '새 대화' 트리거 존재", row.get("hasNewConv") == want_new, json.dumps(row, ensure_ascii=False))
        ok("[F1] ★ 표시 = 📝", (row.get("newConvText") == "📝") != args.negative)
        ok("[F1] ★ 구 '···' 메뉴 트리거 부재", (row.get("hasOldMenuTrigger") == 0) != args.negative)
        ok("[F1] 접근성 속성(role=button · tabindex=0 · aria-label)",
           row.get("newConvRole") == "button" and row.get("newConvTabIndex") == "0"
           and "새 대화" in (row.get("newConvAria") or ""))

        # ── F2: 클릭 → 그 폴더 안에 '작성 중'
        page.click(f'.conv-folder-header[data-folder-id="{fid_a}"] .conv-folder-newconv-trigger')
        page.wait_for_timeout(700)
        menu = page.evaluate(READ_MENU)
        ok("[F2] ★ 클릭이 옵션 메뉴를 열지 않는다", menu.get("open") == 0)
        lst = page.evaluate(READ_LIST)
        rows = lst.get("rows") or []
        idx_a = next((i for i, r in enumerate(rows) if r["folderId"] == str(fid_a)), -1)
        idx_b = next((i for i, r in enumerate(rows) if r["folderId"] == str(fid_b)), -1)
        idx_draft = next((i for i, r in enumerate(rows) if r["isPendingDraft"]), -1)
        ok("[F2] '새 대화 (작성 중)' 행 존재", idx_draft >= 0)
        # 폴더 A 안 = A 헤더 뒤이면서, A 다음에 오는 다른 폴더 헤더보다 앞.
        next_hdr = next((i for i, r in enumerate(rows) if r["isFolderHeader"] and i > idx_a), len(rows))
        ok("[F2] ★ '작성 중' 이 폴더 A 안에 위치", idx_a >= 0 and idx_a < idx_draft < next_hdr,
           f"A={idx_a} draft={idx_draft} nextHdr={next_hdr} B={idx_b}")
        ok("[F2] ★ 폴더 안임이 들여쓰기로 보인다", idx_draft >= 0 and rows[idx_draft]["padLeft"] != "",
           rows[idx_draft]["padLeft"] if idx_draft >= 0 else "")
        ok("[F2] ★ 클릭으로 폴더가 접히지 않는다", idx_a >= 0 and not rows[idx_a]["collapsed"])

        # ── F3: 헤더 우클릭 → 관리 메뉴
        page.click(f'.conv-folder-header[data-folder-id="{fid_a}"] .conv-folder-name', button="right")
        page.wait_for_timeout(600)
        menu = page.evaluate(READ_MENU)
        ok("[F3] ★ 우클릭 → 폴더 관리 메뉴 열림", menu.get("open") == 1, json.dumps(menu, ensure_ascii=False))
        items = menu.get("items") or []
        ok("[F3] ★ 항목 보존(이름 변경 · 하위 폴더 추가 · 설정)",
           "이름 변경" in items and "하위 폴더 추가" in items and "설정" in items)
        ok("[F3] 메뉴가 그 폴더에 귀속", str(menu.get("folderId")) == str(fid_a))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ── F5: 시각 캡처 (폴더 행 — 이모지 교체는 픽셀-클래스 변경)
        shot = f"{args.shot_dir}/folder-newconv-row.png"
        try:
            page.hover(f'.conv-folder-header[data-folder-id="{fid_a}"]')
            page.wait_for_timeout(400)
            page.locator("#conversationList").screenshot(path=shot)
            ok("[F5] 사이드바 캡처", True, shot)
        except Exception as exc:  # noqa: BLE001
            ok("[F5] 사이드바 캡처", False, str(exc))

        # ── F4: 폴더 배정 왕복 (라이브 서버 계약)
        #   원래는 "첫 메시지를 보내면 그 대화가 폴더에 들어간다" 를 통째로 재려 했으나, 서버 LLM
        #   폐기 이후 질의는 **DQA 앱의 로컬 브리지**로만 가므로 일반 브라우저에서는 `#promptInput`
        #   이 비활성이다(실측: `element is not enabled`). 그래서 여기서는 프론트가 cid 확정 직후
        #   호출하는 **바로 그 배정 왕복**을 라이브 서버에 대고 재고, 사이드바가 그 결과를 폴더 하위로
        #   그리는지까지 확인한다. 「전송 → 자동 배정」 배선 자체는 jsdom(case7 + 배선 잠금)이 덮으며
        #   라이브 미검증임을 Run 기록에 분리 표기한다.
        assign = page.evaluate(
            """
            async (fid) => {
              const r1 = await fetch('/api/new_conversation', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'auto' }),
              });
              const j1 = await r1.json();
              const cid = String(j1 && j1.conversation_id || '');
              if (!cid) return { cid: '', step: 'new_conversation', status: r1.status };
              const r2 = await fetch(`/api/conversations/${encodeURIComponent(cid)}/folder`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_id: fid }),
              });
              const j2 = await r2.json();
              const r3 = await fetch('/api/conversations');
              const j3 = await r3.json();
              const row = (j3.items || j3.conversations || []).find((c) => String(c.id) === cid) || null;
              return { cid, patchStatus: r2.status, patched: j2 && j2.folder_id,
                       listedFolderId: row ? row.folder_id : null };
            }
            """, fid_a)
        new_cid = str(assign.get("cid") or "")
        ok("[F4] 새 대화 cid 발급", bool(new_cid), json.dumps(assign, ensure_ascii=False))
        ok("[F4] ★ 폴더 배정 PATCH 200", assign.get("patchStatus") == 200)
        ok("[F4] ★ 서버 목록의 folder_id 가 그 폴더", str(assign.get("listedFolderId")) == str(fid_a))

        # ── F4b: 재적재 후 사이드바가 그 대화를 폴더 하위에 그린다
        page.goto(entry, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        dismiss_overlays()
        lst2 = page.evaluate(READ_LIST)
        rows2 = lst2.get("rows") or []
        i_a = next((i for i, r in enumerate(rows2) if r["folderId"] == str(fid_a)), -1)
        i_conv = next((i for i, r in enumerate(rows2) if r["convId"] == new_cid), -1)
        nxt = next((i for i, r in enumerate(rows2) if r["isFolderHeader"] and i > i_a), len(rows2))
        ok("[F4b] 그 대화가 사이드바에 렌더", i_conv >= 0)
        ok("[F4b] ★ 폴더 A 하위에 위치", i_a >= 0 and i_a < i_conv < nxt, f"A={i_a} conv={i_conv} next={nxt}")

        ok("[전역] pageerror 0", len(errors) == 0, "; ".join(errors[:3]))

        # ── 정리: 본 스크립트가 만든 것만
        if not args.keep:
            cleanup = """
            async ([mark, cid]) => {
              const out = [];
              // 이름(MARK) 기준으로 **전수** 삭제한다 — 앞선 실행이 중간에 끊겨 남긴 잔여까지
              // 같이 청소해야 라이브에 테스트 폴더가 쌓이지 않는다.
              let ids = [];
              try {
                const r = await fetch('/api/folders');
                const j = await r.json();
                ids = (j.folders || []).filter((f) => String(f.name || '').indexOf(mark) >= 0)
                                       .map((f) => f.folder_id);
              } catch (e) { out.push('list err ' + e); }
              if (cid) {
                try {
                  // 대화 삭제는 REST DELETE 가 아니라 POST /api/delete_conversation 이다.
                  const r = await fetch('/api/delete_conversation', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ conversation_id: cid, force: true }),
                  });
                  out.push(`conv ${cid}: ${r.status}`);
                } catch (e) { out.push('conv err ' + e); }
              }
              for (const id of ids) {
                try {
                  const r = await fetch(`/api/folders/${id}`, { method: 'DELETE' });
                  out.push(`folder ${id}: ${r.status}`);
                } catch (e) { out.push('folder err ' + e); }
              }
              return out;
            }
            """
            print("  [정리]", page.evaluate(cleanup, [MARK, new_cid]))

    passed = sum(1 for _, c, _ in results if c)
    failed = len(results) - passed
    print(f"\n결과: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

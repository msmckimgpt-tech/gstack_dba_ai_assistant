#!/usr/bin/env python3
"""PB-0008 계측 — 사이드바 명칭 변경 후 재배치 전환(sidebar-reorder-anim).

실 Windows Chrome(CDP relay, `bin/win-browser.py` 가 띄운 브리지)에 붙어, 명칭을 바꿨을 때
목록 항목이 **이전 자리에서 새 자리로 연속 이동**하는지를 프레임 단위로 기록한다.
스크린샷만으로는 "순간이동인지 트윈인지" 를 가릴 수 없어(정지 이미지) 궤적 계측을 정본으로 둔다.

  · `--mode folder` — 폴더 이름 변경(정렬 = sort_order → name). 부작용 없음(생성/삭제로 정리).
  · `--mode conv`   — 대화 제목 변경(서버가 updated_at 갱신 → 정렬 = last_activity_at desc).
                      오래된 날짜 그룹의 대화가 '오늘' 로 점프하는 실사용 시나리오. 제목은 원복한다.

전제:
  1. `python3 bin/win-browser.py doctor` 가 ok (relay 브리지 동작).
  2. 검증 대상 URL 에 로그인된 탭이 열려 있을 것 — `bin/win-browser.py launch --url <URL>`.
     미머지 브랜치를 라이브 무접촉으로 볼 때는 라이브 web 이미지 + 변경 static 트리를
     bind-mount 한 별도 컨테이너를 쓴다(REVIEW.md 의 cycle 기록 참조).

실행:
  python3 pb0008_sidebar_reorder_measure.py --mode folder
  python3 pb0008_sidebar_reorder_measure.py --mode conv --group month:2026-06

주의: **창을 전면화(bring_to_front)** 해야 한다. 비활성 탭에서는 Chrome 이 rAF/타이머를
throttle 해 애니메이션이 아예 진행되지 않고, 계측이 "전환 없음" 으로 거짓 판정된다.
"""
from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

DEFAULT_ENDPOINT = "http://172.26.144.1:9223"

# 프레임 샘플러 — 인라인 style.transform 은 invert 프레임에만 존재하므로(play 단계에서 제거)
# 진행값은 computed matrix 의 translateY 로 읽는다.
SAMPLER_TMPL = """
(sel) => {
  window.__pbSamples = [];
  const t0 = performance.now();
  const list = document.getElementById('conversationList');
  const readY = (m) => {
    if (!m || m === 'none') return 0;
    const p = m.match(/matrix\\(([^)]+)\\)/);
    return p ? Math.round(parseFloat(p[1].split(',')[5])) : 0;
  };
  const step = () => {
    const e = list.querySelector(sel);
    const rec = { t: Math.round(performance.now() - t0), present: e ? 1 : 0 };
    if (e) {
      rec.y = Math.round(e.getBoundingClientRect().top);   // 화면 위치(transform 반영)
      rec.vy = readY(getComputedStyle(e).transform);       // 트윈 잔여 offset
      rec.fl = e.classList.contains('is-reorder-flash') ? 1 : 0;
      rec.st = list.scrollTop;
      let n = e.previousElementSibling, grp = '(none)';
      while (n) {
        if (n.classList && n.classList.contains('conv-date-group-header')) {
          grp = (n.textContent || '').trim().slice(0, 12);
          break;
        }
        n = n.previousElementSibling;
      }
      rec.grp = grp;
    }
    window.__pbSamples.push(rec);
    if (performance.now() - t0 < 2200) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  return 'armed';
}
"""


def attach(endpoint: str, url_part: str):
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(endpoint)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if url_part in pg.url:
                pg.bring_to_front()
                pg.wait_for_timeout(500)
                return pw, browser, pg
    raise SystemExit(json.dumps({"ok": False, "error": "page_not_found", "url_part": url_part}))


def summarize(samples: list[dict]) -> dict:
    present = [s for s in samples if s.get("present")]
    moving = [s for s in present if s.get("vy")]
    flashing = [s for s in present if s.get("fl")]
    return {
        "frames_present": len(present),
        "frames_moving": len(moving),
        "tween_window_ms": [moving[0]["t"], moving[-1]["t"]] if moving else None,
        "flash_window_ms": [flashing[0]["t"], flashing[-1]["t"]] if flashing else None,
        "track": [
            {"t": s["t"], "screen_y": s["y"], "offset": s["vy"], "group": s.get("grp"), "scrollTop": s["st"]}
            for s in moving
        ],
        # 판정: 이동이 2프레임 이상 연속이면 트윈(순간이동은 0 프레임).
        "verdict": "tween" if len(moving) >= 2 else "instant-or-none",
    }


def _make_folder(page, name: str) -> str | None:
    page.click("#newFolderBtn")
    page.wait_for_selector(".conv-folder-rename-input", timeout=5000)
    page.fill(".conv-folder-rename-input", name)  # 한글: type 은 IME 로 뭉개짐 → fill
    page.press(".conv-folder-rename-input", "Enter")
    page.wait_for_timeout(1200)
    return page.evaluate(
        """(nm) => {
          const h = [...document.querySelectorAll('.conv-folder-header')]
            .find((e) => ((e.querySelector('.conv-folder-name') || {}).textContent || '') === nm);
          return h ? h.dataset.folderId : null;
        }""", name)


def run_folder(page, shot_prefix: str) -> dict:
    # 앵커 폴더가 있어야 이름 변경이 실제 자리 이동을 만든다(폴더가 하나뿐이면 정렬이 바뀌어도 제자리).
    anchor_id = _make_folder(page, "mm-pb0008-앵커")
    fid = _make_folder(page, "zz-pb0008-임시")
    if not fid or not anchor_id:
        return {"ok": False, "error": "temp_folder_not_found", "anchor": anchor_id, "target": fid}
    sel = f'.conv-folder-header[data-folder-id="{fid}"]'
    before = page.evaluate(
        """(sel) => { const e = document.querySelector(sel);
             return { y: Math.round(e.getBoundingClientRect().top),
                      name: (e.querySelector('.conv-folder-name') || {}).textContent }; }""", sel)
    page.screenshot(path=f"{shot_prefix}-folder-1-before.png")

    # 이름을 정렬 앞쪽으로 바꿔 실제 이동을 유발(같은 이름이면 재배치가 없어 예약도 없다).
    page.hover(sel)
    page.click(f"{sel} .conv-folder-menu-trigger")
    page.wait_for_selector("#folderMenu", timeout=5000)
    page.click("#folderMenu >> text=이름 변경")
    page.wait_for_selector(".conv-folder-rename-input", timeout=5000)
    page.fill(".conv-folder-rename-input", "aa-pb0008-임시")
    page.evaluate(SAMPLER_TMPL, sel)
    page.press(".conv-folder-rename-input", "Enter")

    # ⚠ 샘플링 창(2.2초) 안에서는 스크린샷을 찍지 않는다. Playwright 의 캡처가 렌더를 블로킹해
    #   rAF 를 멈추고, 그러면 트윈 프레임이 통째로 누락돼 계측기가 "전환 없음" 으로 **자기 계측을
    #   깨뜨린다**(실제로 겪음 — 브라우저는 정상 트윈 중이었는데 0 프레임으로 보고됐다).
    page.wait_for_timeout(2400)
    page.screenshot(path=f"{shot_prefix}-folder-2-after.png")

    out = {"ok": True, "mode": "folder", "folder_id": fid, "before": before,
           "after": page.evaluate(
               """(sel) => { const e = document.querySelector(sel);
                    return { y: Math.round(e.getBoundingClientRect().top),
                             name: (e.querySelector('.conv-folder-name') || {}).textContent,
                             residual_transform: e.style.transform || '' }; }""", sel)}
    out.update(summarize(page.evaluate("() => window.__pbSamples || []")))
    # 정리 — 검증용 임시 폴더 삭제(대화는 폴더 삭제와 무관하게 보존된다).
    out["cleanup_status"] = page.evaluate(
        """async (ids) => {
             const r = [];
             for (const id of ids) r.push(id + ':' + (await fetch('/api/folders/' + id, { method: 'DELETE' })).status);
             return r.join(' ');
           }""", [fid, anchor_id])
    page.reload()
    return out


def run_conv(page, group_key: str, shot_prefix: str) -> dict:
    page.click(f'.conv-date-group-header[data-date-key="{group_key}"]')  # 대상 그룹 펼침
    page.wait_for_timeout(600)
    target = page.evaluate(
        """(gk) => {
          const list = document.getElementById('conversationList');
          const hdr = list.querySelector('.conv-date-group-header[data-date-key="' + gk + '"]');
          let n = hdr ? hdr.nextElementSibling : null;
          while (n && !(n.classList && n.classList.contains('conv-item'))) n = n.nextElementSibling;
          return n ? { cid: n.dataset.conversationId,
                       title: (n.querySelector('.conv-item-title') || {}).textContent,
                       y: Math.round(n.getBoundingClientRect().top) } : null;
        }""", group_key)
    if not target:
        return {"ok": False, "error": "no_conversation_in_group", "group": group_key}

    cid, orig = target["cid"], target["title"]
    sel = f'.conv-item[data-conversation-id="{cid}"]'
    page.screenshot(path=f"{shot_prefix}-conv-1-before.png")

    def rename(title: str):
        page.hover(sel)
        page.click(f"{sel} .conv-item-menu-trigger")
        page.wait_for_selector("#convItemMenu", timeout=5000)
        page.click("#convItemMenu >> text=설정")
        page.wait_for_selector(".conv-settings-input", timeout=5000)
        page.fill(".conv-settings-input", title)

    rename(orig + " [PB0008]")
    page.evaluate(SAMPLER_TMPL, sel)
    page.click(".conv-settings-panel >> text=저장")

    # 위 folder 모드와 같은 이유로 샘플링 창 안에서는 캡처하지 않는다(캡처가 rAF 를 멈춘다).
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{shot_prefix}-conv-2-after.png")

    out = {"ok": True, "mode": "conv", "cid": cid, "before": target,
           "after": page.evaluate(
               """(sel) => { const e = document.querySelector(sel); if (!e) return null;
                    let n = e.previousElementSibling, grp = '(none)';
                    while (n) { if (n.classList && n.classList.contains('conv-date-group-header')) {
                      grp = (n.textContent || '').trim().slice(0, 12); break; } n = n.previousElementSibling; }
                    return { y: Math.round(e.getBoundingClientRect().top), group: grp,
                             title: (e.querySelector('.conv-item-title') || {}).textContent,
                             residual_transform: e.style.transform || '' }; }""", sel)}
    out.update(summarize(page.evaluate("() => window.__pbSamples || []")))
    try:  # 원복 — 라이브 대화의 제목은 검증 후 되돌린다(updated_at 갱신은 되돌릴 수 없음, REVIEW.md 기록).
        rename(orig)
        page.click(".conv-settings-panel >> text=저장")
        page.wait_for_timeout(1500)
        out["restored_title"] = page.evaluate(
            """(sel) => { const e = document.querySelector(sel);
                 return e ? (e.querySelector('.conv-item-title') || {}).textContent : null; }""", sel)
    except Exception as exc:  # noqa: BLE001
        out["restore_error"] = str(exc)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("folder", "conv"), default="folder")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--url-part", default="localhost:18099", help="대상 탭 URL 의 식별 부분")
    ap.add_argument("--group", default="month:2026-06", help="--mode conv 의 출발 날짜 그룹 키")
    ap.add_argument("--shot-prefix", default="/root/download/docker/mysql_ai_delegated_dev/artifacts/pb0008-reorder")
    args = ap.parse_args()

    pw, browser, page = attach(args.endpoint, args.url_part)
    try:
        out = run_folder(page, args.shot_prefix) if args.mode == "folder" \
            else run_conv(page, args.group, args.shot_prefix)
    finally:
        try:
            browser.close()
        finally:
            pw.stop()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") and out.get("verdict") == "tween" else 1


if __name__ == "__main__":
    sys.exit(main())

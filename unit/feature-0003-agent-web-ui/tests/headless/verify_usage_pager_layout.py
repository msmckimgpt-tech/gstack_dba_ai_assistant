#!/usr/bin/env python3
"""usage-pager-layout(2026-08-14) — 사용 기록/대화 목록 표의 **레이아웃 불변식** 실 렌더 검증.

jsdom 은 레이아웃을 계산하지 않아 다음 결함을 통과시킨다(codex 적대 리뷰 [P2] 로 적발):

  L1 정렬 열 머리 sticky 가 **실제 스크롤러**에 붙는가.
     `.usage-conv-tablewrap { overflow-x: auto }` 가 sticky 의 containing scroll box 가 되는데
     그 박스는 세로로 스크롤하지 않으므로(높이 자동) 머리가 붙을 곳이 없다 — 목록을 내리면
     머리가 함께 사라지고, 정렬 버튼을 다시 누르려면 맨 위로 돌아가야 한다.
  L2 좁은 폭에서 페이저가 컨테이너를 넘치지 않는가(작업 화면 다이얼로그 max-width 640px,
     모바일은 더 좁다). 한 줄 고정이면 컨트롤이 잘린다.
  L3 모달을 연 직후(스크롤 0)에 페이저가 보이는가 — 직전 cycle 의 PB-0008 라이브 실측에서
     실제로 발생했던 결함(50행 아래에 숨음)의 회귀 가드.

정본 CSS(`static/css/search-audit.css`)를 그대로 로드하고 **두 화면의 모달 마크업**을 재현한다 —
관리 콘솔(`.usage-conv-body`)과 작업 화면(`.usage-conv-content`)은 스크롤 컨테이너가 달라
한쪽만 보면 다른 쪽 회귀를 놓친다. 최종 시각 확인은 PB-0008 실 Windows 브라우저.

실행: python3 verify_usage_pager_layout.py     (playwright chromium 필요)
"""
from __future__ import annotations

import os
import sys

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover - 환경 부재
    print(f"playwright 미설치 — {exc}")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(HERE, "..", "..", "src", "static", "css", "search-audit.css")

_passed = 0
_failed = 0


def check(name: str, cond: bool, extra=None) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print("PASS", name)
    else:
        _failed += 1
        print("FAIL", name, "" if extra is None else str(extra)[:300])

ROWS = "".join(
    f"<tr><td class='usage-conv-topic'><a href='#'>대화 {i:03d}</a></td>"
    f"<td class='num'>{i}</td><td class='num'>{i * 13}</td><td class='num'>$0.10</td>"
    f"<td class='usage-conv-when'>2026-08-14</td></tr>"
    for i in range(60)
)
HEAD = "".join(
    f"<th class='{cls}' aria-sort='none'>"
    f"<button type='button' class='usage-rec-sort' data-usage-sort='{key}'>{label}"
    f"<span class='usage-rec-sort-ind'></span></button></th>"
    for key, label, cls in [
        ("what", "대화", ""), ("calls", "호출", "num"), ("total_tokens", "토큰", "num"),
        ("cost_usd", "추정 비용", "num"), ("last_used", "최근 사용", "usage-conv-when"),
    ]
)
PAGER = (
    "<div class='usage-rec-pager'>"
    "<span class='usage-rec-pager-info'>총 120건 중 1–50</span>"
    "<span class='usage-rec-pager-ctl'>"
    "<button class='usage-rec-page-btn' data-usage-page='first'>«</button>"
    "<button class='usage-rec-page-btn' data-usage-page='prev'>‹</button>"
    "<span class='usage-rec-pager-pos'>1 / 3</span>"
    "<button class='usage-rec-page-btn' data-usage-page='next'>›</button>"
    "<button class='usage-rec-page-btn' data-usage-page='last'>»</button>"
    "<label class='usage-rec-pager-size'>페이지당 "
    "<select class='usage-rec-page-size'><option>50행</option></select></label>"
    "</span></div>"
)
TABLE = (
    "<div class='usage-conv-tablewrap'><table class='usage-conv-table'>"
    f"<thead class='usage-rec-head'><tr>{HEAD}</tr></thead>"
    f"<tbody class='usage-rec-body'>{ROWS}</tbody></table></div>"
    "<p class='usage-conv-note usage-conv-hint'>안내 문구</p>"
    + PAGER
)


def _page_html(css: str, variant: str) -> str:
    """variant='admin' → 관리 콘솔 모달(.usage-conv-body), 'profile' → 작업 화면(.usage-conv-content)."""
    if variant == "admin":
        inner = f"<div class='admin-modal usage-conv-modal'><div class='usage-conv-body'>{TABLE}</div></div>"
    else:
        inner = f"<div class='usage-conv-dialog'><div class='usage-conv-content'>{TABLE}</div></div>"
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{margin:0;font-family:sans-serif}"
        ".usage-conv-body,.usage-conv-content{max-height:400px}"
        f"{css}</style></head><body>{inner}</body></html>"
    )




def main() -> int:
    with open(CSS_PATH, encoding="utf-8") as fh:
        css = fh.read()
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            print(f"chromium 미가용 — {exc}")
            return 2
        for variant in ("admin", "profile"):
            scroller = ".usage-conv-body" if variant == "admin" else ".usage-conv-content"
            # L1 — 스크롤 후에도 열 머리가 스크롤러 뷰 안에 남는다(= 실제 스크롤러에 붙었다).
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.set_content(_page_html(css, variant))
            before = page.eval_on_selector(".usage-rec-head th", "el => el.getBoundingClientRect().top")
            page.eval_on_selector(scroller, "el => { el.scrollTop = el.scrollHeight; }")
            r = page.evaluate(
                """([s]) => {
                  const th = document.querySelector('.usage-rec-head th').getBoundingClientRect();
                  const sc = document.querySelector(s).getBoundingClientRect();
                  return {thTop: th.top, thBottom: th.bottom, scTop: sc.top, scBottom: sc.bottom};
                }""", [scroller])
            page.close()
            check(f"L1 {variant}: 스크롤해도 열 머리가 남는다",
                  r["thBottom"] > r["scTop"] and r["thTop"] < r["scBottom"], r)
            check(f"L1b {variant}: 열 머리가 제자리에 고정(sticky)",
                  abs(r["thTop"] - before) < 2, {"before": before, "after": r["thTop"]})

            # L2 — 좁은 폭에서 페이저가 넘치지 않는다.
            for width in (320, 480, 640):
                page = browser.new_page(viewport={"width": width, "height": 700})
                page.set_content(_page_html(css, variant))
                r2 = page.eval_on_selector(
                    ".usage-rec-pager",
                    """el => {
                      const p = el.getBoundingClientRect();
                      const kids = Array.from(el.querySelectorAll('.usage-rec-pager-info, .usage-rec-pager-ctl'))
                        .map(k => k.getBoundingClientRect());
                      return {
                        overflowRight: Math.max(0, ...kids.map(k => k.right - p.right)),
                        overflowLeft: Math.max(0, ...kids.map(k => p.left - k.left)),
                        scrollOverflow: el.scrollWidth - el.clientWidth,
                      };
                    }""")
                page.close()
                check(f"L2 {variant}@{width}px: 페이저가 컨테이너를 넘치지 않는다",
                      r2["overflowRight"] <= 1 and r2["overflowLeft"] <= 1 and r2["scrollOverflow"] <= 1, r2)

            # L3 — 모달을 연 직후(스크롤 0)에 페이저가 보인다.
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.set_content(_page_html(css, variant))
            r3 = page.evaluate(
                """([s]) => {
                  const sc = document.querySelector(s).getBoundingClientRect();
                  const pg = document.querySelector('.usage-rec-pager');
                  const pr = pg.getBoundingClientRect();
                  return {visible: pr.top < sc.bottom && pr.bottom > sc.top, pos: getComputedStyle(pg).position};
                }""", [scroller])
            page.close()
            check(f"L3 {variant}: 첫 화면에 페이저가 보인다(sticky)",
                  r3["visible"] and r3["pos"] == "sticky", r3)
        browser.close()
    print(f"\n{'OK' if _failed == 0 else 'FAILED'} — passed={_passed} failed={_failed}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

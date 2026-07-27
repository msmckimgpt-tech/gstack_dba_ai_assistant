#!/usr/bin/env python3
"""feature-0003 share-bar-layout — 공유 대화 뷰 하단 바 재배치의 헤드리스 레이아웃 실측.

요청(2026-07-27):
  ① ['링크 복사', '내 계정에서 fork'] 등 액션을 하단 바(.share-footer) 내부 **우측**으로 이동
  ② 하단 바의 '조회 N회'(#shareViewCount)를 페이지 **상단**으로 이동
  ③ (추가) 하단 바 크기는 **기존을 거의 유지**하고, 키워야 하면 mouse-hover 반응형 +
     자연스러운 애니메이션으로 확장

높이·좌표는 레이아웃 산출물이라 DOM 없는 단위검증으로 대체할 수 없다. 본 스크립트는
**실 share.html + 실 share.css** 를 chromium 에 올려 다음을 실측한다. 비교 기준(before)은
`git show main:...` 로 꺼낸 **변경 전 원본**을 같은 방식으로 렌더한 값이다.

  T1  액션 그룹이 하단 바 안에 있다(헤더 아님)
  T2  액션 그룹이 하단 바 **우측**에 정렬된다(안내문보다 오른쪽 + 바 우측 여백에 밀착)
  T3  조회수가 페이지 상단(헤더 .share-meta) 안에 있고, 하단 바 위쪽에 위치한다
  T4  **하단 바 기본 높이가 변경 전과 거의 같다**(허용 오차 ±2px)
  T5  hover 시 하단 바가 확장된다(높이 증가) — 조작 시에만 커지는 반응형
  T6  확장이 transition 으로 애니메이션된다(즉시 점프 아님)
  T7  hover 확장 높이까지 본문 하단 여백(.share-container padding-bottom)이 덮는다
  T8  버튼 클릭 타겟이 hover 상태에서 24px 이상으로 커진다

실행:
  PLAYWRIGHT_BROWSERS_PATH=<ms-playwright> python3 tests/headless/verify_share_bar_layout.py

라이브 화면 정본은 PB-0008(Windows-browser) — 본 스크립트는 배포 전 레이아웃 근거다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent.parent / "src" / "static"
REPO_REL = "unit/feature-0003-agent-web-ui/src/static"

FAILURES: list[str] = []
PASSES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILURES).append(f"{name}: {detail}" if detail else name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")


def git_show(ref: str, rel: str) -> str:
    """변경 전(main) 원본을 워킹트리 오염 없이 꺼낸다."""
    return subprocess.run(
        ["git", "show", f"{ref}:{rel}"],
        cwd=HERE.parent.parent.parent.parent,  # repo 루트
        capture_output=True, text=True, check=True,
    ).stdout


def build_page(html: str, css: str) -> str:
    """share.js / vendor 스크립트 없이 구조·스타일만 렌더한다(share.js 는 API 의존).

    조회수·소유자 등 meta 는 share.js 가 채우므로, `:empty` 로 숨지 않도록 여기서 값을 넣는다.
    """
    html = html.replace('<link rel="stylesheet" href="/static/share.css?v=dev" />', f"<style>{css}</style>")
    # 외부 스크립트 제거 (네트워크 불요)
    for tag in ('<script src="/static/vendor/marked.umd.js"></script>',
                '<script src="/static/vendor/purify.min.js"></script>',
                '<script src="/static/vendor/mermaid.min.js?v=mermaid-10.9.3"></script>',
                '<script src="/static/mermaid-render.js?v=dev"></script>',
                '<script src="/static/share.js?v=dev"></script>',
                '<script src="/static/textarea-autogrow.js?v=dev"></script>'):
        html = html.replace(tag, "")
    seed = """
    <script>
      window.addEventListener("DOMContentLoaded", function () {
        var fill = {
          shareTopic: "코드 리뷰 결과 정리 및 액션 아이템 생성",
          shareOwner: "소유자 admin",
          shareScope: "범위: 대화 전체",
          shareProduct: "제품 국내 웹 - QA",
          shareViewCount: "조회 6회"
        };
        Object.keys(fill).forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.textContent = fill[id];
        });
        // fork 버튼은 로그인·권한 조건부(hidden) — 배치 실측을 위해 노출시킨다.
        ["shareForkBtn"].forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.classList.remove("hidden");
        });
        var log = document.getElementById("shareMessages");
        if (log) {
          log.innerHTML = "";
          for (var i = 0; i < 30; i++) {
            var d = document.createElement("div");
            d.className = "share-message";
            d.textContent = "메시지 " + (i + 1);
            log.appendChild(d);
          }
        }
      });
    </script>
    """
    return html.replace("</body>", seed + "</body>")


def measure(page, selector: str) -> dict:
    return page.eval_on_selector(
        selector,
        "el => { const r = el.getBoundingClientRect();"
        " return {x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom}; }",
    )


def main() -> int:
    after_html = (STATIC / "share.html").read_text(encoding="utf-8")
    after_css = (STATIC / "share.css").read_text(encoding="utf-8")
    before_html = git_show("main", f"{REPO_REL}/share.html")
    before_css = git_show("main", f"{REPO_REL}/share.css")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()

        # ── before (main) — 하단 바 기존 높이 실측 ──────────────────────────
        page.set_content(build_page(before_html, before_css))
        page.wait_for_timeout(120)
        before_footer = measure(page, ".share-footer")
        print(f"\n[before/main] .share-footer height = {before_footer['h']:.1f}px")

        # ── after (변경본) ────────────────────────────────────────────────
        page.set_content(build_page(after_html, after_css))
        page.wait_for_timeout(120)
        footer = measure(page, ".share-footer")
        actions = measure(page, ".share-actions")
        note = measure(page, ".share-footer-note")
        header = measure(page, ".share-header")
        view_count = measure(page, "#shareViewCount")
        print(f"[after]      .share-footer height = {footer['h']:.1f}px\n")

        # T1 — 액션은 하단 바 안
        in_footer = page.evaluate(
            "() => !!document.querySelector('.share-footer .share-actions')"
            " && !document.querySelector('.share-header .share-actions')"
        )
        check("T1 액션 그룹이 하단 바 안(헤더 아님)", in_footer)

        # T2 — 우측 정렬: 안내문보다 오른쪽 + 바 우측 padding(16px) 안쪽에 밀착
        right_gap = footer["right"] - actions["right"]
        check(
            "T2 액션 그룹이 하단 바 우측 정렬",
            actions["x"] > note["x"] and right_gap <= 20,
            f"note.x={note['x']:.0f} < actions.x={actions['x']:.0f}, 우측여백={right_gap:.1f}px",
        )

        # T3 — 조회수는 상단(헤더 meta) — 하단 바보다 위
        in_header_meta = page.evaluate(
            "() => !!document.querySelector('.share-header .share-meta #shareViewCount')"
            " && !document.querySelector('.share-footer #shareViewCount')"
        )
        check(
            "T3 조회수가 페이지 상단 meta 안",
            in_header_meta and view_count["bottom"] <= header["bottom"] and view_count["y"] < footer["y"],
            f"viewCount.y={view_count['y']:.0f} < footer.y={footer['y']:.0f}",
        )

        # T4 — 기본 높이 유지 (±2px)
        delta = footer["h"] - before_footer["h"]
        check(
            "T4 하단 바 기본 높이가 변경 전과 거의 동일(±2px)",
            abs(delta) <= 2.0,
            f"before={before_footer['h']:.1f}px → after={footer['h']:.1f}px (Δ{delta:+.1f}px)",
        )

        # T5 — hover 확장
        page.hover(".share-footer")
        page.wait_for_timeout(400)   # transition 완료 대기
        hovered = measure(page, ".share-footer")
        grew = hovered["h"] - footer["h"]
        check(
            "T5 hover 시 하단 바 확장",
            grew > 4.0,
            f"{footer['h']:.1f}px → {hovered['h']:.1f}px (+{grew:.1f}px)",
        )

        # T6 — transition 존재 (즉시 점프 아님)
        transition = page.eval_on_selector(
            ".share-footer", "el => getComputedStyle(el).transitionProperty + ' / ' + getComputedStyle(el).transitionDuration"
        )
        check("T6 확장이 transition 으로 애니메이션", "padding" in transition and "0s /" not in transition, transition)

        # T8 — hover 시 버튼 클릭 타겟 확대
        btn_hover = measure(page, "#shareCopyLinkBtn")
        check("T8 hover 시 버튼 높이 ≥ 24px", btn_hover["h"] >= 24.0, f"{btn_hover['h']:.1f}px")

        # T7 — hover 확장 높이를 본문 하단 여백이 덮는다
        page.mouse.move(10, 10)
        page.wait_for_timeout(400)
        pad_bottom = page.eval_on_selector(
            ".share-container", "el => parseFloat(getComputedStyle(el).paddingBottom)"
        )
        check(
            "T7 본문 하단 여백이 hover 확장 높이를 덮음",
            pad_bottom >= hovered["h"],
            f"padding-bottom={pad_bottom:.0f}px ≥ hover 높이 {hovered['h']:.1f}px",
        )

        # 시각 증거 — 기본 / hover 상태
        evidence = HERE.parent.parent / "docs" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(evidence / "share-bar-layout-after-20260727.png"), full_page=False)
        page.hover(".share-footer")
        page.wait_for_timeout(400)
        page.screenshot(path=str(evidence / "share-bar-layout-hover-20260727.png"), full_page=False)
        page.set_content(build_page(before_html, before_css))
        page.wait_for_timeout(120)
        page.screenshot(path=str(evidence / "share-bar-layout-before-20260727.png"), full_page=False)

        browser.close()

    print(f"\n{len(PASSES)} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print(f"  FAILED: {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())

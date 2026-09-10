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
  T9  **액션이 전부 켜지고 안내가 뜬 상태**에서도, 좁은 뷰포트까지 여백이 바를 덮는다
      (share-client-entry 2026-09-08 추가 — 아래 참조)

⚠ **T1~T8 은 「안내가 숨김인 기본 상태」만 잰다.** 2026-09-08 에 하단 바가 앱 진입 버튼·받기
링크·안내 행을 얻었을 때 T1~T8 은 **전부 초록이었는데**(안내가 `display:none` 이라 기본
높이가 그대로였다) 실제로는 데스크톱 hover 82.5px > 80px, 375px 뷰포트 180.1px > 96px,
320px 뷰포트 198.1px > 96px 로 예산을 넘고 있었다 — 초과분은 `position: fixed` 바에
영구히 가려진 대화 말미가 된다. 적대 리뷰가 그 사각지대를 지적했고 T9 가 그것을 닫는다.

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

#: 하단 고정 바가 뷰포트에서 가져갈 수 있는 최대 비율. 이 화면은 **읽기 위한** 화면이고,
#: 바에 실린 것은 대부분 Windows 전용 경로다 — 그 경로가 실행되지 않는 기기(휴대폰)에서
#: 화면의 1/4 를 영구 점유하면 그것은 기능이 아니라 방해다.
_BAR_BUDGET = 0.25

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
    #
    # ⚠ **정규식으로 지운다** (적대 리뷰 2026-09-08 ux-2R-C2). 종전에는 태그 문자열을 그대로
    #   비교했는데, `share.js` 에 `defer` 가 붙고 `share-client-context.js`(module)가 새로
    #   생기면서 목록이 **조용히 어긋났다** — 그런데도 T1~T8 이 초록이었던 이유는 오직
    #   `set_content` 의 문서 URL 이 `about:blank` 라 상대 경로가 해석되지 않았기 때문이다.
    #   즉 하네스가 스스로 적어 둔 전제(「share.js 없이 렌더한다」)를 지키는 것이 제거 목록이
    #   아니라 **우연**이었다. 누군가 실 base URL 을 물리는 순간 T1~T8 의 의미가 달라진다.
    import re as _re

    html = _re.sub(
        r'<script[^>]*src="/static/(?:vendor/|share\.js|share-client-context\.js|'
        r'mermaid-render\.js|textarea-autogrow\.js)[^"]*"[^>]*></script>',
        "", html)
    # 주석은 `share.js` 를 **언급**할 수 있다 — 남으면 안 되는 것은 `<script>` 태그다.
    assert not _re.search(r'<script[^>]*src="[^"]*share\.js', html), \
        "share.js 스크립트 태그 제거에 실패했다 — T1~T8 의 전제가 깨진다"
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

        # ── T9 — 「전부 켜진 상태 × 좁은 폭」에서도 여백이 바를 덮는가 ──────────
        #
        # 이 화면은 진입 시 맨 아래로 pin 되므로(share.js engageInitialBottomPin),
        # 가려진 구간이 곧 사용자가 **처음 보는 자리**다. 그래서 「가장 큰 상태」로 잰다:
        # 앱 진입 버튼 + 받기 링크 + 가장 긴 안내 문구 + hover 확장.
        #
        # ⚠ 여백은 이제 상수가 아니라 `share.js` 의 `syncFooterSpacing` 이 실제 높이에 맞춘다.
        #   그래서 이 검사는 **share.js 를 실제로 실행한 페이지**에서 해야 한다 — 위 T1~T8 은
        #   구조·스타일만 보므로 스크립트 없이 렌더한다(그 차이가 이 하네스의 사각지대였다).
        long_hint = ("DQA 앱을 여는 중입니다. 창이 안 보이면 다른 창·알림 영역을 확인해 "
                     "주세요. 앱이 없으면 [DQA 앱 받기].")
        share_js = (STATIC / "share.js").read_text(encoding="utf-8")
        # ⚠ **실제 기기 높이로 잰다.** 800px 고정으로 재면 휴대폰에서의 점유율이 실제보다
        #   작게 나온다 — 320×568 에서 바가 174px 일 때 800 기준 22% 지만 실제로는 31% 다.
        for width, height in ((1280, 800), (768, 1024), (375, 667), (320, 568)):
            ctx9 = browser.new_context(viewport={"width": width, "height": height},
                                       has_touch=width <= 420)
            pg9 = ctx9.new_page()
            pg9.set_content(build_page(after_html, after_css))
            pg9.wait_for_timeout(80)
            # ⚠ **플랫폼을 고정한다.** chromium 기본 UA 는 Linux 라, 고정하지 않으면
            #   `appPlatformSupported()` 가 거짓이 되어 **비-Windows 열화 경로**(종전 웹
            #   버튼 3개)를 재게 된다 — 그 상태에서는 앱 진입 버튼도 받기 링크도 뜨지 않으므로
            #   「앱 전용 경로의 바 높이」를 잰다는 전제가 무너진다. 실측으로 그 조합을 재고
            #   있었다: 열화 버튼 3개 + 강제로 켠 안내 = **실제로는 공존하지 않는 화면**.
            #   (`add_init_script` 는 다음 navigation 에 걸리므로 `set_content` 뒤에는 늦다 —
            #    이미 뜬 문서에 직접 정의한다.)
            pg9.evaluate("() => Object.defineProperty(navigator, 'platform',"
                         " { configurable: true, get: () => 'Win32' })")
            pg9.evaluate("(js) => { window.__dqaClientBridge = null;"
                         " window.fetch = () => Promise.resolve({ok:true,status:200,"
                         " json: () => Promise.resolve({share:{token:'t'},conversation:{topic:'T'},"
                         " messages:[],viewer:{is_authenticated:true,can_fork:true,can_join:true,"
                         " joinable:true},client:{app_link:'dqa-connect://open?x',"
                         " download_url:'https://d/x.exe'}})});"
                         " window.marked={parse:s=>String(s||''),setOptions(){}};"
                         " window.DOMPurify={sanitize:s=>String(s||'')};"
                         " window.mermaid={initialize(){},run(){}};"
                         " const s=document.createElement('script'); s.textContent=js;"
                         " document.body.appendChild(s); }", share_js)
            pg9.wait_for_timeout(200)
            # ⚠ 문구는 **자식 span** 에 쓴다 — 문단에 직접 대입하면 좁은 폭에서 그 안으로
            #   접혀 들어온 [DQA 앱 받기] 가 함께 지워진다(실측). 제품 코드도 같은 규약이다.
            pg9.evaluate("(t) => { const h=document.getElementById('shareAppHint');"
                         " h.classList.remove('hidden');"
                         " document.getElementById('shareAppHintText').textContent=t; }", long_hint)
            assert pg9.evaluate("() => !!document.getElementById('shareAppGetLink')"), \
                "안내를 쓰는 사이 받기 링크가 사라졌다 — 안내가 없는 버튼을 가리키게 된다"
            pg9.hover(".share-footer")
            pg9.wait_for_timeout(400)
            fh = pg9.eval_on_selector(".share-footer",
                                      "el => el.getBoundingClientRect().height")
            pad = pg9.eval_on_selector(".share-container",
                                       "el => parseFloat(getComputedStyle(el).paddingBottom)")
            check(f"T9 여백이 바를 덮음 @{width}x{height}",
                  pad >= fh, f"footer={fh:.1f}px ≤ padding-bottom={pad:.1f}px")
            # ⚠ 위 한 줄만으로는 **아무것도 고정하지 못한다** (적대 리뷰 ux-2R-F4):
            #   구현이 `pad = ceil(fh) + 12` 이므로 `pad >= fh` 는 스크립트가 도는 한 실패할
            #   수 없는 **항진명제**다. 바가 500px 여도 초록이다. 그래서 «가려짐 없음» 과 별개로
            #   **절대 예산**을 둔다 — 읽기 전용 열람 화면에서 고정 바가 화면의 얼마를
            #   가져가도 되는가는 여백과 무관한 별개 판정이다.
            check(f"T9-b 바가 화면의 {_BAR_BUDGET:.0%} 를 넘지 않음 @{width}x{height}",
                  fh <= _BAR_BUDGET * height,
                  f"footer={fh:.1f}px / viewport {height}px = {fh / height:.0%}")

            # ── T10 — 인쇄 매체에서는 그 여백이 **남지 않는다** ──────────────────
            #
            # ⚠ 여백을 상수에서 인라인으로 옮긴 순간 생긴 회귀다(적대 리뷰 ux-2R-F1):
            #   인쇄에서는 바가 `display:none` 인데 인라인 `padding-bottom` 은 살아남아
            #   지면 말미에 95~157px 공백이 남고, 페이지 경계 부근에서 빈 페이지가 한 장
            #   더 난다. 일반 규칙은 인라인에 지므로 `@media print` 가 `!important` 로
            #   강제한다. 이 화면은 「수신자가 보고서로 보관」하는 경로를 지원 대상으로
            #   명시하고 있으므로(share.css @media print 주석) 그 축을 가드로 남긴다.
            pg9.emulate_media(media="print")
            pg9.wait_for_timeout(120)
            print_pad = pg9.eval_on_selector(
                ".share-container", "el => parseFloat(getComputedStyle(el).paddingBottom)")
            check(f"T10 인쇄 매체에서 하단 여백이 0 @{width}x{height}",
                  print_pad == 0, f"print padding-bottom={print_pad:.1f}px")
            pg9.emulate_media(media="screen")
            ctx9.close()

        # 시각 증거 — 기본 / hover 상태
        #
        # ⚠ **기본으로 찍지 않는다** (적대 리뷰 3R C5). 이 증적은 커밋돼 있고, 하네스를 돌릴
        #   때마다 덮어쓰면 리뷰어·CI 가 같은 명령을 재현할 때 워킹트리가 더러워진다 —
        #   그리고 증적이 «언제 찍힌 것인가» 의 신뢰가 떨어진다. 갱신이 필요할 때만 명시한다:
        #       python3 tests/headless/verify_share_bar_layout.py --evidence
        if "--evidence" not in sys.argv:
            browser.close()
            print(f"\n{len(PASSES)} passed, {len(FAILURES)} failed")
            for f in FAILURES:
                print(f"  FAILED: {f}")
            return 1 if FAILURES else 0
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

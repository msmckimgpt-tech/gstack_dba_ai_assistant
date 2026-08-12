#!/usr/bin/env python3
"""metadata-pane-refresh: headless Chromium 실렌더 계측.

정적 CSS 단언(`tests/verify_metadata_pane_refresh.mjs`)이 못 보는 축을 실 브라우저 레이아웃
엔진으로 잰다 — cascade 승부, 계산된 대비, **픽셀 정렬**, 줄바꿈 발생 여부. 이 프로젝트에서
jsdom 은 layout 을 계산하지 않으므로 정렬·wrap 류는 원리적으로 검증 불가다.

⚠️ 이것은 PB-0008(실 Windows 브라우저) 을 **대체하지 않는다**. PRE-DEPLOY 로 회귀를 미리
잡는 보조 게이트이고, 완료 게이트는 여전히 PB-0008 이다(AGENTS.md §15.4.1 · §16.6).

실행: python3 tests/headless/verify_metadata_pane_refresh_render.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

STATIC = Path(__file__).resolve().parents[2] / "src" / "static"
# admin.html 의 실제 로드 순서와 동일(다른 metadata 하네스와 같은 concat 순서).
CSS_ORDER = ["base", "shell", "chat", "drawers", "admin", "profile", "search-audit"]

PASSED: list[str] = []
FAILED: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> None:
    tag = "PASS" if cond else "FAIL"
    (PASSED if cond else FAILED).append(name)
    print(f"  {tag}  {name}" + (f"  [{detail}]" if detail else ""))


def _srgb(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_srgb(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def parse_rgb(s: str) -> tuple[float, float, float]:
    nums = [float(x) for x in re.findall(r"[\d.]+", s or "")]
    if len(nums) >= 3:
        return nums[0], nums[1], nums[2]
    return 0.0, 0.0, 0.0


# metadata.js `_metaBootstrapRenderResult` 의 tables 분기와 **동일 구조** 를 재현한다.
# (구조가 어긋나면 계측이 실물과 무관해지므로, 클래스·중첩·속성을 그대로 옮긴다.)
# 행 수는 [7] sticky 계측의 **전제**다 — 컨테이너가 헤더 높이를 넘겨 스크롤되지 않으면
# sticky 는 발동 조건 자체에 도달하지 못하고, 테스트는 "고정 실패" 를 거짓 보고한다
# (초판 5행에서 실 스크롤 여유가 7px 뿐이었다).
ROWS = [
    ("gunzgame.mailreserve", ""),
    ("gunzgame.mailreservehistory", ""),
    ("gunzgame.medalpricesaleratetable", "메달 가격 판매 비율"),
    ("gunzgame.map", ""),
    ("gunzgame.masangcreators", ""),
    ("gunzgame.medalshop", "메달 상점 상품"),
    ("gunzgame.medalshopsaleratebuff", ""),
    ("gunzgame.mission", ""),
    ("gunzgame.missionfirstcomplete", ""),
    ("gunzgame.missionfirstdiscover", ""),
    ("gunzgame.mailreserveitem", ""),
    ("gunzgame.item", "실제 인게임 아이템 정보"),
    ("gunzgame.guild", ""),
    ("gunzgame.register", ""),
    ("gunzgame.ranking", ""),
    ("gunzgame.dblog", ""),
]


def build_page(css: str) -> str:
    rows = "\n".join(
        f"""
        <div class="admin-meta-bs-table is-flat" data-schema="gunzgame" data-table="{name.split('.')[1]}">
          <div class="admin-meta-bs-row">
            <span class="admin-meta-bs-table-name" title="{name}">{name}</span>
            <input type="text" class="admin-meta-input admin-meta-bs-desc admin-meta-bs-desc-inline"
                   placeholder="테이블 설명 입력…" data-kind="table" value="{val}" aria-label="{name} 설명" />
            <span class="admin-meta-bs-hint {'is-filled is-complete' if val else ''}">{'설명 입력됨' if val else '비어있음'}</span>
          </div>
        </div>"""
        for name, val in ROWS
    )
    # ⚠️ 레이아웃 컨테이너 주의: `body.admin-shell` + `.admin-list-detail` 그리드를 그대로 쓰면
    # 사이드바 컬럼 폭 안에 pane 이 들어가 `minmax(360px,1fr) minmax(0,1.05fr)` 의 두 번째 트랙이
    # **0 으로 붕괴**한다(초판에서 행 폭 24px = 좌우 padding 합만 남아 정렬 계측이 무의미했다).
    # 계측 대상 기하는 `.admin-meta-bootstrap` 내부이므로, 상세 컬럼에 실측에 가까운 고정 폭을
    # 주어 그리드 붕괴 변수를 제거한다(스크린샷의 우측 패널 폭 비율 기준).
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head>
<body>
  <section class="admin-pane" data-admin-pane="metadata" style="display:block">
    <div>
      <div class="admin-detail-col" id="metadataDetail" style="width:620px;height:520px;overflow-y:auto">
        <section class="admin-meta-bootstrap" id="metadataBootstrap">
          <div class="admin-meta-bootstrap-body">
            <p class="admin-meta-bootstrap-note">현재 선택한 제품(<strong>건즈 글로벌 QA</strong>)의 접근 DB 에서 골격을 가져옵니다.</p>
            <div class="admin-meta-bs-filterbar">
              <input type="text" class="admin-meta-input admin-meta-bs-search" placeholder="테이블명 검색…" />
              <span class="admin-meta-bs-filter-count">표시 1–5 / 전체 5</span>
              <button type="button" class="btn-secondary admin-meta-bs-expandall">모두 펼치기</button>
            </div>
            <div class="admin-meta-bs-grid-head" id="metadataBootstrapGridHead">
              <span class="admin-meta-bs-gh-name">테이블</span>
              <span class="admin-meta-bs-gh-desc">설명</span>
              <span class="admin-meta-bs-gh-state">상태</span>
            </div>
            <div class="admin-meta-bootstrap-result" id="metadataBootstrapResult">{rows}</div>
            <div class="admin-meta-bs-pager" id="metadataBootstrapPager">
              <button type="button" class="btn-secondary admin-meta-bs-page-btn">‹ 이전</button>
              <span class="admin-meta-bs-page-label">페이지 3 / 5</span>
              <button type="button" class="btn-secondary admin-meta-bs-page-btn">다음 ›</button>
            </div>
            <div class="admin-meta-bootstrap-actions" id="metadataBootstrapSaveActions">
              <button type="button" class="btn-secondary admin-meta-ai-btn">AI 로 설명 일괄 생성</button>
              <button type="button" class="btn-primary">설명 입력분 저장</button>
              <span class="admin-meta-bootstrap-saveinfo">기존 설명은 채워져 표시됩니다. 변경·추가한 행만 저장됩니다. (다른 페이지의 변경도 저장됩니다)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </section>
</body></html>"""


def main() -> int:
    css = "\n".join((STATIC / "css" / f"{n}.css").read_text(encoding="utf-8") for n in CSS_ORDER)
    html = build_page(css)
    out_dir = Path(__file__).resolve().parents[2] / "docs" / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1180, "height": 700}, device_scale_factor=2)
        page.set_content(html)
        page.wait_for_timeout(180)

        # ── 1. 통합 표 — 행이 자체 카드 테두리를 갖지 않는다(격자 노이즈 제거) ────────
        row_borders = page.eval_on_selector_all(
            ".admin-meta-bs-table",
            """els => els.map(el => {
                 const cs = getComputedStyle(el);
                 return {left: cs.borderLeftWidth, right: cs.borderRightWidth,
                         bottom: cs.borderBottomWidth, top: cs.borderTopWidth, radius: cs.borderTopLeftRadius};
               })""",
        )
        no_side = all(r["left"] == "0px" and r["right"] == "0px" and r["bottom"] == "0px" for r in row_borders)
        ok("[1] 행에 좌/우/하 카드 테두리 없음(통합 표)", no_side, json.dumps(row_borders[0]))
        ok("[1] 행 radius 0(카드 아님)", all(r["radius"] == "0px" for r in row_borders))
        ok("[1] 첫 행은 상단 divider 없음, 이후 행은 있음",
           row_borders[0]["top"] == "0px" and all(r["top"] == "1px" for r in row_borders[1:]))

        # ── 2. ghost cell — 기본 투명, focus 시 halo. cascade 승부를 실제로 확인 ─────
        base_desc = page.eval_on_selector(
            ".admin-meta-bs-desc",
            """el => { const cs = getComputedStyle(el);
                      return {bg: cs.backgroundColor, bc: cs.borderTopColor, bw: cs.borderTopWidth, sh: cs.boxShadow}; }""",
        )
        ok("[2] 기본 배경 투명", base_desc["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), base_desc["bg"])
        ok("[2] 기본 테두리 투명", base_desc["bc"] in ("rgba(0, 0, 0, 0)", "transparent"), base_desc["bc"])
        ok("[2] 테두리 폭은 1px 유지(hover/focus 시 레이아웃 이동 0)", base_desc["bw"] == "1px", base_desc["bw"])
        ok("[2] 기본 halo 없음", base_desc["sh"] == "none", base_desc["sh"])

        page.focus(".admin-meta-bs-desc")
        page.wait_for_timeout(220)
        foc = page.eval_on_selector(
            ".admin-meta-bs-desc",
            """el => { const cs = getComputedStyle(el);
                      return {bg: cs.backgroundColor, bc: cs.borderTopColor, sh: cs.boxShadow, z: cs.zIndex}; }""",
        )
        ok("[2] focus 시 halo 부여(D1 — 다른 화면과 동일 계약)",
           "rgb" in foc["sh"] and foc["sh"] != "none" and "3px" in foc["sh"], foc["sh"])
        ok("[2] focus 시 primary 테두리", foc["bc"] == "rgb(37, 99, 235)", foc["bc"])
        ok("[2] focus 시 흰 배경(편집 중인 칸이 도드라짐)", foc["bg"] == "rgb(255, 255, 255)", foc["bg"])
        ok("[2] focus halo 가 divider 위로(z-index 1)", foc["z"] == "1", foc["z"])

        # ── 3. 열 정렬 — 헤더와 모든 데이터행의 입력란 시작 x 가 일치해야 한다 ────────
        # 포커스는 스크롤 위치를 바꾸므로 기하 계측 전에 해제 + 스크롤 원위치(계측 오염 차단).
        page.eval_on_selector(".admin-meta-bs-desc", "el => el.blur()")
        page.evaluate("() => document.getElementById('metadataDetail').scrollTop = 0")
        page.wait_for_timeout(120)
        geo = page.evaluate(
            """() => {
                 const gh = document.querySelector('.admin-meta-bs-gh-desc').getBoundingClientRect();
                 const inputs = [...document.querySelectorAll('.admin-meta-bs-desc-inline')].map(e => e.getBoundingClientRect());
                 const states = [...document.querySelectorAll('.admin-meta-bs-hint')].map(e => e.getBoundingClientRect());
                 return {ghLeft: gh.left, ghRight: gh.right,
                         inLeft: inputs.map(r => r.left), inRight: inputs.map(r => r.right),
                         stRight: states.map(r => r.right)};
               }"""
        )
        left_spread = max(geo["inLeft"]) - min(geo["inLeft"])
        right_spread = max(geo["inRight"]) - min(geo["inRight"])
        ok("[3] 모든 행의 입력란 시작 x 동일(≤0.5px)", left_spread <= 0.5, f"spread={left_spread:.2f}px")
        ok("[3] 모든 행의 입력란 끝 x 동일(≤0.5px)", right_spread <= 0.5, f"spread={right_spread:.2f}px")
        # 헤더 '설명' 열이 입력란 열과 같은 구간을 덮는지(토큰 공유의 실물 증명).
        ok("[3] 헤더 '설명' 열 시작이 입력란 열 시작과 정합(≤2px)",
           abs(geo["ghLeft"] - min(geo["inLeft"])) <= 2.0,
           f"head={geo['ghLeft']:.1f} input={min(geo['inLeft']):.1f}")
        st_spread = max(geo["stRight"]) - min(geo["stRight"])
        ok("[3] 상태 열 우측 끝 동일(≤0.5px)", st_spread <= 0.5, f"spread={st_spread:.2f}px")

        # ── 4. 상태 dot — CSS ::before 가 실제로 렌더되고 색이 상태별로 갈린다 ────────
        dots = page.evaluate(
            """() => [...document.querySelectorAll('.admin-meta-bs-hint')].map(el => {
                 const b = getComputedStyle(el, '::before');
                 const own = getComputedStyle(el);
                 return {w: b.width, h: b.height, r: b.borderTopLeftRadius, bg: b.backgroundColor,
                         op: b.opacity, color: own.color, filled: el.classList.contains('is-filled')};
               })"""
        )
        ok("[4] 상태 dot 이 실제 렌더(7x7 원)",
           all(d["w"] == "7px" and d["h"] == "7px" for d in dots), json.dumps(dots[0]["w"]))
        empty = [d for d in dots if not d["filled"]]
        filled = [d for d in dots if d["filled"]]
        ok("[4] 미입력 dot 은 옅은 중립", bool(empty) and all(float(d["op"]) < 0.5 for d in empty))
        ok("[4] 입력됨 dot 은 불투명 success 색",
           bool(filled) and all(float(d["op"]) == 1.0 and d["bg"] == "rgb(22, 163, 74)" for d in filled),
           filled[0]["bg"] if filled else "-")
        ok("[4] 미입력/입력됨 라벨 색이 서로 다르다(상태 판독 채널)",
           bool(empty) and bool(filled) and empty[0]["color"] != filled[0]["color"],
           f"{empty[0]['color']} vs {filled[0]['color']}" if empty and filled else "-")

        # ── 5. 대비 — 상태 라벨·플레이스홀더가 실 배경 위에서 WCAG 를 넘는지 ─────────
        row_bg = parse_rgb(page.eval_on_selector(".admin-meta-bootstrap-result", "el => getComputedStyle(el).backgroundColor"))
        for label, d in (("미입력", empty[0]), ("입력됨", filled[0])):
            ratio = contrast(parse_rgb(d["color"]), row_bg)
            # 11px 본문 텍스트 → large-text 예외 없음(4.5:1).
            ok(f"[5] 상태 라벨({label}) 대비 ≥ 4.5:1", ratio >= 4.5, f"{ratio:.2f}:1")
        head = page.eval_on_selector(".admin-meta-bs-grid-head",
                                     "el => ({c: getComputedStyle(el).color, bg: getComputedStyle(el).backgroundColor})")
        r_head = contrast(parse_rgb(head["c"]), parse_rgb(head["bg"]))
        ok("[5] 열 헤더 라벨 대비 ≥ 4.5:1", r_head >= 4.5, f"{r_head:.2f}:1")

        # ── 6. D6 — 저장 액션 버튼 라벨이 줄바꿈되지 않는다(스크린샷 결함) ───────────
        btns = page.evaluate(
            """() => [...document.querySelectorAll('.admin-meta-bootstrap-actions > button')].map(b => {
                 const r = b.getBoundingClientRect();
                 const cs = getComputedStyle(b);
                 const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
                 const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
                 return {label: b.textContent.trim(), h: r.height, lines: Math.round((r.height - pad) / lh),
                         ws: cs.whiteSpace, w: r.width, sw: b.scrollWidth};
               })"""
        )
        for b in btns:
            ok(f"[6] '{b['label']}' 단일 행 렌더", b["lines"] <= 1 and b["ws"] == "nowrap",
               f"h={b['h']:.1f} lines={b['lines']} ws={b['ws']}")
            ok(f"[6] '{b['label']}' 라벨 잘림 없음", b["sw"] <= round(b["w"]) + 1, f"scrollW={b['sw']} w={b['w']:.1f}")

        # ── 7. sticky — overflow:clip 덕에 열 헤더가 실 스크롤러 기준으로 고정되는지 ──
        sticky = page.evaluate(
            """async () => {
                 const col = document.getElementById('metadataDetail');
                 const gh = document.getElementById('metadataBootstrapGridHead');
                 // 기준선은 반드시 scrollTop=0 에서 잡는다 — 앞 단계의 focus 가 컨테이너를 스크롤해
                 // 놓았으면 before/after 부호가 뒤집혀 "sticky 실패" 로 오판한다(초판 실측 오진).
                 col.scrollTop = 0;
                 await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                 const before = gh.getBoundingClientRect().top;
                 col.scrollTop = 140;
                 await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                 const after = gh.getBoundingClientRect().top;
                 // 더 스크롤해도 위치가 그대로면 "고정" — 절대 y 를 컨테이너 상단과 비교하는 방식은
                 // 틀린다: sticky 는 스크롤러의 **padding box** 를 기준으로 붙으므로 `top:0` 이어도
                 // border+padding 만큼 아래에 선다(실측 19px). 판정은 절대 좌표가 아니라 **불변성**이다.
                 col.scrollTop = 300;
                 await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                 const after2 = gh.getBoundingClientRect().top;
                 col.scrollTop = 0;
                 return {before, after, after2, scrolled: 140, scrolled2: col.scrollHeight > 0 ? 300 : 0,
                         panelOverflow: getComputedStyle(document.getElementById('metadataBootstrap')).overflow};
               }"""
        )
        ok("[7] 패널이 overflow:clip(scroll container 미생성)", sticky["panelOverflow"] == "clip", sticky["panelOverflow"])
        # (a) 스크롤량보다 적게 움직였다 = 붙기 시작했다.
        resisted = (sticky["before"] - sticky["after"]) < sticky["scrolled"] - 1
        # (b) 더 스크롤해도 위치 불변 = 완전히 고정됐다(정적 요소라면 300-140=160px 더 올라간다).
        pinned = abs(sticky["after"] - sticky["after2"]) <= 1.0
        ok("[7] 열 헤더가 스크롤에 저항(sticky 발동)", resisted,
           f"before={sticky['before']:.1f} after={sticky['after']:.1f} scrolled={sticky['scrolled']}")
        ok("[7] 추가 스크롤에도 위치 불변(완전 고정 — overflow:clip 이 실효)", pinned,
           f"@140={sticky['after']:.1f} @300={sticky['after2']:.1f}")

        # ── 9. halo 등가 — 토큰 파생 값이 base.css `.field input:focus` 와 **computed 동치** ──
        # 리터럴 복제를 피해 `color-mix(--primary 12%)` 로 파생했으므로 소스 문자열은 다르다.
        # 등가 여부는 브라우저가 계산한 값으로만 판정할 수 있다(정적 단언의 사각).
        # ⚠️ in-page `el.focus()` 로는 안 된다 — `:focus` 스타일은 **문서 자체가 포커스**를 가질 때만
        # 적용되므로 헤드리스에서 프로그램적 focus() 는 halo 를 만들지 않는다(초판 오진: 양쪽 모두
        # 0px 그림자로 읽혀 "동치" 가 vacuous 하게 참이 될 수도 있었다). Playwright `page.focus()` 사용.
        page.evaluate(
            """() => {
                 const mk = (wrapCls, cls, id) => { const w = document.createElement('div'); w.className = wrapCls;
                   const e = document.createElement('input'); e.id = id; if (cls) e.className = cls;
                   w.appendChild(e); return w; };
                 document.body.appendChild(mk('field', '', 'probeBase'));
                 // pane 지역 토큰이 상속되도록 메타데이터 pane 컨텍스트 안에 넣는다.
                 document.querySelector('.admin-pane[data-admin-pane="metadata"]')
                   .appendChild(mk('admin-meta-field', 'admin-meta-input', 'probeMeta'));
               }"""
        )
        page.focus("#probeBase")
        page.wait_for_timeout(150)
        halo_base = page.eval_on_selector("#probeBase", "el => getComputedStyle(el).boxShadow")
        page.focus("#probeMeta")
        page.wait_for_timeout(150)
        halo_meta = page.eval_on_selector("#probeMeta", "el => getComputedStyle(el).boxShadow")
        def spread(s: str) -> float:
            nums = [float(x) for x in re.findall(r"(-?[\d.]+)px", s or "")]
            return nums[-1] if nums else -1.0

        # vacuous 방지 — 둘 다 실제 halo 를 가져야 비교가 의미를 갖는다(≈3px 확산).
        ok("[9] 두 계약 모두 실제 halo(≈3px 확산)를 갖는다 — 비교가 vacuous 아님",
           abs(spread(halo_base) - 3.0) < 0.05 and abs(spread(halo_meta) - 3.0) < 0.05,
           f"base={spread(halo_base):.3f}px meta={spread(halo_meta):.3f}px")

        # ⚠️ 문자열 비교는 불가능하다 — Chrome 은 `color-mix()` 를 `oklab(...)` 로 직렬화하므로
        # 값이 같아도 computed 문자열이 다르다(`rgba(37,99,235,0.12)` vs `oklab(...)`).
        # 등가는 **합성 결과 픽셀**로 판정한다: 흰 배경에 각 색을 칠해 최종 RGB 를 비교(시각적 등가).
        composite = page.evaluate(
            """([a, b]) => {
                 const colorOf = s => s.slice(0, s.lastIndexOf(')') + 1);
                 const px = (c) => {
                   const cv = document.createElement('canvas'); cv.width = cv.height = 1;
                   const x = cv.getContext('2d');
                   x.fillStyle = '#ffffff'; x.fillRect(0, 0, 1, 1);
                   x.fillStyle = '#ffffff';                 // 파싱 실패 감지용 sentinel
                   x.fillStyle = c;
                   const parsed = x.fillStyle;
                   x.fillRect(0, 0, 1, 1);
                   return {rgb: [...x.getImageData(0, 0, 1, 1).data].slice(0, 3), parsed};
                 };
                 return {base: px(colorOf(a)), meta: px(colorOf(b))};
               }""",
            [halo_base, halo_meta],
        )
        d = max(abs(x - y) for x, y in zip(composite["base"]["rgb"], composite["meta"]["rgb"]))
        ok("[9] 메타데이터 halo == base.css .field halo (합성 픽셀 동치 — 토큰 파생이 값을 바꾸지 않음)",
           d <= 1, f"base={composite['base']['rgb']} meta={composite['meta']['rgb']} maxΔ={d}")

        # ── 8. row hover 틴트가 그 행에만 적용된다(전역 오염 없음) ──────────────────
        page.eval_on_selector(".admin-meta-bs-desc", "el => el.blur()")
        page.evaluate("() => document.getElementById('metadataDetail').scrollTop = 0")
        # `page.hover()` 는 actionability 검사에서 조상 요소를 pointer 차단으로 보고 재시도 루프에
        # 걸린다(합성 페이지). CSS `:hover` 는 실제 포인터 위치만 보므로 좌표로 직접 이동한다.
        box = page.locator(".admin-meta-bs-table:nth-child(2) .admin-meta-bs-table-name").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(220)
        tints = page.eval_on_selector_all(
            ".admin-meta-bs-row", "els => els.map(e => getComputedStyle(e).backgroundColor)")
        tinted = [i for i, t in enumerate(tints) if t not in ("rgba(0, 0, 0, 0)", "transparent")]
        ok("[8] hover 틴트가 정확히 1행에만", tinted == [1], f"tinted={tinted}")

        # ── 증거 캡처 ───────────────────────────────────────────────────────────
        page.evaluate("() => document.getElementById('metadataDetail').scrollTop = 0")
        page.focus(".admin-meta-bs-table:nth-child(3) .admin-meta-bs-desc")
        page.wait_for_timeout(220)
        shot = out_dir / "headless-metadata-pane-refresh-20260812.png"
        page.locator("#metadataBootstrap").screenshot(path=str(shot))
        print(f"\n  캡처: {shot}")
        browser.close()

    print(f"\n  {len(PASSED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

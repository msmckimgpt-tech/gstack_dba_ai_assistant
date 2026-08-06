"""버전 행 액션 영역(⇄ ⬇ 🗑) 공존 계약 — 실 CSS·실 레이아웃 측정.

**왜 이 파일이 있나**: `REQ-20260806-attach-version-diff`(비교 `⇄`)와
`REQ-20260806-attach-manage`(삭제 `🗑`)가 **서로 모르고 병렬로 개발되어** 같은
`.attach-list-version-actions` 에 버튼을 넣었다. 리베이스 시 git 은 텍스트상 깔끔히
병합했지만 그 결과가 **화면에서 성립하는지는 아무도 재지 않았다** — 버튼이 2개→3개로
늘었고, 버전 박스는 첨부 패널 안에서 좌측 28px 들여쓰기까지 먹는 좁은 영역이다.

이 부류는 pytest·jsdom·정적 스캔이 구조적으로 못 잡는다(레이아웃을 계산하지 않는다).
잡을 수 있는 유일한 선행 지점이 실 브라우저 측정이고, 그게 없으면 배포 후 사람이
스크린샷을 읽을 때까지 아무도 모른다.

계약(hard):
  A1 액션 버튼이 정확히 3개 존재한다 — 병합 누락으로 하나가 사라지면 잡는다.
  A2 액션 영역이 foot 경계 밖으로 넘치지 않는다.
  A3 foot 이 가로 overflow 하지 않는다(버튼 잘림).
  A4 페이지 가로 스크롤이 생기지 않는다.
  A5 긴 파일명이 버튼을 밀어내지 않는다 — 이름이 잘리고 버튼 폭은 유지된다.

관측(WARN, 이 cycle 범위 밖):
  W1 버튼 히트 영역이 WCAG 2.2 AA 최소 타겟(24×24)에 미달한다. 세 버튼 모두 해당하는
     **선행 상태**이고(병합이 만든 것이 아니다), 고치면 방금 랜딩한 `attach-manage` 의
     버튼 외형까지 바꾸므로 사용자 판단 대상으로 남긴다. 수치를 남겨 판단 근거만 제공한다.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

STATIC = pathlib.Path(__file__).resolve().parents[2] / "src" / "static"
CSS = (STATIC / "css/chat.css").read_text(encoding="utf-8")

# `_renderAttachmentVersionsBox` (composer.js) 가 만드는 DOM 구조를 그대로 재현.
# 구조가 바뀌면 A1 이 먼저 깨져 이 재현이 낡았음을 알린다.
ROW = """
<div class="attach-list-version-row">
  <div class="attach-list-version-head">
    <span class="attach-list-version-tag">v2</span>
    <span class="attach-list-version-name">{name}</span>
  </div>
  <div class="attach-list-version-foot">
    <span class="attach-list-version-role">사용자 업로드 · 12.3 KB</span>
    <span class="attach-list-version-actions">
      <button class="attach-list-version-cmp">⇄</button>
      <button class="attach-list-version-dl">⬇</button>
      <button class="attach-list-version-del">🗑</button>
    </span>
  </div>
</div>
"""

PAGE = """
<style>
:root {{ --border-subtle:#e5e7eb; --text-muted:#9ca3af; --bg-elevated:#fff;
        --tag-neutral-bg:#f0efea; --tag-ok-bg:#e6f4ea; --tag-danger-bg:#fdecec;
        --text-primary:#111; --accent:#2563eb; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: system-ui, sans-serif; }}
#panel {{ width: {w}px; border:1px solid #ccc; }}
.attach-list-versions {{ padding-left: 28px; }}
{css}
</style>
<div id="panel"><div class="attach-list-versions">
  <div class="attach-list-versions-head">
    <button class="attach-list-versions-compare">⇄ 버전 비교</button>
  </div>
  {rows}
</div></div>
"""

# 첨부 패널 실측 폭 구간(선행 design 패널이 240/280/360 에서 잘림을 발견한 그 구간).
WIDTHS = [240, 280, 320, 360, 420]
LONG = "2026년_7월_월간_매출집계_최종_검토완료_v3.xlsx"
WCAG_MIN = 24

MEASURE = """() => {
  const row = document.querySelector('.attach-list-version-row');
  const foot = document.querySelector('.attach-list-version-foot');
  const acts = document.querySelector('.attach-list-version-actions');
  const nameEl = document.querySelector('.attach-list-version-name');
  const btns = [...acts.querySelectorAll('button')].map(x => {
    const r = x.getBoundingClientRect();
    return {cls: x.className.replace('attach-list-version-', ''),
            w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right)};
  });
  const fr = foot.getBoundingClientRect(), ar = acts.getBoundingClientRect();
  return {
    rowW: Math.round(row.getBoundingClientRect().width),
    footRight: Math.round(fr.right),
    actsW: Math.round(ar.width), actsLeft: Math.round(ar.left),
    actsRight: Math.round(ar.right), btns,
    nameClipped: nameEl.scrollWidth > nameEl.clientWidth + 1,
    footOverflow: foot.scrollWidth > foot.clientWidth + 1,
    pageHScroll: document.documentElement.scrollWidth >
                 document.documentElement.clientWidth + 1,
  };
}"""


def main() -> int:
    fails: list[str] = []
    warns: list[str] = []
    rows: list[tuple[str, dict]] = []
    acts_widths: set[int] = set()

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for w in WIDTHS:
            for label, name in (("짧은명", "report.csv"), ("긴명", LONG)):
                pg.set_content(PAGE.format(w=w, css=CSS, rows=ROW.format(name=name)))
                m = pg.evaluate(MEASURE)
                tag = f"{w}px/{label}"
                rows.append((tag, m))
                acts_widths.add(m["actsW"])

                if len(m["btns"]) != 3:
                    fails.append(f"A1 {tag}: 액션 버튼 {len(m['btns'])}개 (⇄ ⬇ 🗑 3개여야 함)")
                if m["actsRight"] > m["footRight"] + 1:
                    fails.append(
                        f"A2 {tag}: 액션 영역이 foot 밖으로 {m['actsRight'] - m['footRight']}px 넘침")
                if m["footOverflow"]:
                    fails.append(f"A3 {tag}: foot 가로 overflow — 버튼이 잘린다")
                if m["pageHScroll"]:
                    fails.append(f"A4 {tag}: 페이지 가로 스크롤 발생")
                for btn in m["btns"]:
                    if btn["w"] < WCAG_MIN or btn["h"] < WCAG_MIN:
                        warns.append(
                            f"W1 {tag}: {btn['cls']} {btn['w']}×{btn['h']} < WCAG {WCAG_MIN}×{WCAG_MIN}")
        b.close()

    # A5 — 긴 이름이 버튼을 밀어내지 않는다: 액션 폭이 모든 조합에서 동일해야 한다.
    if len(acts_widths) != 1:
        fails.append(f"A5: 액션 영역 폭이 조합마다 다르다 {sorted(acts_widths)} — 이름이 버튼을 밀어낸다")
    long_clipped = [t for t, m in rows if "긴명" in t and m["nameClipped"]]
    if not long_clipped:
        fails.append("A5: 긴 파일명이 어느 폭에서도 잘리지 않는다 — 재현이 낡았거나 ellipsis 가 죽었다")

    for tag, m in rows:
        bs = " ".join(f"{x['cls']}={x['w']}×{x['h']}" for x in m["btns"])
        print(f"  {tag:>14}  row={m['rowW']} acts={m['actsW']}@{m['actsLeft']}..{m['actsRight']}"
              f" foot→{m['footRight']}  {bs}  이름잘림={m['nameClipped']}")

    print()
    if warns:
        uniq = sorted({w.split(": ", 1)[1] for w in warns})
        print(f"WARN — 히트 영역 WCAG 미달 {len(warns)}건 ({len(uniq)}종, 이 cycle 범위 밖·선행 상태):")
        for u in uniq:
            print("  !", u)
        print()
    if fails:
        print(f"FAIL — {len(fails)}건")
        for f in fails:
            print("  ✗", f)
        return 1
    print(f"OK — {len(rows)} 조합(폭 {len(WIDTHS)}종 × 이름 2종) A1~A5 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())

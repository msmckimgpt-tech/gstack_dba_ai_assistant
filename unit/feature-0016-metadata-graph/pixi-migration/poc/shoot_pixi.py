# feature-0016 §78 Phase A — pixi-poc 스크린샷 + 팬/줌 프레임타임 하네스 (shoot.py 계보)
# usage: python3 shoot_pixi.py file:///.../pixi-poc.html <outdir>
# 주의: WSL headless Chromium 의 WebGL 은 SwiftShader(소프트웨어) — 절대 성능은 참고치.
#       공정 비교를 위해 동일 headless 에서 G6 POC 도 같은 방식으로 측정한다. 정식 게이트는 win-browser 실 Chrome.
import sys, json
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=2)
    con = []
    pg.on("console", lambda m: con.append(f"[{m.type}] {m.text}"))
    pg.on("pageerror", lambda e: con.append(f"[err] {e}"))
    pg.goto(URL, wait_until="networkidle"); pg.wait_for_timeout(1800)
    ok = pg.evaluate("!!window.poc")
    print("READY", ok, "ERR", pg.evaluate("window.__err||[]"))
    if ok:
        print("STATS", pg.evaluate("window.poc.stats()"))
        # ① 디자인 씬 — 줌 배율별 스크린샷 (D1/D2/D3/D5)
        pg.evaluate("window.poc.fit()"); pg.wait_for_timeout(400)
        pg.screenshot(path=f"{OUT}/pixi_design_fit.png")
        for z in [0.35, 0.5, 1.0, 2.5]:
            pg.evaluate(f"window.poc.zoomTo({z})"); pg.wait_for_timeout(300)
            pg.screenshot(path=f"{OUT}/pixi_design_z{str(z).replace('.','_')}.png")
        # ② 실측 등가 씬(≈882노드 emitted 등가: 5스키마 × 24T × 6C) 팬/줌
        pg.evaluate("window.poc.buildPerfScene(5,24,6)"); pg.wait_for_timeout(300)
        pg.evaluate("window.poc.fit()"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{OUT}/pixi_perf_882.png")
        r1 = pg.evaluate("window.poc.panTest(4)"); print("PAN_882", json.dumps(r1))
        z1 = pg.evaluate("window.poc.zoomTest(4)"); print("ZOOM_882", json.dumps(z1))
        # ③ 스트레스(20×50×10 ≈ 11,020 요소) 팬
        pg.evaluate("window.poc.buildPerfScene(20,50,10)"); pg.wait_for_timeout(800)
        pg.evaluate("window.poc.fit()"); pg.wait_for_timeout(400)
        pg.screenshot(path=f"{OUT}/pixi_perf_11k.png")
        r2 = pg.evaluate("window.poc.panTest(4)"); print("PAN_11K", json.dumps(r2))
        z2 = pg.evaluate("window.poc.zoomTest(4)"); print("ZOOM_11K", json.dumps(z2))
    print("CONSOLE(last 12):", "\n".join(con[-12:]))
    b.close()

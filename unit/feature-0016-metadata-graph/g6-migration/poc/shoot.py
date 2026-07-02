import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1];OUT="/tmp/claude-0/-root-download-docker-mysql-ai-delegated-dev/f156b407-0890-45a4-adff-60153853ba02/scratchpad"
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);pg=b.new_page(viewport={"width":1280,"height":860},device_scale_factor=2)
    con=[];pg.on("console",lambda m:con.append(f"[{m.type}] {m.text}"));pg.on("pageerror",lambda e:con.append(f"[err] {e}"))
    pg.goto(URL,wait_until="networkidle");pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{OUT}/p3_1.png")
    ok=pg.evaluate("!!window.poc");print("READY",ok,"ERR",pg.evaluate("window.__err||[]"))
    if ok:
        for step in ["expand('dk_data_release','Payment')","expand('dk_game_release_1','Achievement')",
                     "mark('analyzed','dk_game_release_1','Achievement')","mark('running','dk_data_release','Payment')","fit()"]:
            pg.evaluate(f"window.poc.{step}");pg.wait_for_timeout(700)
        pg.screenshot(path=f"{OUT}/p3_2.png")
        pg.evaluate("window.poc.collapse('dk_data_release','Payment')");pg.wait_for_timeout(500)
        pg.evaluate("window.poc.fit()");pg.wait_for_timeout(600)
        pg.screenshot(path=f"{OUT}/p3_3.png")
    print("LOG:\n"+pg.evaluate("document.getElementById('log').textContent"))
    b.close()

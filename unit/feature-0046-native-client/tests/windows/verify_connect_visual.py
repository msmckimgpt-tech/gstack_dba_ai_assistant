import asyncio,importlib.util,json,mimetypes,re,sys
from pathlib import Path
from urllib.parse import urlparse,unquote
from playwright.async_api import async_playwright
ROOT=Path.cwd(); STATIC=ROOT/'unit/feature-0003-agent-web-ui/src/static'
OUT=ROOT/'unit/feature-0046-native-client/docs/artifacts/20260908-connect-discovery'
OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('wb',ROOT/'bin/win-browser.py');wb=importlib.util.module_from_spec(spec);spec.loader.exec_module(wb)
EP=wb._resolve_endpoint()
WIN={'id':'claude','name':'claude','where':'windows','path':'C:/claude.exe','usable':True}
WSL={'id':'claude (WSL · Ubuntu · alice)','name':'claude','where':'wsl','path':'/home/alice/bin/claude','distro':'Ubuntu','user':'alice','usable':True}
CODEX={'id':'codex (WSL · Ubuntu · root)','name':'codex','where':'wsl','path':'/root/bin/codex','distro':'Ubuntu','user':'root','usable':True}
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.connect_over_cdp(EP)
  results=[]
  for name,small,standalone,failure in [('desktop',False,False,False),('mobile',True,False,False),('standalone',False,True,False),('failure',False,False,True)]:
   ctx=await browser.new_context(ignore_https_errors=True,viewport={'width':390 if small else 1440,'height':844 if small else 1050})
   page=await ctx.new_page();errors=[];calls=[];connected={}
   page.on('pageerror',lambda e:errors.append(str(e)))
   async def route(r):
    url=urlparse(r.request.url);path=url.path
    if url.hostname=='127.0.0.1':
     action=path.strip('/');body=r.request.post_data_json;calls.append(action)
     res={'ok':True}
     if action=='status':res.update(resident=True,connection_session='fixture',connections=list(connected.values()),client_features=['platform_connections'])
     elif action in ('discover','discovery_status'):res.update(runtimes=[WIN,WSL,CODEX],preferences={},discovering=False,completed_platforms=['claude','codex','gemini'])
     elif action=='connect':
      if failure:res={'ok':False,'detail':'연결을 확인하지 못했습니다. 다시 시도해 주세요.'}
      else:
       st=next(s for s in [WIN,WSL,CODEX] if s['id']==body['id']);connected[st['name']]=st
     await r.fulfill(json=res,headers={'Access-Control-Allow-Origin':'https://localhost','Access-Control-Allow-Headers':'content-type,x-dqa-nonce','Access-Control-Allow-Private-Network':'true'});return
    if path=='/api/ai/connect/token':await r.fulfill(json={'connection_session':'fixture','launch':{'protocol':'dqa-connect://start?base=https%3A%2F%2Flocalhost&token=fixture'}});return
    if path=='/api/ai/connect/status':await r.fulfill(json={'logged_in':True,'connected':False,'listening':False,'ai_ready':None,'caps_pending':False,'compose_blocked':False,'username':'DQA','last_os':'windows','client_download':None});return
    if path=='/static/app.js':
     await r.fulfill(content_type='text/javascript',body='export function showToast(m){ const e=document.getElementById("toast");e.textContent=m;e.classList.add("show");window.__toasts=(window.__toasts||[]).concat(m); }');return
    if path.startswith('/static/'):
     file=STATIC/unquote(path[len('/static/'):])
     if file.is_file():await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream');return
    if path in ('/','/ai/connect'):
     html=(STATIC/('ai-connect.html' if standalone else 'index.html')).read_text()
     if not standalone:
      html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S)
      html=html.replace('</body>','<script type="module">import {bindConnectModal,refreshConnState} from "/static/app/connect-modal.js?v=dev";bindConnectModal();refreshConnState();document.querySelectorAll(".auth-overlay").forEach(e=>e.hidden=true);</script></body>')
     await r.fulfill(body=html,content_type='text/html');return
    await r.fulfill(json={})
   await ctx.route('**/*',route)
   await page.goto('https://localhost/'+('ai/connect' if standalone else '')+'?client_port=32145&client_nonce=fixture',wait_until='domcontentloaded')
   await page.locator('[data-platform="claude"] input').first.wait_for(timeout=15000)
   if not standalone:assert await page.locator('#connectModalOverlay').is_visible(),'startup must show only required location choice'
   assert await page.locator('[data-platform="claude"] input').count()==2
   await page.screenshot(path=str(OUT/f'{name}-choices.png'),full_page=True)
   await page.locator('[data-platform="claude"] input').nth(1).click()
   await page.wait_for_function('document.querySelector("[data-platform=claude]").dataset.state === '+json.dumps('error' if failure else 'connected'))
   await page.screenshot(path=str(OUT/f'{name}-result.png'),full_page=True)
   if not failure:
    assert await page.locator('[data-state="connected"]').count()==2
   if small:
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'horizontal overflow'
   if not standalone:
    await page.keyboard.press('Escape');assert not await page.locator('#connectModalOverlay').is_visible()
   assert not errors,errors
   results.append({'scenario':name,'pass':True,'connected':len(connected),'page_errors':errors})
   await ctx.close()
  print(json.dumps({'Environment':'Windows-browser','browser':browser.version,'results':results},ensure_ascii=False))
  (OUT/'visual-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  await browser.close()
asyncio.run(main())

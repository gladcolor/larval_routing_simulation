"""Optional headless-browser smoke test. Its temporary HTTP server is closed."""
from pathlib import Path
import functools, threading, json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
WEB=HERE.parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(WEB)))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1500,'height':1000},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}/route_simulation.html',wait_until='domcontentloaded')
        page.wait_for_function("typeof quadrantLayer!=='undefined' && quadrantLayer && document.getElementById('tdNote').textContent.includes('Four road-aligned')",timeout=45000)
        result=page.evaluate("({sectors:dat().sectors,groups:quadrantLayer.getLayers().length,points:dat().hab.length,note:document.getElementById('tdNote').textContent})")
        assert result['sectors']==['NE','NW','SE','SW'] and result['groups']==2 and result['points']==1518
        page.evaluate("st.camp='Dry24';update()")
        page.wait_for_function('quadrantLayer===null',timeout=20000)
        page.evaluate("st.camp='Predicted';update()")
        page.wait_for_function('quadrantLayer!==null',timeout=20000)
        page.screenshot(path=str(HERE/'outputs/browser_preview.png'),full_page=True)
        assert not errors,errors
        (HERE/'outputs/browser_validation.json').write_text(json.dumps({'passed':True,'javascript_errors':errors,'initial_state':result,'historical_overlay_hidden':True},indent=2),encoding='utf8')
        browser.close()
        print('PASS: live page shows four labels and boundary layers; historical campaigns hide the overlay; no JavaScript errors.')
finally:
    server.shutdown();server.server_close();thread.join(timeout=3)

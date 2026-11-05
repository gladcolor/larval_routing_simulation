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
        assert page.locator('#quadrantLabel').inner_text()=='Four-quadrant sweep (one quadrant at a time)'
        assert page.locator('#covleg [data-algo="sector"]').inner_text()=='Four-quadrant sweep'
        assert 'sector' not in page.locator('body').inner_text().lower()
        assert page.evaluate("habMarkers.every(m=>m.getPopup().getContent().includes('quadrant '))")
        zero=page.evaluate("""() => {
          if(st.day!==0 || document.getElementById('dayRange').min!=='0') throw Error('Not starting at day zero');
          const original={algo:st.algo,teams:st.teams};let checked=0;
          for(const algo of ALGOLIST) for(const teams of [1,2,3]){
            st.algo=algo;st.teams=teams;st.day=0;drawRoutes();
            const cov=coverage(algo,teams);
            if(cov.habCum[0]!==0 || cov.larvPct[0]!==0 || teamDaysUsed(algo,teams,0)!==0) throw Error('Progress at day zero');
            if(habMarkers.some(m=>m.options.fillColor!=='#39424e')) throw Error('Treated marker at day zero');
            if(routeLayer.getLayers().some(layer=>layer instanceof L.Polyline)) throw Error('Travelled path at day zero');
            checked++;
          }
          Object.assign(st,original);update();
          return {policy_team_combinations:checked,habitats:document.getElementById('vHab').textContent,priority:document.getElementById('vLarv').textContent};
        }""")
        page.screenshot(path=str(HERE/'outputs/browser_day0.png'),full_page=True)
        page.locator('#dayRange').fill('1')
        page.locator('#dayRange').dispatch_event('input')
        page.wait_for_function("st.day===1 && !document.getElementById('vHab').textContent.startsWith('0 /')")
        opacity=page.evaluate("""() => {
          const max=Math.max(1,...dat().hab.map(h=>h[2])),cap=larvCap(max);
          for(const team of [-1,0,1]){
            const values=[0,.1,.5,1,2].map(t=>habitatStyle(t*cap,max,team));
            for(let i=1;i<values.length;i++) if(values[i].fillOpacity<values[i-1].fillOpacity) throw Error('Non-monotonic opacity');
            if(values[0].fillOpacity>.05 || values[0].opacity>.05) throw Error('Low priority too opaque');
          }
          function checkMarkers(){
            habMarkers.forEach((m,i)=>{
              const expected=habitatStyle(dat().hab[i][2],max,m.options.fillColor==='#39424e'?-1:0);
              if(Math.abs(m.options.fillOpacity-expected.fillOpacity)>1e-12 || m.options.opacity!==expected.opacity) throw Error('Marker style mismatch');
              if(!m.getPopup()) throw Error('Popup missing');
            });
          }
          checkMarkers();
          const initial=st.algo;
          st.algo='blind';drawRoutes();checkMarkers();
          st.algo=initial;drawRoutes();
          startAnim();
          if(!anim) throw Error('Animation did not start');
          cancelAnimationFrame(anim.raf);animStep(anim.start);cancelAnimationFrame(anim.raf);
          if(st.day!==0 || anim.treated.size!==0 || document.getElementById('vLarv').textContent!=='0%') throw Error('Animation initial frame is not day zero');
          animStep(anim.start+1000);checkMarkers();
          stopAnim();st.day=1;update();
          return {treated:[0,.5,1].map(t=>habitatOpacity(t*cap,cap)),untreated:[0,.5,1].map(t=>habitatOpacity(t*cap,cap,false)),ramp:document.getElementById('ramp').style.background};
        }""")
        page.evaluate("st.camp='Dry24';update()")
        page.wait_for_function('quadrantLayer===null',timeout=20000)
        assert page.locator('#priorityLabel').inner_text()=='larvae per habitat'
        assert page.locator('#quadrantLabel').inner_text()=='Planning-area sweep (historical groups)'
        assert page.evaluate("habMarkers.every(m=>m.getPopup().getContent().includes('planning area '))")
        page.evaluate("st.camp='Predicted';update()")
        page.wait_for_function('quadrantLayer!==null',timeout=20000)
        assert page.locator('#priorityLabel').inner_text()=='predicted priority'
        assert page.locator('#covleg [data-algo="sector"]').inner_text()=='Four-quadrant sweep'
        page.screenshot(path=str(HERE/'outputs/browser_preview.png'),full_page=True)
        assert not errors,errors
        (HERE/'outputs/browser_validation.json').write_text(json.dumps({'passed':True,'javascript_errors':errors,'initial_state':result,'historical_overlay_hidden':True,'day_zero':zero,'opacity':opacity},indent=2),encoding='utf8')
        browser.close()
        print('PASS: live page shows four labels and boundary layers; historical campaigns hide the overlay; no JavaScript errors.')
finally:
    server.shutdown();server.server_close();thread.join(timeout=3)

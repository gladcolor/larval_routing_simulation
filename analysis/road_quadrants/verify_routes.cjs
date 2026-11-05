'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
const html=read('route_simulation.html');
assert(html.includes('src="route_sim_data_four_quadrants.js"'));
assert(html.includes('src="route_quadrants.js"'));
assert(html.includes('drawQuadrants(); buildHab();'));
const code=html.slice(html.indexOf('const $=id=>'),html.indexOf('/* ===================== MAP ===================== */'));
const contexts={};
for(const [name,file] of [['old','route_sim_data.js'],['new','route_sim_data_four_quadrants.js']]){
 const c={};vm.createContext(c);vm.runInContext(read(file)+'\n'+read('route_graph.js')+'\n'+code,c);contexts[name]=c;
}
const get=(c,expr)=>JSON.parse(JSON.stringify(vm.runInContext(expr,c)));
const old=get(contexts.old,'SIM'),fresh=get(contexts.new,'SIM');
assert.deepEqual(fresh.Jigjiga.Predicted.sectors,['NE','NW','SE','SW']);
for(const city of Object.keys(old))for(const camp of Object.keys(old[city])){
 const a=old[city][camp],b=fresh[city][camp];
 if(city!=='Jigjiga'||camp!=='Predicted'){assert.deepEqual(a,b);continue;}
 assert.deepEqual(a.hab.map(h=>[...h.slice(0,3),h[4]]),b.hab.map(h=>[...h.slice(0,3),h[4]]));
 assert.deepEqual(a.habNode,b.habNode);assert.equal(a.depot,b.depot);
}
const results={};
for(const [name,c] of Object.entries(contexts)){
 results[name]=get(c,`(()=>{
 st={city:'Jigjiga',camp:'Predicted',speed:25,service:10,hours:8,teams:1};
 const d=dat();ensureMatrix(d);const result={};
 for(const teams of [1,2,3])for(const algo of ['greedy','sector','nn','zigzag']){
  const routes=computeRoutes(algo,teams),{depots}=zonesFor(d,teams),cost=costArray(d),fac=ttFactor();
  let events=[];
  routes.forEach((r,t)=>{let prev=depots[t],time=0;r.forEach(([i,day])=>{time+=d.lm[prev][i]*fac+cost[i];
   if(Math.floor(time/28800)+1!==day)throw Error('Clock mismatch');
   events.push({site:i,seconds:time,team:t,priority:d.hab[i][2]});prev=i;});});
  events.sort((a,b)=>a.seconds-b.seconds||a.site-b.site);
  const total=d.hab.reduce((a,h)=>a+h[2],0);let cum=0;
  const thresholds={};for(const e of events){cum+=e.priority;for(const f of [.5,.8,.9])if(cum>=f*total&&thresholds[f]===undefined)thresholds[f]=e.seconds/28800;}
  result[teams+'team_'+algo]={routes,days_to_priority_share:thresholds,finish_working_days:Math.max(...events.map(e=>e.seconds))/28800};
 }
 return result;})()`);
}
const summary={};
for(const key of Object.keys(results.old)){
 const a=results.old[key],b=results.new[key];
 for(const run of [a,b]){const ids=run.routes.flat().map(x=>x[0]);assert.equal(ids.length,1518);assert.equal(new Set(ids).size,1518);}
 const same=JSON.stringify(a.routes)===JSON.stringify(b.routes);
 if(!key.endsWith('sector'))assert(same,key+' unexpectedly changed');
 summary[key]={same_route_and_day:same,old_finish_days:a.finish_working_days,new_finish_days:b.finish_working_days,
  old_days_to_priority_share:a.days_to_priority_share,new_days_to_priority_share:b.days_to_priority_share};
}
const out=path.join(__dirname,'outputs');fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'route_validation.json'),JSON.stringify(summary,null,2)+'\n');
console.log('PASS: four labels; unchanged other campaigns, priorities, locations, depot and road nodes; 24 complete unique-visit routes; exact clocks; non-sector routes unchanged for 1, 2 and 3 teams.');
console.log(JSON.stringify(summary['1team_sector'],null,2));

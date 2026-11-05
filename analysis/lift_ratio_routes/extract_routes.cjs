'use strict';
// Run the existing dashboard's pure routing functions, without a browser or changes to the app.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.join(__dirname,'data');
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const html=read('route_simulation.html');
const start=html.indexOf('const $=id=>'),end=html.indexOf('/* ===================== MAP ===================== */',start);
assert(start>=0&&end>start,'Dashboard extraction markers changed');
const context={};vm.createContext(context);
vm.runInContext(read('route_sim_data_four_quadrants.js')+'\n'+read('route_graph.js')+'\n'+html.slice(start,end),context,{timeout:120000});
const result=vm.runInContext(`(()=>{
 st={city:'Jigjiga',camp:'Predicted',teams:1,speed:25,service:10,hours:8};
 const d=dat();ensureMatrix(d);const cost=costArray(d),fac=ttFactor(),day_s=st.hours*3600;
 const strategies=['greedy','sector','nn','zigzag'];
 const routes={};
 for(const strategy of strategies){
  const r=computeRoutes(strategy,1)[0];let elapsed=0,drive=0,walk=0,previous=d.depot;
  routes[strategy]=r.map(([site,day],i)=>{
   const metres=d.lm[previous][site],travel=metres*fac;
   elapsed+=travel+cost[site];drive+=metres;walk+=cost[site]-st.service*60;previous=site;
   if(Math.floor(elapsed/day_s)+1!==day)throw Error('Clock mismatch');
   return {visit:i+1,site,day,completion_seconds:elapsed,cumulative_drive_m:drive,cumulative_walk_seconds:walk,priority:d.hab[site][2]};
  });
 }
 const g=GRAPH.Jigjiga;
 const roads=g.edges.filter(e=>e[0]<e[1]).map(e=>[g.nodes[e[0]],...(e[3]>=0?g.geom[e[3]]:[]),g.nodes[e[1]]]);
 return {scenario:{city:'Jigjiga',dataset:'Predicted',teams:1,drive_kmh:25,walk_kmh:WALK_KMH,service_minutes:10,hours_per_day:8,depot_index:d.depot,horizon_days:SIMD},sites:d.hab,roads,routes};
})()`,context,{timeout:120000});
result.scenario.sector_definition='Four road-aligned planning quadrants';
result.scenario.sector_names=['NE','NW','SE','SW'];
assert.deepEqual(Array.from(vm.runInContext('dat().sectors',context)),result.scenario.sector_names);
for(const [name,rows]of Object.entries(result.routes)){
 assert.equal(rows.length,result.sites.length,name+' must visit the entire population');
 assert.equal(new Set(rows.map(r=>r.site)).size,result.sites.length);
 assert(rows.every(r=>Number.isFinite(r.completion_seconds)&&r.completion_seconds>0));
}
result.provenance={source_files:Object.fromEntries(['route_simulation.html','route_sim_data_four_quadrants.js','route_graph.js'].map(f=>[f,crypto.createHash('sha256').update(read(f)).digest('hex')])),evaluation:'Legacy mapped priorities, not independent observed outcomes. Single common depot, one deterministic run per strategy.',clock:'Cumulative working seconds, continuous across days, without nightly depot return. Value credited only on service completion.',road_display:'Undirected display subset of shipped road geometries; computations retain the full directed graph.'};
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'routes.json'),JSON.stringify(result));
console.log(JSON.stringify({sites:result.sites.length,strategies:Object.fromEntries(Object.entries(result.routes).map(([k,r])=>[k,{stops:r.length,finish_day:r.at(-1).day,drive_km:r.at(-1).cumulative_drive_m/1000}]))}));

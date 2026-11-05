'use strict';
// Extract actual directed shortest-path geometry for fixed-budget route illustrations.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
const html=read('route_simulation.html'),start=html.indexOf('const $=id=>'),end=html.indexOf('/* ===================== MAP ===================== */',start);
assert(start>=0&&end>start);
const ctx={};vm.createContext(ctx);
vm.runInContext(read('route_sim_data_four_quadrants.js')+'\n'+read('route_graph.js')+'\n'+html.slice(start,end),ctx,{timeout:120000});
const result=vm.runInContext(`(()=>{
 st={city:'Jigjiga',camp:'Predicted',teams:1,speed:25,service:10,hours:8};
 const d=dat(),g=GRAPH.Jigjiga;ensureMatrix(d);
 const cost=costArray(d),fac=ttFactor(),adj=buildAdj(),pathCache={};
 function shortest(src,dst){
  const key=src+'_'+dst;if(pathCache[key])return pathCache[key];
  if(src===dst)return {metres:0,nodes:[src],edge_lengths:[],poly:[g.nodes[src]]};
  const dist=new Float64Array(g.nodes.length).fill(Infinity),prev=Array(g.nodes.length).fill(null),done=new Uint8Array(g.nodes.length);
  const heap=new MinHeap();dist[src]=0;heap.push(src,0);
  while(heap.size){const u=heap.pop();if(done[u])continue;done[u]=1;if(u===dst)break;
   for(const [v,len,geom]of adj[u]){const nd=dist[u]+len;if(nd<dist[v]){dist[v]=nd;prev[v]=[u,len,geom];heap.push(v,nd);}}
  }
  if(!Number.isFinite(dist[dst]))throw Error('Unreachable leg: no straight-line fallback permitted');
  const edges=[];let node=dst;
  while(node!==src){const p=prev[node];if(!p)throw Error('Broken predecessor chain');edges.push([p[0],node,p[1],p[2]]);node=p[0];}
  edges.reverse();const poly=[g.nodes[src]];
  for(const [u,v,len,geom]of edges){if(geom>=0)poly.push(...g.geom[geom]);poly.push(g.nodes[v]);}
  return pathCache[key]={metres:dist[dst],nodes:[src,...edges.map(e=>e[1])],edge_lengths:edges.map(e=>e[2]),poly};
 }
 const cases={};
 for(const [id,policy,teams,days]of [['greedy_1team_2days','greedy',1,2],['nn_1team_2days','nn',1,2],['sector_2teams_1day','sector',2,1]]){
  const routes=computeRoutes(policy,teams),depots=zonesFor(d,teams).depots,plan=[];
  for(let team=0;team<teams;team++){
   let previous=depots[team],elapsed=0;const stops=[];
   for(const [site,day]of routes[team]){
    const metres=d.lm[previous][site];elapsed+=metres*fac+cost[site];
    if(Math.floor(elapsed/28800)+1!==day)throw Error('Completion day mismatch');
    if(elapsed>days*28800)break;
    const leg=shortest(d.habNode[previous],d.habNode[site]);
    if(Math.abs(leg.metres-metres)>1e-6)throw Error('Shortest-path distance mismatch');
    stops.push({site,visit:stops.length+1,completion_seconds:elapsed,priority:d.hab[site][2],from_site:previous,road_path:leg});
    previous=site;
   }
   plan.push({team:team+1,depot_site:depots[team],depot_node:g.nodes[d.habNode[depots[team]]],stops});
  }
  const all=plan.flatMap(p=>p.stops),total=d.hab.reduce((s,h)=>s+h[2],0);
  cases[id]={policy,teams,working_days:days,available_team_days:teams*days,plans:plan,
   visited_sites:all.length,priority_fraction:all.reduce((s,v)=>s+v.priority,0)/total,drive_km:all.reduce((s,v)=>s+v.road_path.metres,0)/1000};
 }
 const seen=new Set(),roads=[];
 for(const [u,v,len,geom]of g.edges){const poly=[g.nodes[u],...(geom>=0?g.geom[geom]:[]),g.nodes[v]];
  const a=JSON.stringify(poly),b=JSON.stringify(poly.slice().reverse()),key=a<b?a:b;if(!seen.has(key)){seen.add(key);roads.push(poly);}}
 return {sites:d.hab,roads,cases,scenario:{city:'Jigjiga',dataset:'Predicted',drive_kmh:25,walk_kmh:WALK_KMH,service_minutes:10,hours_per_day:8},
  limitations:'Only completed visits and their inbound road legs are shown; travel toward an unfinished next visit is omitted. No nightly depot return. Two-team sector runs use geography-based zone starts but do not impose exclusive zone membership on sector selection. Legacy predicted priorities, not treatment effects.'};
})()`,ctx,{timeout:120000});
result.scenario.sector_definition='Four road-aligned planning quadrants';
result.scenario.sector_names=['NE','NW','SE','SW'];
assert.deepEqual(Array.from(vm.runInContext('dat().sectors',ctx)),result.scenario.sector_names);
for(const c of Object.values(result.cases)){
 const stops=c.plans.flatMap(p=>p.stops);assert.equal(stops.length,new Set(stops.map(s=>s.site)).size);
 for(const p of c.plans){let prev=0;for(const s of p.stops){assert(s.completion_seconds>prev&&s.completion_seconds<=c.working_days*28800);prev=s.completion_seconds;assert(Math.abs(s.road_path.edge_lengths.reduce((a,b)=>a+b,0)-s.road_path.metres)<1e-6);}}
}
result.provenance={source_sha256:Object.fromEntries(['route_simulation.html','route_sim_data_four_quadrants.js','route_graph.js'].map(f=>[f,crypto.createHash('sha256').update(read(f)).digest('hex')])),path_method:'Dijkstra on shipped directed road graph; each path length verified against the exact matrix used by the dashboard; no straight-line fallback.'};
fs.writeFileSync(path.join(__dirname,'data/route_paths.json'),JSON.stringify(result));
console.log(JSON.stringify(Object.fromEntries(Object.entries(result.cases).map(([k,c])=>[k,{sites:c.visited_sites,priority_pct:100*c.priority_fraction,drive_km:c.drive_km,per_team:c.plans.map(p=>p.stops.length)}])),null,2));

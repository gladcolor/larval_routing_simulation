"""Verify displayed routes against original directed graph edges and timing assumptions."""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET
from PIL import Image
import numpy as np

H=Path(__file__).resolve().parent;root=H.parent.parent
D=json.loads((H/'data/route_paths.json').read_text())
for f,sha in D['provenance']['source_sha256'].items():
    assert hashlib.sha256((root/f).read_bytes()).hexdigest()==sha
text=(root/'route_graph.js').read_text(encoding='utf-8')
graph,_=json.JSONDecoder().raw_decode(text[text.index('=',text.index('const GRAPH'))+1:].lstrip())
g=graph['Jigjiga'];edges={}
for u,v,length,geom in g['edges']:edges.setdefault((u,v),[]).append((length,geom))
sites=np.array(D['sites']);total=sites[:,2].sum()
for key,c in D['cases'].items():
    unique=set();prize=0.;km=0.
    for p in c['plans']:
        previous=p['depot_site'];elapsed=0.;last_node=None
        for s in p['stops']:
            assert s['site'] not in unique;unique.add(s['site'])
            assert s['from_site']==previous;previous=s['site']
            leg=s['road_path'];nodes=leg['nodes']
            assert len(nodes)==len(leg['edge_lengths'])+1
            if last_node is not None:assert nodes[0]==last_node
            else:assert g['nodes'][nodes[0]]==p['depot_node']
            last_node=nodes[-1]
            assert leg['poly'][0]==g['nodes'][nodes[0]] and leg['poly'][-1]==g['nodes'][nodes[-1]]
            for u,v,length in zip(nodes[:-1],nodes[1:],leg['edge_lengths']):assert any(abs(length-e[0])<1e-8 for e in edges[(u,v)])
            assert abs(sum(leg['edge_lengths'])-leg['metres'])<1e-8
            elapsed+=leg['metres']*3600/25000+600+2*sites[s['site'],4]/(4300/3600)
            assert abs(elapsed-s['completion_seconds'])<1e-6
            assert elapsed<=c['working_days']*28800
            assert sites[s['site'],2]==s['priority'];prize+=s['priority'];km+=leg['metres']/1000
    assert len(unique)==c['visited_sites']
    assert abs(prize/total-c['priority_fraction'])<1e-12
    assert abs(km-c['drive_km'])<1e-8
for name in ['05_route_policy_paths','06_two_team_route_paths']:
    ET.parse(H/'figures'/f'{name}.svg')
    with Image.open(H/'figures'/f'{name}.png') as im:
        assert im.width>=3600 and im.height>=2700
        im.verify()
print('PASS: all plotted legs follow original directed edges; lengths, completion times, unique visits, priority totals and both figure exports verified.')

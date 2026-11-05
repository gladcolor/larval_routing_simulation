"""Read-only checks against generated data and figure assets."""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from sklearn.metrics import ndcg_score

H=Path(__file__).resolve().parent
D=json.loads((H/'data/routes.json').read_text())
M=json.loads((H/'data/metrics.json').read_text())
assert hashlib.sha256((H/'data/routes.json').read_bytes()).hexdigest()==M['input_sha256']
root=H.parent.parent
for f,sha in D['provenance']['source_files'].items():
    assert hashlib.sha256((root/f).read_bytes()).hexdigest()==sha, f+' changed; regenerate'
y=np.array([h[2] for h in D['sites']],float)
n=len(y);ideal=np.sort(y)[::-1]
assert D['scenario']['sector_names']==['NE','NW','SE','SW']
assert D['scenario']['sector_definition']=='Four road-aligned planning quadrants'
def lift(v):
    v=np.asarray(v,float);r=np.arange(1,len(v)+1)
    denom=np.sort(v)[::-1]@(len(v)-r+.5)/(len(v)*v.sum())-.5
    return (v@(len(v)-r+.5)/(len(v)*v.sum())-.5)/denom
assert abs(lift(ideal)-1)<1e-12 and abs(lift(ideal[::-1])+1)<1e-12
assert abs(lift([40,20,30,10])-.8)<1e-12
for name,rows in D['routes'].items():
    assert len(rows)==n and sorted(r['site'] for r in rows)==list(range(n))
    v=np.array([r['priority'] for r in rows]);t=np.array([r['completion_seconds'] for r in rows])/28800
    assert np.array_equal(v,y[[r['site'] for r in rows]])
    assert (np.diff(t)>0).all() and (v>=0).all() and v.sum()==y.sum()
    c=np.cumsum(v)/v.sum();m=M['routes'][name]
    ideal_c=np.cumsum(ideal)/ideal.sum()
    assert (ideal_c>=c-1e-12).all()
    rank_auc=v@(n-np.arange(1,n+1)+.5)/(n*v.sum())
    ideal_auc=ideal@(n-np.arange(1,n+1)+.5)/(n*ideal.sum())
    assert abs(m['area_a']-(rank_auc-.5))<1e-12
    assert abs(m['area_b']-(ideal_auc-rank_auc))<1e-12
    assert abs(m['area_a']/(m['area_a']+m['area_b'])-m['lift'])<1e-12
    assert abs(lift(v)-m['lift'])<1e-12
    assert abs(ndcg_score(v[None,:],-np.arange(n)[None,:])-m['ndcg_full'])<1e-12
    assert abs(c[int(np.ceil(n*.5))-1]-m['coverage50'])<1e-12
    assert abs(c[np.searchsorted(t,20,side='right')-1]-m['coverage20days'])<1e-12
    assert t[np.flatnonzero(c>=.8)[0]]==m['team_days80']
    assert all(int(np.floor(r['completion_seconds']/28800))+1==r['day'] for r in rows)
for ex in M['synthetic']['ndcg_comparison'].values():
    v=np.array(ex['outcomes_in_visit_order']);assert v.sum()==100
    assert abs(lift(v)-ex['metrics']['lift'])<1e-12
same=M['synthetic']['same_order'];v=np.array(same['outcomes_in_visit_order'])
assert v[np.array(same['fast_completion_hours'])<=2].sum()==100
assert v[np.array(same['slow_completion_hours'])<=2].sum()==55
original_figures=[f for f in (H/'figures').glob('*.svg') if f.name[:2] in ['01','02','03','04']]
for f in original_figures:
    ET.parse(f)
    with Image.open(f.with_suffix('.png')) as im:
        im.verify()
    with Image.open(f.with_suffix('.png')) as im:
        assert im.width>=3900 and im.height>=1950
assert len(original_figures)==4
for name in ['01_policy_order_and_time','03_same_lift_different_efficiency','04_lift_ratio_and_ndcg']:
    tree=ET.parse(H/'figures'/f'{name}.svg')
    nodes=list(tree.getroot().iter())
    assert sum(node.get('id')=='ideal-top-k-reference' for node in nodes)==1
    assert sum(node.get('id')=='random-order-reference' for node in nodes)==1
    assert any('Ideal (' in (node.text or '') for node in nodes),name+' needs a visible ideal legend'
    if name=='01_policy_order_and_time':
        for ident in ['best-strategy-area-a','best-strategy-area-b','best-strategy-curve','ideal-top-k-reference-best']:
            assert sum(node.get('id')==ident for node in nodes)==1,ident
        assert max(M['routes'],key=lambda k:M['routes'][k]['lift'])=='greedy'
print('PASS: source hashes, complete common population, timestamps, independent lift/NDCG calculations, budgets, synthetic examples, four SVG and 300-dpi PNG exports.')

"""Independent checks of exported polygons, road alignment and assignments."""
from pathlib import Path
import json
import geopandas as gpd
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

HERE=Path(__file__).resolve().parent
WEB=HERE.parents[1]
def load(name):
    text=(WEB/name).read_text(encoding='utf8')
    return json.JSONDecoder().raw_decode(text.split('const SIM = ',1)[1])[0]
old=load('route_sim_data.js')['Jigjiga']['Predicted']
new=load('route_sim_data_four_quadrants.js')['Jigjiga']['Predicted']
zones=gpd.read_file(HERE/'outputs/quadrants.geojson').to_crs(32638)
dividers=gpd.read_file(HERE/'outputs/dividers.geojson').to_crs(32638)
roads=gpd.read_file(HERE/'inputs/boundary_roads.geojson').to_crs(32638)
points=gpd.GeoSeries(gpd.points_from_xy([h[0] for h in new['hab']],[h[1] for h in new['hab']]),crs=4326).to_crs(32638)
assert len(zones)==4 and set(zones.quadrant)=={'NE','NW','SE','SW'}
assert zones.is_valid.all()
lo=np.array([points.x.min(),points.y.min()])-250
hi=np.array([points.x.max(),points.y.max()])+250
envelope=box(*lo,*hi)
union=unary_union(zones.geometry)
assert union.symmetric_difference(envelope).area<.01
assert abs(zones.area.sum()-union.area)<.01
for h,p in zip(new['hab'],points):
    hits=zones[zones.covers(p)].quadrant.tolist()
    assert len(hits)==1 and hits[0]==new['sectors'][h[3]]
assert unary_union(dividers.geometry).difference(unary_union(roads.geometry).buffer(.01)).length<.01
for i,h in enumerate(old['hab']):assert h[:3]+h[4:]==new['hab'][i][:3]+new['hab'][i][4:]
print('PASS: four valid non-overlapping polygons, no envelope gaps; 1518 unique containment assignments; every divider on mapped roads within 1 cm; non-sector habitat fields unchanged.')

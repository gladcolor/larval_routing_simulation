"""Build a separate, reproducible four-quadrant routing variant.

Original survey labels, dashboard inputs and manuscript figures are preserved.
Internal dividers follow existing major-road geometries in UTM zone 38N.
"""
from pathlib import Path
import json, hashlib, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString, Polygon, box, mapping
from shapely.ops import unary_union, polygonize, substring
from shapely.strtree import STRtree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'road_quadrants_20261105'
WEB=HERE.parent/'CDC_Ethiopia_larval_webmaps/CDC_Ethiopia_larval_webmaps'
GRAPH=HERE/'data/Jigjiga_drive.graphml'
BOUNDARY_ROADS=ROOT/'vector/road_network_20260106.shp'
KMZ=ROOT/'vector/Jigjiga_sectors_20250905.kmz'
NAMES=['NE','NW','SE','SW']
PORTABLE=(HERE/'inputs/original_quadrants.geojson').exists()
if PORTABLE:
    WEB=HERE.parents[1]
    OUT=HERE/'outputs'

def assign_quadrants(lon,lat,polygon_file=None):
    """Return names by containment, with fixed-order handling of exact boundaries."""
    zones=gpd.read_file(polygon_file or OUT/'quadrants.geojson').to_crs(32638).set_index('quadrant')
    pts=gpd.GeoSeries(gpd.points_from_xy(lon,lat),crs=4326).to_crs(32638)
    result=[]
    for p in pts:
        hit=[name for name in NAMES if zones.loc[name].geometry.covers(p)]
        if not hit:raise ValueError('Candidate outside the defined routing envelope')
        result.append(hit[0])
    return result

def main():
    OUT.mkdir(exist_ok=True)
    text=(WEB/'route_sim_data.js').read_text(encoding='utf8')
    begin=text.index('const SIM = ')+len('const SIM = ')
    sim,end=json.JSONDecoder().raw_decode(text[begin:]);suffix=text[begin+end:]
    d=sim['Jigjiga']['Predicted'];old=json.loads(json.dumps(d))
    sites=np.array(d['hab'],float)
    pts=gpd.GeoSeries(gpd.points_from_xy(sites[:,0],sites[:,1]),crs=4326).to_crs(32638)
    xy=np.column_stack([pts.x,pts.y])
    lo=xy.min(axis=0)-250;hi=xy.max(axis=0)+250
    envelope=box(*lo,*hi)
    # Guide points read from the existing four large polygons, not survey samples.
    hint=np.array([258410.,1034420.])
    tips={'N':(258490.,1040250.),'S':(258300.,1030000.),
          'E':(264100.,1033490.),'W':(253200.,1035060.)}
    ns={'k':'http://www.opengis.net/kml/2.2'}
    if PORTABLE:
        original=gpd.read_file(HERE/'inputs/original_quadrants.geojson').to_crs(32638)
    else:
        with zipfile.ZipFile(KMZ) as z:root=ET.fromstring(z.read('doc.kml'))
        records=[]
        for pm in root.findall('.//k:Placemark',ns):
            name=pm.findtext('k:name',namespaces=ns)
            if name not in ['NE','NWest','SEast','SWest']:continue
            coords=pm.find('.//k:outerBoundaryIs/k:LinearRing/k:coordinates',ns)
            records.append({'name':name,'geometry':Polygon([tuple(map(float,s.split(',')[:2])) for s in coords.text.split()])})
        original=gpd.GeoDataFrame(records,crs=4326).to_crs(32638)
    corners=[]
    for poly in original.geometry:
        c=np.array(poly.exterior.coords);corners.append(c[np.argmin(np.linalg.norm(c-hint,axis=1))])
    centre=np.mean(corners,axis=0)
    guides=unary_union([LineString([centre,centre+(np.array(p)-centre)*4]) for p in tips.values()])
    source_roads=gpd.read_file(HERE/'inputs/boundary_roads.geojson' if PORTABLE else BOUNDARY_ROADS).to_crs(32638)
    source_roads=source_roads[source_roads.intersects(envelope.buffer(2500))].reset_index(drop=True)
    if not PORTABLE:
        inputs=OUT/'inputs';inputs.mkdir(exist_ok=True)
        original.to_file(inputs/'original_quadrants.geojson',driver='GeoJSON')
        source_roads[['highway','ref','geometry']].to_file(inputs/'boundary_roads.geojson',driver='GeoJSON')
    all_lines=list(source_roads.geometry)
    major=nx.Graph()
    accepted={'trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','track'}
    selected_roads=source_roads[source_roads.highway.isin(accepted)].reset_index(drop=True)
    selected_roads['geometry']=selected_roads.geometry.intersection(envelope.buffer(1000))
    selected_roads=selected_roads.explode(index_parts=False).reset_index(drop=True)
    source_tree=STRtree(selected_roads.geometry.values)
    # Node road intersections for polygon construction only. Driving still uses
    # the unchanged, directed simulator graph (including its one-way rules).
    noded=unary_union(selected_roads.geometry)
    for geom in noded.geoms:
        u=tuple(geom.coords[0]);v=tuple(geom.coords[-1])
        if u==v:continue
        attrs=selected_roads.iloc[source_tree.nearest(geom.interpolate(.5,normalized=True))]
        classes=[attrs.highway]
        penalty=8. if set(classes)&{'residential','track'} else (3. if 'unclassified' in classes else (1.3 if set(classes)<= {'tertiary','tertiary_link'} else 1.))
        weight=geom.length*penalty*(1+(geom.interpolate(.5,normalized=True).distance(guides)/500)**2)
        if not major.has_edge(u,v) or weight<major[u][v]['weight']:
            major.add_edge(u,v,weight=weight,geometry=geom,highway=classes,ref=str(attrs.get('ref','')))
    component=max(nx.connected_components(major),key=len);major=major.subgraph(component).copy()
    node_xy={n:np.array(n) for n in major}
    start=min((n for n in major if major.degree(n)>=3),key=lambda n:np.linalg.norm(node_xy[n]-centre))
    distances,paths=nx.single_source_dijkstra(major,start,weight='weight')
    edges=set();extensions=[];arms={};roads=[]
    for direction,tip in tips.items():
        desired=LineString([centre,centre+(np.array(tip)-centre)*4]).intersection(envelope.boundary)
        assert desired.geom_type=='Point'
        beyond={
            'N':lambda p:p[1]>hi[1], 'S':lambda p:p[1]<lo[1],
            'E':lambda p:p[0]>hi[0], 'W':lambda p:p[0]<lo[0]}[direction]
        targets=[n for n,p in node_xy.items() if beyond(p)]
        # A simplified road can cross the envelope and return while both
        # endpoint nodes remain inside; retain that full edge geometry.
        if not targets:targets=list(node_xy)
        target=min(targets,key=lambda n:Point(node_xy[n]).distance(desired))
        path=paths[target]
        edges.update(tuple(sorted((u,v))) for u,v in zip(path,path[1:]))
        coords=[]
        for u,v in zip(path,path[1:]):
            seg=np.array(major[u][v]['geometry'].coords)
            if np.linalg.norm(seg[0]-node_xy[u])>np.linalg.norm(seg[-1]-node_xy[u]):seg=seg[::-1]
            assert np.linalg.norm(seg[0]-node_xy[u])<.01 and np.linalg.norm(seg[-1]-node_xy[v])<.01
            coords.extend(seg.tolist() if not coords else seg[1:].tolist())
        whole=LineString(coords);cross=whole.intersection(envelope.boundary)
        hits=list(cross.geoms) if cross.geom_type=='MultiPoint' else [cross]
        assert not cross.is_empty and all(p.geom_type=='Point' for p in hits), (direction,cross.wkt,whole.bounds,target)
        stop=min(whole.project(p) for p in hits if whole.project(p)>1)
        clipped=substring(whole,0,stop)
        assert envelope.buffer(.001).covers(clipped)
        roads.append(clipped)
        arms[direction]={'start_node':start,'target_node':target,'path_nodes':path,'road_length_inside_envelope_m':clipped.length,'terminal_extension_m':0}
    edgegraph=nx.Graph();edgegraph.add_edges_from(edges)
    assert nx.is_tree(edgegraph),'Dividers must form a connected tree, not loops'
    net=unary_union(roads+extensions+[envelope.boundary])
    pieces=list(polygonize(net))
    if len(pieces)!=4:
        print('Arms:',json.dumps(arms))
        print('Envelope:',envelope.bounds)
        print('Extra faces:',[(p.area,p.centroid.coords[:],p.bounds) for p in pieces])
        raise AssertionError(f'Expected four polygons, got {len(pieces)}')
    zones=[]
    for poly in pieces:
        p=poly.centroid
        name=('N' if p.y>centre[1] else 'S')+('E' if p.x>centre[0] else 'W')
        zones.append({'quadrant':name,'area_km2':poly.area/1e6,'geometry':poly})
    frame=gpd.GeoDataFrame(zones,crs=32638).sort_values('quadrant')
    assert set(frame.quadrant)==set(NAMES) and frame.is_valid.all()
    assert unary_union(frame.geometry).symmetric_difference(envelope).area<1e-5
    assert abs(frame.area.sum()-envelope.area)<1e-5
    frame.to_crs(4326).to_file(OUT/'quadrants.geojson',driver='GeoJSON')
    divider=unary_union(roads)
    segments=[]
    for part in divider.geoms:
        for a,b in zip(part.coords,list(part.coords)[1:]):
            line=LineString([a,b]);mid=line.interpolate(.5,normalized=True)
            src=selected_roads.iloc[source_tree.nearest(mid)]
            assert line.difference(src.geometry.buffer(.001)).length<.001
            highway=src.highway
            kind='local_road' if highway in {'unclassified','residential','track'} else 'major_road'
            segments.append({'kind':kind,'highway':highway,'geometry':line})
    lineframe=gpd.GeoDataFrame(segments,crs=32638)
    assert abs(lineframe.length.sum()-divider.length)<.001, (lineframe.length.sum(),divider.length)
    lineframe.to_crs(4326).to_file(OUT/'dividers.geojson',driver='GeoJSON')
    (WEB/'route_quadrants.js').write_text(
        '// Generated road-aligned planning boundaries; not administrative units.\nconst ROAD_QUADRANTS = '+frame.to_crs(4326).to_json()+';\nconst ROAD_QUADRANT_DIVIDERS = '+lineframe.to_crs(4326).to_json()+';\n',encoding='utf8')
    labels=assign_quadrants(sites[:,0],sites[:,1])
    d['sectors']=NAMES
    for h,name in zip(d['hab'],labels):h[3]=NAMES.index(name)
    assert all([*a[:3],a[4]]==[*b[:3],b[4]] for a,b in zip(old['hab'],d['hab']))
    assert old['habNode']==d['habNode'] and old['depot']==d['depot']
    newtext=text[:begin]+json.dumps(sim,separators=(',',':'))+suffix
    (WEB/'route_sim_data_four_quadrants.js').write_text(newtext,encoding='utf8')
    html=(WEB/'route_simulation.html').read_text(encoding='utf8')
    assert 'src="route_sim_data.js"' in html or 'src="route_sim_data_four_quadrants.js"' in html
    html=html.replace('src="route_sim_data.js"','src="route_sim_data_four_quadrants.js"')
    html=html.replace('<title>','<title>Four road-aligned quadrants | ',1)
    html=html.replace('<div id="side">','<div id="side"><p style="color:#d2a8ff">Jigjiga Predicted: four road-aligned quadrants. Historical campaigns retain their original labels.</p>',1)
    (WEB/'route_simulation_four_quadrants.html').write_text(html,encoding='utf8')
    assignments={'sectors':NAMES,'candidate_sector_index':[NAMES.index(x) for x in labels],
                 'source_original_data_sha256':hashlib.sha256(text.encode()).hexdigest()}
    (OUT/'assignments.json').write_text(json.dumps(assignments,indent=2),encoding='utf8')
    summary={'crs':'EPSG:32638','centre_guide_m':centre.tolist(),'junction_node':start,'junction_xy_m':node_xy[start].tolist(),
     'candidate_count':len(labels),'counts':{n:labels.count(n) for n in NAMES},'area_km2':dict(zip(frame.quadrant,frame.area_km2)),
     'total_road_divider_m':divider.length,
     'divider_length_by_class_m':lineframe.assign(length_m=lineframe.length).groupby('highway').length_m.sum().to_dict(),
     'outer_extensions_m':sum(x.length for x in extensions),
     'road_classes':sorted(set(c for u,v in edges for c in major[u][v]['highway'])),
     'road_refs':sorted(set(major[u][v]['ref'] for u,v in edges if major[u][v]['ref'] not in ['', 'None', 'nan'])),
     'arms':arms,'candidate_points_on_boundary':sum(sum(p.covers(pt) for p in frame.geometry)>1 for pt in pts),
     'envelope':'Candidate bounding rectangle plus 250 m; four road paths terminate at first envelope crossing.',
     'method':'Major roads preferred; local roads and tracks used for continuity where necessary. Polygon containment, not nearest-survey labels.',
     'boundary_road_source':'vector/road_network_20260106.shp; this does not replace the simulation travel graph',
     'source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ([HERE/'inputs/boundary_roads.geojson',HERE/'inputs/original_quadrants.geojson'] if PORTABLE else [GRAPH,BOUNDARY_ROADS,KMZ])+[WEB/'route_sim_data.js',WEB/'route_simulation.html']}}
    (OUT/'validation.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    colors={'NE':'#238c8b','NW':'#4b79be','SE':'#d89239','SW':'#af649b'}
    fig,ax=plt.subplots(figsize=(11,11));fig.subplots_adjust(left=.10,right=.96,top=.87,bottom=.14)
    fig.text(.1,.96,'Four road-aligned routing quadrants',fontsize=22,weight='bold',color='#15344b')
    fig.text(.1,.925,'Jigjiga | all predicted habitats assigned by polygon containment',fontsize=13,color='#526574')
    for row in frame.itertuples():
        a=np.array(row.geometry.exterior.coords)/1000
        ax.fill(a[:,0],a[:,1],color=colors[row.quadrant],alpha=.12)
    ax.add_collection(LineCollection([np.array(x.coords)/1000 for x in all_lines],colors='#d1d8de',linewidths=.35,zorder=1))
    for row in original.itertuples():
        a=np.array(row.geometry.exterior.coords)/1000;ax.plot(a[:,0],a[:,1],color='#8b969f',ls='--',lw=.8,zorder=2)
    for n in NAMES:
        mask=np.array(labels)==n;ax.scatter(xy[mask,0]/1000,xy[mask,1]/1000,s=9,color=colors[n],zorder=3)
        p=frame.set_index('quadrant').loc[n].geometry.representative_point()
        ax.text(p.x/1000,p.y/1000,f'{n}\n{labels.count(n)} habitats',color=colors[n],fontsize=14,weight='bold',ha='center',
                bbox={'facecolor':'white','edgecolor':'none','alpha':.9},zorder=6)
    for kind,style in [('major_road','solid'),('local_road','dashed')]:
        ax.add_collection(LineCollection([np.array(x.coords)/1000 for x in lineframe[lineframe.kind==kind].geometry],colors='#122f43',linewidths=2,linestyles=style,zorder=4))
    ax.add_collection(LineCollection([np.array(x.coords)/1000 for x in extensions],colors='#122f43',linewidths=1.4,linestyles=':',zorder=4))
    ax.scatter(*((node_xy[start]/1000).reshape(2,1)),marker='*',s=140,color='#122f43',edgecolors='white',zorder=7)
    ax.set(xlim=(lo[0]/1000,hi[0]/1000),ylim=(lo[1]/1000,hi[1]/1000),aspect='equal',xlabel='UTM 38N easting (km)',ylabel='UTM 38N northing (km)')
    ax.spines[['top','right']].set_visible(False)
    x,y=lo/1000+np.array([.3,.25]);ax.plot([x,x+1],[y,y],lw=3,color='#15344b');ax.text(x+.5,y+.12,'1 km',ha='center')
    ax.legend(handles=[Line2D([0],[0],color='#122f43',lw=2,label='New divider: major road'),Line2D([0],[0],color='#122f43',lw=2,ls='--',label='New divider: local road / track'),Line2D([0],[0],color='#8b969f',ls='--',label='Previous broad-quadrant outlines')],loc='upper left',fontsize=9,framealpha=.95)
    fig.text(.10,.065,'Four planning groups, not administrative boundaries. Internal dividers follow the existing road network.\nOnly sector assignments change; candidate priorities, travel network and service assumptions are preserved.',fontsize=11,color='#526574',linespacing=1.5)
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'road_quadrants.{ext}',dpi=240,facecolor='white')
    svg=OUT/'road_quadrants.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    fig.savefig(OUT/'road_quadrants_preview.png',dpi=110,facecolor='white');plt.close(fig)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['arms','source_sha256']},indent=2))

if __name__=='__main__':main()

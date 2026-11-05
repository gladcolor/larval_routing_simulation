"""Redraw network-following routes as SVG and 300-dpi PNG, never screenshots."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.colors import Normalize
from pyproj import Transformer

HERE=Path(__file__).resolve().parent
D=json.loads((HERE/'data/route_paths.json').read_text())
OUT=HERE/'figures'
INK,MUTED,BG,STREET='#17324d','#596a7a','#0d1420','#3a4758'
BLUE,AMBER='#58b7ff','#ffbc4d'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.color':INK,'svg.fonttype':'none','lines.solid_capstyle':'round','lines.solid_joinstyle':'round'})
transform=Transformer.from_crs(4326,32638,always_xy=True)
h=np.asarray(D['sites']);e,n=transform.transform(h[:,0],h[:,1]);origin=np.array([e.min(),n.min()])
xy=(np.c_[e,n]-origin)/1000
def project(poly):
    a=np.asarray(poly);e,n=transform.transform(a[:,1],a[:,0]);return (np.c_[e,n]-origin)/1000
roads=[project(poly) for poly in D['roads']]
norm=Normalize(float(h[:,2].min()),float(h[:,2].max()))
cmap=plt.get_cmap('YlOrRd')

def bounds(cases):
    parts=[]
    for c in cases:
        for p in c['plans']:
            parts.append(xy[[p['depot_site']]+[s['site'] for s in p['stops']]])
            parts.extend(project(s['road_path']['poly']) for s in p['stops'])
    a=np.vstack(parts);lo=a.min(axis=0)-.35;hi=a.max(axis=0)+.35
    return lo,hi

def base(ax,extent):
    ax.set_facecolor(BG)
    ax.add_collection(LineCollection(roads,colors=STREET,linewidths=.55,alpha=.9,zorder=1))
    ax.scatter(xy[:,0],xy[:,1],s=12,color='#566270',alpha=.25,edgecolors='none',zorder=2)
    lo,hi=extent;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal')
    ax.set_xticks([]);ax.set_yticks([])
    for sp in ax.spines.values():sp.set_visible(False)
    ax.text(.97,.95,'N ↑',transform=ax.transAxes,ha='right',va='top',color='#edf3fa',fontsize=12)
    span=hi-lo;length=.5 if span[0]<5 else 1
    x=lo[0]+span[0]*.05;y=lo[1]+span[1]*.045
    ax.plot([x,x+length],[y,y],color='#e4edf5',lw=2,zorder=10)
    ax.text(x+length/2,y+span[1]*.018,f'{length:g} km',ha='center',color='#e4edf5',fontsize=10,zorder=10)

def draw(ax,p,color,team_label=None):
    stops=p['stops'];allpaths=[];walk=[]
    for s in stops:
        line=project(s['road_path']['poly']);allpaths.append(line)
        walk.append([line[-1],xy[s['site']]])
    ax.add_collection(LineCollection(allpaths,colors='#050b13',linewidths=3,alpha=.8,zorder=3))
    ax.add_collection(LineCollection(allpaths,colors=color,linewidths=1.3,alpha=.95,zorder=4))
    ax.add_collection(LineCollection(walk,colors=color,linewidths=.75,linestyles='dashed',alpha=.65,zorder=5))
    # A few direction arrows on actual road segments, not straight site-to-site connectors.
    for j in range(0,len(stops),7):
        line=allpaths[j]
        if len(line)<2:continue
        seg=np.diff(line,axis=0);lens=np.linalg.norm(seg,axis=1);i=int(np.argmax(lens))
        if lens[i]<.045:continue
        a=line[i]+seg[i]*.30;b=line[i]+seg[i]*.72
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'-|>','color':color,'lw':1.2,'mutation_scale':11},zorder=6)
    idx=[s['site'] for s in stops]
    ax.scatter(xy[idx,0],xy[idx,1],s=44,c=h[idx,2],norm=norm,cmap=cmap,edgecolors=color,linewidths=.95,zorder=7)
    # Sparse labels keep dense clusters readable. Numbers are within-team visit positions.
    for s in stops:
        if s['visit'] in [1,20,40,60,80]:
            ax.annotate(str(s['visit']),xy=xy[s['site']],xytext=(5,5),textcoords='offset points',color='white',fontsize=9,weight='bold',bbox={'facecolor':BG,'edgecolor':'none','pad':1.2,'alpha':.9},zorder=9)
    start=project([p['depot_node']])[0]
    ax.scatter(*start,s=95,marker='D',color=color,edgecolors=BG,linewidths=1.5,zorder=10)
    near_left=(start[0]-ax.get_xlim()[0])/(ax.get_xlim()[1]-ax.get_xlim()[0])<.2
    ax.annotate(team_label or 'Start',xy=start,xytext=(8 if near_left else -8,-17),textcoords='offset points',color=color,fontsize=11,weight='bold',ha='left' if near_left else 'right',bbox={'facecolor':BG,'edgecolor':'none','alpha':.85,'pad':1.6},zorder=11)
    if stops:
        last=xy[stops[-1]['site']];ax.scatter(*last,s=115,marker='s',facecolors='none',edgecolors=color,linewidths=1.7,zorder=10)

def footer(fig,y=.07):
    handles=[Line2D([],[],color=BLUE,lw=2,label='Road travel (arrows show direction)'),
             Line2D([],[],color=BLUE,lw=1,ls='--',label='Road-to-site link'),
             Line2D([],[],marker='D',color='none',markerfacecolor=BLUE,markersize=7,label='Start'),
             Line2D([],[],marker='s',color='none',markeredgecolor=BLUE,markersize=8,label='Last completed visit')]
    fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.05,y),ncol=4,frameon=False,fontsize=10.5,handlelength=2)
    fig.text(.06,.028,'Legacy predicted priorities, not treatment effects. Completed visits only; unfinished next legs and nightly returns are not shown.\nRoads: shipped OpenStreetMap-derived network. WGS 84 / UTM zone 38N. Numbers label selected visit positions.',fontsize=10,color=MUTED,linespacing=1.5)

def save(fig,name):
    fig.savefig(OUT/(name+'.svg'),facecolor='white')
    fig.savefig(OUT/(name+'.png'),dpi=300,facecolor='white')
    fig.savefig(OUT/(name+'_preview.png'),dpi=100,facecolor='white')
    plt.close(fig)

def comparison():
    cases=[D['cases']['greedy_1team_2days'],D['cases']['nn_1team_2days']]
    extent=bounds(cases)
    fig,axs=plt.subplots(1,2,figsize=(15,9.2));fig.subplots_adjust(left=.055,right=.96,bottom=.24,top=.81,wspace=.05)
    fig.text(.055,.95,'How routing policies move through Jigjiga',fontsize=24,weight='bold')
    fig.text(.055,.905,'One team · first two working days · same start and cost assumptions · each panel uses the same map extent',fontsize=13,color=MUTED)
    for ax,c,color,title in zip(axs,cases,[BLUE,AMBER],['a   Priority per minute','b   Nearest neighbour']):
        base(ax,extent);draw(ax,c['plans'][0],color)
        ax.set_title(title,loc='left',fontsize=16,weight='bold',pad=13)
        ax.text(0,-.085,f"{c['visited_sites']} visits  |  {c['priority_fraction']:.1%} of mapped priority  |  {c['drive_km']:.1f} km driving",transform=ax.transAxes,fontsize=12,color=INK)
    fig.text(.055,.155,'Visited habitats are coloured by mapped priority; outlines and paths identify the policy. Higher priorities are darker red.',fontsize=11,color=MUTED)
    footer(fig,.09);save(fig,'05_route_policy_paths')

def two_teams():
    c=D['cases']['sector_2teams_1day'];extent=bounds([c])
    fig=plt.figure(figsize=(12,10.5));ax=fig.add_axes([.06,.24,.73,.57])
    fig.text(.06,.955,'Two teams, one working day',fontsize=25,weight='bold')
    fig.text(.06,.913,'Four-quadrant sweep · zone-based starts · 25 km/h driving · 10 min/site + walk-in · 8 h/team',fontsize=11.5,color=MUTED)
    base(ax,extent)
    for p,color in zip(c['plans'],[BLUE,AMBER]):draw(ax,p,color,'Team '+str(p['team']))
    side=fig.add_axes([.81,.30,.17,.48]);side.set_axis_off()
    for p,color,y in zip(c['plans'],['#0072b2','#a86200'],[.92,.68]):
        side.text(0,y,'TEAM '+str(p['team']),color=color,fontsize=16,weight='bold')
        side.text(0,y-.085,f"{len(p['stops'])} completed visits",fontsize=11)
        km=sum(s['road_path']['metres'] for s in p['stops'])/1000
        side.text(0,y-.15,f'{km:.1f} km driving',fontsize=11,color=MUTED)
    side.text(0,.34,'COMBINED',fontsize=12,weight='bold',color=MUTED)
    side.text(0,.23,f"{c['priority_fraction']:.1%}",fontsize=31,weight='bold')
    side.text(0,.14,'of mapped priority',fontsize=11)
    side.text(0,.02,'2 team-days available',fontsize=11,color=MUTED)
    cax=fig.add_axes([.82,.24,.145,.014]);bar=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,orientation='horizontal')
    bar.set_label('Mapped priority',fontsize=10);bar.ax.tick_params(labelsize=9,length=2);bar.outline.set_visible(False)
    fig.text(.06,.18,'Circle fill shows mapped priority; outlines and road paths identify the team. Both teams use the same candidate population.',fontsize=11,color=MUTED)
    footer(fig,.10);save(fig,'06_two_team_route_paths')

comparison();two_teams()
print('Created two route-path figures in SVG, 300-dpi PNG and preview PNG formats.')

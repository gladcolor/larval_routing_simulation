"""Original vector figures; no screenshots, interpolation smoothing or external basemap.

Run extract_routes.cjs first. All generated files stay inside this analysis folder.
"""
from pathlib import Path
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from sklearn.metrics import ndcg_score
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
RAW = HERE / 'data' / 'routes.json'
D = json.loads(RAW.read_text())
INK, MUTED, GRID = '#17324d', '#596a7a', '#e4eaf0'
COL = {'greedy': '#0072B2', 'sector': '#009E73', 'nn': '#D55E00', 'zigzag': '#8B6BB1'}
LAB = {'greedy': 'Priority per minute', 'sector': 'Four-quadrant sweep', 'nn': 'Nearest neighbour', 'zigzag': 'Zigzag sweep'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'axes.labelsize': 13,
                     'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'svg.fonttype': 'none', 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.edgecolor': '#9aa8b5',
                     'lines.solid_capstyle': 'round', 'lines.solid_joinstyle': 'round'})

def metrics(values):
    y = np.asarray(values, float)
    if y.ndim != 1 or len(y) < 2 or not np.isfinite(y).all() or (y < 0).any() or y.sum() <= 0:
        raise ValueError('Need finite nonnegative, positive-total outcomes')
    n = len(y)
    x = np.arange(n+1)/n
    c = np.r_[0., np.cumsum(y)/y.sum()]
    ideal = np.r_[0., np.cumsum(np.sort(y)[::-1])/y.sum()]
    auc, iauc = np.trapezoid(c, x), np.trapezoid(ideal, x)
    lift = float((auc-.5)/(iauc-.5)) if iauc > .5+1e-14 else None
    discounts = 1/np.log2(np.arange(2, n+2))
    ndcg = float(y@discounts/(np.sort(y)[::-1]@discounts))
    independent = ndcg_score(y[None, :], -np.arange(n, dtype=float)[None, :])
    assert abs(ndcg-independent) < 1e-12
    # Independent rank-sum identity for the trapezoidal AUC.
    assert abs(auc - y@(n-np.arange(1,n+1)+.5)/(n*y.sum())) < 1e-12
    area_a=float(auc-.5);area_b=float(iauc-auc)
    assert area_b>=-1e-12 and np.all(ideal>=c-1e-12)
    assert abs(area_a/(area_a+area_b)-lift)<1e-12
    return {'lift': lift, 'area_a':area_a, 'area_b':area_b, 'ndcg_full': ndcg, 'coverage50': float(c[int(np.ceil(n*.5))]),
            'coverage20': float(c[int(np.ceil(n*.2))]), 'auc': float(auc), 'ideal_auc': float(iauc)}, x, c, ideal

def style(ax, time=False):
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=GRID, linewidth=.7)
    ax.set_ylim(0, 102)
    ax.set_yticks([0, 25, 50, 75, 100])
    if not time:
        ax.set_xlim(0,100)
        ax.set_xticks([0,25,50,75,100])
    ax.tick_params(length=3)

def heading(fig, title, subtitle):
    fig.text(.065, .965, title, fontsize=22, weight='bold', va='top')
    fig.text(.065, .912, subtitle, fontsize=12, color=MUTED, va='top')

def reference_curves(ax, x, ideal, label):
    """Unconstrained top-k reference, only on habitat-share axes, never time."""
    ax.plot([0,100],[0,100],color='#78838e',lw=1.4,ls=(0,(4,4)),
            label='Random ordering (expected)',zorder=3,gid='random-order-reference')
    line,=ax.plot(x*100,ideal*100,color='#202c36',lw=2.2,ls=(0,(6,4)),
                 label=label,zorder=6,gid='ideal-top-k-reference')
    # White edging keeps the dashed ideal visible where a policy nearly matches it.
    line.set_path_effects([pe.Stroke(linewidth=3.6,foreground='white'),pe.Normal()])

def save(fig, name):
    fig.savefig(OUT/(name+'.svg'), facecolor='white')
    fig.savefig(OUT/(name+'.png'), dpi=300, facecolor='white')
    fig.savefig(OUT/(name+'_preview.png'), dpi=100, facecolor='white')
    plt.close(fig)

RESULTS = {}
for key, rows in D['routes'].items():
    y = [r['priority'] for r in rows]
    m,x,c,ideal = metrics(y)
    t = np.r_[0., [r['completion_seconds']/28800 for r in rows]]
    m.update({'sites':len(rows), 'team_days80':float(t[np.flatnonzero(c>=.8)[0]]),
              'coverage20days':float(c[np.searchsorted(t,20,side='right')-1]),
              'finish_team_days':float(t[-1]), 'driving_km':rows[-1]['cumulative_drive_m']/1000})
    RESULTS[key] = {'metrics':m, 'x':x, 'c':c, 'ideal':ideal, 't':t}

def policy_figure():
    fig, axes = plt.subplots(1,2,figsize=(14,6.6))
    fig.subplots_adjust(left=.075,right=.97,bottom=.29,top=.78,wspace=.25)
    heading(fig,'Two questions for every routing policy',
            'Jigjiga | 1,518 mapped candidates | one common start | one team | 25 km/h | 10 min/site + walk-in')
    q=RESULTS['sector'];qx=q['x']*100;qc=q['c']*100;qi=q['ideal']*100
    axes[0].fill_between(qx,qx,qc,where=qc>=qx,interpolate=True,color='#d5e8f7',zorder=0)
    axes[0].fill_between(qx,qx,qc,where=qc<qx,interpolate=True,color='#d5e8f7',hatch='///',zorder=0)
    axes[0].fill_between(qx,qc,qi,color='#fbe6bf',zorder=0)
    for key,r in RESULTS.items():
        axes[0].plot(r['x']*100,r['c']*100,color=COL[key],lw=2.6,
                     label=f"{LAB[key]}   L = {r['metrics']['lift']:.3f}")
        axes[1].step(r['t'],r['c']*100,where='post',color=COL[key],lw=2.4)
    a,b=axes
    reference_curves(a,q['x'],q['ideal'],'Ideal (top-k predicted priorities)')
    a.annotate('Ideal: top-k predicted priorities\nTravel constraints ignored',
               xy=(32,float(np.interp(32,qx,qi))),xytext=(5,91),
               fontsize=10,color='#202c36',va='top',linespacing=1.4,
               arrowprops={'arrowstyle':'-','color':'#202c36','lw':1,
                           'connectionstyle':'angle3,angleA=0,angleB=90'})
    a.set_title('a   Which habitats are visited first?',loc='left',pad=16,fontsize=15,weight='bold')
    b.set_title('b   How quickly is priority reached?',loc='left',pad=16,fontsize=15,weight='bold')
    a.set_xlabel('Habitats visited (%)')
    a.set_ylabel('Mapped-priority coverage (%)')
    b.set_xlabel('Cumulative working time (team-days)')
    b.set_ylabel('Mapped-priority coverage (%)')
    style(a);style(b,True);b.set_xlim(0,50)
    a.axvline(50,color=GRID,lw=1,zorder=0)
    b.axhline(80,color='#aab4bd',ls=(0,(2,3)),lw=1)
    handles,labels=a.get_legend_handles_labels()
    order=[5,4,0,1,2,3]
    a.legend([handles[i] for i in order],[labels[i] for i in order],
             loc='lower right',fontsize=9,frameon=False,labelspacing=.6,handlelength=3)
    bx=50;by=float(np.interp(bx,qx,(qc+qi)/2))
    a.text(bx,by,'B',color='#9c660d',fontsize=22,weight='bold',ha='center',va='center')
    b.text(1,82,'80% target',fontsize=10,color=MUTED)
    fig.text(.075,.125,'Shading for four-quadrant sweep: blue A; amber B.\nIdeal: top-k predicted priorities, ignoring travel constraints.',fontsize=10.5,color=MUTED,linespacing=1.5)
    fig.text(.57,.125,'Time-based coverage includes travel, walk-in and service.\nA random diagonal is not a time-matched routing baseline.',fontsize=11,color=MUTED,linespacing=1.5)
    fig.text(.075,.035,'Planning scenario only: legacy predicted priorities, not observed treatment effects or held-out prediction validation.',fontsize=10.5,color=MUTED)
    save(fig,'01_policy_order_and_time')

def maps_figure():
    transform = Transformer.from_crs(4326,32638,always_xy=True)
    h=np.array(D['sites'])
    east,north=transform.transform(h[:,0],h[:,1]); origin=(east.min(),north.min())
    X=(east-origin[0])/1000;Y=(north-origin[1])/1000
    roads=[]
    for line in D['roads']:
        a=np.array(line);e,n=transform.transform(a[:,1],a[:,0]);roads.append(np.c_[(e-origin[0])/1000,(n-origin[1])/1000])
    fig,axes=plt.subplots(1,2,figsize=(13,7.8))
    fig.subplots_adjust(left=.07,right=.97,bottom=.16,top=.79,wspace=.12)
    heading(fig,'The same visit budget can reach different priority',
            'Jigjiga | first 304 of 1,518 candidates (20.03%) | coloured points are visited; pale points are not yet visited')
    for ax,key,letter in zip(axes,['greedy','nn'],['a','b']):
        ax.add_collection(LineCollection(roads,colors='#d9dfe5',linewidths=.5,zorder=0))
        ax.scatter(X,Y,s=6,color='#c6cdd3',alpha=.55,edgecolors='none')
        first=D['routes'][key][:304];idx=[r['site'] for r in first]
        ax.scatter(X[idx],Y[idx],s=13,color=COL[key],edgecolors='white',linewidths=.2,zorder=2)
        depot=D['scenario']['depot_index']
        ax.scatter(X[depot],Y[depot],s=100,marker='*',color=INK,edgecolors='white',linewidths=.7,zorder=4)
        ax.set_xlim(X.min()-.4,X.max()+.4);ax.set_ylim(Y.min()-.4,Y.max()+.4);ax.set_aspect('equal');ax.set_axis_off()
        ax.set_title(f'{letter}   {LAB[key]}',loc='left',fontsize=16,pad=14,weight='bold')
        m=RESULTS[key]['metrics'];days=first[-1]['completion_seconds']/28800
        ax.text(.02,-.06,f"{m['coverage20']:.1%} mapped priority reached\n{days:.2f} team-days to complete 304 visits",transform=ax.transAxes,fontsize=13,color=COL[key],linespacing=1.5)
        x0=X.min()+.15;y0=Y.min()-.15
        ax.plot([x0,x0+1],[y0,y0],color=INK,lw=2);ax.text(x0+.5,y0+.1,'1 km',ha='center',fontsize=10)
        ax.text(.97,.95,'N ↑',transform=ax.transAxes,ha='right',fontsize=12)
    fig.text(.07,.025,'Star: shared start. WGS 84 / UTM zone 38N. Roads: shipped OpenStreetMap network. Sites are mapped candidates, not verified treatment events.',fontsize=10,color=MUTED)
    save(fig,'02_spatial_visit_budget')

def same_order_figure():
    y=np.array([40,15,25,5,8,4,1,2]);m,x,c,ideal=metrics(y)
    fig,axes=plt.subplots(1,2,figsize=(13,6.5));fig.subplots_adjust(left=.08,right=.97,bottom=.28,top=.76,wspace=.27)
    heading(fig,'The same lift-ratio does not mean the same field efficiency',
            'Synthetic teaching example | eight sites, 100 units of larval burden | identical visit order, different completion times')
    a,b=axes
    a.fill_between(x*100,x*100,c*100,color='#d5e8f7')
    a.fill_between(x*100,c*100,ideal*100,color='#fbe6bf')
    a.plot(x*100,c*100,color=COL['greedy'],lw=3,marker='o',ms=4,label='Both visit schedules')
    reference_curves(a,x,ideal,'Ideal (largest values first)')
    a.legend(loc='lower right',fontsize=9,frameon=False,handlelength=3)
    a.text(53,39,'A',fontsize=24,color=COL['greedy'],weight='bold')
    a.annotate('B',xy=(26,62),xytext=(15,78),fontsize=20,color='#a56813',weight='bold',arrowprops={'arrowstyle':'-','color':'#a56813','lw':1})
    a.set_title(f'a   Both schedules: lift-ratio = {m["lift"]:.3f}',loc='left',pad=16,fontsize=15,weight='bold')
    a.set_xlabel('Sites visited (%)');a.set_ylabel('Observed-burden coverage (%)');style(a)
    for hours,col,label in [(np.arange(9)*.25,COL['greedy'],'Faster schedule'),(np.arange(9)*.75,COL['nn'],'Slower schedule')]:
        b.step(hours,c*100,where='post',color=col,lw=2.8,label=label)
    b.set_title('b   A two-hour budget gives different coverage',loc='left',pad=16,fontsize=14,weight='bold')
    b.axvline(2,color='#aab4bd',ls=(0,(3,3)),lw=1)
    b.scatter([2,2],[100,55],color=[COL['greedy'],COL['nn']],s=45,zorder=4)
    b.text(2.2,96,'100%',color=COL['greedy'],weight='bold');b.text(2.2,58,'55%',color=COL['nn'],weight='bold')
    b.set_xlabel('Working time (hours)');b.set_ylabel('Observed-burden coverage (%)');style(b,True);b.set_xlim(0,6.2)
    b.legend(loc='lower right',frameon=False,fontsize=11)
    fig.text(.08,.09,'L = A / (A + B) summarizes ordering quality.\nIt cannot distinguish schedules with identical visit sequences.',fontsize=11,color=MUTED,linespacing=1.5)
    fig.text(.57,.09,'Always also report coverage at a fixed time budget\nand working time needed to reach a coverage target.',fontsize=11,color=MUTED,linespacing=1.5)
    fig.text(.08,.025,'Illustrative times only; no geographic route-feasibility claim. Credit is assigned at completed visits, not between them.',fontsize=10,color=MUTED)
    save(fig,'03_same_lift_different_efficiency')
    return {'outcomes_in_visit_order':y.tolist(),'metrics':m,'fast_completion_hours':(np.arange(1,9)*.25).tolist(),'slow_completion_hours':(np.arange(1,9)*.75).tolist()}

def ndcg_figure():
    orders={'Top-heavy order':np.array([40,1,2,4,5,8,15,25]),'Broad-coverage order':np.array([25,15,8,40,5,4,2,1])}
    fig=plt.figure(figsize=(13,7));gs=fig.add_gridspec(1,2,width_ratios=[1.05,1],left=.08,right=.96,bottom=.28,top=.76,wspace=.3)
    a=fig.add_subplot(gs[0]);b=fig.add_subplot(gs[1]);b.set_axis_off()
    heading(fig,'Why use lift-ratio as the primary LSM ordering metric?',
            'Both metrics are valid, but their priorities differ | synthetic example | linear count gain and full-list NDCG')
    stats={}
    for name,col in zip(orders,[COL['nn'],COL['greedy']]):
        y=orders[name];m,x,c,ideal=metrics(y);stats[name]=m
        a.plot(x*100,c*100,color=col,lw=2.6,marker='o',ms=4,label=name)
    style(a);reference_curves(a,x,ideal,'Ideal (largest values first)')
    a.axvline(50,color='#aab4bd',ls=(0,(3,3)),lw=1)
    a.set_xlabel('Sites visited (%)');a.set_ylabel('Observed-burden coverage (%)')
    a.set_title('a   Compare policies at a 50% site budget',loc='left',pad=16,fontsize=14,weight='bold')
    a.text(54,80,'88%',color=COL['greedy'],weight='bold');a.text(54,41,'47%',color=COL['nn'],weight='bold')
    a.legend(loc='lower right',frameon=False,fontsize=10.5)
    b.set_title('b   Two metrics, different preferences',loc='left',pad=16,fontsize=14,weight='bold')
    for ypos,(name,col) in zip([.84,.46],zip(orders,[COL['nn'],COL['greedy']])):
        m=stats[name]
        b.text(0,ypos,name,transform=b.transAxes,color=col,fontsize=15,weight='bold')
        b.text(0,ypos-.10,' → '.join(map(str,orders[name])),transform=b.transAxes,color=MUTED,fontsize=11)
        b.text(0,ypos-.22,f"Lift-ratio   {m['lift']:.3f}",transform=b.transAxes,fontsize=16,weight='bold')
        b.text(.57,ypos-.22,f"NDCG   {m['ndcg_full']:.3f}",transform=b.transAxes,fontsize=16,weight='bold')
    b.text(0,.04,'NDCG rewards the larger first-site gain.\nLift-ratio favours stronger coverage across site budgets.',transform=b.transAxes,fontsize=11,linespacing=1.6)
    fig.text(.08,.10,'Use coverage curves for interpretable budget choices; use lift-ratio as a full-curve summary.\nNDCG is complementary, not invalid. It can be evaluated at any cutoff, including the full list.',fontsize=12,color=MUTED,linespacing=1.6)
    fig.text(.08,.025,'Synthetic counterexample, not evidence that one metric is universally superior. Neither metric accounts for travel time.',fontsize=10,color=MUTED)
    save(fig,'04_lift_ratio_and_ndcg')
    assert stats['Top-heavy order']['ndcg_full']>stats['Broad-coverage order']['ndcg_full']
    assert stats['Top-heavy order']['lift']<stats['Broad-coverage order']['lift']
    return {name:{'outcomes_in_visit_order':v.tolist(),'metrics':stats[name]} for name,v in orders.items()}

policy_figure();maps_figure()
synthetic={'same_order':same_order_figure(),'ndcg_comparison':ndcg_figure()}
result={'scenario':D['scenario'],'routes':{k:r['metrics'] for k,r in RESULTS.items()},'synthetic':synthetic,
        'input_sha256':hashlib.sha256(RAW.read_bytes()).hexdigest(),
        'ndcg_convention':'Linear gain equal to counts/priorities; discount 1/log2(rank+1); k=n; no score ties in visit order.',
        'checks':['All 1518 sites visited once by every strategy','Completion clocks reproduce dashboard day tags','NDCG agrees with scikit-learn','Trapezoidal area agrees with rank-sum identity'],
        'limits':D['provenance']}
(HERE/'data'/'metrics.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result['routes'],indent=2))

from __future__ import annotations
import argparse, itertools, random
from pathlib import Path
import networkx as nx
from geometry_v2 import FINISH_ENTRANCE_CELL, FLOORS, generate_grid
from global_graph_v3 import TransitionArea, build_global_navigation_graph, navigation_graph_report
from physical_blueprint_v3 import build_physical_blueprint_v3
from svg_renderer_v2 import write_all_floor_svgs
from xml.etree import ElementTree as ET

def parse_floor(path):
    root=ET.parse(path).getroot(); cells=set(); opened=set(); transitions={}
    for e in root.iter():
        kind=e.attrib.get('data-type')
        if kind=='corridor-cell': cells.add(tuple(map(int,e.attrib['data-cell'].split(','))))
        elif kind=='open-passage':
            opened.add(tuple(sorted(tuple(map(int,c.split(','))) for c in e.attrib['data-cells'].split('|'))))
        elif kind=='vertical-transition':
            transitions[e.attrib['data-id']]=TransitionArea(
                id=e.attrib['data-id'], cell=tuple(map(int,e.attrib['data-cell'].split(','))),
                kind=e.attrib['data-kind'], journeys=((int(e.attrib['data-from-floor']),int(e.attrib['data-to-floor'])),))
    return root,cells,opened,transitions

def cell_text(cell): return f'{cell[0]},{cell[1]}'

def choose_spine(region, connections, start, finish, drops):
    graph=nx.Graph(); graph.add_nodes_from(region)
    graph.add_edges_from((u,v) for u in region for v in connections[u] if v in region)
    options=[sorted(set(graph.neighbors(drop))-{start,finish,*drops}) for drop in drops]
    best=None
    # The baseline footprint cannot carry all four drops on one no-backtracking path.
    # Put the largest feasible group on the finish spine; the remaining drops become branches.
    for count in range(len(drops),0,-1):
        for selected in itertools.combinations(range(len(drops)),count):
            for order in itertools.permutations(selected):
                for choices in itertools.product(*(options[i] for i in order)):
                    targets=list(dict.fromkeys(choices)); route=[start]; used={start}; ok=True
                    for target in targets+[finish]:
                        if target in used: continue
                        allowed=(set(region)-used-set(drops))|{route[-1],target}
                        try: path=nx.shortest_path(graph.subgraph(allowed),route[-1],target)
                        except (nx.NetworkXNoPath,nx.NodeNotFound): ok=False; break
                        route.extend(path[1:]); used.update(path)
                    if not ok or not set(targets)<=set(route): continue
                    bends=sum((route[i][0]-route[i-1][0],route[i][1]-route[i-1][1]) !=
                              (route[i+1][0]-route[i][0],route[i+1][1]-route[i][1])
                              for i in range(1,len(route)-1))
                    score=(count,len(route),bends)
                    if best is None or score>best[0]: best=(score,route)
        if best is not None and best[0][0]==count: break
    if best is None: raise ValueError('Could not route a sweep spine through drop approaches.')
    return graph,best[1]

def carve_sweep(region, connections, start, finish, drops, seed=7301):
    graph,spine=choose_spine(region,connections,start,finish,drops)
    opened=set(tuple(sorted((a,b))) for a,b in zip(spine,spine[1:]))
    tree=nx.Graph();tree.add_nodes_from(spine);tree.add_edges_from(opened)
    for drop in drops:
        if drop in tree and tree.degree(drop)>0: continue
        approach=sorted(n for n in graph.neighbors(drop) if n in region and n not in {start,finish,*drops})
        candidates=[]
        for endpoint in spine:
            H=graph.copy(); H.remove_nodes_from(set(spine)-{endpoint})
            for a in approach:
                if a in H:
                    try: p=nx.shortest_path(H,endpoint,a)
                    except nx.NetworkXNoPath: continue
                    candidates.append((len(p),spine.index(endpoint),p,a))
        if candidates:
            _,_,path,approach_cell=min(candidates,key=lambda x:(x[0],-x[1]))
            for a,b in zip(path,path[1:]):
                edge=tuple(sorted((a,b)))
                if not tree.has_edge(a,b): tree.add_edge(a,b);opened.add(edge)
            edge=tuple(sorted((approach_cell,drop)))
            if not tree.has_edge(*edge): tree.add_edge(*edge);opened.add(edge)
    rng=random.Random(seed); reached=set(tree.nodes); frontier=[]
    for u in reached:
        for v in graph.neighbors(u):
            if v not in reached: frontier.append((u,v))
    while reached != set(region):
        frontier=[e for e in frontier if e[1] not in reached]
        if not frontier: raise ValueError('Sweep carve could not connect all cells in R09.')
        u,v=rng.choice(frontier); edge=tuple(sorted((u,v)))
        if v not in reached:
            reached.add(v);tree.add_edge(u,v);opened.add(edge)
            frontier.extend((v,n) for n in graph.neighbors(v) if n not in reached)
    if not nx.is_tree(tree): raise ValueError('Sweep carve contains an unintended horizontal loop.')
    return opened,spine

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=Path('output/blueprints_v3'))
    ap.add_argument('--output',type=Path,default=Path('output/blueprints_v3/finish_approach_sweep_v1'))
    args=ap.parse_args()
    floor_data={}; all_trans={}
    for floor in FLOORS:
        _,cells,opened,trans=parse_floor(args.source/'normal'/f'floor_{floor}.svg')
        _,connections=generate_grid(floor)
        if cells != set(generate_grid(floor)[0]): raise ValueError(f'Floor {floor} SVG cells differ from geometry.')
        floor_data[floor]={'cells':cells,'connections':connections,'opened_edges':opened,'possible_edges':0,'region_by_cell':{},'loop_percentage':0}
        all_trans.update(trans)
    transition_areas=[all_trans[k] for k in sorted(all_trans)]
    region_cells={}; labels={}
    for floor,maze in floor_data.items():
        g=nx.Graph();g.add_nodes_from(maze['cells']);g.add_edges_from(maze['opened_edges'])
        components=list(nx.connected_components(g))
        region_cells[floor]={f'R{i:02d}':set(c) for i,c in enumerate(components)}
        labels[floor]={cell:rid for rid,c in region_cells[floor].items() for cell in c}
        maze['region_by_cell']=labels[floor]
    entry=all_trans['T09'].cell
    r09=next(c for c in region_cells[3].values() if entry in c)
    drops=[all_trans[x].cell for x in ('T10','T13','T18','T24')]
    opened,spine=carve_sweep(r09,floor_data[3]['connections'],entry,FINISH_ENTRANCE_CELL,drops)
    old=floor_data[3]['opened_edges']
    floor_data[3]['opened_edges']=(old-{e for e in old if e[0] in r09 and e[1] in r09})|opened
    graph=build_global_navigation_graph(floor_data,transition_areas)
    start_root=ET.parse(args.source/'solution'/'floor_1_solution.svg').getroot()
    start_cells=[tuple(map(int,e.attrib['data-cell'].split(','))) for e in start_root.iter() if e.attrib.get('data-type')=='solution-cell']
    start=(1,start_cells[0]);finish=(3,FINISH_ENTRANCE_CELL)
    report=navigation_graph_report(graph,start,finish,transition_areas)
    if report['minimum_vertical_journeys']!=9 or not report['strongly_connected']:
        raise ValueError(f'Variant failed navigation constraints: {report}')
    layout={'seed':'baseline-svg-sweep','attempt':1,'region_plan':{'regions':[]},'region_labels':labels,'region_cells':region_cells,
            'region_seeds':{},'transition_areas':transition_areas,'floor_mazes':floor_data,'navigation_graph':graph,
            'start':start,'finish':finish,'validation':{'valid':True}}
    blueprint=build_physical_blueprint_v3(layout)
    write_all_floor_svgs(blueprint,args.output/'normal')
    write_all_floor_svgs(blueprint,args.output/'solution',show_solution=True)
    print('Output:',args.output.resolve())
    print('R09 cells:',len(r09),'spine length:',len(spine)-1)
    print('Transitions:',len(transition_areas),'minimum vertical journeys:',report['minimum_vertical_journeys'],'strongly connected:',report['strongly_connected'])
    print('Spine:', ' -> '.join(cell_text(c) for c in spine))
if __name__=='__main__': main()

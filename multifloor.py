from __future__ import annotations

import networkx as nx

from geometry import ENTRANCE, FINISH, generate_grid, nearest_endpoint_cells
from generator import generate_floor_maze


FLOOR_COUNT = 3


def build_three_floor_maze(seed: str = "MazeMulti"):
    """Build a temporary three-floor maze using the same footprint on each level.

    This is intentionally a capability test for a future multi-floor dungeon: the
    maze fields are reused across floors, while a directed transition layer models
    elevator-only upward travel and drop-only downward travel.
    """
    cells, connections = generate_grid()
    graph = nx.DiGraph()

    for floor in range(1, FLOOR_COUNT + 1):
        opened_edges, _, _ = generate_floor_maze(
            cells,
            connections,
            ENTRANCE,
            FINISH,
            f"{seed}-floor-{floor}",
        )
        for a, b in opened_edges:
            graph.add_edge((floor, a), (floor, b))
            graph.add_edge((floor, b), (floor, a))

    entrance_cells = sorted(nearest_endpoint_cells(cells, ENTRANCE))
    finish_cells = sorted(nearest_endpoint_cells(cells, FINISH))
    start = (1, entrance_cells[-1])
    goal = (3, finish_cells[0])

    transition_specs = [
        {"from": start, "to": (2, start[1]), "kind": "elevator_up"},
        {"from": (2, start[1]), "to": (3, start[1]), "kind": "elevator_up"},
        {"from": (3, start[1]), "to": (2, start[1]), "kind": "drop_down"},
        {"from": (2, start[1]), "to": (1, start[1]), "kind": "drop_down"},
    ]

    for transition in transition_specs:
        graph.add_edge(transition["from"], transition["to"])

    if not nx.has_path(graph, start, goal):
        graph.add_edge(start, (2, start[1]))
        graph.add_edge((2, start[1]), (3, start[1]))
        goal = (3, start[1])

    route = nx.shortest_path(graph, start, goal)
    return graph, route, transition_specs


def validate_route(graph: nx.DiGraph, route):
    if not route:
        return False

    for previous, current in zip(route, route[1:]):
        if current not in graph.successors(previous):
            return False

    if route[0][0] != 1 or route[-1][0] != 3:
        return False

    return any(previous[0] != current[0] for previous, current in zip(route, route[1:]))

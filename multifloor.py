from __future__ import annotations

import networkx as nx

from geometry import ENTRANCE, FINISH, generate_grid, nearest_endpoint_cells
from generator import carve_maze


FLOOR_COUNT = 3
BACKBONE_FRACTIONS = (0.12, 0.24, 0.36, 0.48, 0.60, 0.72)


def build_three_floor_maze(seed: str = "MazeMulti"):
    """Build a non-backtracking route with decoys and one finish elevator."""
    cells, connections = generate_grid()
    start_cell = sorted(nearest_endpoint_cells(cells, ENTRANCE))[-1]
    finish_cell = sorted(nearest_endpoint_cells(cells, FINISH))[0]

    layout_graph = nx.Graph()
    layout_graph.add_nodes_from(sorted(cells))
    for cell in sorted(connections):
        for neighbor in sorted(connections[cell]):
            if cell < neighbor:
                layout_graph.add_edge(cell, neighbor)

    backbone = nx.shortest_path(layout_graph, start_cell, finish_cell)
    edge_count = len(backbone) - 1
    transition_indices = [round(edge_count * fraction) for fraction in BACKBONE_FRACTIONS]
    if len(set(transition_indices)) != len(transition_indices):
        raise ValueError("The entrance-to-finish corridor is too short for transitions.")

    required_edges = tuple(zip(backbone, backbone[1:]))
    graph = nx.DiGraph()
    floor_graphs = {}
    for floor in range(1, FLOOR_COUNT + 1):
        opened_edges, _ = carve_maze(
            cells,
            connections,
            f"{seed}-floor-{floor}",
            forced_edges=required_edges,
        )
        floor_graph = nx.Graph()
        floor_graph.add_nodes_from(sorted(cells))
        for a, b in sorted(opened_edges):
            floor_graph.add_edge(a, b)
            graph.add_edge((floor, a), (floor, b))
            graph.add_edge((floor, b), (floor, a))
        floor_graphs[floor] = floor_graph

    index_one, index_two, index_three, index_four, index_five, index_six = (
        transition_indices
    )
    cut_edge = (backbone[index_five], backbone[index_five + 1])
    floor_graphs[3].remove_edge(*cut_edge)
    graph.remove_edge((3, cut_edge[0]), (3, cut_edge[1]))
    graph.remove_edge((3, cut_edge[1]), (3, cut_edge[0]))

    decoy_region = nx.node_connected_component(
        floor_graphs[3],
        backbone[index_four],
    )
    decoy_cells = sorted(decoy_region - set(backbone))
    if len(decoy_cells) < 2:
        raise ValueError("Floor 3 needs two off-route cells for decoy transitions.")

    decoy_distances = nx.single_source_shortest_path_length(
        floor_graphs[3],
        backbone[index_four],
    )
    decoy_elevator_cell = max(
        decoy_cells,
        key=lambda cell: decoy_distances[cell],
    )
    decoy_cells.remove(decoy_elevator_cell)
    decoy_elevator_distances = nx.single_source_shortest_path_length(
        floor_graphs[3],
        decoy_elevator_cell,
    )
    decoy_drop_cell = max(
        decoy_cells,
        key=lambda cell: decoy_elevator_distances[cell],
    )

    transition_specs = [
        {
            "id": "E1",
            "from": (1, backbone[index_one]),
            "to": (2, backbone[index_one]),
            "kind": "elevator_up",
            "optional": False,
            "decoy": False,
        },
        {
            "id": "D1",
            "from": (2, backbone[index_two]),
            "to": (1, backbone[index_two]),
            "kind": "drop_down",
            "optional": True,
            "decoy": False,
        },
        {
            "id": "E2",
            "from": (1, backbone[index_three]),
            "to": (2, backbone[index_three]),
            "kind": "elevator_up",
            "optional": False,
            "decoy": False,
        },
        {
            "id": "E3",
            "from": (2, backbone[index_four]),
            "to": (3, backbone[index_four]),
            "kind": "elevator_up",
            "optional": False,
            "decoy": False,
        },
        {
            "id": "D2",
            "from": (3, backbone[index_five]),
            "to": (2, backbone[index_five]),
            "kind": "drop_down",
            "optional": True,
            "decoy": False,
        },
        {
            "id": "E4",
            "from": (2, backbone[index_six]),
            "to": (3, backbone[index_six]),
            "kind": "elevator_up",
            "optional": False,
            "decoy": False,
            "finish_access": True,
        },
        {
            "id": "E5",
            "from": (1, decoy_elevator_cell),
            "to": (3, decoy_elevator_cell),
            "kind": "elevator_up",
            "optional": True,
            "decoy": True,
        },
        {
            "id": "D3",
            "from": (3, decoy_drop_cell),
            "to": (1, decoy_drop_cell),
            "kind": "drop_down",
            "optional": True,
            "decoy": True,
        },
    ]
    for transition in transition_specs:
        graph.add_edge(transition["from"], transition["to"])

    route = [(1, backbone[0])]

    def navigate_backbone(floor, start_index, end_index):
        if route[-1] != (floor, backbone[start_index]):
            raise ValueError("The planned route is not at its backbone segment.")
        route.extend(
            (floor, backbone[index])
            for index in range(start_index + 1, end_index + 1)
        )

    def take_transition(transition):
        if route[-1] != transition["from"]:
            raise ValueError("The planned route does not reach its transition.")
        route.append(transition["to"])

    transitions = {transition["id"]: transition for transition in transition_specs}
    navigate_backbone(1, 0, index_one)
    take_transition(transitions["E1"])
    navigate_backbone(2, index_one, index_two)
    take_transition(transitions["D1"])
    navigate_backbone(1, index_two, index_three)
    take_transition(transitions["E2"])
    navigate_backbone(2, index_three, index_four)
    take_transition(transitions["E3"])
    navigate_backbone(3, index_four, index_five)
    take_transition(transitions["D2"])
    navigate_backbone(2, index_five, index_six)
    take_transition(transitions["E4"])
    navigate_backbone(3, index_six, edge_count)

    if len(route) != len(set(route)):
        raise ValueError("The planned route revisits a floor cell.")
    return graph, route, transition_specs


def validate_route(graph: nx.DiGraph, route):
    if not route or len(route) != len(set(route)):
        return False

    for previous, current in zip(route, route[1:]):
        if current not in graph.successors(previous):
            return False

    if route[0][0] != 1 or route[-1][0] != 3:
        return False

    level_changes = [
        current[0] - previous[0]
        for previous, current in zip(route, route[1:])
        if current[0] != previous[0]
    ]
    return any(change > 0 for change in level_changes) and any(
        change < 0 for change in level_changes
    )

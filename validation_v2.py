from __future__ import annotations

import networkx as nx

from geometry_v2 import (
    ENTRANCE,
    FINISH_ENTRANCE_CELL,
    FLOORS,
    Rectangle,
    finish_connector_is_valid,
    generate_grid,
    nearest_endpoint_cells,
    shared_grid_cells,
)


def _edge_key(a, b):
    return tuple(sorted((a, b)))


def _rectangles_share_open_boundary(a, b):
    """Return True when two rectangles touch along at least one block edge."""
    vertical_touch = (
        a.max_x + 1 == b.min_x or b.max_x + 1 == a.min_x
    ) and max(a.min_z, b.min_z) <= min(a.max_z, b.max_z)
    horizontal_touch = (
        a.max_z + 1 == b.min_z or b.max_z + 1 == a.min_z
    ) and max(a.min_x, b.min_x) <= min(a.max_x, b.max_x)
    return vertical_touch or horizontal_touch


def _cell_rectangle(cell):
    x, z = cell
    return Rectangle(x, x + 2, z, z + 2)


def _validate_floor(floor, maze, errors):
    if floor not in FLOORS:
        errors.append(f"Unknown floor {floor}.")
        return

    expected_cells, expected_connections = generate_grid(floor)
    cells = set(maze.get("cells", ()))

    if cells != expected_cells:
        errors.append(
            f"Floor {floor}: generated cells do not match the valid floor grid."
        )

    connections = maze.get("connections", {})
    if set(connections) != cells:
        errors.append(
            f"Floor {floor}: connection entries do not match the maze cells."
        )
    else:
        for cell, neighbors in connections.items():
            if set(neighbors) != set(expected_connections.get(cell, ())):
                errors.append(
                    f"Floor {floor}: invalid or missing neighbors for cell {cell}."
                )
                break

    opened_edges = {
        _edge_key(a, b) for a, b in maze.get("opened_edges", ())
    }
    valid_edges = {
        _edge_key(cell, neighbor)
        for cell, neighbors in expected_connections.items()
        for neighbor in neighbors
    }
    if not opened_edges <= valid_edges:
        errors.append(f"Floor {floor}: an opened passage is not a valid connection.")

    carved_graph = nx.Graph()
    carved_graph.add_nodes_from(cells)
    carved_graph.add_edges_from(opened_edges)
    if cells and not nx.is_connected(carved_graph):
        errors.append(f"Floor {floor}: the carved horizontal maze is disconnected.")


def validate_multifloor_maze(floor_mazes, graph, route, transitions):
    """
    Validate the generated maze's geometry references and navigation graph.

    This checks consistency against the floor geometry and generated passage
    data. It does not replace a later block-by-block blueprint collision check.
    """
    errors = []

    if set(floor_mazes) != set(FLOORS):
        errors.append("The maze does not contain exactly the defined floors.")

    for floor in FLOORS:
        if floor in floor_mazes:
            _validate_floor(floor, floor_mazes[floor], errors)

    if not route:
        errors.append("The solution route is empty.")
        start = finish = None
    else:
        start, finish = route[0], route[-1]
        if start[0] != 1:
            errors.append("The solution route does not start on Floor 1.")
        if finish != (3, FINISH_ENTRANCE_CELL):
            errors.append("The solution route does not end at the finish connector.")
        if len(route) != len(set(route)):
            errors.append("The solution route revisits a cell.")
        if not all(graph.has_edge(a, b) for a, b in zip(route, route[1:])):
            errors.append("The solution route contains a missing graph connection.")

    # The entrance marker must physically touch the selected starting cell.
    if start is not None:
        start_floor, start_cell = start
        if start_floor != 1 or start_cell not in floor_mazes.get(1, {}).get("cells", ()):
            errors.append("The selected entrance cell is not a valid Floor 1 cell.")
        else:
            nearest = nearest_endpoint_cells(floor_mazes[1]["cells"], ENTRANCE)
            if start_cell not in nearest:
                errors.append("The selected start is not one of the nearest entrance cells.")
            if not _rectangles_share_open_boundary(
                _cell_rectangle(start_cell), ENTRANCE
            ):
                errors.append("The selected start cell does not touch the entrance.")

    # The finish is a special two-block doorway, not an ordinary grid edge.
    if not finish_connector_is_valid():
        errors.append("The special finish doorway is not physically valid.")
    if FINISH_ENTRANCE_CELL not in floor_mazes.get(3, {}).get("cells", ()):
        errors.append("The finish doorway's source cell is missing from Floor 3.")

    expected_nodes = {
        (floor, cell)
        for floor, maze in floor_mazes.items()
        for cell in maze.get("cells", ())
    }
    if set(graph.nodes) != expected_nodes:
        errors.append("The navigation graph nodes do not match the floor maze cells.")

    transition_by_id = {}
    for transition in transitions:
        transition_id = transition.get("id")
        if not transition_id or transition_id in transition_by_id:
            errors.append("A transition is missing a unique ID.")
            continue
        transition_by_id[transition_id] = transition

        source = transition.get("from")
        destination = transition.get("to")
        cell = transition.get("cell")
        if not source or not destination or source[1] != cell or destination[1] != cell:
            errors.append(f"Transition {transition_id}: source, destination, and cell disagree.")
            continue

        source_floor, destination_floor = source[0], destination[0]
        if source_floor == destination_floor:
            errors.append(f"Transition {transition_id}: vertical transition stays on one floor.")
            continue
        if source_floor not in floor_mazes or destination_floor not in floor_mazes:
            errors.append(f"Transition {transition_id}: references an unknown floor.")
            continue
        if (
            cell not in floor_mazes[source_floor]["cells"]
            or cell not in floor_mazes[destination_floor]["cells"]
        ):
            errors.append(f"Transition {transition_id}: its 3x3 cell does not fit both floors.")

        if cell not in shared_grid_cells((source_floor, destination_floor)):
            errors.append(f"Transition {transition_id}: its cell is not shared by both floors.")

        expected_kind = (
            "elevator_up"
            if destination_floor > source_floor
            else "drop_down"
        )
        if transition.get("kind") != expected_kind:
            errors.append(f"Transition {transition_id}: direction and type disagree.")

        if not graph.has_edge(source, destination):
            errors.append(f"Transition {transition_id}: graph edge is missing.")
        else:
            edge_data = graph[source][destination]
            if (
                edge_data.get("kind") != expected_kind
                or edge_data.get("transition_id") != transition_id
            ):
                errors.append(f"Transition {transition_id}: graph edge metadata disagrees.")

        if graph.has_edge(destination, source):
            errors.append(f"Transition {transition_id}: reverse travel is incorrectly enabled.")

    # Every graph edge must correspond to a carved horizontal passage or one
    # of the explicitly defined one-way vertical transitions.
    expected_horizontal = set()
    for floor, maze in floor_mazes.items():
        for a, b in maze.get("opened_edges", ()):
            expected_horizontal.add(((floor, a), (floor, b)))
            expected_horizontal.add(((floor, b), (floor, a)))

    actual_horizontal = set()
    actual_vertical = set()
    for source, destination, data in graph.edges(data=True):
        kind = data.get("kind")
        if kind == "corridor":
            actual_horizontal.add((source, destination))
        elif kind in ("elevator_up", "drop_down"):
            actual_vertical.add((source, destination))
        else:
            errors.append(f"Graph edge {source} -> {destination} has an unknown type.")

    if actual_horizontal != expected_horizontal:
        errors.append("Horizontal graph edges do not match the carved passages.")

    expected_vertical = {
        (transition["from"], transition["to"])
        for transition in transition_by_id.values()
        if transition.get("from") and transition.get("to")
    }
    if actual_vertical != expected_vertical:
        errors.append("Vertical graph edges do not match the defined transitions.")

    return {
        "valid": not errors,
        "errors": errors,
        "checks": {
            "floor_count": len(floor_mazes),
            "transition_count": len(transitions),
            "route_cell_count": len(route),
            "entrance_touches_start": start is not None and not any(
                "entrance" in error.lower() or "start" in error.lower()
                for error in errors
            ),
            "finish_connector_valid": finish_connector_is_valid(),
            "one_way_transitions": not any(
                "reverse travel" in error for error in errors
            ),
        },
    }

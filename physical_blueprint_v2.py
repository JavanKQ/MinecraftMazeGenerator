from __future__ import annotations

from geometry_v2 import (
    CORRIDOR_WIDTH,
    ENTRANCE,
    FINISH,
    FINISH_ENTRANCE_BLOCKS,
    FINISH_ENTRANCE_CELL,
    FLOORS,
    finish_connector_is_valid,
)
from validation_v2 import validate_multifloor_maze


def _edge_key(a, b):
    return tuple(sorted((a, b)))


def _rectangle_data(rectangle):
    return {
        "min_x": rectangle.min_x,
        "max_x": rectangle.max_x,
        "min_z": rectangle.min_z,
        "max_z": rectangle.max_z,
    }


def _cell_blocks(cell):
    x, z = cell
    return [
        (x + dx, z + dz)
        for dx in range(CORRIDOR_WIDTH)
        for dz in range(CORRIDOR_WIDTH)
    ]


def _wall_segment(a, b):
    """Return the three physical blocks between adjacent 3x3 cells."""
    ax, az = a
    bx, bz = b

    if az == bz and abs(ax - bx) == CORRIDOR_WIDTH + 1:
        west_x = min(ax, bx)
        return [
            (west_x + CORRIDOR_WIDTH, az + offset)
            for offset in range(CORRIDOR_WIDTH)
        ]

    if ax == bx and abs(az - bz) == CORRIDOR_WIDTH + 1:
        south_z = min(az, bz)
        return [
            (ax + offset, south_z + CORRIDOR_WIDTH)
            for offset in range(CORRIDOR_WIDTH)
        ]

    # Cells that touch directly have no physical wall segment between them.
    if az == bz and abs(ax - bx) == CORRIDOR_WIDTH:
        return []
    if ax == bx and abs(az - bz) == CORRIDOR_WIDTH:
        return []

    raise ValueError(f"Cells {a} and {b} do not have supported adjacency geometry.")


def _shared_boundary_blocks(cell, marker):
    """Find marker blocks directly adjoining a corridor cell."""
    x, z = cell
    cell_max_x = x + CORRIDOR_WIDTH - 1
    cell_max_z = z + CORRIDOR_WIDTH - 1
    blocks = set()

    if cell_max_x + 1 == marker.min_x:
        for block_z in range(max(z, marker.min_z), min(cell_max_z, marker.max_z) + 1):
            blocks.add((marker.min_x, block_z))
    elif marker.max_x + 1 == x:
        for block_z in range(max(z, marker.min_z), min(cell_max_z, marker.max_z) + 1):
            blocks.add((marker.max_x, block_z))

    if cell_max_z + 1 == marker.min_z:
        for block_x in range(max(x, marker.min_x), min(cell_max_x, marker.max_x) + 1):
            blocks.add((block_x, marker.min_z))
    elif marker.max_z + 1 == z:
        for block_x in range(max(x, marker.min_x), min(cell_max_x, marker.max_x) + 1):
            blocks.add((block_x, marker.max_z))

    return sorted(blocks)


def build_physical_blueprint(floor_mazes, graph, route, transitions):
    """
    Convert validated maze data into a renderer-independent physical blueprint.

    This function does not generate or alter the maze. It records the physical
    floor regions, traversable cells, open passages, closed wall segments,
    special connectors, vertical transitions, and solution route.
    """
    validation = validate_multifloor_maze(
        floor_mazes, graph, route, transitions
    )
    if not validation["valid"]:
        details = "; ".join(validation["errors"])
        raise ValueError(f"Cannot blueprint an invalid maze: {details}")

    if not finish_connector_is_valid():
        raise ValueError("The special finish connector is not physically valid.")

    start_floor, start_cell = route[0]
    finish_floor, finish_cell = route[-1]
    if start_floor != 1:
        raise ValueError("The solution route must begin on Floor 1.")
    if (finish_floor, finish_cell) != (3, FINISH_ENTRANCE_CELL):
        raise ValueError("The solution route must end at the finish connector.")

    entrance_blocks = _shared_boundary_blocks(start_cell, ENTRANCE)
    if not entrance_blocks:
        raise ValueError("The selected starting cell does not touch the entrance.")

    floor_blueprints = {}
    for floor, maze in floor_mazes.items():
        cells = set(maze["cells"])
        opened_edges = {_edge_key(a, b) for a, b in maze["opened_edges"]}
        possible_edges = {
            _edge_key(cell, neighbor)
            for cell, neighbors in maze["connections"].items()
            for neighbor in neighbors
        }

        open_passages = []
        wall_segments = []
        for a, b in sorted(possible_edges):
            blocks = _wall_segment(a, b)
            if _edge_key(a, b) in opened_edges:
                open_passages.append({
                    "cells": [a, b],
                    "opening_blocks": blocks,
                })
            elif not blocks:
                raise ValueError(
                    f"Floor {floor}: adjacent cells {a} and {b} cannot be separated by a wall."
                )
            else:
                wall_segments.append({
                    "cells": [a, b],
                    "blocks": blocks,
                })

        floor_route = [
            cell for route_floor, cell in route if route_floor == floor
        ]
        floor_transitions = [
            {
                "id": transition["id"],
                "cell": transition["cell"],
                "kind": transition["kind"],
                "from_floor": transition["from"][0],
                "to_floor": transition["to"][0],
                "is_departure": transition["from"][0] == floor,
                "is_arrival": transition["to"][0] == floor,
            }
            for transition in transitions
            if floor in (transition["from"][0], transition["to"][0])
        ]

        floor_blueprints[floor] = {
            "floor": floor,
            "y": FLOORS[floor]["y"],
            "footprint": [
                _rectangle_data(rectangle)
                for rectangle in FLOORS[floor]["footprint"]
            ],
            "cells": sorted(cells),
            "cell_blocks": [
                {"cell": cell, "blocks": _cell_blocks(cell)}
                for cell in sorted(cells)
            ],
            "open_passages": open_passages,
            "wall_segments": wall_segments,
            "route_cells": floor_route,
            "transitions": floor_transitions,
        }

    route_steps = []
    for index, node in enumerate(route):
        floor, cell = node
        incoming = None
        if index:
            previous = route[index - 1]
            edge_data = graph.get_edge_data(previous, node)
            incoming = {
                "from": previous,
                "kind": edge_data["kind"],
                "transition_id": edge_data.get("transition_id"),
            }
        route_steps.append({
            "index": index,
            "floor": floor,
            "cell": cell,
            "incoming": incoming,
        })

    return {
        "schema_version": 1,
        "grid": {
            "origin_x": 11360,
            "origin_z": 10904,
            "pitch": 4,
            "corridor_width": CORRIDOR_WIDTH,
            "wall_thickness": 1,
        },
        "floors": floor_blueprints,
        "entrance": {
            "floor": 1,
            "y": FLOORS[1]["y"],
            "marker": _rectangle_data(ENTRANCE),
            "source_cell": start_cell,
            "opening_blocks": entrance_blocks,
        },
        "finish": {
            "floor": 3,
            "y": FLOORS[3]["y"],
            "region": _rectangle_data(FINISH),
            "source_cell": FINISH_ENTRANCE_CELL,
            "opening_blocks": sorted(FINISH_ENTRANCE_BLOCKS),
        },
        "vertical_transitions": [
            {
                "id": transition["id"],
                "cell": transition["cell"],
                "from": transition["from"],
                "to": transition["to"],
                "kind": transition["kind"],
                "floors_apart": transition["floors_apart"],
            }
            for transition in transitions
        ],
        "solution_route": route_steps,
    }

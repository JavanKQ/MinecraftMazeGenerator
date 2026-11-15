"""Translate a validated v3 physical layout into the v2 renderer's blueprint schema.

This adapter deliberately does not call v2 maze validation or modify the
existing renderer. It only translates already-generated v3 geometry.
"""

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
from global_graph_v3 import find_minimum_journey_route


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


def build_physical_blueprint_v3(layout):
    """Build the renderer-compatible blueprint from a validated v3 layout."""
    validation = layout.get("validation", {})
    if not validation.get("valid"):
        details = "; ".join(validation.get("errors", ["missing validation report"]))
        raise ValueError(f"Cannot blueprint an invalid v3 layout: {details}")

    if not finish_connector_is_valid():
        raise ValueError("The special finish connector is not physically valid.")

    floor_mazes = layout["floor_mazes"]
    graph = layout["navigation_graph"]
    start = layout["start"]
    finish = layout["finish"]

    if start[0] != 1:
        raise ValueError("The solution route must begin on Floor 1.")
    if finish != (3, FINISH_ENTRANCE_CELL):
        raise ValueError("The solution route must end at the finish connector.")

    route = find_minimum_journey_route(graph, start, finish)
    entrance_blocks = _shared_boundary_blocks(start[1], ENTRANCE)
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

        floor_transitions = []
        for area in layout["transition_areas"]:
            for source_floor, destination_floor in area.journeys:
                if floor not in (source_floor, destination_floor):
                    continue
                floor_transitions.append({
                    "id": area.id,
                    "cell": area.cell,
                    "kind": area.kind,
                    "from_floor": source_floor,
                    "to_floor": destination_floor,
                    "is_departure": source_floor == floor,
                    "is_arrival": destination_floor == floor,
                })

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

    vertical_transitions = []
    for area in layout["transition_areas"]:
        for source_floor, destination_floor in area.journeys:
            vertical_transitions.append({
                "id": area.id,
                "cell": area.cell,
                "from": (source_floor, area.cell),
                "to": (destination_floor, area.cell),
                "kind": area.kind,
                "floors_apart": abs(destination_floor - source_floor),
            })

    return {
        "schema_version": 1,
        "source_architecture": "v3",
        "seed": layout["seed"],
        "generation_attempt": layout["attempt"],
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
            "source_cell": start[1],
            "opening_blocks": entrance_blocks,
        },
        "finish": {
            "floor": 3,
            "y": FLOORS[3]["y"],
            "region": _rectangle_data(FINISH),
            "source_cell": FINISH_ENTRANCE_CELL,
            "opening_blocks": sorted(FINISH_ENTRANCE_BLOCKS),
        },
        "vertical_transitions": vertical_transitions,
        "solution_route": route_steps,
    }

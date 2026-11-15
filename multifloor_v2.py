from __future__ import annotations

import math
import random

import networkx as nx

from geometry_v2 import (
    ENTRANCE,
    FINISH_ENTRANCE_CELL,
    FLOORS,
    generate_grid,
    nearest_endpoint_cells,
    shared_grid_cells,
)
from generator_v2 import generate_floor_mazes


def _transition_type(source_floor, destination_floor):
    return "elevator_up" if destination_floor > source_floor else "drop_down"


def _random_extra_count(rng, candidate_count):
    """Scale the number of optional transitions to the available shared space."""
    maximum = max(1, round(math.sqrt(candidate_count) / 8))
    return rng.randint(0, maximum)


def build_multifloor_maze(seed="Maze1", loop_percentage=12):
    """
    Build independent floor mazes and connect them with randomized,
    direction-aware vertical transitions.

    One upward connection between each adjacent floor pair guarantees a
    route from Floor 1 to Floor 3. All other transition counts, positions,
    directions, and two-floor jumps are randomized.
    """
    rng = random.Random(seed)
    floor_mazes = generate_floor_mazes(seed, loop_percentage)
    graph = nx.DiGraph()

    # Horizontal passages are walkable in both directions.
    for floor, maze in floor_mazes.items():
        nodes = [(floor, cell) for cell in maze["cells"]]
        graph.add_nodes_from(nodes)
        for cell_a, cell_b in maze["opened_edges"]:
            graph.add_edge((floor, cell_a), (floor, cell_b), kind="corridor")
            graph.add_edge((floor, cell_b), (floor, cell_a), kind="corridor")

    start_cells = sorted(
        nearest_endpoint_cells(floor_mazes[1]["cells"], ENTRANCE)
    )
    start = (1, rng.choice(start_cells))
    finish = (3, FINISH_ENTRANCE_CELL)
    if finish[1] not in floor_mazes[3]["cells"]:
        raise ValueError("The finish connector source is not a valid Floor 3 cell.")

    transitions = []
    transition_number = 1
    used_positions = set()

    # Adjacent upward links form the guaranteed route between all floors.
    # The direct 1-to-3 pair is optional and may create a shortcut.
    floor_pairs = ((1, 2, True), (2, 3, True), (1, 3, False))

    for lower_floor, upper_floor, required in floor_pairs:
        candidates = sorted(shared_grid_cells((lower_floor, upper_floor)))
        candidates = [cell for cell in candidates if cell not in used_positions]
        if not candidates:
            if required:
                raise ValueError(
                    f"No shared cells are available between floors "
                    f"{lower_floor} and {upper_floor}."
                )
            continue

        extra_count = _random_extra_count(rng, len(candidates))
        count = min(len(candidates), extra_count + int(required))
        selected = rng.sample(candidates, count)

        if required:
            # The first selected cell is the guaranteed upward connection.
            guaranteed_cell = selected[0]
            selected_specs = [
                (guaranteed_cell, lower_floor, upper_floor, True)
            ]
            remaining = selected[1:]
        else:
            remaining = selected
            selected_specs = []

        for cell in remaining:
            if rng.choice((True, False)):
                source_floor, destination_floor = lower_floor, upper_floor
            else:
                source_floor, destination_floor = upper_floor, lower_floor
            selected_specs.append((cell, source_floor, destination_floor, False))

        for cell, source_floor, destination_floor, guaranteed in selected_specs:
            used_positions.add(cell)
            transition_id = f"T{transition_number}"
            transition_number += 1
            transition = {
                "id": transition_id,
                "cell": cell,
                "from": (source_floor, cell),
                "to": (destination_floor, cell),
                "kind": _transition_type(source_floor, destination_floor),
                "floors_apart": abs(destination_floor - source_floor),
                "guaranteed_route_link": guaranteed,
                "decoy": False,
            }
            transitions.append(transition)
            graph.add_edge(
                transition["from"],
                transition["to"],
                kind=transition["kind"],
                transition_id=transition_id,
            )

    if not nx.has_path(graph, start, finish):
        raise ValueError(
            "The generated transition network does not connect entrance to finish."
        )

    # Random positive weights select a reproducible but non-obvious valid route.
    for source, destination in graph.edges:
        graph[source][destination]["route_weight"] = rng.random() + 0.01

    route = nx.shortest_path(
        graph,
        start,
        finish,
        weight="route_weight",
    )
    route_edges = set(zip(route, route[1:]))
    for transition in transitions:
        transition["decoy"] = (
            transition["from"], transition["to"]
        ) not in route_edges

    if not validate_multifloor_route(graph, route, start, finish):
        raise ValueError("The generated solution route failed validation.")

    return floor_mazes, graph, route, transitions


def validate_multifloor_route(graph, route, start=None, finish=None):
    if not route:
        return False
    if len(route) != len(set(route)):
        return False
    if start is not None and route[0] != start:
        return False
    if finish is not None and route[-1] != finish:
        return False

    for previous, current in zip(route, route[1:]):
        if not graph.has_edge(previous, current):
            return False

    return True

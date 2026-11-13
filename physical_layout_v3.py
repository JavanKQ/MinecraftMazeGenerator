"""Physical floor-cell partitioning and corridor carving for maze v3.

This module maps the abstract ten-region plan onto the real shared-grid
footprints. Each region is grown as a connected multi-source-free territory
(one seed per region per floor), then transition locations are assigned by a
bipartite matching so all 25 physical areas have unique X/Z coordinates.
"""

from __future__ import annotations

from collections import deque
import math
import random

import networkx as nx

from geometry_v2 import (
    ENTRANCE,
    FINISH_ENTRANCE_CELL,
    FINISH_FLOOR,
    FLOORS,
    finish_connector_is_valid,
    generate_grid,
    nearest_endpoint_cells,
)
from global_graph_v3 import (
    TARGET_TRANSITION_AREA_COUNT,
    TransitionArea,
    build_global_navigation_graph,
    navigation_graph_report,
)
from region_plan_v3 import build_region_plan, validate_region_plan


DEFAULT_LOOP_PERCENTAGE = 12


def _edge_key(cell_a, cell_b):
    return tuple(sorted((cell_a, cell_b)))


def _grow_connected_regions(cells, connections, regions, rng, floor, fixed_seeds):
    """Connect each region's anchors first, then grow connected territories."""
    cells = set(cells)
    if not cells:
        raise ValueError(f"Floor {floor} has no playable cells.")

    base_graph = nx.Graph()
    base_graph.add_nodes_from(cells)
    base_graph.add_edges_from(
        (cell, neighbor)
        for cell in cells
        for neighbor in connections[cell]
        if neighbor in cells
    )
    if not nx.is_connected(base_graph):
        raise ValueError(f"Floor {floor}'s physical cell graph is disconnected.")

    region_ids = {region["id"] for region in regions}
    if set(fixed_seeds) != region_ids:
        raise ValueError(
            f"Floor {floor} must have transition anchors for every assigned region."
        )

    anchors = {}
    anchor_owner = {}
    for region in regions:
        region_id = region["id"]
        region_anchors = set(fixed_seeds[region_id])
        if not region_anchors:
            raise ValueError(f"Region {region_id} has no physical anchor on Floor {floor}.")
        if not region_anchors <= cells:
            raise ValueError(f"An anchor for {region_id} is not playable on Floor {floor}.")
        anchors[region_id] = region_anchors
        for cell in region_anchors:
            if cell in anchor_owner:
                raise ValueError(
                    f"Two regions claim anchor {cell} on Floor {floor}."
                )
            anchor_owner[cell] = region_id

    # Reserve a connected path-tree for every region. Paths may use unclaimed
    # cells, but may not cross another region's anchors or an existing tree.
    # Regions with more anchors are handled first to reduce later conflicts.
    region_order = list(region_ids)
    rng.shuffle(region_order)
    region_order.sort(key=lambda region_id: -len(anchors[region_id]))
    region_trees = {}
    claimed_by = {}

    for region_id in region_order:
        region_anchors = list(anchors[region_id])
        rng.shuffle(region_anchors)
        tree_cells = {region_anchors.pop()}
        for cell in tree_cells:
            claimed_by[cell] = region_id

        while region_anchors:
            rng.shuffle(region_anchors)
            best_path = None
            best_anchor = None
            for anchor in region_anchors:
                allowed = {
                    cell for cell in cells
                    if (
                        (cell not in claimed_by or claimed_by[cell] == region_id)
                        and anchor_owner.get(cell, region_id) == region_id
                    )
                }
                allowed_graph = base_graph.subgraph(allowed)
                try:
                    path = nx.shortest_path(
                        allowed_graph,
                        source=min(tree_cells),
                        target=anchor,
                    )
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    # A multi-source search below may still reach the anchor
                    # from another branch of this region's existing tree.
                    try:
                        path = nx.multi_source_dijkstra_path(
                            allowed_graph,
                            sources=tree_cells,
                            target=anchor,
                        )
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue
                if best_path is None or len(path) < len(best_path):
                    best_path = path
                    best_anchor = anchor

            if best_path is None:
                raise ValueError(
                    f"Could not connect all anchors for {region_id} on Floor {floor}."
                )
            for cell in best_path:
                previous_owner = claimed_by.get(cell)
                if previous_owner not in (None, region_id):
                    raise ValueError("Region connector path crossed another region.")
                claimed_by[cell] = region_id
                tree_cells.add(cell)
            region_anchors.remove(best_anchor)

        region_trees[region_id] = tree_cells

    # Grow all unclaimed cells from the already-connected region trees.
    # Each newly claimed cell touches an existing cell of that same region,
    # so connectedness is preserved throughout the expansion.
    labels = dict(claimed_by)
    pending = deque()
    seed_items = [
        (region_id, cell)
        for region_id, tree in region_trees.items()
        for cell in tree
    ]
    rng.shuffle(seed_items)
    pending.extend(seed_items)

    while pending:
        region_id, cell = pending.popleft()
        neighbors = list(connections[cell])
        rng.shuffle(neighbors)
        for neighbor in neighbors:
            if neighbor in cells and neighbor not in labels:
                labels[neighbor] = region_id
                pending.append((region_id, neighbor))

    if set(labels) != cells:
        raise ValueError(f"Floor {floor} region growth did not cover every cell.")

    region_cells = {region["id"]: set() for region in regions}
    for cell, region_id in labels.items():
        region_cells[region_id].add(cell)

    for region_id, assigned in region_cells.items():
        if not assigned or not nx.is_connected(base_graph.subgraph(assigned)):
            raise ValueError(
                f"Region {region_id} is disconnected on Floor {floor}."
            )

    return labels, region_cells, region_trees, base_graph

def _select_transition_cells(plan, floor_grids, reserved_cells, rng):
    """Choose unique valid X/Z cells before assigning any region boundaries.

    Candidate cells need only fit on the two floors served by that physical
    transition. Region membership is then built around these fixed anchors.
    """
    matching_graph = nx.Graph()
    area_nodes = []
    candidates_by_area = {}

    for area in plan["transition_areas"]:
        area_node = ("area", area["id"])
        area_nodes.append(area_node)
        source_floor = area["from_floor"]
        destination_floor = area["to_floor"]
        source_cells = floor_grids[source_floor][0]
        destination_cells = floor_grids[destination_floor][0]
        candidates = (source_cells & destination_cells) - set(reserved_cells)
        if not candidates:
            raise ValueError(
                f"{area['id']} has no physically shared cell between "
                f"Floor {source_floor} and Floor {destination_floor}."
            )

        ordered_candidates = list(candidates)
        rng.shuffle(ordered_candidates)
        candidates_by_area[area["id"]] = candidates
        matching_graph.add_node(area_node, bipartite=0)
        for cell in ordered_candidates:
            matching_graph.add_edge(area_node, ("cell", cell))

    matching = nx.algorithms.bipartite.maximum_matching(
        matching_graph,
        top_nodes=set(area_nodes),
    )
    assigned = {
        area_node[1]: matching[area_node][1]
        for area_node in area_nodes
        if area_node in matching
    }

    if len(assigned) != len(plan["transition_areas"]):
        missing = sorted(
            {area["id"] for area in plan["transition_areas"]} - set(assigned)
        )
        raise ValueError(
            "Could not assign unique physical cells to all transition areas; "
            f"unmatched: {', '.join(missing)}."
        )

    chosen = list(assigned.values())
    if len(chosen) != len(set(chosen)) or set(chosen) & set(reserved_cells):
        raise ValueError("Transition matching produced duplicate or reserved cells.")
    for area_id, cell in assigned.items():
        if cell not in candidates_by_area[area_id]:
            raise ValueError(f"{area_id} was assigned a cell outside its floor overlap.")

    return assigned

def _carve_region(region_cells, connections, rng, loop_percentage):
    """Carve a randomized spanning tree plus a percentage of extra loops."""
    if not 0 <= loop_percentage <= 100:
        raise ValueError("loop_percentage must be between 0 and 100.")

    region_cells = set(region_cells)
    graph = nx.Graph()
    graph.add_nodes_from(sorted(region_cells))
    possible_edges = {
        _edge_key(cell, neighbor)
        for cell in region_cells
        for neighbor in connections[cell]
        if neighbor in region_cells
    }
    graph.add_edges_from(sorted(possible_edges))

    if not region_cells or not nx.is_connected(graph):
        raise ValueError("A region must be non-empty and horizontally connected.")

    for cell_a, cell_b in graph.edges:
        graph[cell_a][cell_b]["weight"] = rng.random()

    tree = nx.minimum_spanning_tree(graph, algorithm="kruskal", weight="weight")
    if len(region_cells) > 1 and not nx.is_tree(tree):
        raise ValueError("Region carving failed to produce a spanning tree.")

    opened_edges = {
        _edge_key(cell_a, cell_b)
        for cell_a, cell_b in tree.edges
    }
    closed_edges = sorted(possible_edges - opened_edges)
    loop_count = min(
        len(closed_edges),
        math.floor(len(opened_edges) * loop_percentage / 100 + 0.5),
    )
    if loop_count:
        opened_edges.update(rng.sample(closed_edges, loop_count))

    return opened_edges, len(possible_edges)


def _build_floor_mazes(region_labels, region_cells, rng, loop_percentage):
    floor_mazes = {}
    for floor in FLOORS:
        cells, connections = generate_grid(floor)
        opened_edges = set()
        possible_edge_count = 0

        floor_regions = sorted(region_cells[floor])
        for region_id in floor_regions:
            region_rng = random.Random(rng.getrandbits(128))
            region_edges, region_possible = _carve_region(
                region_cells[floor][region_id],
                connections,
                region_rng,
                loop_percentage,
            )
            opened_edges.update(region_edges)
            possible_edge_count += region_possible

        floor_mazes[floor] = {
            "cells": cells,
            "connections": connections,
            "opened_edges": opened_edges,
            "possible_edges": possible_edge_count,
            "region_by_cell": dict(region_labels[floor]),
            "loop_percentage": loop_percentage,
        }

    return floor_mazes


def validate_physical_layout(layout):
    """Validate physical partitions, passage boundaries, transitions and routes."""
    errors = []
    plan = layout["region_plan"]
    floor_mazes = layout["floor_mazes"]
    region_cells = layout["region_cells"]
    transition_areas = layout["transition_areas"]
    graph = layout["navigation_graph"]
    start = layout["start"]
    finish = layout["finish"]

    plan_report = validate_region_plan(plan)
    if not plan_report["valid"]:
        errors.extend(f"Region plan: {error}" for error in plan_report["errors"])

    if len(transition_areas) != TARGET_TRANSITION_AREA_COUNT:
        errors.append(
            f"Expected {TARGET_TRANSITION_AREA_COUNT} physical transition areas."
        )

    seen_cells = set()
    for area in transition_areas:
        if area.cell in seen_cells:
            errors.append(f"Duplicate transition coordinate: {area.cell}.")
        seen_cells.add(area.cell)

        plan_area = next(
            (item for item in plan["transition_areas"] if item["id"] == area.id),
            None,
        )
        if plan_area is None:
            errors.append(f"Unexpected transition area {area.id}.")
            continue

        source_floor = plan_area["from_floor"]
        destination_floor = plan_area["to_floor"]
        source_region = plan_area["source_region"]
        destination_region = plan_area["destination_region"]

        if area.cell not in region_cells[source_floor].get(source_region, set()):
            errors.append(
                f"{area.id} is not inside source region {source_region}."
            )
        if area.cell not in region_cells[destination_floor].get(destination_region, set()):
            errors.append(
                f"{area.id} is not inside destination region {destination_region}."
            )

    for floor, maze in floor_mazes.items():
        cells = set(maze["cells"])
        labels = maze["region_by_cell"]
        if set(labels) != cells:
            errors.append(f"Floor {floor} region labels do not cover its cells.")

        for cell_a, cell_b in maze["opened_edges"]:
            if cell_a not in cells or cell_b not in cells:
                errors.append(f"Floor {floor} has a passage outside its cell set.")
            elif labels.get(cell_a) != labels.get(cell_b):
                errors.append(
                    f"Floor {floor} has a horizontal passage crossing region boundaries."
                )

        for region_id, assigned in region_cells[floor].items():
            region_graph = nx.Graph()
            region_graph.add_nodes_from(assigned)
            region_graph.add_edges_from(
                (cell_a, cell_b)
                for cell_a, cell_b in maze["opened_edges"]
                if cell_a in assigned and cell_b in assigned
            )
            if not assigned or not nx.is_connected(region_graph):
                errors.append(
                    f"Carved region {region_id} is disconnected on Floor {floor}."
                )

    if not finish_connector_is_valid():
        errors.append("The special finish entrance connector is physically invalid.")

    report = navigation_graph_report(
        graph,
        start,
        finish,
        transition_areas,
    )
    if not report["strongly_connected"]:
        errors.append("The complete physical navigation graph is not strongly connected.")
    if report["minimum_vertical_journeys"] != 9:
        errors.append(
            "The complete physical graph does not require exactly nine "
            "vertical journeys from entrance to finish."
        )

    return {
        "valid": not errors,
        "errors": errors,
        "region_plan": plan_report,
        "navigation": report,
        "floor_cell_counts": {
            floor: len(maze["cells"]) for floor, maze in floor_mazes.items()
        },
        "region_cell_counts": {
            floor: {
                region_id: len(cells)
                for region_id, cells in regions.items()
            }
            for floor, regions in region_cells.items()
        },
    }


def build_physical_layout(
    seed="Maze1",
    loop_percentage=DEFAULT_LOOP_PERCENTAGE,
    max_attempts=250,
):
    """Generate a complete physical v3 layout, retrying randomized partitions.

    The same seed and parameters reproduce the same result. Each attempt may
    choose a different valid region-floor sequence and a new connected
    partition, but no failed attempt is returned as a usable maze.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    rng = random.Random(seed)
    grids = {floor: generate_grid(floor) for floor in FLOORS}
    for floor, (cells, connections) in grids.items():
        graph = nx.Graph()
        graph.add_nodes_from(cells)
        graph.add_edges_from(
            (cell, neighbor)
            for cell in cells
            for neighbor in connections[cell]
            if neighbor in cells
        )
        if not cells or not nx.is_connected(graph):
            raise ValueError(f"Floor {floor}'s geometry is not one connected grid.")

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            plan_seed = f"{seed}:region-plan:{attempt}"
            plan = build_region_plan(plan_seed)
            region_labels = {}
            region_cells = {}
            region_seeds = {}

            start_candidates = sorted(
                nearest_endpoint_cells(grids[1][0], ENTRANCE)
            )
            start_cell = rng.choice(start_candidates)

            assigned_cells = _select_transition_cells(
                plan,
                grids,
                {start_cell, FINISH_ENTRANCE_CELL},
                rng,
            )

            # Build a set of required endpoint anchors for every region on
            # every floor. The transition map is now fixed before partitioning.
            anchors_by_floor = {
                floor: {
                    region["id"]: set()
                    for region in plan["regions"]
                    if region["floor"] == floor
                }
                for floor in FLOORS
            }
            for area in plan["transition_areas"]:
                cell = assigned_cells[area["id"]]
                anchors_by_floor[area["from_floor"]][area["source_region"]].add(cell)
                anchors_by_floor[area["to_floor"]][area["destination_region"]].add(cell)

            anchors_by_floor[1]["R00"].add(start_cell)
            anchors_by_floor[FINISH_FLOOR]["R09"].add(FINISH_ENTRANCE_CELL)

            for floor in FLOORS:
                floor_regions = [
                    region
                    for region in plan["regions"]
                    if region["floor"] == floor
                ]
                if not floor_regions:
                    raise ValueError(f"No regions were assigned to Floor {floor}.")

                labels, assigned, seeds, _ = _grow_connected_regions(
                    grids[floor][0],
                    grids[floor][1],
                    floor_regions,
                    rng,
                    floor,
                    fixed_seeds=anchors_by_floor[floor],
                )
                region_labels[floor] = labels
                region_cells[floor] = assigned
                region_seeds[floor] = seeds

            transition_areas = []
            for area in plan["transition_areas"]:
                transition_areas.append(
                    TransitionArea(
                        id=area["id"],
                        cell=assigned_cells[area["id"]],
                        kind=area["kind"],
                        journeys=((area["from_floor"], area["to_floor"]),),
                    )
                )

            floor_mazes = _build_floor_mazes(
                region_labels,
                region_cells,
                rng,
                loop_percentage,
            )
            navigation_graph = build_global_navigation_graph(
                floor_mazes,
                transition_areas,
            )

            layout = {
                "seed": seed,
                "attempt": attempt,
                "region_plan": plan,
                "region_labels": region_labels,
                "region_cells": region_cells,
                "region_seeds": region_seeds,
                "transition_areas": transition_areas,
                "floor_mazes": floor_mazes,
                "navigation_graph": navigation_graph,
                "start": (1, start_cell),
                "finish": (FINISH_FLOOR, FINISH_ENTRANCE_CELL),
            }
            report = validate_physical_layout(layout)
            if not report["valid"]:
                raise ValueError("; ".join(report["errors"]))
            layout["validation"] = report
            return layout

        except (ValueError, nx.NetworkXException) as error:
            last_error = error

    raise RuntimeError(
        f"Could not generate a valid physical layout after {max_attempts} "
        f"attempts. Last failure: {last_error}"
    )

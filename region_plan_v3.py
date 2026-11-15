"""Region-level backbone planning for the v3 global maze.

This module plans the navigation topology before assigning real X/Z cells.
It guarantees a nine-journey entrance-to-finish route and a strongly connected
region graph, while treating each physical transition area as one location.
"""

from __future__ import annotations

from itertools import product
import random

import networkx as nx

from global_graph_v3 import TARGET_TRANSITION_AREA_COUNT


REGION_COUNT = 10
SOLUTION_JOURNEY_COUNT = REGION_COUNT - 1
RETURN_TRANSITION_COUNT = 1
ALTERNATIVE_TRANSITION_COUNT = (
    TARGET_TRANSITION_AREA_COUNT
    - SOLUTION_JOURNEY_COUNT
    - RETURN_TRANSITION_COUNT
)


def _valid_floor_sequences():
    """Enumerate ten-region floor assignments with fixed entrance/finish floors."""
    sequences = []
    for middle in product((1, 2, 3), repeat=REGION_COUNT - 2):
        sequence = (1, *middle, 3)
        if any(a == b for a, b in zip(sequence, sequence[1:])):
            continue
        if set(sequence) != {1, 2, 3}:
            continue
        sequences.append(sequence)
    return sequences


_VALID_FLOOR_SEQUENCES = _valid_floor_sequences()


def _transition_kind(source_floor: int, destination_floor: int) -> str:
    if destination_floor > source_floor:
        return "elevator_up"
    if destination_floor < source_floor:
        return "drop_down"
    raise ValueError("A vertical transition must connect different floors.")


def _make_area(
    number: int,
    source_region: int,
    destination_region: int,
    region_floors: tuple[int, ...],
    role: str,
) -> dict:
    source_floor = region_floors[source_region]
    destination_floor = region_floors[destination_region]
    return {
        "id": f"T{number:02d}",
        "source_region": f"R{source_region:02d}",
        "destination_region": f"R{destination_region:02d}",
        "from_floor": source_floor,
        "to_floor": destination_floor,
        "kind": _transition_kind(source_floor, destination_floor),
        "role": role,
    }


def build_region_plan(seed="Maze1") -> dict:
    """Build a randomized ten-region, 25-area topology.

    Nine forward backbone areas form the minimum entrance-to-finish route.
    One return area closes the region cycle. Fifteen additional areas point
    backward in backbone order, so they add choices without shortening the
    nine-journey minimum.
    """
    rng = random.Random(seed)
    region_floors = rng.choice(_VALID_FLOOR_SEQUENCES)

    regions = [
        {"id": f"R{index:02d}", "floor": floor}
        for index, floor in enumerate(region_floors)
    ]

    areas = []

    # The nine directed backbone journeys lead from entrance region R00
    # to finish region R09.
    for index in range(REGION_COUNT - 1):
        areas.append(
            _make_area(
                len(areas) + 1,
                index,
                index + 1,
                region_floors,
                "solution_backbone",
            )
        )

    # A separate physical area provides the return journey to the entrance.
    areas.append(
        _make_area(
            len(areas) + 1,
            REGION_COUNT - 1,
            0,
            region_floors,
            "return_cycle",
        )
    )

    # All additional area options point from a later region to an earlier one.
    # They create detours and alternate recovery routes, never forward shortcuts.
    backward_pairs = [
        (source, destination)
        for source in range(1, REGION_COUNT)
        for destination in range(source)
        if region_floors[source] != region_floors[destination]
    ]
    if len(backward_pairs) < ALTERNATIVE_TRANSITION_COUNT:
        raise ValueError(
            "The selected region-floor sequence does not provide enough "
            "valid backward transition pairs."
        )

    rng.shuffle(backward_pairs)
    for source, destination in backward_pairs[:ALTERNATIVE_TRANSITION_COUNT]:
        areas.append(
            _make_area(
                len(areas) + 1,
                source,
                destination,
                region_floors,
                "alternative",
            )
        )

    graph = nx.DiGraph()
    graph.add_nodes_from(
        (region["id"], {"floor": region["floor"]})
        for region in regions
    )
    for area in areas:
        graph.add_edge(
            area["source_region"],
            area["destination_region"],
            transition_id=area["id"],
            journey_cost=1,
            role=area["role"],
        )

    start = "R00"
    finish = "R09"
    shortest_journeys = nx.shortest_path_length(
        graph,
        start,
        finish,
        weight="journey_cost",
    )
    solution_route = nx.shortest_path(
        graph,
        start,
        finish,
        weight="journey_cost",
    )

    plan = {
        "regions": regions,
        "region_floors": list(region_floors),
        "transition_areas": areas,
        "region_graph": graph,
        "start_region": start,
        "finish_region": finish,
        "solution_region_route": solution_route,
        "minimum_vertical_journeys": shortest_journeys,
        "seed": seed,
    }

    report = validate_region_plan(plan)
    if not report["valid"]:
        raise ValueError(
            "Generated region plan failed validation: "
            + "; ".join(report["errors"])
        )

    plan["validation"] = report
    return plan


def validate_region_plan(plan: dict) -> dict:
    """Validate counts, direction, recoverability, and shortest journey count."""
    errors = []
    regions = plan.get("regions", ())
    areas = plan.get("transition_areas", ())
    graph = plan.get("region_graph")

    region_ids = {region["id"] for region in regions}
    if len(regions) != REGION_COUNT or len(region_ids) != REGION_COUNT:
        errors.append(f"The plan must contain {REGION_COUNT} unique regions.")

    if len(areas) != TARGET_TRANSITION_AREA_COUNT:
        errors.append(
            f"The plan must contain exactly {TARGET_TRANSITION_AREA_COUNT} "
            "physical transition areas."
        )

    area_ids = [area.get("id") for area in areas]
    if len(area_ids) != len(set(area_ids)):
        errors.append("Physical transition area IDs are not unique.")

    if graph is None or not isinstance(graph, nx.DiGraph):
        errors.append("The region navigation graph is missing or invalid.")
        strongly_connected = False
        shortest_journeys = None
    else:
        if set(graph.nodes) != region_ids:
            errors.append("Region graph nodes do not match the planned regions.")

        for area in areas:
            source = area.get("source_region")
            destination = area.get("destination_region")
            if source not in region_ids or destination not in region_ids:
                errors.append(f"Transition {area.get('id')} references an unknown region.")
                continue
            if source == destination:
                errors.append(f"Transition {area.get('id')} connects a region to itself.")
            if not graph.has_edge(source, destination):
                errors.append(f"Transition {area.get('id')} is missing from the graph.")

            expected_kind = _transition_kind(
                area["from_floor"],
                area["to_floor"],
            )
            if area.get("kind") != expected_kind:
                errors.append(f"Transition {area.get('id')} has an invalid direction.")

        strongly_connected = bool(graph) and nx.is_strongly_connected(graph)
        if not strongly_connected:
            errors.append("The region navigation graph is not strongly connected.")

        try:
            shortest_journeys = nx.shortest_path_length(
                graph,
                plan.get("start_region", "R00"),
                plan.get("finish_region", "R09"),
                weight="journey_cost",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            shortest_journeys = None

        if shortest_journeys != SOLUTION_JOURNEY_COUNT:
            errors.append(
                f"The minimum entrance-to-finish journey count is "
                f"{shortest_journeys}, not {SOLUTION_JOURNEY_COUNT}."
            )

    if len(areas) != (
        SOLUTION_JOURNEY_COUNT
        + RETURN_TRANSITION_COUNT
        + ALTERNATIVE_TRANSITION_COUNT
    ):
        errors.append("Transition-area count breakdown is inconsistent.")

    return {
        "valid": not errors,
        "errors": errors,
        "region_count": len(regions),
        "transition_area_count": len(areas),
        "solution_backbone_area_count": sum(
            area.get("role") == "solution_backbone" for area in areas
        ),
        "return_area_count": sum(
            area.get("role") == "return_cycle" for area in areas
        ),
        "alternative_area_count": sum(
            area.get("role") == "alternative" for area in areas
        ),
        "strongly_connected": strongly_connected,
        "minimum_vertical_journeys": shortest_journeys,
    }

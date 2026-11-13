"""Global navigation graph primitives for the v3 maze architecture.

The v3 graph is built from horizontal passages and explicit vertical journey
options. A physical transition area may provide multiple journey options, but
it is counted once by its unique ID and X/Z cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import networkx as nx

from geometry_v2 import FLOORS


HORIZONTAL_JOURNEY_COST = 0
VERTICAL_JOURNEY_COST = 1
TARGET_TRANSITION_AREA_COUNT = 25


@dataclass(frozen=True)
class TransitionArea:
    """One physical elevator/drop location and its directed journey options.

    Each journey is a (source_floor, destination_floor) pair. A journey only
    exists between floors explicitly listed in journeys. A skipped intermediate
    floor is not implicitly a stop.
    """

    id: str
    cell: tuple[int, int]
    kind: str
    journeys: tuple[tuple[int, int], ...]

    @property
    def stops(self) -> frozenset[int]:
        """Floors with an actual stop in at least one journey option."""
        return frozenset(
            floor
            for journey in self.journeys
            for floor in journey
        )

    @property
    def journey_option_count(self) -> int:
        return len(self.journeys)


def transition_area_from_dict(data: dict) -> TransitionArea:
    """Create a typed transition area from a JSON-friendly dictionary."""
    return TransitionArea(
        id=data["id"],
        cell=tuple(data["cell"]),
        kind=data["kind"],
        journeys=tuple(tuple(journey) for journey in data["journeys"]),
    )


def validate_transition_area(
    area: TransitionArea,
    floor_mazes: dict,
) -> list[str]:
    """Return structural errors for one physical transition area."""
    errors = []

    if not area.id:
        errors.append("A transition area must have a non-empty ID.")

    if area.kind not in ("elevator_up", "drop_down"):
        errors.append(
            f"Transition area {area.id}: kind must be 'elevator_up' "
            "or 'drop_down'."
        )

    if not area.journeys:
        errors.append(f"Transition area {area.id}: no journey options are defined.")

    if len(area.journeys) != len(set(area.journeys)):
        errors.append(f"Transition area {area.id}: duplicate journey options exist.")

    if len(area.cell) != 2 or not all(isinstance(value, int) for value in area.cell):
        errors.append(f"Transition area {area.id}: cell must be an integer X/Z pair.")
        return errors

    for journey in area.journeys:
        if len(journey) != 2:
            errors.append(
                f"Transition area {area.id}: each journey must name two floors."
            )
            continue

        source_floor, destination_floor = journey
        if source_floor not in FLOORS or destination_floor not in FLOORS:
            errors.append(
                f"Transition area {area.id}: journey references an unknown floor."
            )
            continue

        if source_floor == destination_floor:
            errors.append(
                f"Transition area {area.id}: a vertical journey must change floors."
            )
            continue

        if area.kind == "elevator_up" and destination_floor <= source_floor:
            errors.append(
                f"Transition area {area.id}: an elevator journey must travel upward."
            )
        elif area.kind == "drop_down" and destination_floor >= source_floor:
            errors.append(
                f"Transition area {area.id}: a drop journey must travel downward."
            )

        for floor in (source_floor, destination_floor):
            if floor not in floor_mazes:
                errors.append(
                    f"Transition area {area.id}: Floor {floor} is missing."
                )
            elif area.cell not in floor_mazes[floor].get("cells", ()):
                errors.append(
                    f"Transition area {area.id}: its cell is not playable "
                    f"on Floor {floor}."
                )

    return errors


def build_global_navigation_graph(
    floor_mazes: dict,
    transition_areas: Iterable[TransitionArea],
) -> nx.DiGraph:
    """Build the directed global graph from carved corridors and transitions.

    Horizontal passages are bidirectional and cost zero vertical journeys.
    Each explicitly defined vertical journey is directed and costs one.
    """
    graph = nx.DiGraph()

    for floor, maze in floor_mazes.items():
        if floor not in FLOORS:
            raise ValueError(f"Unknown floor in maze data: {floor}")

        cells = set(maze.get("cells", ()))
        graph.add_nodes_from((floor, cell) for cell in cells)

        for cell_a, cell_b in maze.get("opened_edges", ()):
            if cell_a not in cells or cell_b not in cells:
                raise ValueError(
                    f"Floor {floor}: an opened passage references a missing cell."
                )
            if cell_a == cell_b:
                raise ValueError(
                    f"Floor {floor}: a horizontal passage cannot connect a cell to itself."
                )

            graph.add_edge(
                (floor, cell_a),
                (floor, cell_b),
                kind="corridor",
                journey_cost=HORIZONTAL_JOURNEY_COST,
            )
            graph.add_edge(
                (floor, cell_b),
                (floor, cell_a),
                kind="corridor",
                journey_cost=HORIZONTAL_JOURNEY_COST,
            )

    seen_ids = set()
    seen_cells = set()

    for area in transition_areas:
        if area.id in seen_ids:
            raise ValueError(f"Duplicate transition area ID: {area.id}")
        if area.cell in seen_cells:
            raise ValueError(
                f"Two physical transition areas use the same X/Z cell: {area.cell}"
            )

        errors = validate_transition_area(area, floor_mazes)
        if errors:
            raise ValueError("\n".join(errors))

        seen_ids.add(area.id)
        seen_cells.add(area.cell)

        for source_floor, destination_floor in area.journeys:
            graph.add_edge(
                (source_floor, area.cell),
                (destination_floor, area.cell),
                kind=area.kind,
                journey_cost=VERTICAL_JOURNEY_COST,
                transition_id=area.id,
            )

    return graph


def minimum_vertical_journeys(
    graph: nx.DiGraph,
    start: tuple,
    finish: tuple,
) -> int:
    """Return the minimum number of vertical rides over every possible route."""
    return nx.shortest_path_length(
        graph,
        source=start,
        target=finish,
        weight="journey_cost",
    )


def find_minimum_journey_route(
    graph: nx.DiGraph,
    start: tuple,
    finish: tuple,
) -> list[tuple]:
    """Return a route minimizing vertical rides, not total corridor length."""
    return nx.shortest_path(
        graph,
        source=start,
        target=finish,
        weight="journey_cost",
    )


def navigation_graph_report(
    graph: nx.DiGraph,
    start: tuple,
    finish: tuple,
    transition_areas: Iterable[TransitionArea],
) -> dict:
    """Summarize recoverability and journey counts for a completed graph."""
    areas = tuple(transition_areas)
    strongly_connected = bool(graph) and nx.is_strongly_connected(graph)

    try:
        shortest_journeys = minimum_vertical_journeys(graph, start, finish)
        route = find_minimum_journey_route(graph, start, finish)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        shortest_journeys = None
        route = []

    return {
        "strongly_connected": strongly_connected,
        "all_nodes_recoverable": strongly_connected,
        "transition_area_count": len(areas),
        "journey_option_count": sum(
            area.journey_option_count for area in areas
        ),
        "minimum_vertical_journeys": shortest_journeys,
        "minimum_journey_route": route,
        "target_transition_area_count": TARGET_TRANSITION_AREA_COUNT,
        "transition_area_target_met": (
            len(areas) == TARGET_TRANSITION_AREA_COUNT
        ),
    }

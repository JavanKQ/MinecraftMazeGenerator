import unittest

from global_graph_v3 import (
    TransitionArea,
    build_global_navigation_graph,
    find_minimum_journey_route,
    minimum_vertical_journeys,
    navigation_graph_report,
    validate_transition_area,
)


CELL = (11360, 10904)


def sample_floor_mazes():
    return {
        floor: {
            "cells": {CELL},
            "opened_edges": set(),
        }
        for floor in (1, 2, 3)
    }


class GlobalGraphV3Tests(unittest.TestCase):
    def test_one_physical_area_can_have_multiple_journey_options(self):
        floors = sample_floor_mazes()
        area = TransitionArea(
            id="T01",
            cell=CELL,
            kind="elevator_up",
            journeys=((1, 2), (1, 3)),
        )

        graph = build_global_navigation_graph(floors, [area])

        self.assertEqual(area.journey_option_count, 2)
        self.assertEqual(area.stops, frozenset({1, 2, 3}))
        self.assertTrue(graph.has_edge((1, CELL), (2, CELL)))
        self.assertTrue(graph.has_edge((1, CELL), (3, CELL)))
        self.assertFalse(graph.has_edge((2, CELL), (3, CELL)))

    def test_skipped_floor_is_not_an_implicit_stop(self):
        floors = sample_floor_mazes()
        area = TransitionArea(
            id="T01",
            cell=CELL,
            kind="elevator_up",
            journeys=((1, 3),),
        )

        graph = build_global_navigation_graph(floors, [area])

        self.assertEqual(area.stops, frozenset({1, 3}))
        self.assertTrue(graph.has_edge((1, CELL), (3, CELL)))
        self.assertFalse(graph.has_edge((1, CELL), (2, CELL)))
        self.assertFalse(graph.has_edge((2, CELL), (3, CELL)))

    def test_drop_must_travel_downward(self):
        floors = sample_floor_mazes()
        invalid_area = TransitionArea(
            id="T01",
            cell=CELL,
            kind="drop_down",
            journeys=((1, 3),),
        )

        errors = validate_transition_area(invalid_area, floors)

        self.assertTrue(any("downward" in error for error in errors))

    def test_elevator_must_travel_upward(self):
        floors = sample_floor_mazes()
        invalid_area = TransitionArea(
            id="T01",
            cell=CELL,
            kind="elevator_up",
            journeys=((3, 1),),
        )

        errors = validate_transition_area(invalid_area, floors)

        self.assertTrue(any("upward" in error for error in errors))

    def test_duplicate_physical_locations_are_rejected(self):
        floors = sample_floor_mazes()
        areas = [
            TransitionArea("T01", CELL, "elevator_up", ((1, 2),)),
            TransitionArea("T02", CELL, "elevator_up", ((1, 3),)),
        ]

        with self.assertRaisesRegex(ValueError, "same X/Z cell"):
            build_global_navigation_graph(floors, areas)

    def test_shortest_route_counts_each_vertical_journey_once(self):
        floors = sample_floor_mazes()
        cell_b = (11364, 10904)
        for maze in floors.values():
            maze["cells"].add(cell_b)

        area_a = TransitionArea("T01", CELL, "elevator_up", ((1, 2),))
        area_b = TransitionArea("T02", cell_b, "elevator_up", ((2, 3),))
        floors[1]["opened_edges"].add((CELL, cell_b))
        floors[2]["opened_edges"].add((CELL, cell_b))

        graph = build_global_navigation_graph(floors, [area_a, area_b])
        start = (1, CELL)
        finish = (3, cell_b)

        self.assertEqual(minimum_vertical_journeys(graph, start, finish), 2)
        route = find_minimum_journey_route(graph, start, finish)
        self.assertEqual(route[0], start)
        self.assertEqual(route[-1], finish)
        self.assertEqual(
            sum(
                graph[a][b]["journey_cost"]
                for a, b in zip(route, route[1:])
            ),
            2,
        )

    def test_report_separates_area_count_from_journey_option_count(self):
        floors = sample_floor_mazes()
        area = TransitionArea(
            "T01", CELL, "elevator_up", ((1, 2), (1, 3))
        )
        graph = build_global_navigation_graph(floors, [area])

        report = navigation_graph_report(
            graph,
            (1, CELL),
            (3, CELL),
            [area],
        )

        self.assertEqual(report["transition_area_count"], 1)
        self.assertEqual(report["journey_option_count"], 2)
        self.assertEqual(report["minimum_vertical_journeys"], 1)

    def test_horizontal_passages_are_bidirectional_and_cost_zero(self):
        floors = sample_floor_mazes()
        other = (11364, 10904)
        floors[1]["cells"].add(other)
        floors[1]["opened_edges"].add((CELL, other))

        graph = build_global_navigation_graph(floors, [])

        self.assertTrue(graph.has_edge((1, CELL), (1, other)))
        self.assertTrue(graph.has_edge((1, other), (1, CELL)))
        self.assertEqual(graph[(1, CELL)][(1, other)]["journey_cost"], 0)
        self.assertEqual(graph[(1, other)][(1, CELL)]["journey_cost"], 0)


if __name__ == "__main__":
    unittest.main()

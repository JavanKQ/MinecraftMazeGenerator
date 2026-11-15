import unittest

import networkx as nx

from geometry_v2 import FINISH_ENTRANCE_CELL, FLOORS, shared_grid_cells
from multifloor_v2 import (
    build_multifloor_maze,
    validate_multifloor_route,
)


class MultiFloorV2Tests(unittest.TestCase):
    def test_route_connects_entrance_to_finish(self):
        floors, graph, route, transitions = build_multifloor_maze("route-test")
        self.assertEqual(route[0][0], 1)
        self.assertEqual(route[-1], (3, FINISH_ENTRANCE_CELL))
        self.assertEqual(set(floors), set(FLOORS))
        self.assertTrue(validate_multifloor_route(graph, route))
        self.assertTrue(nx.has_path(graph, route[0], route[-1]))

    def test_each_transition_uses_a_valid_shared_cell(self):
        _, graph, _, transitions = build_multifloor_maze("shared-cell-test")
        for transition in transitions:
            with self.subTest(transition=transition["id"]):
                source_floor = transition["from"][0]
                destination_floor = transition["to"][0]
                self.assertEqual(transition["from"][1], transition["cell"])
                self.assertEqual(transition["to"][1], transition["cell"])
                self.assertIn(
                    transition["cell"],
                    shared_grid_cells((source_floor, destination_floor)),
                )
                self.assertTrue(
                    graph.has_edge(transition["from"], transition["to"])
                )

    def test_required_links_guarantee_each_floor_is_reachable(self):
        for seed in ("Maze1", "Maze2", "Maze3", "Maze4", "Maze5"):
            with self.subTest(seed=seed):
                _, graph, route, transitions = build_multifloor_maze(seed)
                self.assertTrue(nx.has_path(graph, route[0], route[-1]))
                for pair in ((1, 2), (2, 3)):
                    self.assertTrue(
                        any(
                            transition["guaranteed_route_link"]
                            and transition["from"][0] == pair[0]
                            and transition["to"][0] == pair[1]
                            for transition in transitions
                        )
                    )

    def test_transition_types_match_direction(self):
        _, _, _, transitions = build_multifloor_maze("direction-test")
        for transition in transitions:
            source_floor = transition["from"][0]
            destination_floor = transition["to"][0]
            if destination_floor > source_floor:
                self.assertEqual(transition["kind"], "elevator_up")
            else:
                self.assertEqual(transition["kind"], "drop_down")

    def test_same_seed_reproduces_layout_and_transitions(self):
        first = build_multifloor_maze("repeatable")
        second = build_multifloor_maze("repeatable")
        self.assertEqual(first[0][1]["opened_edges"], second[0][1]["opened_edges"])
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[3], second[3])

    def test_different_seeds_can_change_transition_layout(self):
        first = build_multifloor_maze("different-a")[3]
        second = build_multifloor_maze("different-b")[3]
        self.assertNotEqual(
            [(item["cell"], item["from"][0], item["to"][0]) for item in first],
            [(item["cell"], item["from"][0], item["to"][0]) for item in second],
        )


if __name__ == "__main__":
    unittest.main()

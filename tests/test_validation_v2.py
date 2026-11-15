import copy
import unittest

from geometry_v2 import FINISH_ENTRANCE_CELL
from multifloor_v2 import build_multifloor_maze
from validation_v2 import validate_multifloor_maze


class ValidationV2Tests(unittest.TestCase):
    def setUp(self):
        self.floor_mazes, self.graph, self.route, self.transitions = (
            build_multifloor_maze("validation-test")
        )

    def test_generated_maze_passes_validation(self):
        report = validate_multifloor_maze(
            self.floor_mazes, self.graph, self.route, self.transitions
        )
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["checks"]["finish_connector_valid"], True)
        self.assertEqual(
            self.route[-1],
            (3, FINISH_ENTRANCE_CELL),
        )

    def test_disconnected_carved_floor_is_rejected(self):
        floor_mazes = copy.deepcopy(self.floor_mazes)
        floor = 1
        floor_mazes[floor]["opened_edges"] = set()
        report = validate_multifloor_maze(
            floor_mazes, self.graph, self.route, self.transitions
        )
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("disconnected" in error for error in report["errors"])
        )

    def test_reverse_vertical_edge_is_rejected(self):
        graph = self.graph.copy()
        transition = self.transitions[0]
        graph.add_edge(
            transition["to"],
            transition["from"],
            kind=transition["kind"],
            transition_id=transition["id"],
        )
        report = validate_multifloor_maze(
            self.floor_mazes, graph, self.route, self.transitions
        )
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("reverse travel" in error for error in report["errors"])
        )

    def test_invalid_transition_cell_is_rejected(self):
        transitions = copy.deepcopy(self.transitions)
        invalid_cell = (-1, -1)
        transitions[0]["cell"] = invalid_cell
        transitions[0]["from"] = (transitions[0]["from"][0], invalid_cell)
        transitions[0]["to"] = (transitions[0]["to"][0], invalid_cell)
        report = validate_multifloor_maze(
            self.floor_mazes, self.graph, self.route, transitions
        )
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("does not fit both floors" in error for error in report["errors"])
        )

    def test_route_with_missing_edge_is_rejected(self):
        graph = self.graph.copy()
        first, second = self.route[0], self.route[1]
        graph.remove_edge(first, second)
        report = validate_multifloor_maze(
            self.floor_mazes, graph, self.route, self.transitions
        )
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("missing graph connection" in error for error in report["errors"])
        )


if __name__ == "__main__":
    unittest.main()

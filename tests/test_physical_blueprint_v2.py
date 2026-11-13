import unittest

from geometry_v2 import (
    FINISH_ENTRANCE_BLOCKS,
    FINISH_ENTRANCE_CELL,
)
from generator_v2 import generate_floor_mazes
from multifloor_v2 import build_multifloor_maze
from physical_blueprint_v2 import build_physical_blueprint


class TestPhysicalBlueprint(unittest.TestCase):
    def setUp(self):
        self.floor_mazes, self.graph, self.route, self.transitions = (
            build_multifloor_maze(seed="BlueprintTest")
        )
        self.blueprint = build_physical_blueprint(
            self.floor_mazes,
            self.graph,
            self.route,
            self.transitions,
        )

    def test_blueprint_contains_all_floors_and_physical_regions(self):
        self.assertEqual(set(self.blueprint["floors"]), {1, 2, 3})
        for floor, maze in self.floor_mazes.items():
            blueprint_floor = self.blueprint["floors"][floor]
            self.assertEqual(set(blueprint_floor["cells"]), maze["cells"])
            self.assertEqual(len(blueprint_floor["footprint"]), len(
                __import__("geometry_v2").FLOORS[floor]["footprint"]
            ))

    def test_every_possible_connection_is_either_open_or_walled(self):
        for floor_data in self.blueprint["floors"].values():
            open_edges = {
                frozenset(tuple(cell) for cell in passage["cells"])
                for passage in floor_data["open_passages"]
            }
            wall_edges = {
                frozenset(tuple(cell) for cell in wall["cells"])
                for wall in floor_data["wall_segments"]
            }
            self.assertFalse(open_edges & wall_edges)
            self.assertEqual(
                len(open_edges) + len(wall_edges),
                len(floor_data["open_passages"]) + len(floor_data["wall_segments"]),
            )

    def test_wall_segments_have_three_blocks(self):
        for floor_data in self.blueprint["floors"].values():
            for wall in floor_data["wall_segments"]:
                self.assertEqual(len(wall["blocks"]), 3)

    def test_entrance_and_finish_connectors_are_preserved(self):
        self.assertEqual(
            set(self.blueprint["finish"]["opening_blocks"]),
            FINISH_ENTRANCE_BLOCKS,
        )
        self.assertEqual(
            self.blueprint["finish"]["source_cell"],
            FINISH_ENTRANCE_CELL,
        )
        self.assertTrue(self.blueprint["entrance"]["opening_blocks"])

    def test_solution_route_steps_match_graph_edges(self):
        steps = self.blueprint["solution_route"]
        self.assertEqual(len(steps), len(self.route))
        self.assertIsNone(steps[0]["incoming"])
        for index in range(1, len(steps)):
            previous = self.route[index - 1]
            current = self.route[index]
            expected = self.graph.get_edge_data(previous, current)
            self.assertEqual(steps[index]["incoming"]["kind"], expected["kind"])

    def test_transitions_match_generator_output(self):
        self.assertEqual(
            len(self.blueprint["vertical_transitions"]),
            len(self.transitions),
        )
        for rendered, original in zip(
            self.blueprint["vertical_transitions"], self.transitions
        ):
            self.assertEqual(rendered["id"], original["id"])
            self.assertEqual(rendered["from"], original["from"])
            self.assertEqual(rendered["to"], original["to"])


if __name__ == "__main__":
    unittest.main()

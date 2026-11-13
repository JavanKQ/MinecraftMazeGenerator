import unittest

import networkx as nx

from geometry_v2 import FLOORS, generate_grid
from physical_layout_v3 import build_physical_layout


class PhysicalLayoutV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = build_physical_layout(seed="physical-layout-test")

    def test_all_floor_cells_are_assigned_to_one_region(self):
        for floor in FLOORS:
            cells, _ = generate_grid(floor)
            labels = self.layout["region_labels"][floor]
            self.assertEqual(set(labels), cells)

    def test_every_region_is_horizontally_connected(self):
        for floor, regions in self.layout["region_cells"].items():
            _, connections = generate_grid(floor)
            for region_id, cells in regions.items():
                graph = nx.Graph()
                graph.add_nodes_from(cells)
                graph.add_edges_from(
                    (cell, neighbor)
                    for cell in cells
                    for neighbor in connections[cell]
                    if neighbor in cells
                )
                with self.subTest(floor=floor, region=region_id):
                    self.assertTrue(cells)
                    self.assertTrue(nx.is_connected(graph))

    def test_horizontal_passages_never_cross_region_boundaries(self):
        for floor, maze in self.layout["floor_mazes"].items():
            labels = maze["region_by_cell"]
            for cell_a, cell_b in maze["opened_edges"]:
                with self.subTest(floor=floor, edge=(cell_a, cell_b)):
                    self.assertEqual(labels[cell_a], labels[cell_b])

    def test_all_twenty_five_transition_areas_have_unique_valid_cells(self):
        areas = self.layout["transition_areas"]
        self.assertEqual(len(areas), 25)
        self.assertEqual(len({area.id for area in areas}), 25)
        self.assertEqual(len({area.cell for area in areas}), 25)

        plan_by_id = {
            area["id"]: area
            for area in self.layout["region_plan"]["transition_areas"]
        }
        for area in areas:
            planned = plan_by_id[area.id]
            with self.subTest(area=area.id):
                self.assertIn(
                    area.cell,
                    self.layout["region_cells"][planned["from_floor"]][
                        planned["source_region"]
                    ],
                )
                self.assertIn(
                    area.cell,
                    self.layout["region_cells"][planned["to_floor"]][
                        planned["destination_region"]
                    ],
                )

    def test_complete_navigation_graph_is_recoverable_and_requires_nine_journeys(self):
        report = self.layout["validation"]["navigation"]
        self.assertTrue(report["strongly_connected"])
        self.assertTrue(report["all_nodes_recoverable"])
        self.assertEqual(report["minimum_vertical_journeys"], 9)
        self.assertEqual(report["transition_area_count"], 25)

    def test_finish_and_entrance_are_the_planned_endpoints(self):
        self.assertEqual(self.layout["start"][0], 1)
        self.assertEqual(self.layout["finish"], (3, (11440, 10984)))
        self.assertEqual(
            self.layout["region_labels"][1][self.layout["start"][1]],
            "R00",
        )
        self.assertEqual(
            self.layout["region_labels"][3][self.layout["finish"][1]],
            "R09",
        )

    def test_same_seed_reproduces_region_and_transition_layout(self):
        repeated = build_physical_layout(seed="physical-layout-test")
        self.assertEqual(
            self.layout["region_plan"]["region_floors"],
            repeated["region_plan"]["region_floors"],
        )
        self.assertEqual(
            [(area.id, area.cell) for area in self.layout["transition_areas"]],
            [(area.id, area.cell) for area in repeated["transition_areas"]],
        )
        for floor in FLOORS:
            self.assertEqual(
                self.layout["floor_mazes"][floor]["opened_edges"],
                repeated["floor_mazes"][floor]["opened_edges"],
            )


if __name__ == "__main__":
    unittest.main()

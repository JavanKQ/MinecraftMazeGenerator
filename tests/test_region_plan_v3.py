import unittest

import networkx as nx

from region_plan_v3 import (
    ALTERNATIVE_TRANSITION_COUNT,
    REGION_COUNT,
    SOLUTION_JOURNEY_COUNT,
    build_region_plan,
    validate_region_plan,
)


class RegionPlanV3Tests(unittest.TestCase):
    def test_plan_has_ten_regions_and_twenty_five_physical_areas(self):
        plan = build_region_plan("counts")
        report = plan["validation"]

        self.assertEqual(report["region_count"], REGION_COUNT)
        self.assertEqual(report["transition_area_count"], 25)
        self.assertEqual(report["solution_backbone_area_count"], 9)
        self.assertEqual(report["return_area_count"], 1)
        self.assertEqual(
            report["alternative_area_count"],
            ALTERNATIVE_TRANSITION_COUNT,
        )

    def test_region_graph_is_strongly_connected(self):
        for seed in range(20):
            with self.subTest(seed=seed):
                plan = build_region_plan(seed)
                self.assertTrue(
                    nx.is_strongly_connected(plan["region_graph"])
                )

    def test_shortest_route_requires_exactly_nine_journeys(self):
        for seed in range(50):
            with self.subTest(seed=seed):
                plan = build_region_plan(seed)
                self.assertEqual(
                    plan["minimum_vertical_journeys"],
                    SOLUTION_JOURNEY_COUNT,
                )
                self.assertEqual(
                    plan["solution_region_route"],
                    [f"R{i:02d}" for i in range(REGION_COUNT)],
                )

    def test_backbone_moves_forward_one_region_at_a_time(self):
        plan = build_region_plan("backbone")
        backbone = [
            area
            for area in plan["transition_areas"]
            if area["role"] == "solution_backbone"
        ]

        self.assertEqual(len(backbone), 9)
        for index, area in enumerate(backbone):
            self.assertEqual(area["source_region"], f"R{index:02d}")
            self.assertEqual(area["destination_region"], f"R{index + 1:02d}")

    def test_extra_areas_never_point_forward(self):
        plan = build_region_plan("no-shortcuts")
        for area in plan["transition_areas"]:
            if area["role"] != "alternative":
                continue
            source = int(area["source_region"][1:])
            destination = int(area["destination_region"][1:])
            self.assertGreater(source, destination)

    def test_all_transition_areas_change_floors_and_have_correct_direction(self):
        plan = build_region_plan("directions")
        for area in plan["transition_areas"]:
            with self.subTest(area=area["id"]):
                self.assertNotEqual(area["from_floor"], area["to_floor"])
                if area["to_floor"] > area["from_floor"]:
                    self.assertEqual(area["kind"], "elevator_up")
                else:
                    self.assertEqual(area["kind"], "drop_down")

    def test_same_seed_reproduces_region_plan(self):
        first = build_region_plan("repeatable")
        second = build_region_plan("repeatable")

        self.assertEqual(first["region_floors"], second["region_floors"])
        self.assertEqual(first["transition_areas"], second["transition_areas"])
        self.assertEqual(
            first["solution_region_route"],
            second["solution_region_route"],
        )

    def test_validation_rejects_broken_graph(self):
        plan = build_region_plan("broken")
        plan["region_graph"].remove_edge("R00", "R01")

        report = validate_region_plan(plan)

        self.assertFalse(report["valid"])
        self.assertFalse(report["strongly_connected"])
        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()

import unittest

from physical_blueprint_v3 import build_physical_blueprint_v3
from physical_layout_v3 import build_physical_layout
from svg_renderer_v2 import render_all_floor_svgs


class PhysicalBlueprintV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = build_physical_layout(seed="stress-0001")
        cls.blueprint = build_physical_blueprint_v3(cls.layout)

    def test_blueprint_contains_all_three_floors(self):
        self.assertEqual(set(self.blueprint["floors"]), {1, 2, 3})
        for floor in (1, 2, 3):
            floor_data = self.blueprint["floors"][floor]
            self.assertTrue(floor_data["cells"])
            self.assertTrue(floor_data["cell_blocks"])

    def test_blueprint_preserves_transition_areas_and_journeys(self):
        self.assertEqual(len(self.layout["transition_areas"]), 25)
        self.assertEqual(
            len(self.blueprint["vertical_transitions"]),
            sum(area.journey_option_count for area in self.layout["transition_areas"]),
        )

    def test_skipped_floors_have_no_transition_marker(self):
        for area in self.layout["transition_areas"]:
            served_floors = {
                floor
                for journey in area.journeys
                for floor in journey
            }
            marked_floors = {
                floor
                for floor, floor_data in self.blueprint["floors"].items()
                if any(item["id"] == area.id for item in floor_data["transitions"])
            }
            self.assertEqual(marked_floors, served_floors, area.id)

    def test_solution_route_contains_nine_vertical_journeys(self):
        vertical_steps = [
            step
            for step in self.blueprint["solution_route"]
            if step["incoming"]
            and step["incoming"]["kind"] in ("elevator_up", "drop_down")
        ]
        self.assertEqual(len(vertical_steps), 9)

    def test_renderer_produces_normal_and_solution_views(self):
        normal = render_all_floor_svgs(self.blueprint)
        solution = render_all_floor_svgs(self.blueprint, show_solution=True)

        self.assertEqual(set(normal), {1, 2, 3})
        self.assertEqual(set(solution), {1, 2, 3})

        for floor in (1, 2, 3):
            self.assertIn(f'data-floor="{floor}"', normal[floor])
            self.assertNotIn('data-type="solution-overlay"', normal[floor])
            self.assertIn('data-type="solution-overlay"', solution[floor])

    def test_finish_and_entrance_are_preserved(self):
        self.assertEqual(self.blueprint["entrance"]["floor"], 1)
        self.assertEqual(self.blueprint["finish"]["floor"], 3)
        self.assertEqual(
            self.blueprint["finish"]["source_cell"],
            self.layout["finish"][1],
        )


if __name__ == "__main__":
    unittest.main()

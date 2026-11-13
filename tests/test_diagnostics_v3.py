"""Unit tests for the v3 diagnostic metric extraction."""

import unittest

from diagnostics_v3 import summarize_layout
from global_graph_v3 import TransitionArea


class DiagnosticSummaryTests(unittest.TestCase):
    def test_summarize_layout_reports_regions_transitions_and_loops(self):
        area = TransitionArea(
            id="T01",
            cell=(10, 20),
            kind="elevator_up",
            journeys=((1, 2),),
        )
        layout = {
            "seed": "diagnostic-test",
            "attempt": 3,
            "region_cells": {
                1: {"R00": {(0, 0), (1, 0), (2, 0)}},
                2: {"R01": {(0, 0), (1, 0)}},
                3: {"R02": {(0, 0)}},
            },
            "floor_mazes": {
                1: {
                    "opened_edges": {((0, 0), (1, 0)), ((1, 0), (2, 0)), ((0, 0), (2, 0))},
                    "possible_edges": 3,
                },
                2: {
                    "opened_edges": {((0, 0), (1, 0))},
                    "possible_edges": 1,
                },
                3: {
                    "opened_edges": set(),
                    "possible_edges": 0,
                },
            },
            "transition_areas": [area],
            "region_plan": {"region_floors": [1, 2, 3]},
            "validation": {
                "valid": True,
                "navigation": {
                    "strongly_connected": True,
                    "minimum_vertical_journeys": 9,
                    "transition_area_count": 25,
                },
            },
        }

        result = summarize_layout(layout)

        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["region_sizes"][1]["R00"], 3)
        self.assertEqual(result["transition_pair_counts"], {"1->2": 1})
        self.assertEqual(result["loop_metrics"][1]["tree_edges"], 2)
        self.assertEqual(result["loop_metrics"][1]["loop_edges"], 1)
        self.assertEqual(result["loop_metrics"][1]["loop_rate_percent"], 50.0)
        self.assertEqual(result["navigation"]["minimum_vertical_journeys"], 9)


if __name__ == "__main__":
    unittest.main()

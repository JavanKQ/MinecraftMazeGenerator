import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from multifloor_v2 import build_multifloor_maze
from physical_blueprint_v2 import build_physical_blueprint
from svg_renderer_v2 import (
    SVG_NS,
    render_all_floor_svgs,
    render_floor_svg,
    write_all_floor_svgs,
)


def _elements(root, data_type):
    return root.findall(f".//*[@data-type='{data_type}']")


class TestSvgRenderer(unittest.TestCase):
    def setUp(self):
        floor_mazes, graph, route, transitions = build_multifloor_maze(
            seed="SvgRendererTest"
        )
        self.blueprint = build_physical_blueprint(
            floor_mazes, graph, route, transitions
        )

    def parse(self, svg):
        return ET.fromstring(svg)

    def test_renders_one_svg_per_floor(self):
        svgs = render_all_floor_svgs(self.blueprint)
        self.assertEqual(set(svgs), {1, 2, 3})
        for floor, svg in svgs.items():
            root = self.parse(svg)
            self.assertEqual(root.attrib["data-floor"], str(floor))
            self.assertEqual(root.tag, f"{{{SVG_NS}}}svg")

    def test_svg_geometry_counts_match_blueprint(self):
        svgs = render_all_floor_svgs(self.blueprint)
        for floor, svg in svgs.items():
            root = self.parse(svg)
            data = self.blueprint["floors"][floor]
            self.assertEqual(
                len(_elements(root, "footprint")),
                len(data["footprint"]),
            )
            self.assertEqual(
                len(_elements(root, "corridor-cell")),
                len(data["cell_blocks"]),
            )
            self.assertEqual(
                len(_elements(root, "wall-segment")),
                len(data["wall_segments"]),
            )
            self.assertEqual(
                len(_elements(root, "open-passage")),
                len(data["open_passages"]),
            )
            self.assertEqual(
                len(_elements(root, "vertical-transition")),
                len(data["transitions"]),
            )

    def test_each_svg_wall_segment_contains_its_three_exact_blocks(self):
        svgs = render_all_floor_svgs(self.blueprint)
        for floor, svg in svgs.items():
            root = self.parse(svg)
            groups = _elements(root, "wall-segment")
            expected = self.blueprint["floors"][floor]["wall_segments"]
            self.assertEqual(len(groups), len(expected))
            for group, wall in zip(groups, expected):
                actual_blocks = {
                    (int(rect.attrib["x"]), int(rect.attrib["y"]))
                    for rect in group.findall(f"{{{SVG_NS}}}rect")
                }
                self.assertEqual(actual_blocks, set(map(tuple, wall["blocks"])))

    def test_normal_view_has_no_solution_overlay(self):
        for svg in render_all_floor_svgs(self.blueprint).values():
            root = self.parse(svg)
            self.assertEqual(root.attrib["data-solution-overlay"], "false")
            self.assertEqual(len(_elements(root, "solution-edge")), 0)
            self.assertEqual(len(_elements(root, "solution-cell")), 0)

    def test_solution_view_contains_exact_horizontal_route_edges(self):
        svgs = render_all_floor_svgs(self.blueprint, show_solution=True)
        for floor, svg in svgs.items():
            root = self.parse(svg)
            expected = []
            steps = self.blueprint["solution_route"]
            for index in range(1, len(steps)):
                previous = steps[index - 1]
                current = steps[index]
                incoming = current.get("incoming") or {}
                if (
                    previous["floor"] == floor
                    and current["floor"] == floor
                    and incoming.get("kind") == "corridor"
                ):
                    expected.append((previous["cell"], current["cell"]))

            actual = [
                (
                    tuple(map(int, edge.attrib["data-from-cell"].split(","))),
                    tuple(map(int, edge.attrib["data-to-cell"].split(","))),
                )
                for edge in _elements(root, "solution-edge")
            ]
            self.assertEqual(actual, expected)
            self.assertEqual(
                len(_elements(root, "solution-cell")),
                len(self.blueprint["floors"][floor]["route_cells"]),
            )

    def test_special_connectors_are_rendered_on_their_floors(self):
        svgs = render_all_floor_svgs(self.blueprint)
        floor_one = self.parse(svgs[1])
        floor_three = self.parse(svgs[3])
        self.assertEqual(len(_elements(floor_one, "entrance")), 1)
        self.assertEqual(len(_elements(floor_one, "entrance-connector")), 2)
        self.assertEqual(len(_elements(floor_three, "finish")), 1)
        self.assertEqual(len(_elements(floor_three, "finish-connector")), 2)

    def test_open_passage_blocks_match_the_blueprint(self):
        svgs = render_all_floor_svgs(self.blueprint)
        for floor, svg in svgs.items():
            root = self.parse(svg)
            groups = _elements(root, "open-passage")
            expected = self.blueprint["floors"][floor]["open_passages"]
            self.assertEqual(len(groups), len(expected))
            for group, passage in zip(groups, expected):
                actual_blocks = {
                    (int(rect.attrib["x"]), int(rect.attrib["y"]))
                    for rect in group.findall(f"{{{SVG_NS}}}rect")
                }
                self.assertEqual(
                    actual_blocks, set(map(tuple, passage["opening_blocks"]))
                )

    def test_solution_transition_is_highlighted_on_both_floors(self):
        svgs = render_all_floor_svgs(self.blueprint, show_solution=True)
        for floor, svg in svgs.items():
            root = self.parse(svg)
            actual = {
                item.attrib["data-id"]
                for item in _elements(root, "solution-transition")
            }
            expected = set()
            steps = self.blueprint["solution_route"]
            for index in range(1, len(steps)):
                previous = steps[index - 1]
                current = steps[index]
                incoming = current.get("incoming") or {}
                if (
                    incoming.get("kind") in ("elevator_up", "drop_down")
                    and floor in (previous["floor"], current["floor"])
                ):
                    expected.add(incoming["transition_id"])
            self.assertEqual(actual, expected)

    def test_file_export_writes_both_view_modes(self):
        with TemporaryDirectory() as directory:
            normal = write_all_floor_svgs(self.blueprint, Path(directory) / "normal")
            solution = write_all_floor_svgs(
                self.blueprint,
                Path(directory) / "solution",
                show_solution=True,
            )
            self.assertEqual(set(normal), {1, 2, 3})
            self.assertEqual(set(solution), {1, 2, 3})
            self.assertTrue(all(path.is_file() for path in normal.values()))
            self.assertTrue(all(path.is_file() for path in solution.values()))
            self.assertTrue(all(path.name.endswith("_solution.svg") for path in solution.values()))

    def test_single_floor_rendering_rejects_unknown_floor(self):
        with self.assertRaises(ValueError):
            render_floor_svg(self.blueprint, 4)


if __name__ == "__main__":
    unittest.main()

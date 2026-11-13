import unittest

import networkx as nx

from geometry_v2 import FLOORS
from generator_v2 import (
    calculate_statistics,
    carve_maze,
    edge_key,
    generate_floor_mazes,
)


class GeneratorV2Tests(unittest.TestCase):
    def test_each_floor_generates_a_spanning_tree(self):
        mazes = generate_floor_mazes("geometry-v2-test")

        self.assertEqual(set(mazes), set(FLOORS))
        for floor, maze in mazes.items():
            with self.subTest(floor=floor):
                cells = maze["cells"]
                opened_edges = maze["opened_edges"]
                graph = nx.Graph()
                graph.add_nodes_from(cells)
                graph.add_edges_from(opened_edges)

                self.assertEqual(len(opened_edges), len(cells) - 1)
                self.assertTrue(nx.is_tree(graph))
                self.assertTrue(
                    all(
                        edge_key(a, b) in {
                            edge_key(cell, neighbor)
                            for cell, neighbors in maze["connections"].items()
                            for neighbor in neighbors
                        }
                        for a, b in opened_edges
                    )
                )

    def test_generation_is_reproducible(self):
        first = generate_floor_mazes("same-seed")
        second = generate_floor_mazes("same-seed")

        for floor in FLOORS:
            with self.subTest(floor=floor):
                self.assertEqual(
                    first[floor]["opened_edges"],
                    second[floor]["opened_edges"],
                )

    def test_different_floor_seeds_are_independent(self):
        mazes = generate_floor_mazes("same-seed")
        self.assertEqual(
            {mazes[floor]["seed"] for floor in FLOORS},
            {f"same-seed:floor:{floor}" for floor in FLOORS},
        )

    def test_statistics_match_tree(self):
        mazes = generate_floor_mazes("statistics-test")
        for floor, maze in mazes.items():
            with self.subTest(floor=floor):
                stats = calculate_statistics(
                    maze["cells"],
                    maze["opened_edges"],
                )
                self.assertEqual(stats["cells"], len(maze["cells"]))
                self.assertEqual(stats["passages"], len(maze["cells"]) - 1)
                self.assertEqual(
                    stats["dead_ends"] + stats["junctions"]
                    <= stats["cells"],
                    True,
                )

    def test_disconnected_input_is_rejected(self):
        cells = {(0, 0), (10, 10)}
        connections = {cell: [] for cell in cells}
        with self.assertRaises(ValueError):
            carve_maze(cells, connections, "bad-input")


if __name__ == "__main__":
    unittest.main()

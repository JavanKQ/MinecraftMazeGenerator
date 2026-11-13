import unittest
from collections import deque

from geometry_v2 import (
    FINISH,
    FLOORS,
    floor_y,
    count_floor_blocks,
    generate_grid,
    shared_grid_cells,
    cell_overlaps_finish,
)


EXPECTED_BLOCK_COUNTS = {1: 24822, 2: 20502, 3: 13608}
EXPECTED_GRID_COUNTS = {1: 1524, 2: 1216, 3: 808}


def component_sizes(connections):
    remaining = set(connections)
    sizes = []

    while remaining:
        start = remaining.pop()
        pending = [start]
        size = 0

        while pending:
            cell = pending.pop()
            size += 1
            for neighbor in connections[cell]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)

        sizes.append(size)

    return sorted(sizes, reverse=True)


class GeometryV2Tests(unittest.TestCase):
    def test_floor_heights(self):
        self.assertEqual(
            {floor: floor_y(floor) for floor in FLOORS},
            {1: 135, 2: 142, 3: 147},
        )

    def test_floor_areas(self):
        self.assertEqual(
            {floor: count_floor_blocks(floor) for floor in FLOORS},
            EXPECTED_BLOCK_COUNTS,
        )

    def test_grid_counts(self):
        for floor, expected in EXPECTED_GRID_COUNTS.items():
            with self.subTest(floor=floor):
                cells, connections = generate_grid(floor)
                self.assertEqual(len(cells), expected)
                self.assertEqual(set(connections), cells)

    def test_each_floor_grid_is_connected(self):
        for floor in FLOORS:
            with self.subTest(floor=floor):
                _, connections = generate_grid(floor)
                self.assertEqual(component_sizes(connections), [
                    EXPECTED_GRID_COUNTS[floor]
                ])

    def test_finish_overlapping_cells_are_reserved(self):
        cells, _ = generate_grid(3)
        self.assertTrue(FINISH.contains(11441, 10988))
        self.assertFalse(any(cell_overlaps_finish(x, z) for x, z in cells))
        self.assertEqual(len(cells), EXPECTED_GRID_COUNTS[3])

    def test_shared_grid_cells(self):
        shared = shared_grid_cells()
        self.assertEqual(len(shared), 776)
        for floor in FLOORS:
            cells, _ = generate_grid(floor)
            self.assertLessEqual(shared, cells)

    def test_empty_floor_selection_has_no_shared_cells(self):
        self.assertEqual(shared_grid_cells([]), set())


if __name__ == "__main__":
    unittest.main()

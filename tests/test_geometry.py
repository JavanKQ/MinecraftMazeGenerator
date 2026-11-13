from geometry import (
    FINISH,
    FLOORS,
    GRID_ORIGIN_X,
    GRID_ORIGIN_Z,
    GRID_PITCH,
    count_floor_blocks,
    floor_contains,
    floor_y,
    generate_grid,
    shared_grid_cells,
)


def test_each_floor_has_its_own_footprint_and_height():
    assert [floor_y(floor) for floor in (1, 2, 3)] == [135, 142, 147]
    assert len(FLOORS) == 3

    expected_areas = {1: 24822, 2: 20502, 3: 13608}
    assert {
        floor: count_floor_blocks(floor)
        for floor in (1, 2, 3)
    } == expected_areas


def test_floor_grids_share_one_global_alignment_but_have_distinct_cells():
    grids = {
        floor: generate_grid(floor)[0]
        for floor in (1, 2, 3)
    }

    assert GRID_ORIGIN_X == 11360
    assert GRID_ORIGIN_Z == 10904
    assert GRID_PITCH == 4
    assert len(grids[1]) == 1524
    assert len(grids[2]) == 1216
    assert len(grids[3]) == 812

    shared = set.intersection(*grids.values())
    assert shared == shared_grid_cells()
    assert len(shared) == 776
    assert grids[1] != grids[2] != grids[3]


def test_every_generated_cell_fits_its_own_floor():
    for floor in (1, 2, 3):
        cells, connections = generate_grid(floor)
        assert cells
        assert set(connections) == cells
        for x, z in cells:
            assert all(
                floor_contains(x + dx, z + dz, floor)
                for dx in range(3)
                for dz in range(3)
            )


def test_finish_region_is_the_supplied_floor_three_destination():
    assert (FINISH.min_x, FINISH.max_x, FINISH.min_z, FINISH.max_z) == (
        11441, 11445, 10988, 10993
    )
    assert all(
        floor_contains(x, z, 3)
        for x in range(FINISH.min_x, FINISH.max_x + 1)
        for z in range(FINISH.min_z, FINISH.max_z + 1)
    )

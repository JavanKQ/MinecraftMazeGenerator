from dataclasses import dataclass

CORRIDOR_WIDTH = 3
WALL_THICKNESS = 1
GRID_PITCH = CORRIDOR_WIDTH + WALL_THICKNESS

# Every floor uses the same grid alignment. Footprints do not get re-originated.
GRID_ORIGIN_X = 11360
GRID_ORIGIN_Z = 10904

FINISH_FLOOR = 3


@dataclass(frozen=True)
class Rectangle:
    min_x: int
    max_x: int
    min_z: int
    max_z: int

    def contains(self, x, z):
        return (
            self.min_x <= x <= self.max_x
            and self.min_z <= z <= self.max_z
        )

    def overlaps(self, other):
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_z < other.min_z
            or self.min_z > other.max_z
        )


FLOORS = {
    1: {
        "y": 135,
        "footprint": (
            Rectangle(11459, 11527, 10904, 11065),
            Rectangle(11456, 11458, 10904, 11002),
            Rectangle(11360, 11455, 10904, 10981),
            Rectangle(11360, 11431, 10982, 11002),
            Rectangle(11360, 11428, 11003, 11065),
        ),
    },
    2: {
        "y": 142,
        "footprint": (
            Rectangle(11366, 11422, 11003, 11059),
            Rectangle(11366, 11431, 10910, 11002),
            Rectangle(11432, 11455, 10910, 10981),
            Rectangle(11456, 11521, 10910, 11002),
            Rectangle(11465, 11521, 11003, 11059),
        ),
    },
    3: {
        "y": 147,
        "footprint": (
            Rectangle(11381, 11407, 11003, 11044),
            Rectangle(11381, 11506, 10913, 11002),
            Rectangle(11480, 11506, 11003, 11044),
        ),
    },
}

FLOOR_COUNT = len(FLOORS)
# Compatibility-friendly alias for code that needs the original footprint.
FLOOR_1 = list(FLOORS[1]["footprint"])

ENTRANCE = Rectangle(11455, 11455, 10985, 10990)
FINISH = Rectangle(11441, 11445, 10988, 10993)

# The finish is reached from the south by a deliberately narrower doorway.
# Its source is one ordinary grid cell; the two connector blocks bridge the
# one-block gap between that cell and the finish rectangle.
FINISH_ENTRANCE_CELL = (11440, 10984)
FINISH_ENTRANCE_WIDTH = 2
FINISH_ENTRANCE_BLOCKS = frozenset({
    (11441, 10987),
    (11442, 10987),
})


def get_floor(floor=1):
    try:
        return FLOORS[floor]
    except KeyError as error:
        raise ValueError(f"Unknown floor: {floor}") from error


def floor_footprint(floor=1):
    return get_floor(floor)["footprint"]


def floor_y(floor=1):
    return get_floor(floor)["y"]


def floor_contains(x, z, floor=1):
    return any(rect.contains(x, z) for rect in floor_footprint(floor))


def floor_block_coordinates(floor=1):
    return {
        (x, z)
        for rect in floor_footprint(floor)
        for x in range(rect.min_x, rect.max_x + 1)
        for z in range(rect.min_z, rect.max_z + 1)
    }


def count_floor_blocks(floor=1):
    return len(floor_block_coordinates(floor))


def cell_fits(x, z, floor=1):
    return all(
        floor_contains(x + dx, z + dz, floor)
        for dx in range(CORRIDOR_WIDTH)
        for dz in range(CORRIDOR_WIDTH)
    )


def finish_connector_is_valid():
    cells, _ = generate_grid(FINISH_FLOOR)
    if FINISH_ENTRANCE_CELL not in cells:
        return False

    for x, z in FINISH_ENTRANCE_BLOCKS:
        if not floor_contains(x, z, FINISH_FLOOR):
            return False
        touches_source = (
            FINISH_ENTRANCE_CELL[0] <= x < FINISH_ENTRANCE_CELL[0] + CORRIDOR_WIDTH
            and z == FINISH_ENTRANCE_CELL[1] + CORRIDOR_WIDTH
        )
        touches_finish = FINISH.contains(x, z + 1)
        if not (touches_source and touches_finish):
            return False

    return len(FINISH_ENTRANCE_BLOCKS) == FINISH_ENTRANCE_WIDTH


def cell_overlaps_finish(x, z):
    cell = Rectangle(
        x,
        x + CORRIDOR_WIDTH - 1,
        z,
        z + CORRIDOR_WIDTH - 1,
    )
    return cell.overlaps(FINISH)


def wall_fits(x, z, direction, floor=1):
    if direction == "east":
        return all(
            floor_contains(x + CORRIDOR_WIDTH, z + dz, floor)
            for dz in range(CORRIDOR_WIDTH)
        )

    if direction == "north":
        return all(
            floor_contains(x + dx, z + CORRIDOR_WIDTH, floor)
            for dx in range(CORRIDOR_WIDTH)
        )

    raise ValueError(f"Unknown wall direction: {direction}")


def cells_can_connect(a, b, floor=1):
    if a[1] == b[1]:
        distance = abs(a[0] - b[0])
        if distance == CORRIDOR_WIDTH:
            return True
        if distance == GRID_PITCH:
            return wall_fits(min(a[0], b[0]), a[1], "east", floor)

    if a[0] == b[0]:
        distance = abs(a[1] - b[1])
        if distance == CORRIDOR_WIDTH:
            return True
        if distance == GRID_PITCH:
            return wall_fits(a[0], min(a[1], b[1]), "north", floor)

    return False


def build_connections(cells, floor=1):
    connections = {cell: [] for cell in cells}

    for x, z in cells:
        for distance in (CORRIDOR_WIDTH, GRID_PITCH):
            east = (x + distance, z)
            north = (x, z + distance)

            if east in cells and cells_can_connect((x, z), east, floor):
                connections[(x, z)].append(east)
                connections[east].append((x, z))

            if north in cells and cells_can_connect((x, z), north, floor):
                connections[(x, z)].append(north)
                connections[north].append((x, z))

    return connections


def generate_grid(floor=1):
    footprint = floor_footprint(floor)
    cells = {
        (x, z)
        for x in range(
            GRID_ORIGIN_X,
            max(rect.max_x for rect in footprint) + 1,
            GRID_PITCH,
        )
        for z in range(
            GRID_ORIGIN_Z,
            max(rect.max_z for rect in footprint) + 1,
            GRID_PITCH,
        )
        if cell_fits(x, z, floor)
        and not (floor == FINISH_FLOOR and cell_overlaps_finish(x, z))
    }
    return cells, build_connections(cells, floor)


def shared_grid_cells(floors=None):
    """Cells whose full 3x3 area fits on every requested floor."""
    floor_ids = tuple(FLOORS if floors is None else floors)
    if not floor_ids:
        return set()

    shared = None
    for floor in floor_ids:
        cells, _ = generate_grid(floor)
        shared = cells if shared is None else shared & cells
    return shared


def nearest_endpoint_cells(cells, marker):
    def distance_to(cell):
        x, z = cell
        x_gap = max(
            marker.min_x - (x + CORRIDOR_WIDTH - 1),
            x - marker.max_x,
            0,
        )
        z_gap = max(
            marker.min_z - (z + CORRIDOR_WIDTH - 1),
            z - marker.max_z,
            0,
        )
        return x_gap + z_gap

    if not cells:
        raise ValueError("Cannot find an endpoint in an empty cell set.")

    distances = {cell: distance_to(cell) for cell in cells}
    nearest_distance = min(distances.values())
    return {
        cell
        for cell, distance in distances.items()
        if distance == nearest_distance
    }

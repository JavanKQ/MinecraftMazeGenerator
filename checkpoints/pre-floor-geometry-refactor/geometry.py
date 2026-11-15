from dataclasses import dataclass

CORRIDOR_WIDTH = 3
WALL_THICKNESS = 1
GRID_PITCH = CORRIDOR_WIDTH + WALL_THICKNESS

GRID_ORIGIN_X = 11360
GRID_ORIGIN_Z = 10904


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


FLOOR_1 = [
	Rectangle(11459, 11527, 10904, 11065),
	Rectangle(11456, 11458, 10904, 11002),
	Rectangle(11360, 11455, 10904, 10981),
	Rectangle(11360, 11431, 10982, 11002),
	Rectangle(11360, 11428, 11003, 11065),
]

ENTRANCE = Rectangle(11455, 11455, 10985, 10990)
FINISH = Rectangle(11359, 11363, 10904, 10904)


def floor_contains(x, z):
	return any(rect.contains(x, z) for rect in FLOOR_1)


def floor_block_coordinates():
	return {
		(x, z)
		for rect in FLOOR_1
		for x in range(rect.min_x, rect.max_x + 1)
		for z in range(rect.min_z, rect.max_z + 1)
	}


def count_floor_blocks():
	return len(floor_block_coordinates())


def cell_fits(x, z):
	return all(
		floor_contains(x + dx, z + dz)
		for dx in range(CORRIDOR_WIDTH)
		for dz in range(CORRIDOR_WIDTH)
	)


def wall_fits(x, z, direction):
	if direction == "east":
		return all(
			floor_contains(x + CORRIDOR_WIDTH, z + dz)
			for dz in range(CORRIDOR_WIDTH)
		)

	if direction == "north":
		return all(
			floor_contains(x + dx, z + CORRIDOR_WIDTH)
			for dx in range(CORRIDOR_WIDTH)
		)

	return False


def cells_can_connect(a, b):
	if a[1] == b[1]:
		distance = abs(a[0] - b[0])
		if distance == CORRIDOR_WIDTH:
			return True
		if distance == GRID_PITCH:
			return wall_fits(min(a[0], b[0]), a[1], "east")

	if a[0] == b[0]:
		distance = abs(a[1] - b[1])
		if distance == CORRIDOR_WIDTH:
			return True
		if distance == GRID_PITCH:
			return wall_fits(a[0], min(a[1], b[1]), "north")

	return False


def build_connections(cells):
	connections = {cell: [] for cell in cells}

	for x, z in cells:
		for distance in (CORRIDOR_WIDTH, GRID_PITCH):
			east = (x + distance, z)
			north = (x, z + distance)

			if east in cells and cells_can_connect((x, z), east):
				connections[(x, z)].append(east)
				connections[east].append((x, z))

			if north in cells and cells_can_connect((x, z), north):
				connections[(x, z)].append(north)
				connections[north].append((x, z))

	return connections


def generate_grid():
	cells = {
		(x, z)
		for x in range(
			GRID_ORIGIN_X,
			max(rect.max_x for rect in FLOOR_1) + 1,
			GRID_PITCH,
		)
		for z in range(
			GRID_ORIGIN_Z,
			max(rect.max_z for rect in FLOOR_1) + 1,
			GRID_PITCH,
		)
		if cell_fits(x, z)
	}
	return cells, build_connections(cells)


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

	distances = {cell: distance_to(cell) for cell in cells}
	nearest_distance = min(distances.values())
	return {
		cell
		for cell, distance in distances.items()
		if distance == nearest_distance
	}

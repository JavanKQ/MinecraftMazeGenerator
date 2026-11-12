
from dataclasses import dataclass
from collections import deque
import random
from pathlib import Path

# ==================================================
# SETTINGS
# ==================================================

SEED = "Maze1"

CORRIDOR_WIDTH = 3
WALL_THICKNESS = 1
GRID_PITCH = CORRIDOR_WIDTH + WALL_THICKNESS

EXTRA_LOOP_PERCENT = 12

GRID_ORIGIN_X = 11360
GRID_ORIGIN_Z = 10904


# ==================================================
# FLOOR GEOMETRY
# ==================================================

@dataclass
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


def floor_contains(x, z):
    return any(rect.contains(x, z) for rect in FLOOR_1)


def floor_block_coordinates():
    coordinates = set()

    for rect in FLOOR_1:
        for x in range(rect.min_x, rect.max_x + 1):
            for z in range(rect.min_z, rect.max_z + 1):
                coordinates.add((x, z))

    return coordinates


def count_floor_blocks():
    return len(floor_block_coordinates())


# ==================================================
# GRID GENERATION
# ==================================================

def cell_fits(x, z):
    for dx in range(CORRIDOR_WIDTH):
        for dz in range(CORRIDOR_WIDTH):
            if not floor_contains(x + dx, z + dz):
                return False

    return True


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

            if east in cells and cells_can_connect((x, z), east):
                connections[(x, z)].append(east)
                connections[east].append((x, z))

            north = (x, z + distance)

            if north in cells and cells_can_connect((x, z), north):
                connections[(x, z)].append(north)
                connections[north].append((x, z))

    return connections


def generate_grid():
    cells = set()

    max_x = max(rect.max_x for rect in FLOOR_1)
    max_z = max(rect.max_z for rect in FLOOR_1)

    for x in range(GRID_ORIGIN_X, max_x + 1, GRID_PITCH):
        for z in range(GRID_ORIGIN_Z, max_z + 1, GRID_PITCH):
            if cell_fits(x, z):
                cells.add((x, z))

    return cells, build_connections(cells)


# ==================================================
# MAZE CARVING
# ==================================================

def edge_key(a, b):
    """Give an undirected connection a consistent identity."""
    return tuple(sorted((a, b)))


def cell_block_coordinates(cells):
    return {
        (x + dx, z + dz)
        for x, z in cells
        for dx in range(CORRIDOR_WIDTH)
        for dz in range(CORRIDOR_WIDTH)
    }


def edge_block_coordinates(a, b):
    if a[1] == b[1] and abs(a[0] - b[0]) == GRID_PITCH:
        x = min(a[0], b[0]) + CORRIDOR_WIDTH
        return {
            (x, a[1] + dz)
            for dz in range(CORRIDOR_WIDTH)
        }

    if a[0] == b[0] and abs(a[1] - b[1]) == GRID_PITCH:
        z = min(a[1], b[1]) + CORRIDOR_WIDTH
        return {
            (a[0] + dx, z)
            for dx in range(CORRIDOR_WIDTH)
        }

    return set()


def build_passage_blocks(opened_edges):
    passage_blocks = set()

    for a, b in opened_edges:
        passage_blocks.update(edge_block_coordinates(a, b))

    return passage_blocks


def build_edge_wall_blocks(connections, opened_edges):
    """Build walls only along the current maze's closed grid edges."""
    wall_blocks = set()

    for cell, neighbors in connections.items():
        for neighbor in neighbors:
            if cell > neighbor or edge_key(cell, neighbor) in opened_edges:
                continue

            wall_blocks.update(edge_block_coordinates(cell, neighbor))

    return wall_blocks


def corner_block_coordinates(cells):
    corners = set()

    for x, z in cells:
        corners.update((
            (x + CORRIDOR_WIDTH, z + CORRIDOR_WIDTH),
            (x - 1, z + CORRIDOR_WIDTH),
            (x + CORRIDOR_WIDTH, z - 1),
            (x - 1, z - 1),
        ))

    return corners & floor_block_coordinates()


def build_wall_corner_blocks(cells, edge_walls):
    wall_corners = set()

    for x, z in corner_block_coordinates(cells):
        adjacent_walls = (
            (x + 1, z),
            (x - 1, z),
            (x, z + 1),
            (x, z - 1),
        )

        if sum(block in edge_walls for block in adjacent_walls) >= 2:
            wall_corners.add((x, z))

    return wall_corners


def build_open_corner_blocks(
    cells,
    edge_walls,
    wall_corners,
    corridor_blocks,
    passage_blocks
):
    walkable_blocks = corridor_blocks | passage_blocks
    open_corners = set()

    for corner in corner_block_coordinates(cells):
        if corner in edge_walls or corner in wall_corners:
            continue

        x, z = corner
        adjacent_blocks = (
            (x + 1, z),
            (x - 1, z),
            (x, z + 1),
            (x, z - 1),
        )

        if any(block in walkable_blocks for block in adjacent_blocks):
            open_corners.add(corner)

    return open_corners


def generate_extension_cells(cells, connections, opened_edges):
    """Add connected cells in unused three-block-wide floor bands."""
    floor_blocks = floor_block_coordinates()
    corridor_blocks = cell_block_coordinates(cells)
    passage_blocks = build_passage_blocks(opened_edges)
    edge_walls = build_edge_wall_blocks(connections, opened_edges)
    wall_corners = build_wall_corner_blocks(cells, edge_walls)
    unused_blocks = (
        floor_blocks
        - corridor_blocks
        - passage_blocks
        - edge_walls
        - wall_corners
    )

    candidates = set()

    for x, z in unused_blocks:
        cell_blocks = {
            (x + dx, z + dz)
            for dx in range(CORRIDOR_WIDTH)
            for dz in range(CORRIDOR_WIDTH)
        }

        if cell_blocks <= unused_blocks:
            candidates.add((x, z))

    rows = {}

    for x, z in candidates:
        rows.setdefault(z, set()).add(x)

    added_cells = set()
    occupied_blocks = set(corridor_blocks)

    for z, row_xs in sorted(rows.items()):
        row_xs = sorted(row_xs)
        runs = []
        run_start = previous_x = row_xs[0]

        for x in row_xs[1:]:
            if x - previous_x > GRID_PITCH:
                runs.append((run_start, previous_x))
                run_start = x

            previous_x = x

        runs.append((run_start, previous_x))

        for start_x, end_x in runs:
            run_candidates = {
                (x, z)
                for x in row_xs
                if start_x <= x <= end_x
            }
            anchors = {
                x
                for x, row_z in run_candidates
                if any(
                    cells_can_connect((x, row_z), cell)
                    for cell in cells
                )
            }

            single_entry_anchors = {
                x
                for x in anchors
                if sum(
                    cells_can_connect((x, z), cell)
                    for cell in cells
                ) == 1
            }

            if not single_entry_anchors:
                continue

            anchor_x = min(single_entry_anchors)
            anchor_blocks = {
                (anchor_x + dx, z + dz)
                for dx in range(CORRIDOR_WIDTH)
                for dz in range(CORRIDOR_WIDTH)
            }

            if anchor_blocks & occupied_blocks:
                continue

            occupied_blocks.update(anchor_blocks)
            blocked_anchors = anchors - {anchor_x}
            positions = {anchor_x}

            for direction in (-1, 1):
                current_x = anchor_x
                first_step = True

                while True:
                    steps = (
                        (CORRIDOR_WIDTH, GRID_PITCH)
                        if first_step
                        else (GRID_PITCH, CORRIDOR_WIDTH)
                    )
                    next_x = None

                    for step in steps:
                        candidate_x = current_x + direction * step

                        if (
                            (candidate_x, z) in run_candidates
                            and candidate_x not in blocked_anchors
                        ):
                            candidate_blocks = {
                                (candidate_x + dx, z + dz)
                                for dx in range(CORRIDOR_WIDTH)
                                for dz in range(CORRIDOR_WIDTH)
                            }

                            if not candidate_blocks & occupied_blocks:
                                next_x = candidate_x
                                break

                    if next_x is None:
                        break

                    positions.add(next_x)
                    occupied_blocks.update(
                        (next_x + dx, z + dz)
                        for dx in range(CORRIDOR_WIDTH)
                        for dz in range(CORRIDOR_WIDTH)
                    )
                    current_x = next_x
                    first_step = False

            added_cells.update((x, z) for x in positions)

    return added_cells


def build_wall_blocks(connections, opened_edges):
    """Make every floor block either a corridor, passage, or wall."""
    floor_blocks = floor_block_coordinates()
    corridor_blocks = cell_block_coordinates(connections)
    passage_blocks = build_passage_blocks(opened_edges)
    edge_walls = build_edge_wall_blocks(connections, opened_edges)
    wall_corners = build_wall_corner_blocks(connections, edge_walls)
    open_corners = build_open_corner_blocks(
        connections,
        edge_walls,
        wall_corners,
        corridor_blocks,
        passage_blocks
    )
    walkable_blocks = corridor_blocks | passage_blocks | open_corners
    return floor_blocks - walkable_blocks


def carve_maze(cells, connections):
    rng = random.Random(SEED)

    # Start with a randomized depth-first search.
    start = min(cells)
    visited = {start}
    stack = [start]

    opened_edges = {
        edge_key(cell, neighbor)
        for cell, neighbors in connections.items()
        for neighbor in neighbors
        if cell < neighbor
        and (
            (
                cell[1] == neighbor[1]
                and abs(cell[0] - neighbor[0]) == CORRIDOR_WIDTH
            )
            or (
                cell[0] == neighbor[0]
                and abs(cell[1] - neighbor[1]) == CORRIDOR_WIDTH
            )
        )
    }

    while stack:
        current = stack[-1]

        unvisited = [
            neighbor
            for neighbor in connections[current]
            if neighbor not in visited
        ]

        if unvisited:
            next_cell = rng.choice(unvisited)

            opened_edges.add(edge_key(current, next_cell))
            visited.add(next_cell)
            stack.append(next_cell)

        else:
            stack.pop()

    if len(visited) != len(cells):
        raise ValueError("Maze grid contains disconnected corridor cells.")

    # Identify every possible connection not used by the tree.
    all_edges = {
        edge_key(cell, neighbor)
        for cell in cells
        for neighbor in connections[cell]
    }

    unused_edges = list(all_edges - opened_edges)
    rng.shuffle(unused_edges)

    # Add 12% of the remaining possible connections.
    loop_count = round(
        len(unused_edges) * EXTRA_LOOP_PERCENT / 100
    )

    extra_loops = unused_edges[:loop_count]
    opened_edges.update(extra_loops)

    return opened_edges, len(all_edges), len(extra_loops)


# ==================================================
# MAZE STATISTICS
# ==================================================

def calculate_statistics(cells, connections, opened_edges):
    degrees = {cell: 0 for cell in cells}

    for a, b in opened_edges:
        degrees[a] += 1
        degrees[b] += 1

    dead_ends = sum(
        1 for degree in degrees.values() if degree == 1
    )

    junctions = sum(
        1 for degree in degrees.values() if degree >= 3
    )

    return dead_ends, junctions


def export_blueprint(connections, opened_edges):
    """Export a color-coded, zoomable maze blueprint."""

    scale = 4
    margin = 30
    legend_height = 100

    COLORS = {
        "unusable": "#000000",
        "floor": "#FFFFFF",
        "entrance": "#16A34A",
        "wall": "#2563EB",
        "elevator": "#9333EA",
        "drop": "#F97316",
        "finish": "#DC2626",
    }

    min_x = min(rect.min_x for rect in FLOOR_1)
    max_x = max(rect.max_x for rect in FLOOR_1)
    min_z = min(rect.min_z for rect in FLOOR_1)
    max_z = max(rect.max_z for rect in FLOOR_1)

    map_width = (max_x - min_x + 1) * scale
    map_height = (max_z - min_z + 1) * scale

    svg_width = map_width + margin * 2
    svg_height = map_height + margin * 2 + legend_height

    def screen_x(x):
        return margin + (x - min_x) * scale

    def screen_y(z, height):
        return margin + (max_z - z - height + 1) * scale

    def draw_rect(x, z, width, height, color):
        return (
            f'<rect x="{screen_x(x)}" '
            f'y="{screen_y(z, height)}" '
            f'width="{width * scale}" '
            f'height="{height * scale}" '
            f'fill="{color}"/>'
        )

    wall_blocks = build_wall_blocks(connections, opened_edges)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_width}" height="{svg_height}" '
        f'viewBox="0 0 {svg_width} {svg_height}">',

        '<title>Minecraft Maze - Floor 1</title>',

        f'<rect width="100%" height="100%" fill="{COLORS["unusable"]}"/>',
    ]

    # Draw the full floor footprint so black only marks out-of-bounds areas.
    for rect in FLOOR_1:
        parts.append(
            draw_rect(
                rect.min_x,
                rect.min_z,
                rect.max_x - rect.min_x + 1,
                rect.max_z - rect.min_z + 1,
                COLORS["floor"]
            )
        )

    # Draw remaining walls.
    for x, z in wall_blocks:
        parts.append(
            draw_rect(
                x, z,
                1, 1,
                COLORS["wall"]
            )
        )

    # Draw the color legend.
    legend_y = margin + map_height + 20

    legend_items = [
        ("Unusable", COLORS["unusable"]),
        ("Floor", COLORS["floor"]),
        ("Entrance", COLORS["entrance"]),
        ("Walls", COLORS["wall"]),
        ("Elevator up", COLORS["elevator"]),
        ("Drop down", COLORS["drop"]),
        ("Finish", COLORS["finish"]),
    ]

    item_width = (svg_width - margin * 2) // 4

    for index, (label, color) in enumerate(legend_items):
        column = index % 4
        row = index // 4

        x = margin + column * item_width
        y = legend_y + row * 32

        parts.append(
            f'<rect x="{x}" y="{y}" width="18" height="18" '
            f'fill="{color}" stroke="#888888" stroke-width="1"/>'
        )

        parts.append(
            f'<text x="{x + 26}" y="{y + 14}" '
            f'font-family="Arial" font-size="13" fill="#FFFFFF">'
            f'{label}</text>'
        )

    parts.append("</svg>")

    output_path = Path(__file__).with_name("maze_floor_1.svg")

    output_path.write_text(
        "\n".join(parts),
        encoding="utf-8"
    )

    return output_path

# ==================================================
# MAIN
# ==================================================

def main():
    cells, connections = generate_grid()

    initial_opened_edges, _, _ = carve_maze(cells, connections)
    added_cells = generate_extension_cells(
        cells,
        connections,
        initial_opened_edges
    )
    cells.update(added_cells)
    connections = build_connections(cells)

    opened_edges, possible_edges, loop_count = carve_maze(
        cells, connections
    )
    blueprint_path = export_blueprint(connections, opened_edges)

    dead_ends, junctions = calculate_statistics(
        cells, connections, opened_edges
    )

    floor_blocks = count_floor_blocks()

    corridor_blocks = len(cells) * CORRIDOR_WIDTH ** 2

    print()
    print("MINECRAFT MAZE GENERATOR")
    print("=" * 40)

    print(f"Random seed:           {SEED}")
    print(f"Floor blocks:          {floor_blocks:,}")
    print(f"Valid corridor cells:  {len(cells):,}")

    print()
    print("MAZE GENERATION")
    print("-" * 40)

    print(f"Possible connections:  {possible_edges:,}")
    print(f"Main maze connections:{len(cells) - 1:>8,}")
    print(f"Additional loops:      {loop_count:,}")
    print(f"Total open passages:   {len(opened_edges):,}")

    print()
    print("MAZE CHARACTERISTICS")
    print("-" * 40)

    print(f"Dead ends:             {dead_ends:,}")
    print(f"Junctions:             {junctions:,}")
    print(f"Corridor coverage:     {corridor_blocks / floor_blocks * 100:.1f}%")

    print()
    print(f"Blueprint saved:      {blueprint_path}")
    print("Maze successfully generated.")
    print("Same seed and settings will reproduce the same maze.")


if __name__ == "__main__":
    main()
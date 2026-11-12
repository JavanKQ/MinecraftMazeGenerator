from pathlib import Path
import re
from xml.sax.saxutils import escape

from geometry import (
	CORRIDOR_WIDTH,
	ENTRANCE,
	FINISH,
	FLOOR_1,
	floor_block_coordinates,
)
SCALE = 4
MARGIN = 30
LEGEND_HEIGHT = 100

COLORS = {
	"unusable": "#000000",
	"floor": "#FFFFFF",
	"entrance": "#16A34A",
	"wall": "#2563EB",
	"elevator": "#9333EA",
	"drop": "#F97316",
	"finish": "#DC2626",
}


def cell_block_coordinates(cells):
	return {
		(x + dx, z + dz)
		for x, z in cells
		for dx in range(CORRIDOR_WIDTH)
		for dz in range(CORRIDOR_WIDTH)
	}


def edge_block_coordinates(a, b):
	if a[1] == b[1] and abs(a[0] - b[0]) == CORRIDOR_WIDTH + 1:
		x = min(a[0], b[0]) + CORRIDOR_WIDTH
		return {(x, a[1] + dz) for dz in range(CORRIDOR_WIDTH)}

	if a[0] == b[0] and abs(a[1] - b[1]) == CORRIDOR_WIDTH + 1:
		z = min(a[1], b[1]) + CORRIDOR_WIDTH
		return {(a[0] + dx, z) for dx in range(CORRIDOR_WIDTH)}

	return set()


def build_passage_blocks(opened_edges):
	return {
		block
		for a, b in opened_edges
		for block in edge_block_coordinates(a, b)
	}


def remove_isolated_wall_blocks(wall_blocks):
	remaining = set(wall_blocks)
	isolated = set()

	while remaining:
		component = set()
		pending = [remaining.pop()]

		while pending:
			x, z = pending.pop()
			component.add((x, z))
			for neighbor in (
				(x + 1, z),
				(x - 1, z),
				(x, z + 1),
				(x, z - 1),
			):
				if neighbor in remaining:
					remaining.remove(neighbor)
					pending.append(neighbor)

		if len(component) == 1:
			isolated.update(component)

	return set(wall_blocks) - isolated


def build_wall_blocks(cells, opened_edges):
	floor_blocks = floor_block_coordinates()
	walkable_blocks = (
		cell_block_coordinates(cells)
		| build_passage_blocks(opened_edges)
	)
	return remove_isolated_wall_blocks(floor_blocks - walkable_blocks)


def export_blueprint(cells, opened_edges, seed):
	min_x = min(rect.min_x for rect in FLOOR_1)
	max_x = max(rect.max_x for rect in FLOOR_1)
	min_z = min(rect.min_z for rect in FLOOR_1)
	max_z = max(rect.max_z for rect in FLOOR_1)
	map_width = (max_x - min_x + 1) * SCALE
	map_height = (max_z - min_z + 1) * SCALE
	svg_width = map_width + MARGIN * 2
	svg_height = map_height + MARGIN * 2 + LEGEND_HEIGHT

	def screen_x(x, width):
		return MARGIN + (max_x - x - width + 1) * SCALE

	def screen_y(z, height):
		return MARGIN + (max_z - z - height + 1) * SCALE

	def draw_rect(x, z, width, height, color):
		return (
			f'<rect x="{screen_x(x, width)}" '
			f'y="{screen_y(z, height)}" '
			f'width="{width * SCALE}" '
			f'height="{height * SCALE}" '
			f'fill="{color}"/>'
		)

	marker_blocks = {
		(x, z)
		for marker in (ENTRANCE, FINISH)
		for x in range(marker.min_x, marker.max_x + 1)
		for z in range(marker.min_z, marker.max_z + 1)
	}
	walls = build_wall_blocks(cells, opened_edges) - marker_blocks
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" '
		f'width="{svg_width}" height="{svg_height}" '
		f'viewBox="0 0 {svg_width} {svg_height}">',
		f'<title>Minecraft Maze - Floor 1 - Seed: {escape(str(seed))}</title>',
		f'<rect width="100%" height="100%" fill="{COLORS["unusable"]}"/>',
	]

	for rect in FLOOR_1:
		parts.append(draw_rect(
			rect.min_x,
			rect.min_z,
			rect.max_x - rect.min_x + 1,
			rect.max_z - rect.min_z + 1,
			COLORS["floor"],
		))

	for x, z in walls:
		parts.append(draw_rect(x, z, 1, 1, COLORS["wall"]))

	for marker, color in (
		(ENTRANCE, COLORS["entrance"]),
		(FINISH, COLORS["finish"]),
	):
		parts.append(draw_rect(
			marker.min_x,
			marker.min_z,
			marker.max_x - marker.min_x + 1,
			marker.max_z - marker.min_z + 1,
			color,
		))

	legend_y = MARGIN + map_height + 20
	legend_items = (
		("Unusable", COLORS["unusable"]),
		("Floor", COLORS["floor"]),
		("Entrance", COLORS["entrance"]),
		("Walls", COLORS["wall"]),
		("Elevator up", COLORS["elevator"]),
		("Drop down", COLORS["drop"]),
		("Finish", COLORS["finish"]),
	)
	item_width = (svg_width - MARGIN * 2) // 4

	for index, (label, color) in enumerate(legend_items):
		x = MARGIN + (index % 4) * item_width
		y = legend_y + (index // 4) * 32
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
	filename_seed = re.sub(r"[^A-Za-z0-9._-]+", "_", str(seed)).strip("._-")
	filename_seed = filename_seed or "seed"
	output_path = Path(__file__).with_name(
		f"maze_floor_1_seed-{filename_seed}.svg"
	)
	output_path.write_text("\n".join(parts), encoding="utf-8")
	return output_path

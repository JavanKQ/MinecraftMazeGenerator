from pathlib import Path
import re
from xml.sax.saxutils import escape

from geometry import (
	CORRIDOR_WIDTH,
	ENTRANCE,
	FINISH,
	FLOOR_1,
	floor_footprint,
	floor_block_coordinates,
)
SCALE = 8
MARGIN = 30

COLORS = {
	"unusable": "#000000",
	"floor": "#FFFFFF",
	"entrance": "#16A34A",
	"wall": "#2563EB",
	"elevator_1": "#9333EA",
	"elevator_2": "#6D28D9",
	"drop_1": "#F97316",
	"drop_2": "#C2410C",
	"finish": "#DC2626",
	"route": "#FDE047",
}

LEGEND_ITEMS = (
	("Unusable", COLORS["unusable"]),
	("Floor", COLORS["floor"]),
	("Entrance", COLORS["entrance"]),
	("Walls", COLORS["wall"]),
	("Elevator up 1 floor", COLORS["elevator_1"]),
	("Elevator up 2 floors", COLORS["elevator_2"]),
	("Drop down 1 floor", COLORS["drop_1"]),
	("Drop down 2 floors", COLORS["drop_2"]),
	("Finish", COLORS["finish"]),
	("Solution route", COLORS["route"]),
)
LEGEND_COLUMNS = 3


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


def build_wall_blocks(cells, opened_edges, floor=1):
	floor_blocks = floor_block_coordinates(floor)
	walkable_blocks = (
		cell_block_coordinates(cells)
		| build_passage_blocks(opened_edges)
	)
	return remove_isolated_wall_blocks(floor_blocks - walkable_blocks)


def export_blueprint(
	cells,
	opened_edges,
	seed,
	floor=1,
	route_segments=(),
	transition_markers=(),
	transition_notes=(),
	route_notes=(),
	output_directory=None,
):
	footprint = floor_footprint(floor)
	min_x = min(rect.min_x for rect in footprint)
	max_x = max(rect.max_x for rect in footprint)
	min_z = min(rect.min_z for rect in footprint)
	max_z = max(rect.max_z for rect in footprint)
	map_width = (max_x - min_x + 1) * SCALE
	map_height = (max_z - min_z + 1) * SCALE
	svg_width = map_width + MARGIN * 2
	legend_y = MARGIN + map_height + 20
	notes = [*transition_notes, *route_notes]
	legend_rows = (len(LEGEND_ITEMS) + LEGEND_COLUMNS - 1) // LEGEND_COLUMNS
	notes_y = legend_y + legend_rows * 30 + 12
	svg_height = notes_y + len(notes) * 20 + MARGIN

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

	endpoint_regions = []
	if floor == 1:
		endpoint_regions.append(ENTRANCE)
	if floor == 3:
		endpoint_regions.append(FINISH)
	marker_blocks = {
		(x, z)
		for marker in endpoint_regions
		for x in range(marker.min_x, marker.max_x + 1)
		for z in range(marker.min_z, marker.max_z + 1)
	}
	walls = build_wall_blocks(cells, opened_edges, floor) - marker_blocks
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" '
		f'width="{svg_width}" height="{svg_height}" '
		f'viewBox="0 0 {svg_width} {svg_height}">',
		f'<title>Minecraft Maze - Floor {floor} - Seed: {escape(str(seed))}</title>',
		f'<rect width="100%" height="100%" fill="{COLORS["unusable"]}"/>',
	]

	for rect in footprint:
		parts.append(draw_rect(
			rect.min_x,
			rect.min_z,
			rect.max_x - rect.min_x + 1,
			rect.max_z - rect.min_z + 1,
			COLORS["floor"],
		))

	for x, z in sorted(walls):
		parts.append(draw_rect(x, z, 1, 1, COLORS["wall"]))

	for segment in route_segments:
		if not segment:
			continue
		points = " ".join(
			f"{screen_x(x, 1) + SCALE / 2:g},{screen_y(z, 1) + SCALE / 2:g}"
			for x, z in segment
		)
		parts.append(
			f'<polyline points="{points}" fill="none" '
			f'stroke="#111827" stroke-width="10" stroke-linecap="round" '
			f'stroke-linejoin="round"/>'
		)
		parts.append(
			f'<polyline points="{points}" fill="none" '
			f'stroke="{COLORS["route"]}" stroke-width="5" '
			f'stroke-linecap="round" stroke-linejoin="round"/>'
		)

	for marker in transition_markers:
		x, z = marker["cell"]
		color = COLORS[marker["kind"]]
		parts.append(
			f'<rect x="{screen_x(x, CORRIDOR_WIDTH)}" '
			f'y="{screen_y(z, CORRIDOR_WIDTH)}" '
			f'width="{CORRIDOR_WIDTH * SCALE}" '
			f'height="{CORRIDOR_WIDTH * SCALE}" fill="{color}" '
			f'stroke="{COLORS["route"] if marker["solution"] else "#111827"}" '
			f'stroke-width="{4 if marker["solution"] else 2}"/>'
		)
		parts.append(
			f'<text x="{screen_x(x, CORRIDOR_WIDTH) + CORRIDOR_WIDTH * SCALE / 2:g}" '
			f'y="{screen_y(z, CORRIDOR_WIDTH) + CORRIDOR_WIDTH * SCALE / 2:g}" '
			'font-family="Arial" font-size="12" font-weight="bold" '
			'text-anchor="middle" dominant-baseline="central" fill="#FFFFFF">'
			f'{escape(marker["label"])}</text>'
		)

	endpoint_markers = []
	if floor == 1:
		endpoint_markers.append((ENTRANCE, COLORS["entrance"]))
	if floor == 3:
		endpoint_markers.append((FINISH, COLORS["finish"]))
	for marker, color in endpoint_markers:
		parts.append(draw_rect(
			marker.min_x,
			marker.min_z,
			marker.max_x - marker.min_x + 1,
			marker.max_z - marker.min_z + 1,
			color,
		))

	item_width = (svg_width - MARGIN * 2) // LEGEND_COLUMNS

	for index, (label, color) in enumerate(LEGEND_ITEMS):
		x = MARGIN + (index % LEGEND_COLUMNS) * item_width
		y = legend_y + (index // LEGEND_COLUMNS) * 30
		parts.append(
			f'<rect x="{x}" y="{y}" width="18" height="18" '
			f'fill="{color}" stroke="#888888" stroke-width="1"/>'
		)
		parts.append(
			f'<text x="{x + 26}" y="{y + 14}" '
			f'font-family="Arial" font-size="13" fill="#FFFFFF">'
			f'{label}</text>'
		)

	for index, note in enumerate(notes):
		y = notes_y + index * 20
		parts.append(
			f'<text x="{MARGIN}" y="{y}" font-family="Arial" '
			f'font-size="13" fill="#FFFFFF">{escape(note)}</text>'
		)

	parts.append("</svg>")
	filename_seed = re.sub(r"[^A-Za-z0-9._-]+", "_", str(seed)).strip("._-")
	filename_seed = filename_seed or "seed"
	output_dir = Path(output_directory) if output_directory else Path(__file__).parent
	output_path = output_dir / f"maze_floor_{floor}_seed-{filename_seed}.svg"
	output_path.write_text("\n".join(parts), encoding="utf-8")
	return output_path


def export_three_floor_blueprints(
	cells_by_floor,
	graph,
	route,
	transitions,
	seed,
	output_directory=None,
):
	floor_edges = {floor: set() for floor in range(1, 4)}
	for (floor_a, cell_a), (floor_b, cell_b) in graph.edges:
		if floor_a == floor_b:
			floor_edges[floor_a].add(tuple(sorted((cell_a, cell_b))))

	route_segments = {floor: [] for floor in range(1, 4)}
	current_floor = None
	current_segment = []
	for floor, cell in route:
		if floor != current_floor:
			if current_segment:
				route_segments[current_floor].append(current_segment)
			current_floor = floor
			current_segment = [cell]
		else:
			current_segment.append(cell)
	if current_segment:
		route_segments[current_floor].append(current_segment)

	markers_by_floor = {floor: {} for floor in range(1, 4)}
	notes_by_floor = {floor: [] for floor in range(1, 4)}
	transition_by_edge = {}
	route_edges = set(zip(route, route[1:]))
	for transition in transitions:
		floor_span = abs(transition["to"][0] - transition["from"][0])
		move_type = "elevator" if transition["kind"] == "elevator_up" else "drop"
		kind = f"{move_type}_{floor_span}"
		transition_by_edge[(transition["from"], transition["to"])] = transition
		from_floor, from_cell = transition["from"]
		to_floor, to_cell = transition["to"]
		if transition.get("decoy", False):
			designation = "optional decoy "
		elif transition.get("optional", False):
			designation = "optional "
		else:
			designation = ""
		span_label = f"{floor_span} floor" if floor_span == 1 else f"{floor_span} floors"
		if move_type == "elevator":
			if transition.get("finish_access", False):
				descriptions = (
					(
						from_floor,
						from_cell,
						f'{transition["id"]}: elevator up {span_label} to the '
						f'Floor {to_floor} finish area',
					),
					(
						to_floor,
						to_cell,
						f'{transition["id"]}: only elevator access to the finish area '
						f'({span_label})',
					),
				)
			else:
				descriptions = (
					(
						from_floor,
						from_cell,
						f'{transition["id"]}: {designation}elevator up {span_label} to Floor {to_floor}',
					),
					(
						to_floor,
						to_cell,
						f'{transition["id"]}: {designation}elevator arrival from Floor {from_floor} '
						f'({span_label})',
					),
				)
		else:
			descriptions = (
				(
					from_floor,
					from_cell,
					f'{transition["id"]}: {designation}drop {span_label} to Floor {to_floor}',
				),
				(
					to_floor,
					to_cell,
					f'{transition["id"]}: {designation}drop landing from Floor {from_floor} '
					f'({span_label})',
				),
			)

		for floor, cell, description in descriptions:
			marker = markers_by_floor[floor].setdefault(
				(cell, kind),
				{"cell": cell, "kind": kind, "ids": set(), "edges": set()},
			)
			marker["ids"].add(transition["id"])
			marker["edges"].add((transition["from"], transition["to"]))
			if description not in notes_by_floor[floor]:
				notes_by_floor[floor].append(description)

	elevator_count = sum(
		transition["kind"] == "elevator_up" for transition in transitions
	)
	drop_count = sum(
		transition["kind"] == "drop_down" for transition in transitions
	)
	decoy_count = sum(transition.get("decoy", False) for transition in transitions)
	for floor in notes_by_floor:
		notes_by_floor[floor].insert(
			0,
			f"Transitions: {elevator_count} elevators; {drop_count} drops; "
			f"{decoy_count} optional decoy routes",
		)

	route_notes_by_floor = {floor: [] for floor in range(1, 4)}
	for previous, current in zip(route, route[1:]):
		if previous[0] == current[0]:
			continue
		transition = transition_by_edge[(previous, current)]
		floor_span = abs(current[0] - previous[0])
		span_label = f"{floor_span} floor" if floor_span == 1 else f"{floor_span} floors"
		description = (
			f'Solution: {transition["id"]} {previous[0]} -> {current[0]} '
			f'({span_label})'
		)
		for floor in (previous[0], current[0]):
			if description not in route_notes_by_floor[floor]:
				route_notes_by_floor[floor].append(description)

	output_paths = []
	for floor in range(1, 4):
		floor_cells = (
			cells_by_floor[floor]
			if isinstance(cells_by_floor, dict)
			else cells_by_floor
		)
		markers = [
			{
				"cell": marker["cell"],
				"kind": marker["kind"],
				"label": "/".join(sorted(marker["ids"])),
				"solution": any(edge in route_edges for edge in marker["edges"]),
			}
			for marker in markers_by_floor[floor].values()
		]
		output_paths.append(export_blueprint(
			floor_cells,
			floor_edges[floor],
			seed,
			floor=floor,
			route_segments=route_segments[floor],
			transition_markers=markers,
			transition_notes=notes_by_floor[floor],
			route_notes=route_notes_by_floor[floor],
			output_directory=output_directory,
		))
	return output_paths

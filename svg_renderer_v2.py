from __future__ import annotations

from xml.etree import ElementTree as ET

from geometry_v2 import CORRIDOR_WIDTH


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _tag(name):
    return f"{{{SVG_NS}}}{name}"


def _point(cell):
    """Return the center of a 3x3 corridor cell in world coordinates."""
    x, z = cell
    return x + CORRIDOR_WIDTH / 2, z + CORRIDOR_WIDTH / 2


def _cell_text(cell):
    return f"{cell[0]},{cell[1]}"


def _add(parent, name, attributes=None, text=None):
    element = ET.SubElement(parent, _tag(name), attributes or {})
    if text is not None:
        element.text = str(text)
    return element


def _rect(parent, x, z, width, height, data_type, **attributes):
    values = {
        "x": str(x),
        "y": str(z),
        "width": str(width),
        "height": str(height),
        "data-type": data_type,
    }
    values.update({key.replace("_", "-"): str(value) for key, value in attributes.items()})
    return _add(parent, "rect", values)


def _route_segments(blueprint, floor):
    """Extract only horizontal solution steps belonging to this floor."""
    segments = []
    steps = blueprint["solution_route"]
    for index in range(1, len(steps)):
        previous = steps[index - 1]
        current = steps[index]
        incoming = current.get("incoming") or {}
        if (
            previous["floor"] == floor
            and current["floor"] == floor
            and incoming.get("kind") == "corridor"
        ):
            segments.append((previous["cell"], current["cell"]))
    return segments


def render_floor_svg(blueprint, floor, show_solution=False):
    """
    Render one floor from the canonical physical blueprint.

    The renderer only draws geometry already present in the blueprint. It
    does not regenerate cells, infer adjacency, or decide where walls belong.
    Set show_solution=True to add the validated route as an overlay.
    """
    floors = blueprint.get("floors", {})
    if floor not in floors:
        raise ValueError(f"Floor {floor} is not present in the blueprint.")

    floor_data = floors[floor]
    rectangles = floor_data["footprint"]
    min_x = min(rectangle["min_x"] for rectangle in rectangles)
    max_x = max(rectangle["max_x"] for rectangle in rectangles)
    min_z = min(rectangle["min_z"] for rectangle in rectangles)
    max_z = max(rectangle["max_z"] for rectangle in rectangles)

    margin_x = 6
    margin_top = 8
    margin_bottom = 7
    view_x = min_x - margin_x
    view_z = min_z - margin_top
    view_width = max_x - min_x + 1 + margin_x * 2
    view_height = max_z - min_z + 1 + margin_top + margin_bottom

    root = ET.Element(
        _tag("svg"),
        {
            "version": "1.1",
            "viewBox": f"{view_x} {view_z} {view_width} {view_height}",
            "width": "1200",
            "height": "1200",
            "role": "img",
            "data-floor": str(floor),
            "data-solution-overlay": str(bool(show_solution)).lower(),
        },
    )
    _add(root, "title", text=f"Floor {floor} maze blueprint")
    _add(
        root,
        "desc",
        text=(
            f"Floor {floor}, elevation Y={floor_data['y']}. "
            "One SVG coordinate unit represents one Minecraft block."
        ),
    )

    _rect(
        root,
        view_x,
        view_z,
        view_width,
        view_height,
        "canvas",
        fill="#ffffff",
    )

    _add(
        root,
        "text",
        {
            "x": str(min_x),
            "y": str(min_z - 3),
            "font-size": "2.2",
            "font-family": "sans-serif",
            "font-weight": "bold",
            "data-type": "floor-title",
        },
        (
            f"FLOOR {floor}  |  Y={floor_data['y']}  |  1 unit = 1 block"
            + ("  |  SOLUTION ROUTE" if show_solution else "")
        ),
    )

    # The footprint is the actual floor platform, including its irregular edges.
    for index, rectangle in enumerate(rectangles):
        _rect(
            root,
            rectangle["min_x"],
            rectangle["min_z"],
            rectangle["max_x"] - rectangle["min_x"] + 1,
            rectangle["max_z"] - rectangle["min_z"] + 1,
            "footprint",
            **{"data-index": index, "fill": "#e8e8e8", "stroke": "#777777", "stroke-width": "0.18"},
        )

    # Corridor cells are drawn directly from the blueprint's physical block extents.
    for item in floor_data["cell_blocks"]:
        cell = item["cell"]
        x_values = [block[0] for block in item["blocks"]]
        z_values = [block[1] for block in item["blocks"]]
        _rect(
            root,
            min(x_values),
            min(z_values),
            max(x_values) - min(x_values) + 1,
            max(z_values) - min(z_values) + 1,
            "corridor-cell",
            **{
                "data-cell": _cell_text(cell),
                "fill": "#ffffff",
            },
        )

    # Open passages are represented as explicit metadata groups. Their physical
    # appearance is the absence of the wall that would otherwise occupy the gap.
    for passage in floor_data["open_passages"]:
        cells = passage["cells"]
        group = _add(
            root,
            "g",
            {
                "data-type": "open-passage",
                "data-cells": f"{_cell_text(cells[0])}|{_cell_text(cells[1])}",
            },
        )
        for x, z in passage["opening_blocks"]:
            _rect(group, x, z, 1, 1, "open-passage-block", fill="#ffffff")

    for wall in floor_data["wall_segments"]:
        cells = wall["cells"]
        group = _add(
            root,
            "g",
            {
                "data-type": "wall-segment",
                "data-cells": f"{_cell_text(cells[0])}|{_cell_text(cells[1])}",
            },
        )
        for x, z in wall["blocks"]:
            _rect(
                group,
                x,
                z,
                1,
                1,
                "wall-block",
                fill="#2457a6",
            )

    if floor == blueprint["entrance"]["floor"]:
        entrance = blueprint["entrance"]
        marker = entrance["marker"]
        _rect(
            root,
            marker["min_x"],
            marker["min_z"],
            marker["max_x"] - marker["min_x"] + 1,
            marker["max_z"] - marker["min_z"] + 1,
            "entrance",
            fill="#b8e6c5",
            stroke="#16833b",
            stroke_width="0.3",
        )
        for x, z in entrance["opening_blocks"]:
            _rect(
                root, x, z, 1, 1, "entrance-connector", fill="#16833b"
            )

    if floor == blueprint["finish"]["floor"]:
        finish = blueprint["finish"]
        region = finish["region"]
        _rect(
            root,
            region["min_x"],
            region["min_z"],
            region["max_x"] - region["min_x"] + 1,
            region["max_z"] - region["min_z"] + 1,
            "finish",
            fill="#f4d5a6",
            stroke="#b66a12",
            stroke_width="0.3",
        )
        for x, z in finish["opening_blocks"]:
            _rect(
                root, x, z, 1, 1, "finish-connector", fill="#16833b"
            )
        _add(
            root,
            "text",
            {
                "x": str(region["min_x"] + 2.5),
                "y": str(region["min_z"] + 3.5),
                "font-size": "1.1",
                "font-family": "sans-serif",
                "font-weight": "bold",
                "text-anchor": "middle",
                "fill": "#7a430b",
                "data-type": "finish-label",
            },
            "END",
        )

    # Transition markers are placed at the center of their shared 3x3 cells.
    for transition in floor_data["transitions"]:
        x, z = _point(transition["cell"])
        group = _add(
            root,
            "g",
            {
                "data-type": "vertical-transition",
                "data-id": transition["id"],
                "data-kind": transition["kind"],
                "data-cell": _cell_text(transition["cell"]),
                "data-from-floor": str(transition["from_floor"]),
                "data-to-floor": str(transition["to_floor"]),
            },
        )
        _add(
            group,
            "circle",
            {
                "cx": str(x),
                "cy": str(z),
                "r": "0.95",
                "fill": "#eadcf5",
                "stroke": "#7438a5",
                "stroke-width": "0.25",
            },
        )
        arrow = "↑" if transition["kind"] == "elevator_up" else "↓"
        _add(
            group,
            "text",
            {
                "x": str(x),
                "y": str(z + 0.48),
                "font-size": "1.35",
                "font-family": "sans-serif",
                "font-weight": "bold",
                "text-anchor": "middle",
                "fill": "#54217e",
            },
            arrow,
        )

    if show_solution:
        solution_group = _add(
            root,
            "g",
            {
                "data-type": "solution-overlay",
                "fill": "none",
                "stroke": "#d12a8a",
                "stroke-width": "0.8",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            },
        )
        for start, end in _route_segments(blueprint, floor):
            x1, y1 = _point(start)
            x2, y2 = _point(end)
            _add(
                solution_group,
                "line",
                {
                    "x1": str(x1),
                    "y1": str(y1),
                    "x2": str(x2),
                    "y2": str(y2),
                    "data-type": "solution-edge",
                    "data-floor": str(floor),
                    "data-from-cell": _cell_text(start),
                    "data-to-cell": _cell_text(end),
                },
            )

        route_cells = floor_data["route_cells"]
        for cell in route_cells:
            x, z = _point(cell)
            _add(
                solution_group,
                "circle",
                {
                    "cx": str(x),
                    "cy": str(z),
                    "r": "0.55",
                    "fill": "#d12a8a",
                    "stroke": "#ffffff",
                    "stroke-width": "0.18",
                    "data-type": "solution-cell",
                    "data-cell": _cell_text(cell),
                },
            )

        route_transition_ids = set()
        for index in range(1, len(blueprint["solution_route"])):
            previous = blueprint["solution_route"][index - 1]
            current = blueprint["solution_route"][index]
            incoming = current.get("incoming") or {}
            if (
                incoming.get("kind") in ("elevator_up", "drop_down")
                and floor in (previous["floor"], current["floor"])
            ):
                if incoming.get("transition_id"):
                    route_transition_ids.add(incoming["transition_id"])
        for transition in floor_data["transitions"]:
            if transition["id"] in route_transition_ids:
                x, z = _point(transition["cell"])
                _add(
                    solution_group,
                    "circle",
                    {
                        "cx": str(x),
                        "cy": str(z),
                        "r": "1.35",
                        "fill": "none",
                        "stroke": "#d12a8a",
                        "stroke-width": "0.45",
                        "data-type": "solution-transition",
                        "data-id": transition["id"],
                    },
                )

    # Compact legend; all geometry remains at one SVG unit per Minecraft block.
    legend_y = max_z + 4
    legend = [
        ("#e8e8e8", "Floor footprint"),
        ("#ffffff", "Corridor cells"),
        ("#2457a6", "Walls"),
        ("#16833b", "Entrance / connectors"),
        ("#7438a5", "Elevator / drop"),
    ]
    legend_x = min_x
    for fill, label in legend:
        _rect(
            root,
            legend_x,
            legend_y - 1.1,
            1,
            1,
            "legend-swatch",
            fill=fill,
            stroke="#555555",
            stroke_width="0.12",
        )
        _add(
            root,
            "text",
            {
                "x": str(legend_x + 1.4),
                "y": str(legend_y - 0.2),
                "font-size": "1.25",
                "font-family": "sans-serif",
                "fill": "#222222",
            },
            label,
        )
        legend_x += 27

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def render_all_floor_svgs(blueprint, show_solution=False):
    """Return one SVG string per floor, keyed by floor number."""
    return {
        floor: render_floor_svg(blueprint, floor, show_solution=show_solution)
        for floor in sorted(blueprint["floors"])
    }


def write_all_floor_svgs(blueprint, output_dir, show_solution=False):
    """Write one SVG per floor and return the resulting paths."""
    from pathlib import Path

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "_solution" if show_solution else ""
    paths = {}
    for floor, svg in render_all_floor_svgs(
        blueprint, show_solution=show_solution
    ).items():
        path = directory / f"floor_{floor}{suffix}.svg"
        path.write_text(svg, encoding="utf-8")
        paths[floor] = path
    return paths

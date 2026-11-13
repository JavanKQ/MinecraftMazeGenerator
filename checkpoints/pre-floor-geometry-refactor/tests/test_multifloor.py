import xml.etree.ElementTree as ET

import networkx as nx

from exporter import COLORS, SCALE, export_three_floor_blueprints
from geometry import CORRIDOR_WIDTH, generate_grid
from multifloor import build_three_floor_maze, validate_route


def test_route_uses_decoys_and_finish_requires_its_elevator():
    graph, route, transitions = build_three_floor_maze(seed="MazeMulti")

    assert route
    assert route[0][0] == 1
    assert route[-1][0] == 3
    assert {node[0] for node in route} == {1, 2, 3}
    assert len(route) == len(set(route))
    assert validate_route(graph, route)
    level_changes = [
        current[0] - previous[0]
        for previous, current in zip(route, route[1:])
        if previous[0] != current[0]
    ]
    assert any(change > 0 for change in level_changes)
    assert any(change < 0 for change in level_changes)
    assert len(level_changes) >= 6
    assert all(
        sum(node[0] == floor for node in route) > 1
        for floor in range(1, 4)
    )
    drops = [transition for transition in transitions if transition["kind"] == "drop_down"]
    two_floor_transitions = [
        transition
        for transition in transitions
        if abs(transition["to"][0] - transition["from"][0]) == 2
    ]
    assert all(graph.has_edge(transition["from"], transition["to"]) for transition in transitions)
    route_edges = set(zip(route, route[1:]))
    assert all(
        (transition["from"], transition["to"]) in route_edges
        for transition in transitions
        if not transition["decoy"]
    )
    assert all(
        (transition["from"], transition["to"]) not in route_edges
        for transition in transitions
        if transition["decoy"]
    )
    assert sum(transition["decoy"] for transition in transitions) >= 2
    assert len(drops) >= 3
    assert {transition["kind"] for transition in two_floor_transitions} == {
        "elevator_up",
        "drop_down",
    }
    assert all(
        transition["optional"] and transition["decoy"]
        for transition in two_floor_transitions
    )

    finish_access = [
        transition for transition in transitions if transition.get("finish_access")
    ]
    assert len(finish_access) == 1
    graph_without_finish_elevator = graph.copy()
    graph_without_finish_elevator.remove_edge(
        finish_access[0]["from"],
        finish_access[0]["to"],
    )
    assert not nx.has_path(
        graph_without_finish_elevator,
        route[0],
        route[-1],
    )


def test_exports_one_svg_per_floor_with_transitions_and_solution(tmp_path):
    cells, _ = generate_grid()
    graph, route, transitions = build_three_floor_maze(seed="MazeMulti")

    output_paths = export_three_floor_blueprints(
        cells,
        graph,
        route,
        transitions,
        seed="MazeMulti",
        output_directory=tmp_path,
    )

    assert len(output_paths) == 3
    for floor, output_path in enumerate(output_paths, start=1):
        root = ET.parse(output_path).getroot()
        assert root.find("{http://www.w3.org/2000/svg}title").text.startswith(
            f"Minecraft Maze - Floor {floor}"
        )
        assert "decoy routes" in "".join(root.itertext())
        text_elements = root.findall(".//{http://www.w3.org/2000/svg}text")
        legend_labels = {
            "Unusable",
            "Floor",
            "Entrance",
            "Walls",
            "Elevator up 1 floor",
            "Elevator up 2 floors",
            "Drop down 1 floor",
            "Drop down 2 floors",
            "Finish",
            "Solution route",
        }
        legend_y = [
            float(element.attrib["y"])
            for element in text_elements
            if element.text in legend_labels
        ]
        note_y = [
            float(element.attrib["y"])
            for element in text_elements
            if element.text
            and element.text not in legend_labels
            and element.text.startswith(
                (
                    "Transitions:",
                    "E1:",
                    "E2:",
                    "E3:",
                    "E4:",
                    "E5:",
                    "D1:",
                    "D2:",
                    "D3:",
                    "Solution:",
                )
            )
        ]
        assert note_y and min(note_y) >= max(legend_y) + 18
        assert any(
            element.attrib.get("stroke") == COLORS["route"]
            for element in root.findall(".//{http://www.w3.org/2000/svg}rect")
        )

    combined_text = " ".join(
        "".join(ET.parse(path).getroot().itertext()) for path in output_paths
    )
    assert "only elevator access to the finish area" in combined_text
    assert "decoy elevator" in combined_text
    assert "decoy drop" in combined_text
    assert "elevator up 2 floors" in combined_text
    assert "drop 2 floors" in combined_text
    assert "Elevator up 1 floor" in combined_text
    assert "Elevator up 2 floors" in combined_text
    assert "Drop down 1 floor" in combined_text
    assert "Drop down 2 floors" in combined_text

    transition_rects = [
        element
        for output_path in output_paths
        for element in ET.parse(output_path).getroot().findall(
            ".//{http://www.w3.org/2000/svg}rect"
        )
        if element.attrib.get("fill") in (
            COLORS["elevator_1"],
            COLORS["elevator_2"],
            COLORS["drop_1"],
            COLORS["drop_2"],
        )
        and int(element.attrib.get("width", "0")) == CORRIDOR_WIDTH * SCALE
        and int(element.attrib.get("height", "0")) == CORRIDOR_WIDTH * SCALE
    ]
    assert transition_rects

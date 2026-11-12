from multifloor import build_three_floor_maze, validate_route


def test_three_floor_route_is_valid_and_reaches_floor_three():
    graph, route, transitions = build_three_floor_maze(seed="MazeMulti")

    assert route
    assert route[0][0] == 1
    assert route[-1][0] == 3
    assert any(node[0] != route[0][0] for node in route[1:])
    assert validate_route(graph, route)
    assert transitions

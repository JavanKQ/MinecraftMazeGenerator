from exporter import export_three_floor_blueprints
from generator import calculate_statistics, find_solution_path
from geometry import (
    CORRIDOR_WIDTH,
    ENTRANCE,
    FINISH,
    count_floor_blocks,
    generate_grid,
    nearest_endpoint_cells,
)
from multifloor import build_three_floor_maze, validate_route

SEED = "Maze13"


def main():
    cells, connections = generate_grid()
    multi_graph, multi_route, multi_transitions = build_three_floor_maze(SEED)
    opened_edges = {
        tuple(sorted((cell_a, cell_b)))
        for (floor_a, cell_a), (floor_b, cell_b) in multi_graph.edges
        if floor_a == floor_b == 1
    }
    possible_edges = sum(len(neighbors) for neighbors in connections.values()) // 2
    path = find_solution_path(
        connections,
        opened_edges,
        {sorted(nearest_endpoint_cells(cells, ENTRANCE))[-1]},
        nearest_endpoint_cells(cells, FINISH),
    )
    if not path:
        raise ValueError("The generated Floor 1 maze does not connect entrance to finish.")

    blueprint_paths = export_three_floor_blueprints(
        cells,
        multi_graph,
        multi_route,
        multi_transitions,
        SEED,
    )
    dead_ends, junctions = calculate_statistics(cells, opened_edges)

    floor_blocks = count_floor_blocks()
    corridor_blocks = len(cells) * CORRIDOR_WIDTH ** 2
    elevator_count = sum(
        transition["kind"] == "elevator_up" for transition in multi_transitions
    )
    drop_count = sum(
        transition["kind"] == "drop_down" for transition in multi_transitions
    )
    decoy_count = sum(
        transition.get("decoy", False) for transition in multi_transitions
    )
    two_floor_count = sum(
        abs(transition["to"][0] - transition["from"][0]) == 2
        for transition in multi_transitions
    )

    print()
    print("MINECRAFT MAZE GENERATOR")
    print("=" * 40)
    print(f"Random seed:           {SEED}")
    print(f"Floor blocks:          {floor_blocks:,}")
    print(f"Valid corridor cells:  {len(cells):,}")
    print()
    print("MAZE GENERATION")
    print("-" * 40)
    print("Carving algorithm:     NetworkX randomized Kruskal")
    print("Maze type:             Perfect floor trees with a gated Floor 3 finish")
    print(f"Possible connections:  {possible_edges:,}")
    print(f"Passages:              {len(opened_edges):,}")
    print()
    print("MAZE CHARACTERISTICS")
    print("-" * 40)
    print(f"Floor 1 shortest route: {len(path) - 1:,} cell steps")
    print(f"Dead ends:             {dead_ends:,}")
    print(f"Junctions:             {junctions:,}")
    print(f"Corridor coverage:     {corridor_blocks / floor_blocks * 100:.1f}%")
    print()
    print("Floor maps saved:")
    for blueprint_path in blueprint_paths:
        print(f"  {blueprint_path}")
    print(
        f"Transitions: {elevator_count} elevators, {drop_count} drops, "
        f"{decoy_count} decoys, {two_floor_count} two-floor moves | "
        "footprint: 3x3 blocks each"
    )
    floor_changes = sum(
        previous[0] != current[0]
        for previous, current in zip(multi_route, multi_route[1:])
    )
    no_backtracking = len(multi_route) == len(set(multi_route))
    print(
        f"Three-floor route:    {len(multi_route) - 1:,} steps | "
        f"valid={validate_route(multi_graph, multi_route)} | "
        f"floor changes={floor_changes} | no backtracking={no_backtracking}"
    )
    print("Maze successfully generated.")


if __name__ == "__main__":
    main()
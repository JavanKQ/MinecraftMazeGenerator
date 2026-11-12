from exporter import export_blueprint
from generator import calculate_statistics, generate_floor_maze
from geometry import (
    CORRIDOR_WIDTH,
    ENTRANCE,
    FINISH,
    count_floor_blocks,
    generate_grid,
)
from multifloor import build_three_floor_maze, validate_route

SEED = "Maze11"


def main():
    cells, connections = generate_grid()
    opened_edges, possible_edges, path = generate_floor_maze(
        cells,
        connections,
        ENTRANCE,
        FINISH,
        SEED,
    )
    blueprint_path = export_blueprint(cells, opened_edges, SEED)
    dead_ends, junctions = calculate_statistics(cells, opened_edges)

    floor_blocks = count_floor_blocks()
    corridor_blocks = len(cells) * CORRIDOR_WIDTH ** 2

    multi_graph, multi_route, multi_transitions = build_three_floor_maze(SEED)
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
    print("Maze type:             Perfect (one route between every cell pair)")
    print(f"Possible connections:  {possible_edges:,}")
    print(f"Passages:              {len(opened_edges):,}")
    print()
    print("MAZE CHARACTERISTICS")
    print("-" * 40)
    print(f"Shortest route:        {len(path) - 1:,} cell steps")
    print(f"Dead ends:             {dead_ends:,}")
    print(f"Junctions:             {junctions:,}")
    print(f"Corridor coverage:     {corridor_blocks / floor_blocks * 100:.1f}%")
    print()
    print(f"Blueprint saved:      {blueprint_path}")
    print(
        f"Three-floor route:    {len(multi_route) - 1:,} steps | valid={validate_route(multi_graph, multi_route)} | transitions={len(multi_transitions)}"
    )
    print("Maze successfully generated.")


if __name__ == "__main__":
    main()
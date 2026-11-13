from __future__ import annotations

import argparse
from pathlib import Path

from multifloor_v2 import build_multifloor_maze
from physical_blueprint_v2 import build_physical_blueprint
from svg_renderer_v2 import write_all_floor_svgs


def main():
    parser = argparse.ArgumentParser(
        description="Generate normal and solution-overlay SVG maze blueprints."
    )
    parser.add_argument("--seed", default="Maze1", help="Reproducible maze seed.")
    parser.add_argument(
        "--loop-percentage",
        type=int,
        default=12,
        help="Percentage of extra horizontal passages to add.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output") / "blueprints",
        help="Directory in which the two SVG sets will be written.",
    )
    args = parser.parse_args()

    floor_mazes, graph, route, transitions = build_multifloor_maze(
        seed=args.seed,
        loop_percentage=args.loop_percentage,
    )
    blueprint = build_physical_blueprint(
        floor_mazes,
        graph,
        route,
        transitions,
    )

    normal_paths = write_all_floor_svgs(
        blueprint,
        args.output_dir / "normal",
    )
    solution_paths = write_all_floor_svgs(
        blueprint,
        args.output_dir / "solution",
        show_solution=True,
    )

    print(f"Generated SVG blueprints using seed: {args.seed}")
    print("Normal views:")
    for path in normal_paths.values():
        print(f"  {path}")
    print("Solution overlays:")
    for path in solution_paths.values():
        print(f"  {path}")


if __name__ == "__main__":
    main()

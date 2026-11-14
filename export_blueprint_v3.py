"""Generate floor-by-floor SVG blueprints from the v3 global maze layout."""

from __future__ import annotations

import argparse
from pathlib import Path

from physical_blueprint_v3 import build_physical_blueprint_v3
from physical_layout_v3 import build_physical_layout
from svg_renderer_v2 import write_all_floor_svgs


def main():
    parser = argparse.ArgumentParser(
        description="Generate normal and solution-overlay SVG blueprints from v3."
    )
    parser.add_argument("--seed", default="stress-0001", help="Reproducible maze seed.")
    parser.add_argument(
        "--loop-percentage",
        type=int,
        default=12,
        help="Percentage of extra horizontal passages to add.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=250,
        help="Maximum randomized physical-layout attempts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output") / "blueprints_v3",
        help="Directory in which the two SVG sets will be written.",
    )
    args = parser.parse_args()

    layout = build_physical_layout(
        seed=args.seed,
        loop_percentage=args.loop_percentage,
        max_attempts=args.max_attempts,
    )
    blueprint = build_physical_blueprint_v3(layout)

    normal_paths = write_all_floor_svgs(
        blueprint,
        args.output_dir / "normal",
    )
    solution_paths = write_all_floor_svgs(
        blueprint,
        args.output_dir / "solution",
        show_solution=True,
    )

    print(f"Generated v3 SVG blueprints using seed: {args.seed}")
    print(f"Successful generation attempt: {layout['attempt']}")
    print(
        "Minimum vertical journeys: "
        f"{layout['validation']['navigation']['minimum_vertical_journeys']}"
    )
    print(f"Physical transition areas: {len(layout['transition_areas'])}")
    print("Normal views:")
    for path in normal_paths.values():
        print(f"  {path}")
    print("Solution overlays:")
    for path in solution_paths.values():
        print(f"  {path}")


if __name__ == "__main__":
    main()

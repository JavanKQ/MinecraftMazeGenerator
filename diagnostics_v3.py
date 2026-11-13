"""Repeatable diagnostics for randomized physical maze v3 layouts.

This module is intentionally separate from the normal unit-test suite. Run it
as a script to stress-test multiple deterministic seeds without making every
test run take several minutes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from statistics import mean, median

from geometry_v2 import FLOORS
from physical_layout_v3 import build_physical_layout


def summarize_layout(layout: dict) -> dict:
    """Extract compact generation, partition, transition, and loop metrics."""
    region_sizes = {
        floor: {
            region_id: len(cells)
            for region_id, cells in regions.items()
        }
        for floor, regions in layout["region_cells"].items()
    }

    loop_metrics = {}
    for floor, maze in layout["floor_mazes"].items():
        tree_edges = sum(
            max(0, len(cells) - 1)
            for cells in layout["region_cells"][floor].values()
        )
        opened_edges = len(maze["opened_edges"])
        loop_edges = opened_edges - tree_edges
        loop_metrics[floor] = {
            "tree_edges": tree_edges,
            "loop_edges": loop_edges,
            "opened_edges": opened_edges,
            "possible_edges": maze["possible_edges"],
            # The generator targets loops as a percentage of tree edges.
            "loop_rate_percent": (
                round(loop_edges / tree_edges * 100, 2)
                if tree_edges
                else 0.0
            ),
        }

    transition_pairs = Counter(
        f'{area.journeys[0][0]}->{area.journeys[0][1]}'
        for area in layout["transition_areas"]
    )

    return {
        "seed": layout["seed"],
        "attempts": layout["attempt"],
        "valid": layout["validation"]["valid"],
        "region_floors": list(layout["region_plan"]["region_floors"]),
        "region_sizes": region_sizes,
        "transition_pair_counts": dict(sorted(transition_pairs.items())),
        "loop_metrics": loop_metrics,
        "navigation": {
            "strongly_connected": layout["validation"]["navigation"]["strongly_connected"],
            "minimum_vertical_journeys": layout["validation"]["navigation"][
                "minimum_vertical_journeys"
            ],
            "transition_area_count": layout["validation"]["navigation"][
                "transition_area_count"
            ],
        },
    }


def run_stress_test(
    seed_count: int = 5,
    seed_prefix: str = "stress",
    loop_percentage: int = 12,
    max_attempts: int = 250,
) -> dict:
    """Generate and summarize a deterministic sequence of independent seeds.

    A failed seed is recorded and the remaining seeds are still attempted.
    The exception text is retained so failures are visible and diagnosable.
    """
    if seed_count < 1:
        raise ValueError("seed_count must be at least 1.")
    if not seed_prefix:
        raise ValueError("seed_prefix must not be empty.")
    if not 0 <= loop_percentage <= 100:
        raise ValueError("loop_percentage must be between 0 and 100.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    results = []
    failures = []
    for index in range(1, seed_count + 1):
        seed = f"{seed_prefix}-{index:04d}"
        try:
            layout = build_physical_layout(
                seed=seed,
                loop_percentage=loop_percentage,
                max_attempts=max_attempts,
            )
            results.append(summarize_layout(layout))
        except Exception as error:
            failures.append({
                "seed": seed,
                "error": f"{type(error).__name__}: {error}",
            })

    attempts = [item["attempts"] for item in results]
    all_region_sizes = [
        size
        for result in results
        for floor_sizes in result["region_sizes"].values()
        for size in floor_sizes.values()
    ]

    transition_totals = Counter()
    for result in results:
        transition_totals.update(result["transition_pair_counts"])

    loop_rates = {
        floor: [
            result["loop_metrics"][floor]["loop_rate_percent"]
            for result in results
        ]
        for floor in FLOORS
    }

    return {
        "configuration": {
            "requested_seeds": seed_count,
            "seed_prefix": seed_prefix,
            "loop_percentage": loop_percentage,
            "max_attempts": max_attempts,
        },
        "successful_count": len(results),
        "failed_count": len(failures),
        "attempt_statistics": {
            "minimum": min(attempts) if attempts else None,
            "median": median(attempts) if attempts else None,
            "mean": round(mean(attempts), 2) if attempts else None,
            "maximum": max(attempts) if attempts else None,
        },
        "region_size_statistics": {
            "minimum": min(all_region_sizes) if all_region_sizes else None,
            "median": median(all_region_sizes) if all_region_sizes else None,
            "mean": round(mean(all_region_sizes), 2) if all_region_sizes else None,
            "maximum": max(all_region_sizes) if all_region_sizes else None,
        },
        "loop_rate_by_floor": {
            floor: {
                "minimum": min(values) if values else None,
                "mean": round(mean(values), 2) if values else None,
                "maximum": max(values) if values else None,
            }
            for floor, values in loop_rates.items()
        },
        "transition_pair_totals": dict(sorted(transition_totals.items())),
        "results": results,
        "failures": failures,
    }


def print_report(report: dict) -> None:
    """Print a readable console report from run_stress_test()."""
    config = report["configuration"]
    attempts = report["attempt_statistics"]
    sizes = report["region_size_statistics"]

    print("Minecraft Maze v3 — physical layout stress test")
    print("=" * 52)
    print(
        f'Seeds: {report["successful_count"]} passed, '
        f'{report["failed_count"]} failed, '
        f'{config["requested_seeds"]} requested'
    )
    print(
        f'Loop target: {config["loop_percentage"]}% | '
        f'Max attempts per seed: {config["max_attempts"]}'
    )
    print(
        "Attempts: "
        f'min={attempts["minimum"]}, median={attempts["median"]}, '
        f'mean={attempts["mean"]}, max={attempts["maximum"]}'
    )
    print(
        "Region sizes (cells): "
        f'min={sizes["minimum"]}, median={sizes["median"]}, '
        f'mean={sizes["mean"]}, max={sizes["maximum"]}'
    )

    print("\nPer-seed results:")
    for result in report["results"]:
        floor_summary = ", ".join(
            f'F{floor}:{min(sizes.values())}-{max(sizes.values())}'
            for floor, sizes in result["region_sizes"].items()
        )
        print(
            f'  {result["seed"]}: attempt {result["attempts"]}, '
            f'{result["navigation"]["transition_area_count"]} areas, '
            f'{result["navigation"]["minimum_vertical_journeys"]} journeys, '
            f'{floor_summary}'
        )

    print("\nTransition connections (source floor -> destination floor):")
    for pair, count in report["transition_pair_totals"].items():
        print(f"  {pair}: {count}")

    print("\nLoop rates by floor (actual loops / spanning-tree edges):")
    for floor, metrics in report["loop_rate_by_floor"].items():
        print(
            f'  Floor {floor}: min={metrics["minimum"]}%, '
            f'mean={metrics["mean"]}%, max={metrics["maximum"]}%'
        )

    if report["failures"]:
        print("\nFAILED SEEDS:")
        for failure in report["failures"]:
            print(f'  {failure["seed"]}: {failure["error"]}')
    else:
        print("\nNo generation failures.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stress-test randomized physical maze v3 layouts."
    )
    parser.add_argument(
        "--seed-count", type=int, default=5,
        help="Number of deterministic seeds to generate (default: 5).",
    )
    parser.add_argument(
        "--seed-prefix", default="stress",
        help="Prefix used to create deterministic seed names.",
    )
    parser.add_argument(
        "--loop-percentage", type=int, default=12,
        help="Extra corridor loops as a percentage of spanning-tree edges.",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=250,
        help="Maximum generation attempts allowed for each seed.",
    )
    args = parser.parse_args()

    report = run_stress_test(
        seed_count=args.seed_count,
        seed_prefix=args.seed_prefix,
        loop_percentage=args.loop_percentage,
        max_attempts=args.max_attempts,
    )
    print_report(report)


if __name__ == "__main__":
    main()

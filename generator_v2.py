from collections import deque
import random
import math

import networkx as nx

from geometry_v2 import FLOORS, generate_grid


def edge_key(a, b):
    return tuple(sorted((a, b)))


DEFAULT_LOOP_PERCENTAGE = 12


def carve_maze(cells, connections, seed, loop_percentage=DEFAULT_LOOP_PERCENTAGE):
    """Carve a randomized spanning tree, then add the configured extra loops."""
    if not 0 <= loop_percentage <= 100:
        raise ValueError("loop_percentage must be between 0 and 100.")
    graph = nx.Graph()
    graph.add_nodes_from(sorted(cells))
    graph_edges = sorted({
        edge_key(cell, neighbor)
        for cell, neighbors in connections.items()
        for neighbor in neighbors
    })
    graph.add_edges_from(graph_edges)

    if not cells or not nx.is_connected(graph):
        raise ValueError("The floor must produce one connected cell graph.")

    rng = random.Random(seed)
    for a, b in graph_edges:
        graph[a][b]["weight"] = rng.random()

    tree = nx.minimum_spanning_tree(
        graph,
        algorithm="kruskal",
        weight="weight",
    )

    if not nx.is_tree(tree):
        raise ValueError("Maze carving did not produce a spanning tree.")

    opened_edges = {edge_key(a, b) for a, b in tree.edges}
    closed_edges = sorted(
        edge_key(a, b)
        for a, b in graph.edges
        if edge_key(a, b) not in opened_edges
    )

    # Extra loops are measured against the spanning-tree passage count.
    extra_loop_count = min(
        len(closed_edges),
        math.floor(len(opened_edges) * loop_percentage / 100 + 0.5),
    )
    opened_edges.update(rng.sample(closed_edges, extra_loop_count))

    return opened_edges, graph.number_of_edges()


def find_solution_path(connections, opened_edges, starts, goals):
    """Find a path through carved passages between any start and goal cells."""
    parents = {cell: None for cell in starts}
    pending = deque(sorted(starts))
    goal = None

    while pending:
        current = pending.popleft()
        if current in goals:
            goal = current
            break

        for neighbor in connections[current]:
            if edge_key(current, neighbor) in opened_edges and neighbor not in parents:
                parents[neighbor] = current
                pending.append(neighbor)

    if goal is None:
        return []

    path = []
    current = goal
    while current is not None:
        path.append(current)
        current = parents[current]

    return list(reversed(path))


def calculate_statistics(cells, opened_edges):
    degrees = {cell: 0 for cell in cells}
    for a, b in opened_edges:
        degrees[a] += 1
        degrees[b] += 1

    dead_ends = sum(degree == 1 for degree in degrees.values())
    junctions = sum(degree >= 3 for degree in degrees.values())
    return {
        "dead_ends": dead_ends,
        "junctions": junctions,
        "cells": len(cells),
        "passages": len(opened_edges),
    }


def generate_floor_mazes(seed, loop_percentage=DEFAULT_LOOP_PERCENTAGE):
    """Generate an independent horizontal maze tree for every defined floor."""
    mazes = {}

    for floor in FLOORS:
        cells, connections = generate_grid(floor)
        floor_seed = f"{seed}:floor:{floor}"
        opened_edges, possible_edges = carve_maze(
            cells,
            connections,
            floor_seed,
            loop_percentage=loop_percentage,
        )

        mazes[floor] = {
            "cells": cells,
            "connections": connections,
            "opened_edges": opened_edges,
            "possible_edges": possible_edges,
            "loop_percentage": loop_percentage,
            "statistics": calculate_statistics(cells, opened_edges),
            "seed": floor_seed,
        }

    return mazes

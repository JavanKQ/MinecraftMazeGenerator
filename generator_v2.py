from collections import deque
import random

import networkx as nx

from geometry_v2 import FLOORS, generate_grid


def edge_key(a, b):
    return tuple(sorted((a, b)))


def carve_maze(cells, connections, seed):
    """Carve a randomized spanning tree through one floor's valid cell graph."""
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


def generate_floor_mazes(seed):
    """Generate an independent horizontal maze tree for every defined floor."""
    mazes = {}

    for floor in FLOORS:
        cells, connections = generate_grid(floor)
        floor_seed = f"{seed}:floor:{floor}"
        opened_edges, possible_edges = carve_maze(
            cells,
            connections,
            floor_seed,
        )

        mazes[floor] = {
            "cells": cells,
            "connections": connections,
            "opened_edges": opened_edges,
            "possible_edges": possible_edges,
            "statistics": calculate_statistics(cells, opened_edges),
            "seed": floor_seed,
        }

    return mazes

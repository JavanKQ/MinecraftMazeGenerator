from collections import deque
import random

import networkx as nx

from geometry import nearest_endpoint_cells


def edge_key(a, b):
	return tuple(sorted((a, b)))


def carve_maze(cells, connections, seed, forced_edges=()):
	"""Generate a randomized Kruskal spanning tree of the valid cell graph."""
	graph = nx.Graph()
	graph.add_nodes_from(sorted(cells))
	graph_edges = sorted({
		edge_key(cell, neighbor)
		for cell, neighbors in connections.items()
		for neighbor in neighbors
	})
	graph.add_edges_from(graph_edges)

	if not cells or not nx.is_connected(graph):
		raise ValueError("The irregular floor must produce one connected cell graph.")

	rng = random.Random(seed)
	for a, b in graph_edges:
		graph[a][b]["weight"] = rng.random()

	tree = nx.minimum_spanning_tree(graph, algorithm="kruskal", weight="weight")
	required_edges = {edge_key(a, b) for a, b in forced_edges}

	for a, b in sorted(required_edges):
		if not graph.has_edge(a, b):
			raise ValueError(f"Required passage {a} -> {b} is not valid.")
		if tree.has_edge(a, b):
			continue

		tree_path = nx.shortest_path(tree, a, b)
		replaceable_edges = [
			edge_key(left, right)
			for left, right in zip(tree_path, tree_path[1:])
			if edge_key(left, right) not in required_edges
		]
		if not replaceable_edges:
			raise ValueError("Required passages cannot all fit in one spanning tree.")

		tree.remove_edge(*rng.choice(replaceable_edges))
		tree.add_edge(a, b)

	if not nx.is_tree(tree):
		raise ValueError("Maze carving did not produce a spanning tree.")

	opened_edges = {edge_key(a, b) for a, b in tree.edges}
	return opened_edges, graph.number_of_edges()


def find_solution_path(connections, opened_edges, starts, goals):
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


def generate_floor_maze(cells, connections, entrance, finish, seed):
	entrance_cells = sorted(nearest_endpoint_cells(cells, entrance))
	finish_cells = nearest_endpoint_cells(cells, finish)
	forced_edges = tuple(zip(entrance_cells, entrance_cells[1:]))
	opened_edges, possible_edges = carve_maze(
		cells,
		connections,
		seed,
		forced_edges,
	)
	path = find_solution_path(
		connections,
		opened_edges,
		{entrance_cells[-1]},
		finish_cells,
	)
	if not path:
		raise ValueError("The spanning tree does not connect entrance to finish.")

	return opened_edges, possible_edges, path


def calculate_statistics(cells, opened_edges):
	degrees = {cell: 0 for cell in cells}
	for a, b in opened_edges:
		degrees[a] += 1
		degrees[b] += 1

	dead_ends = sum(degree == 1 for degree in degrees.values())
	junctions = sum(degree >= 3 for degree in degrees.values())
	return dead_ends, junctions

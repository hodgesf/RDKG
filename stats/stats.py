#!/usr/bin/env python3

import json
from collections import Counter


def compute_stats(nodes_file, edges_file, out_file):

    node_count = 0
    edge_count = 0

    node_category_counts = Counter()
    edge_predicate_counts = Counter()
    edge_category_counts = Counter()

    in_degree = Counter()
    out_degree = Counter()

    node_ids = set()

    # --- NODES ---
    with open(nodes_file) as f:
        for line in f:
            node = json.loads(line)
            node_count += 1

            node_ids.add(node["id"])

            for cat in node.get("category", []):
                node_category_counts[cat] += 1

    # --- EDGES ---
    with open(edges_file) as f:
        for line in f:
            edge = json.loads(line)
            edge_count += 1

            edge_predicate_counts[edge["predicate"]] += 1

            for cat in edge.get("category", []):
                edge_category_counts[cat] += 1

            s = edge["subject"]
            o = edge["object"]

            out_degree[s] += 1
            in_degree[o] += 1

    # --- DEGREE ---
    degrees = []
    for nid in node_ids:
        deg = in_degree[nid] + out_degree[nid]
        degrees.append(deg)

    degrees.sort()

    def pct(p):
        return degrees[int(len(degrees) * p)] if degrees else 0

    # --- WRITE OUTPUT ---
    with open(out_file, "w") as out:

        out.write("=== BASIC ===\n")
        out.write(f"Nodes: {node_count}\n")
        out.write(f"Edges: {edge_count}\n\n")

        out.write("=== NODE CATEGORIES ===\n")
        for k, v in node_category_counts.most_common(20):
            out.write(f"{k} {v}\n")

        out.write("\n=== EDGE PREDICATES ===\n")
        for k, v in edge_predicate_counts.most_common(20):
            out.write(f"{k} {v}\n")

        out.write("\n=== EDGE CATEGORIES ===\n")
        for k, v in edge_category_counts.most_common(20):
            out.write(f"{k} {v}\n")

        out.write("\n=== DEGREE ===\n")
        out.write(f"Mean: {sum(degrees)/len(degrees) if degrees else 0}\n")
        out.write(f"Median: {pct(0.5)}\n")
        out.write(f"90th: {pct(0.9)}\n")
        out.write(f"99th: {pct(0.99)}\n")
        out.write(f"Max: {max(degrees) if degrees else 0}\n")

        connected_nodes = len([d for d in degrees if d > 0])
        out.write("\n=== CONNECTIVITY ===\n")
        out.write(f"Connected nodes: {connected_nodes}\n")
        out.write(f"Isolated nodes: {node_count - connected_nodes}\n")


# --- RUN BOTH ---
compute_stats("files/all_nodes.jsonl", "files/all_edges.jsonl", "stats_all.txt")
compute_stats("files/nodes_filtered.jsonl", "files/edges_filtered.jsonl", "stats_filtered.txt")

print("Done: stats_all.txt and stats_filtered.txt")
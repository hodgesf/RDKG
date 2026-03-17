#!/usr/bin/env python3

import json

EDGES_IN = "all_edges.jsonl"
NODES_IN = "all_nodes.jsonl"

EDGES_OUT = "edges_filtered.jsonl"
NODES_OUT = "nodes_filtered.jsonl"


kept_nodes = set()

# --- FILTER EDGES ---
with open(EDGES_IN) as fin, open(EDGES_OUT, "w") as fout:
    for line in fin:
        edge = json.loads(line)

        if edge.get("predicate") == "biolink:subclass_of":
            continue

        fout.write(json.dumps(edge) + "\n")

        kept_nodes.add(edge["subject"])
        kept_nodes.add(edge["object"])


# --- FILTER NODES ---
with open(NODES_IN) as fin, open(NODES_OUT, "w") as fout:
    for line in fin:
        node = json.loads(line)

        if node["id"] in kept_nodes:
            fout.write(json.dumps(node) + "\n")


print("Done")
print(f"Kept nodes: {len(kept_nodes)}")
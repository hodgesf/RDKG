#!/usr/bin/env python3
"""
merge_graphs.py

Merge multiple KG node/edge JSONL files into a single graph.

Features
• deduplicate nodes by CURIE
• merge node attributes
• remove duplicate edges
• filter orphan edges
• streaming processing for large graphs

Usage:

merge_graphs.py
    --nodes nodes1.jsonl nodes2.jsonl ...
    --edges edges1.jsonl edges2.jsonl ...
    --outputNodes merged_nodes.jsonl
    --outputEdges merged_edges.jsonl
    [--orphanEdges orphan_edges.jsonl]
"""

import argparse
import sys
import kg2_util


def make_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--nodes", nargs="+", required=True)
    parser.add_argument("--edges", nargs="+", required=True)

    parser.add_argument("--outputNodes", required=True)
    parser.add_argument("--outputEdges", required=True)

    parser.add_argument("--orphanEdges", default=None)

    parser.add_argument("--test", action="store_true", default=False)

    return parser


def merge_nodes(node_files, nodes_output):

    nodes = {}

    for file in node_files:

        kg2_util.log_message("reading nodes", ontology_name=file, output_stream=sys.stderr)

        read_info = kg2_util.start_read_jsonlines(file)
        node_iter = read_info[0]

        added = 0

        for node in node_iter:

            node_id = node["id"]

            if node_id not in nodes:
                nodes[node_id] = node
                added += 1
            else:
                nodes[node_id] = kg2_util.merge_two_dicts(nodes[node_id], node)

        kg2_util.end_read_jsonlines(read_info)

        kg2_util.log_message(
            f"nodes added: {added}",
            ontology_name=file,
            output_stream=sys.stderr
        )

    node_set = set(nodes.keys())

    for node in nodes.values():
        nodes_output.write(node)

    return node_set


def merge_edges(edge_files, node_set, edges_output, orphan_output=None):

    edge_keys = set()

    added = 0
    orphan = 0

    for file in edge_files:

        kg2_util.log_message("reading edges", ontology_name=file, output_stream=sys.stderr)

        read_info = kg2_util.start_read_jsonlines(file)
        edge_iter = read_info[0]

        for edge in edge_iter:

            subject = edge["subject"]
            obj = edge["object"]

            if subject not in node_set or obj not in node_set:

                orphan += 1

                if orphan_output:
                    orphan_output.write(edge)

                continue

            edge_id = edge["id"]

            if edge_id in edge_keys:
                continue

            edge_keys.add(edge_id)

            edges_output.write(edge)

            added += 1

        kg2_util.end_read_jsonlines(read_info)

        kg2_util.log_message(
            f"edges added: {added}",
            ontology_name=file,
            output_stream=sys.stderr
        )

    return added, orphan


def main():

    args = make_parser().parse_args()

    nodes_info, edges_info = kg2_util.create_kg2_jsonlines(args.test)

    nodes_output = nodes_info[0]
    edges_output = edges_info[0]

    orphan_output = None
    orphan_info = None

    if args.orphanEdges:
        orphan_info = kg2_util.create_single_jsonlines(args.test)
        orphan_output = orphan_info[0]

    print("Merging nodes")

    node_set = merge_nodes(args.nodes, nodes_output)

    print("Merging edges")

    added, orphan = merge_edges(
        args.edges,
        node_set,
        edges_output,
        orphan_output
    )

    print("Edges added:", added)
    print("Orphan edges:", orphan)

    kg2_util.close_kg2_jsonlines(
        nodes_info,
        edges_info,
        args.outputNodes,
        args.outputEdges
    )

    if orphan_info:
        kg2_util.close_single_jsonlines(orphan_info, args.orphanEdges)

    print("Merge complete")


if __name__ == "__main__":
    main()
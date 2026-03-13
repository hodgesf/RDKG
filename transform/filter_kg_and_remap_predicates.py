#!/usr/bin/env python3
"""
filter_kg_and_remap_predicates.py

Normalize and simplify a combined KG by:

• remapping predicates
• inverting predicates when configured
• removing negated edges
• remapping knowledge sources → infores
• attaching knowledge_level and agent_type
• filtering blocked edges
• rebuilding edge IDs

Usage:

filter_kg_and_remap_predicates.py
    <predicate_remap_yaml>
    <infores_remap_yaml>
    <knowledge_level_agent_type_yaml>
    <edge_blocklist_yaml>
    <input_nodes_jsonl>
    <input_edges_jsonl>
    <output_nodes_jsonl>
    <output_edges_jsonl>
    <version_file>

Optional flags:

--test
--dropNegated
--dropSelfEdgesExcept predicate1,predicate2
"""

import argparse
import sys
import pprint
from datetime import datetime

import kg2_util


def make_arg_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("predicateRemapYaml")
    parser.add_argument("inforesRemapYaml")
    parser.add_argument("knowledgeLevelAgentTypeYaml")
    parser.add_argument("edgeBlocklistYaml")

    parser.add_argument("inputNodesFile")
    parser.add_argument("inputEdgesFile")

    parser.add_argument("outputNodesFile")
    parser.add_argument("outputEdgesFile")

    parser.add_argument("versionFile")

    parser.add_argument("--test", action="store_true", default=False)
    parser.add_argument("--dropNegated", action="store_true", default=False)
    parser.add_argument("--dropSelfEdgesExcept", default=None)

    return parser


def update_edge_id(edge_id,
                   qualified_predicate=None,
                   object_aspect_qualifier=None,
                   object_direction_qualifier=None):

    keys = edge_id.split("---")

    subject = keys[0]
    predicate = keys[1]
    object_node = keys[-2]
    knowledge_source = keys[-1]

    return (
        f"{subject}---{predicate}---"
        f"{qualified_predicate}---"
        f"{object_aspect_qualifier}---"
        f"{object_direction_qualifier}---"
        f"{object_node}---"
        f"{knowledge_source}"
    )


def load_edge_blocklist(edge_blocklist_yaml):

    blocklist = set()

    for edge in edge_blocklist_yaml:
        for subject in edge["subject_ids"]:
            for obj in edge["object_ids"]:
                blocklist.add((subject, edge["predicate"], obj))

    return blocklist


def process_nodes(input_nodes_file,
                  infores_map,
                  nodes_output):

    nodes = set()
    missing_sources = set()

    read_info = kg2_util.start_read_jsonlines(input_nodes_file)
    node_iter = read_info[0]

    count = 0

    for node in node_iter:

        count += 1
        if count % 1000000 == 0:
            print(f"Processing node {count}")

        node_id = node["id"]
        nodes.add(node_id)

        provided_by = node.get("provided_by")

        if provided_by is None:
            provided_by = node.get("knowledge_source")

        if provided_by is None:
            provided_by = []

        if isinstance(provided_by, str):
            provided_by = [provided_by]

        new_sources = []

        for source in provided_by:

            mapping = infores_map.get(source)

            if mapping is None:
                missing_sources.add(source)
            else:
                new_sources.append(mapping["infores_curie"])

        node["provided_by"] = new_sources

        nodes_output.write(node)

    kg2_util.end_read_jsonlines(read_info)

    if missing_sources:
        print(
            "ERROR: missing knowledge_source → infores mappings:",
            missing_sources,
            file=sys.stderr
        )
        sys.exit(1)

    print("Finished nodes", kg2_util.date())

    return nodes


def process_edges(input_edges_file,
                  nodes,
                  predicate_map,
                  infores_map,
                  klat_map,
                  edge_blocklist,
                  edges_output,
                  drop_negated,
                  drop_self_edges_except):

    missing_predicates = set()
    missing_sources = set()
    missing_klat = set()

    read_info = kg2_util.start_read_jsonlines(input_edges_file)
    edge_iter = read_info[0]

    count = 0

    print("Starting edges", kg2_util.date())

    for edge in edge_iter:

        count += 1
        if count % 1000000 == 0:
            print(f"Processing edge {count}")

        if drop_negated and edge.get("negated"):
            continue

        source_pred = edge.get("source_predicate") or edge.get("original_predicate")

        if source_pred not in predicate_map:
            missing_predicates.add(source_pred)
            command = {"operation": "keep"}
        else:
            command = predicate_map[source_pred]

        operation = command["operation"]

        if operation == "delete":
            continue

        invert = operation == "invert"

        core_pred = command.get("core_predicate", source_pred)
        qualified_pred = command.get("qualified_predicate")

        qualifiers = command.get("qualifiers", {})
        aspect = qualifiers.get("object_aspect")
        direction = qualifiers.get("object_direction")

        subject = edge["subject"]
        obj = edge["object"]

        if invert:
            subject, obj = obj, subject

        if drop_self_edges_except and subject == obj:
            if core_pred not in drop_self_edges_except:
                continue

        edge["subject"] = subject
        edge["object"] = obj
        edge["predicate"] = core_pred

        edge["qualified_predicate"] = qualified_pred
        edge["object_aspect_qualifier"] = aspect
        edge["object_direction_qualifier"] = direction

        edge["id"] = update_edge_id(
            edge["id"],
            qualified_pred,
            aspect,
            direction
        )

        source = edge.get("primary_knowledge_source") or edge.get("knowledge_source")

        mapping = infores_map.get(source)

        if mapping is None:
            missing_sources.add(source)
        else:
            edge["primary_knowledge_source"] = mapping["infores_curie"]

        klat = klat_map.get(edge.get("primary_knowledge_source"))

        if klat is None:
            missing_klat.add(edge.get("primary_knowledge_source"))
        else:
            edge["knowledge_level"] = klat["knowledge_level"]
            edge["agent_type"] = klat["agent_type"]

        triple = (subject, core_pred, obj)

        if triple in edge_blocklist:
            continue

        edges_output.write(edge)

    kg2_util.end_read_jsonlines(read_info)

    print("Finished edges", kg2_util.date())

    if missing_predicates:
        print("Missing predicate mappings:", missing_predicates, file=sys.stderr)

    if missing_sources:
        print("Missing infores mappings:", missing_sources, file=sys.stderr)

    if missing_klat:
        print("Missing knowledge level mappings:", missing_klat, file=sys.stderr)


def main():

    args = make_arg_parser().parse_args()

    predicate_map = kg2_util.safe_load_yaml_from_string(
        kg2_util.read_file_to_string(args.predicateRemapYaml)
    )

    infores_map = kg2_util.safe_load_yaml_from_string(
        kg2_util.read_file_to_string(args.inforesRemapYaml)
    )

    klat_map = kg2_util.safe_load_yaml_from_string(
        kg2_util.read_file_to_string(args.knowledgeLevelAgentTypeYaml)
    )

    blocklist_yaml = kg2_util.safe_load_yaml_from_string(
        kg2_util.read_file_to_string(args.edgeBlocklistYaml)
    )

    edge_blocklist = load_edge_blocklist(blocklist_yaml)

    nodes_info, edges_info = kg2_util.create_kg2_jsonlines(args.test)

    nodes_output = nodes_info[0]
    edges_output = edges_info[0]

    if args.dropSelfEdgesExcept:
        drop_set = set(args.dropSelfEdgesExcept.split(","))
    else:
        drop_set = None

    nodes = process_nodes(
        args.inputNodesFile,
        infores_map,
        nodes_output
    )

    process_edges(
        args.inputEdgesFile,
        nodes,
        predicate_map,
        infores_map,
        klat_map,
        edge_blocklist,
        edges_output,
        args.dropNegated,
        drop_set
    )

    version_line = open(args.versionFile).readline().strip()

    build_name = f"RTX-KG{version_line}"
    if args.test:
        build_name += "-TEST"

    update_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    build_node = kg2_util.make_node(
        kg2_util.CURIE_PREFIX_RTX + ":KG2",
        kg2_util.BASE_URL_RTX + "KG2",
        build_name,
        kg2_util.SOURCE_NODE_CATEGORY,
        update_date,
        kg2_util.CURIE_PREFIX_RTX + ":"
    )

    nodes_output.write(build_node)

    pprint.pprint({
        "version": build_name,
        "timestamp_utc": update_date
    })

    kg2_util.close_kg2_jsonlines(
        nodes_info,
        edges_info,
        args.outputNodesFile,
        args.outputEdgesFile
    )

    print("Completed", kg2_util.date())


if __name__ == "__main__":
    main()
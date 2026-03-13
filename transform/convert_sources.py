#!/usr/bin/env python3
"""
sources_jsonl_to_kg_jsonl.py

Convert non-ontology JSONL produced by source_parser.py into KG2 node/edge JSONL.

Usage:

sources_jsonl_to_kg_jsonl.py
    [--test]
    <input_jsonl>
    <curies_to_categories_yaml>
    <curies_to_urls_yaml>
    <output_nodes_jsonl>
    <output_edges_jsonl>
"""

import argparse
import json
import kg2_util


FILE_MAPPING = "file"
PREFIX_MAPPING = "prefix"


class SourceConverter:

    def __init__(self, curies_to_categories, curies_to_urls):

        self.NODE_CATEGORY_MAPPINGS = {}
        self.PREFIX_MAPPINGS = {}

        self.URI_MAP = {}
        self.URI_MAP_KEYS = []

        self.SEEN_NODES = set()

        self.load_category_mappings(curies_to_categories)
        self.load_uri_map(curies_to_urls)

    def load_category_mappings(self, path):

        data = kg2_util.safe_load_yaml_from_string(
            kg2_util.read_file_to_string(path)
        )

        for node, cat in data.get("term-mappings", {}).items():
            self.NODE_CATEGORY_MAPPINGS[node] = (cat, FILE_MAPPING)

        self.PREFIX_MAPPINGS.update(data.get("prefix-mappings", {}))

    def load_uri_map(self, path):

        data = kg2_util.safe_load_yaml_from_string(
            kg2_util.read_file_to_string(path)
        )

        for section in ["use_for_bidirectional_mapping", "use_for_contraction_only"]:
            for mapping in data.get(section, []):
                for prefix, iri in mapping.items():
                    self.URI_MAP[iri] = prefix

        self.URI_MAP_KEYS = sorted(self.URI_MAP.keys(), key=len, reverse=True)

    def match_prefix(self, iri):

        if iri is None:
            return None

        for url in self.URI_MAP_KEYS:
            if iri.startswith(url):
                return iri.replace(url, self.URI_MAP[url] + ":")

        if ":" in iri:
            return iri

        return None

    def categorize(self, curie):

        if curie in self.NODE_CATEGORY_MAPPINGS:
            return self.NODE_CATEGORY_MAPPINGS[curie][0]

        prefix = curie.split(":")[0]

        if prefix in self.PREFIX_MAPPINGS:
            return self.PREFIX_MAPPINGS[prefix]

        return kg2_util.BIOLINK_CATEGORY_NAMED_THING

    def create_node(self, node_id, nodes_output, source):

        if node_id in self.SEEN_NODES:
            return

        category = self.categorize(node_id)

        node = kg2_util.make_node(
            node_id,
            node_id,
            node_id,
            category,
            kg2_util.date(),
            source
        )

        nodes_output.write(node)

        self.SEEN_NODES.add(node_id)

    def process_record(self, record, nodes_output, edges_output):

        subject = self.match_prefix(record.get("subject"))
        predicate = record.get("predicate")
        obj = self.match_prefix(record.get("object"))

        source = record.get("source")

        if not subject or not obj or not predicate:
            return

        provided_by = f"infores:{source}" if source else None

        self.create_node(subject, nodes_output, provided_by)
        self.create_node(obj, nodes_output, provided_by)

        edge = kg2_util.make_edge(
            subject,
            obj,
            predicate,
            predicate.split(":")[-1] if ":" in predicate else predicate,
            provided_by,
            kg2_util.date()
        )

        edges_output.write(edge)


def get_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("--test", action="store_true", default=False)

    parser.add_argument("inputFile")
    parser.add_argument("curiesToCategories")
    parser.add_argument("curiesToUrls")
    parser.add_argument("outputNodes")
    parser.add_argument("outputEdges")

    return parser.parse_args()


def main():

    args = get_args()

    print("Start:", kg2_util.date())

    converter = SourceConverter(
        args.curiesToCategories,
        args.curiesToUrls
    )

    nodes_info, edges_info = kg2_util.create_kg2_jsonlines(args.test)

    nodes_output = nodes_info[0]
    edges_output = edges_info[0]

    with open(args.inputFile) as f:

        for line in f:

            record = json.loads(line)

            converter.process_record(
                record,
                nodes_output,
                edges_output
            )

    kg2_util.close_kg2_jsonlines(
        nodes_info,
        edges_info,
        args.outputNodes,
        args.outputEdges
    )

    print("Finish:", kg2_util.date())


if __name__ == "__main__":
    main()
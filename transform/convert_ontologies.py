#!/usr/bin/env python3
"""
ontologies_jsonl_to_kg_jsonl.py

Convert ontology JSONL output from owl_parser.py into KG2 node/edge JSONL.

Usage:
ontologies_jsonl_to_kg_jsonl.py
    [--test]
    <input_jsonl>
    <curies_to_categories_yaml>
    <curies_to_urls_yaml>
    <biolink_version>
    <output_nodes_jsonl>
    <output_edges_jsonl>
"""

import argparse
import json
import datetime
import kg2_util

TEXT_KEY = "ENTRY_TEXT"
RESOURCE_KEY = "rdf:resource"
ID_TAG = "rdf:about"

OWL_SOURCE_KEY = "owl_source"
OWL_SOURCE_NAME_KEY = "owl_source_name"

DESCRIPTION_DELIM = " // "
COMMENT_PREFIX = "COMMENTS: "

FILE_MAPPING = "file"
PREFIX_MAPPING = "prefix"
RECURSE_MAPPING = "recurse"


SYNONYM_KEYS = [
    "oboInOwl:hasExactSynonym",
    "oboInOwl:hasRelatedSynonym",
    "oboInOwl:hasBroadSynonym",
    "oboInOwl:hasNarrowSynonym",
    "go:hasExactSynonym",
    "go:hasSynonym",
    "go:hasRelatedSynonym",
    "go:hasBroadSynonym",
    "go:hasNarrowSynonym",
    "skos:prefLabel",
]


BASE_EDGE_TYPES = {
    "skos:exactMatch": RESOURCE_KEY,
    "skos:closeMatch": RESOURCE_KEY,
    "skos:broadMatch": RESOURCE_KEY,
    "skos:relatedMatch": RESOURCE_KEY,
    "skos:narrowMatch": RESOURCE_KEY,
    "oboInOwl:hasAlternativeId": TEXT_KEY,
    "oboInOwl:hasDbXref": TEXT_KEY,
    "oboInOwl:xref": TEXT_KEY,
}


class OntologyConverter:

    def __init__(self, curies_to_categories, curies_to_urls, biolink_version):

        self.CLASS_TO_SUPERCLASSES = {}
        self.SAVED_NODE_INFO = {}
        self.SOURCE_INFO = {}

        self.NODE_CATEGORY_MAPPINGS = {}
        self.PREFIX_MAPPINGS = {}

        self.URI_MAP = {}
        self.URI_MAP_KEYS = []
        self.PREFIX_TO_IRI_MAP = {}

        self.biolink_version = biolink_version

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
                    self.PREFIX_TO_IRI_MAP[prefix] = iri

        self.URI_MAP_KEYS = sorted(self.URI_MAP.keys(), key=len, reverse=True)

    def match_prefix(self, iri):

        for url in self.URI_MAP_KEYS:
            if iri.startswith(url):
                return iri.replace(url, self.URI_MAP[url] + ":")

        return None

    def categorize_node(self, node_id, depth=0):

        if node_id in self.NODE_CATEGORY_MAPPINGS:
            return self.NODE_CATEGORY_MAPPINGS[node_id][0]

        prefix = node_id.split(":")[0]

        if prefix in self.PREFIX_MAPPINGS:
            cat = self.PREFIX_MAPPINGS[prefix]
            self.NODE_CATEGORY_MAPPINGS[node_id] = (cat, PREFIX_MAPPING)
            return cat

        if depth > 10:
            return kg2_util.BIOLINK_CATEGORY_NAMED_THING

        counts = {}

        for parent in self.CLASS_TO_SUPERCLASSES.get(node_id, []):
            cat = self.categorize_node(parent, depth + 1)
            counts[cat] = counts.get(cat, 0) + 1

        if not counts:
            return kg2_util.BIOLINK_CATEGORY_NAMED_THING

        cat = max(counts, key=counts.get)
        self.NODE_CATEGORY_MAPPINGS[node_id] = (cat, RECURSE_MAPPING)
        return cat

    def parse_date(self, text):

        if not text:
            return None

        try:
            return datetime.datetime.fromisoformat(text.replace("Z", ""))
        except Exception:
            return None

    def extract_restriction_edges(self, edge):

        edges = []

        for restriction in edge.get("owl:Restriction", []):

            prop = restriction.get("owl:onProperty", [])
            obj = restriction.get("owl:someValuesFrom", [])

            if prop and obj:

                p = prop[0].get(RESOURCE_KEY)
                o = obj[0].get(RESOURCE_KEY)

                p = self.match_prefix(p)
                o = self.match_prefix(o)

                if p and o:
                    edges.append((p, o))

        return edges

    def extract_edges(self, owl_class, node_id):

        edges = []

        for pred, key in BASE_EDGE_TYPES.items():

            for entry in owl_class.get(pred, []):

                if key in entry:

                    obj = self.match_prefix(entry[key])

                    if obj:
                        edges.append((pred, obj))

        for sub in owl_class.get("rdfs:subClassOf", []):

            if RESOURCE_KEY in sub:

                obj = self.match_prefix(sub[RESOURCE_KEY])

                if obj:
                    edges.append(("rdfs:subClassOf", obj))
                    self.CLASS_TO_SUPERCLASSES.setdefault(node_id, set()).add(obj)

            edges += self.extract_restriction_edges(sub)

        for equiv in owl_class.get("owl:equivalentClass", []):

            for cls in equiv.get("owl:Class", []):

                for inter in cls.get("owl:intersectionOf", []):

                    edges += self.extract_restriction_edges(inter)

        return edges

    def process_class(self, owl_class, source):

        raw_id = owl_class.get(ID_TAG)
        if not raw_id:
            return

        node_id = self.match_prefix(raw_id)
        if not node_id:
            return

        names = [
            x.get(TEXT_KEY)
            for x in owl_class.get("rdfs:label", [])
            if TEXT_KEY in x
        ]

        if not names:
            return

        label = names[0]

        deprecated = (
            "obsolete" in label.lower()
            or "(obsolete" in label.lower()
            or "obsolete " in label.lower()
        )

        descriptions = [
            x.get(TEXT_KEY)
            for x in owl_class.get("obo:IAO_0000115", [])
            if TEXT_KEY in x
        ]

        descriptions += [
            COMMENT_PREFIX + x.get(TEXT_KEY)
            for x in owl_class.get("rdfs:comment", [])
            if TEXT_KEY in x
        ]

        synonyms = []

        for key in SYNONYM_KEYS:
            synonyms += [
                s.get(TEXT_KEY)
                for s in owl_class.get(key, [])
                if TEXT_KEY in s
            ]

        sequences = {
            "smiles": [x.get(TEXT_KEY) for x in owl_class.get("chebi:smiles", []) if TEXT_KEY in x],
            "inchi": [x.get(TEXT_KEY) for x in owl_class.get("chebi:inchi", []) if TEXT_KEY in x],
            "inchikey": [x.get(TEXT_KEY) for x in owl_class.get("chebi:inchikey", []) if TEXT_KEY in x],
            "formula": [x.get(TEXT_KEY) for x in owl_class.get("chebi:formula", []) if TEXT_KEY in x],
        }

        edges = self.extract_edges(owl_class, node_id)

        self.SAVED_NODE_INFO.setdefault(node_id, []).append({
            "id": node_id,
            "iri": raw_id,
            "name": label,
            "description": DESCRIPTION_DELIM.join(descriptions),
            "synonyms": synonyms,
            "sequences": sequences,
            "edges": edges,
            "source": source,
            "deprecated": deprecated
        })

    def process_ontology_term(self, ontology_node, source, ontology_name):

        version = None

        if "owl:versionInfo" in ontology_node:
            version = ontology_node["owl:versionInfo"][0].get(TEXT_KEY)

        elif "owl:versionIRI" in ontology_node:
            version = ontology_node["owl:versionIRI"][0].get(RESOURCE_KEY)

        self.SOURCE_INFO[source] = {
            "name": ontology_name,
            "version": version,
        }

    def write_source_nodes(self, nodes_output):

        for source in self.SOURCE_INFO:

            node_id = f"obo:{source}"

            name = self.SOURCE_INFO[source]["name"]
            version = self.SOURCE_INFO[source]["version"]

            label = f"{name} v{version}" if version else name

            node = kg2_util.make_node(
                node_id,
                node_id,
                label,
                kg2_util.SOURCE_NODE_CATEGORY,
                None,
                node_id
            )

            nodes_output.write(node)

    def write_graph(self, nodes_output, edges_output):

        self.write_source_nodes(nodes_output)

        for node_id, entries in self.SAVED_NODE_INFO.items():

            category = self.categorize_node(node_id)

            for info in entries:

                if info["deprecated"]:
                    continue

                node = kg2_util.make_node(
                    info["id"],
                    info["iri"],
                    info["name"],
                    category,
                    kg2_util.date(),
                    f"obo:{info['source']}"
                )

                node["description"] = info["description"]
                node["synonym"] = info["synonyms"]
                node["has_biological_sequence"] = info["sequences"]

                nodes_output.write(node)

                for pred, obj in info["edges"]:

                    edge = kg2_util.make_edge(
                        info["id"],
                        obj,
                        pred,
                        pred.split(":")[-1],
                        f"obo:{info['source']}",
                        kg2_util.date()
                    )

                    edges_output.write(edge)


def get_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("--test", action="store_true", default=False)

    parser.add_argument("inputFile")
    parser.add_argument("curiesToCategories")
    parser.add_argument("curiesToUrls")
    parser.add_argument("biolinkVersion")
    parser.add_argument("outputNodes")
    parser.add_argument("outputEdges")

    return parser.parse_args()


def main():

    args = get_args()

    print("Start:", kg2_util.date())

    converter = OntologyConverter(
        args.curiesToCategories,
        args.curiesToUrls,
        args.biolinkVersion
    )

    nodes_info, edges_info = kg2_util.create_kg2_jsonlines(args.test)

    nodes_output = nodes_info[0]
    edges_output = edges_info[0]

    with open(args.inputFile) as f:

        for line in f:

            item = json.loads(line)

            source = item.get(OWL_SOURCE_KEY)
            source_name = item.get(OWL_SOURCE_NAME_KEY)

            for cls in item.get("owl:Class", []):
                converter.process_class(cls, source)

            for ont in item.get("owl:Ontology", []):
                converter.process_ontology_term(ont, source, source_name)

    converter.write_graph(nodes_output, edges_output)

    kg2_util.close_kg2_jsonlines(
        nodes_info,
        edges_info,
        args.outputNodes,
        args.outputEdges
    )

    print("Finish:", kg2_util.date())


if __name__ == "__main__":
    main()
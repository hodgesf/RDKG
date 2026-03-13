import yaml

ONT_INV = yaml.safe_load(open("yaml/ont-load-inventory.yaml"))
SRC_INV = yaml.safe_load(open("yaml/source-load-inventory.yaml"))

ONTOLOGY_FILES = [x["file"] for x in ONT_INV]
SOURCE_FILES = [x["file"] for x in SRC_INV]


rule all:
    input:
        "jsonl/nodes-simplified.jsonl",
        "jsonl/edges-simplified.jsonl"


rule extract_ontology:
    input:
        inventory="yaml/ont-load-inventory.yaml"
    output:
        "jsonl/ontologies.jsonl"
    threads: 4
    shell:
        """
        python extract/owl_parser.py \
        {input.inventory} \
        owl_files/ \
        {output}
        """


rule extract_sources:
    input:
        inventory="yaml/source-load-inventory.yaml"
    output:
        "jsonl/sources.jsonl"
    threads: 4
    shell:
        """
        python extract/source_parser.py \
        {input.inventory} \
        jsonl/ \
        {output}
        """


rule convert_ontologies:
    input:
        "jsonl/ontologies.jsonl"
    output:
        nodes="jsonl/ontology_nodes.jsonl",
        edges="jsonl/ontology_edges.jsonl"
    threads: 8
    shell:
        """
        python transform/convert_ontologies.py \
        {input} \
        yaml/curies-to-categories.yaml \
        yaml/curies-to-urls-map.yaml \
        4.2.5 \
        {output.nodes} \
        {output.edges}
        """


rule convert_sources:
    input:
        "jsonl/sources.jsonl"
    output:
        nodes="jsonl/source_nodes.jsonl",
        edges="jsonl/source_edges.jsonl"
    threads: 8
    shell:
        """
        python transform/convert_sources.py \
        {input} \
        yaml/curies-to-categories.yaml \
        yaml/curies-to-urls-map.yaml \
        {output.nodes} \
        {output.edges}
        """


rule merge_graphs:
    input:
        nodes=[
            "jsonl/ontology_nodes.jsonl",
            "jsonl/source_nodes.jsonl"
        ],
        edges=[
            "jsonl/ontology_edges.jsonl",
            "jsonl/source_edges.jsonl"
        ]
    output:
        nodes="jsonl/nodes.jsonl",
        edges="jsonl/edges.jsonl"
    threads: 2
    shell:
        """
        python transform/merge_graphs.py \
        --nodes {input.nodes} \
        --edges {input.edges} \
        --outputNodes {output.nodes} \
        --outputEdges {output.edges}
        """


rule simplify_graph:
    input:
        nodes="jsonl/nodes.jsonl",
        edges="jsonl/edges.jsonl"
    output:
        nodes="jsonl/nodes-simplified.jsonl",
        edges="jsonl/edges-simplified.jsonl"
    threads: 4
    shell:
        """
        python transform/filter_kg_and_remap_predicates.py \
        yaml/predicate-remap.yaml \
        yaml/kg2-provided-by-curie-to-infores-curie.yaml \
        yaml/knowledge-level-agent-type-map.yaml \
        yaml/edge-blocklist.yaml \
        {input.nodes} \
        {input.edges} \
        {output.nodes} \
        {output.edges} \
        versions.md
        """
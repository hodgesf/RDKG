# Rare Disease Knowledge Graph (RDKG)

## Overview

This repository contains a biomedical knowledge graph focused on rare diseases. It integrates multiple curated sources into a unified Biolink-style schema for downstream tasks such as drug repurposing, molecular target discovery, and clinical decision support.

The pipeline is fully reproducible and designed for HPC environments. Raw data is **not versioned in Git** and is instead downloaded programmatically.

---

## Quick Start

Build the entire graph with a single command:

```
./build_graph.sh --setup
```

This will:

1. Create/activate a virtual environment
2. Install dependencies
3. Download all source data from S3
4. Extract archives
5. Merge graphs
6. Filter edges/nodes
7. Compute statistics

---

## Data Sources

| Source         | Expanded Name                                           | Description                                                                                                                                            |
| -------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| bindingdb      | BindingDB                                               | Protein–small molecule binding affinities.                                                                                                             |
| chembl         | ChEMBL                                                  | Drug bioactivity database with target information.                                                                                                     |
| dgidb          | Drug–Gene Interaction Database                          | Aggregated drug–gene interactions.                                                                                                                     |
| gene2phenotype | Gene2Phenotype (G2P)                                    | Gene–disease relationships with curated pathogenicity evidence.                                                                                        |
| goa            | Gene Ontology Annotations                               | Functional annotations using GO terms.                                                                                                                 |
| hpoa           | Human Phenotype Ontology Annotations                    | Disease–phenotype associations (HPO).                                                                                                                  |
| icees          | Integrated Clinical and Environmental Exposures Service | Clinical and environmental exposure associations.                                                                                                      |
| intact         | IntAct                                                  | Molecular and protein–protein interactions.                                                                                                            |
| ncbi_gene      | NCBI Gene                                               | Gene identifiers and metadata.                                                                                                                         |
| orphanet       | Orphanet                                                | Rare disease definitions and classifications. Includes en_product1, en_product4, en_product6, and en_func_consequences datasets used in this pipeline. |
| panther        | PANTHER                                                 | Protein families and pathways.                                                                                                                         |
| sider          | SIDER                                                   | Drug side effects.                                                                                                                                     |
| signor         | SIGNOR                                                  | Causal signaling relationships.                                                                                                                        |
| ubergraph      | Ubergraph                                               | Integrated ontology graph (OBO stack). Incorporates ontologies including NCBITaxon, CHEBI, UniProtKB, PR, GO, MONDO, UMLS, NCIT, HP, and UBERON.       |

All sources (except Orphanet) are downloaded from the Translator ingest S3 bucket.


---

## Graph Statistics

### Basic

* Nodes: 989,045
* Edges: 4,038,447

### Disease Distribution

* Total diseases: 56,171
* Rare diseases (OrPHA): 11,456
* ~21% rare diseases

### Degree Distribution

* Mean: 8.17
* Median: 1
* 90th: 7
* 99th: 122
* Max: 27,278

No isolated nodes.

---

## Repository Structure

```
.
├── build_graph.sh              # full pipeline entrypoint
│
├── files/                      # generated + downloaded data (NOT versioned)
│   ├── all_nodes.jsonl
│   ├── all_edges.jsonl
│   ├── nodes_filtered.jsonl
│   ├── edges_filtered.jsonl
│   ├── orphan_edges.jsonl
│   └── data/
│       ├── <source>/
│       │   ├── *.tar.zst
│       │   ├── nodes.jsonl
│       │   ├── edges.jsonl
│       │   └── graph-metadata.json
│
├── process/
│   ├── ingest_data.sh          # downloads from S3
│   ├── unzip.sh                # extracts .tar.zst
│   ├── merge_graphs.py         # graph merge
│   └── filter_graph.py         # filtering
│
├── stats/
│   ├── stats.py
│   ├── stats_all.txt
│   └── stats_filtered.txt
│
├── setup/
│   ├── requirements.txt
│   └── versions.md
│
└── README.md
```

---

## Pipeline Details

### 1. Data Download

Downloads all sources from:

```
https://translator-ingests.s3.us-east-1.amazonaws.com/releases/<source>/latest/<source>.tar.zst
```

### 2. Extraction

Archives are extracted into per-source directories.

### 3. Merge

Combines all source graphs:

* deduplicates nodes
* removes orphan edges

Outputs:

* `files/all_nodes.jsonl`
* `files/all_edges.jsonl`
* `files/orphan_edges.jsonl`

### 4. Filtering

Removes unwanted predicates (e.g., `biolink:subclass_of`) and prunes unused nodes.

Outputs:

* `files/nodes_filtered.jsonl`
* `files/edges_filtered.jsonl`

### 5. Statistics

Computes summary metrics and distributions.

Outputs:

* `stats/stats_all.txt`
* `stats/stats_filtered.txt`

---

## Data Format

### Nodes

* `id` (CURIE)
* `name`
* `category`
* `attributes`

### Edges

* `subject`
* `predicate`
* `object`
* `category`
* `provided_by`

---

## Requirements

```
pip install -r setup/requirements.txt
```

---

## Important Notes

* Large datasets (`.tar.zst`, JSONL outputs) are **not tracked in Git**
* All data is downloaded at runtime
* Designed for HPC usage (disk + memory intensive)
* Pipeline is deterministic and reproducible

---

## Use Cases

* Rare disease target discovery
* Drug repurposing
* Biomedical knowledge graph embeddings
* RAG pipelines for LLMs
* Clinical decision support

---

## License

MIT

---

## Maintainer

Frankie Hodges
Oregon State University

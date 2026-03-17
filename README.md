# Rare Disease Knowledge Graph (RDKG)

## Overview

This repository contains a large-scale biomedical knowledge graph focused on rare diseases. The graph integrates multiple curated biomedical sources into a unified schema (Biolink-style), enabling downstream tasks such as drug repurposing, molecular target discovery, and clinical decision support.

The pipeline ingests heterogeneous datasets, normalizes entities and relationships, and produces a merged graph with consistent node and edge representations.

---

## Data Sources

The following sources are included in the graph:

| Source         | Expanded Name                                                 | Description                                                                                              |
| -------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| bindingdb      | BindingDB                                                     | Database of measured binding affinities between proteins and small molecules (drug–target interactions). |
| chembl         | ChEMBL                                                        | Curated bioactivity database of drugs and drug-like molecules with target information.                   |
| dgidb          | Drug–Gene Interaction Database                                | Aggregates known and potential drug–gene interactions from multiple sources.                             |
| gene2phenotype | Gene2Phenotype (G2P)                                          | Links genes to diseases and phenotypes with curated evidence of pathogenicity.                           |
| goa            | Gene Ontology Annotations                                     | Provides functional annotations of genes using Gene Ontology terms.                                      |
| hpoa           | Human Phenotype Ontology Annotations                          | Associates diseases with human phenotypic abnormalities (HPO terms).                                     |
| icees          | Integrated Clinical and Environmental Exposures Service       | Clinical + environmental exposure data for exploring associations in patient cohorts.                    |
| intact         | IntAct Molecular Interaction Database                         | Curated database of molecular and protein–protein interactions.                                          |
| ncbi_gene      | NCBI Gene                                                     | Central repository of gene-specific information including identifiers and metadata.                      |
| orphanet       | Orphanet                                                      | Comprehensive resource on rare diseases, including disease definitions and classifications.              |
| panther        | PANTHER (Protein ANalysis THrough Evolutionary Relationships) | Protein families, functions, and pathways based on evolutionary relationships.                           |
| sider          | SIDER (Side Effect Resource)                                  | Database of drug side effects extracted from public documents and labels.                                |
| signor         | SIGNOR (Signaling Network Open Resource)                      | Curated causal relationships between biological entities in signaling pathways.                          |
| ubergraph      | Ubergraph                                                     | Integrated ontology graph combining multiple OBO ontologies into a unified structure.                    |


These sources collectively cover drugs, genes, phenotypes, pathways, molecular interactions, and disease ontologies, with strong emphasis on rare disease representation (via Orphanet and HPO).

---

## Graph Statistics

### Basic

* Nodes: 989,045
* Edges: 4,038,447

### Disease Distribution

* Total diseases: 56,171
* Rare diseases (Orphanet): 11,456
* Rare disease proportion: ~21%

### Degree Distribution

* Mean degree: 8.17
* Median: 1
* 90th percentile: 7
* 99th percentile: 122
* Max: 27,278

All nodes participate in at least one edge (no isolated nodes).

---

## Node Distribution (Top Categories)

* biolink:NamedThing — 976,246
* biolink:PhysicalEssenceOrOccurrent — 930,000
* biolink:ChemicalEntityOrGeneOrGeneProduct — 929,554
* biolink:PhysicalEssence — 912,200
* biolink:ChemicalEntityOrProteinOrPolypeptide — 907,337

---

## Edge Distribution

### Top Predicates

* biolink:directly_physically_interacts_with — 1,068,950
* biolink:physically_interacts_with — 622,361
* biolink:related_to — 420,963
* biolink:associated_with — 335,447
* biolink:enables — 274,241

### Top Edge Categories

* biolink:ChemicalGeneInteractionAssociation — 1,087,629
* biolink:GeneToGoTermAssociation — 791,755
* biolink:PairwiseMolecularInteraction — 622,361
* biolink:Association — 363,085
* biolink:GeneToPhenotypicFeatureAssociation — 324,912

---

## Repository Structure

```
.
├── files/
│   └── data/
│       ├── <source>/
│       │   ├── *.tar.zst          # raw compressed data
│       │   └── graph-metadata.json
│
├── process/
│   ├── merge_graphs.py            # merges all sources
│   ├── filter_graph.py            # applies filtering rules
│   └── unzip.sh                   # extraction script
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

## Data Format

All graph data is stored in JSON Lines format:

### Nodes (`nodes.jsonl`)

Each line is a JSON object representing a node:

* id (CURIE)
* name
* category (Biolink class)
* attributes (optional metadata)

### Edges (`edges.jsonl`)

Each line is a JSON object representing an edge:

* subject
* predicate
* object
* category
* provided_by

---

## Pipeline

### 1. Extraction

Raw `.tar.zst` files are unpacked:

```
bash extract/unzip.sh
```

### 2. Source Parsing

Each source is converted into:

* `nodes.jsonl`
* `edges.jsonl`

### 3. Merge

All sources are merged:

```
python merge_graphs.py
```

Outputs:

* `all_nodes.jsonl`
* `all_edges.jsonl`

### 4. Filtering

Optional filtering (predicate cleanup, deduplication, etc.):

```
python filter_graph.py
```

Outputs:

* `nodes_filtered.jsonl`
* `edges_filtered.jsonl`

### 5. Statistics

```
python stats/stats.py
```

---

## Design Notes

* Uses Biolink-style categories and predicates
* Emphasizes rare disease coverage via Orphanet + HPO
* Maintains full provenance via `provided_by`
* No isolated nodes (fully connected graph)
* Heavy-tailed degree distribution typical of biological networks
* All sources, except for Orphanet, were obtained from translater-ingest team, copied from the public s3 bucket called `translator-ingests`

---

## Use Cases

* Rare disease molecular target discovery
* Drug repurposing
* Knowledge graph embeddings
* RAG pipelines for biomedical LLMs
* Clinical decision support systems

---

## Requirements

Install dependencies:

```
pip install -r setup/requirements.txt
```

---

## Notes

* Raw data is large and intended for HPC environments
* Intermediate files may require significant disk space
* Processing ~1M nodes / ~4M edges benefits from parallelization

---

## License

MIT 

---

## Maintainer

Frankie Hodges
Oregon State University

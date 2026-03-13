# Overview

This repository constructs a biomedical knowledge graph by ingesting
biomedical ontologies and structured biomedical datasets, converting
them into a unified representation, merging them into a single graph,
and normalizing predicates and provenance.

The pipeline produces a graph stored in JSON Lines format consisting of
node and edge records.

The workflow is orchestrated using **Snakemake**, but every step can
also be executed manually.

# Pipeline Architecture

The build process consists of five major stages.

```
download
  ↓
extract
  ↓
convert
  ↓
merge
  ↓
simplify
  ↓
normalize
```


## Download

Ontology and dataset files are downloaded from remote sources specified
in YAML inventory files.

## Extract

Raw source files are parsed into intermediate JSONL representations.

## Convert

Intermediate records are transformed into graph nodes and edges.

## Merge

Ontology and source graphs are merged into a unified graph.

## Simplify / Normalize

Predicates and provenance are normalized to Biolink and Translator
conventions.

# Repository Structure

    .
    ├── Snakefile
    ├── extract
    │   ├── owl_parser.py
    │   └── source_parser.py
    ├── transform
    │   ├── convert_ontologies.py
    │   ├── convert_sources.py
    │   ├── merge_graphs.py
    │   └── filter_kg_and_remap_predicates.py
    ├── yaml
    │   ├── ont-load-inventory.yaml
    │   ├── source-load-inventory.yaml
    │   ├── predicate-remap.yaml
    │   ├── curies-to-categories.yaml
    │   ├── curies-to-urls-map.yaml
    │   ├── edge-blocklist.yaml
    │   ├── kg2-provided-by-curie-to-infores-curie.yaml
    │   └── knowledge-level-agent-type-map.yaml
    ├── owl_files
    ├── jsonl
    ├── scripts
    ├── global_config_and_helpers
    │   └── kg2_util.py
    └── versions.md

# Ontologies Ingested

The following ontologies are included.

| Ontology | Description |
|----------|-------------|
| BFO | Basic Formal Ontology |
| CHEBI | Chemical Entities of Biological Interest |
| CL | Cell Ontology |
| GO | Gene Ontology |
| HP | Human Phenotype Ontology |
| INO | Interaction Network Ontology |
| MI | Molecular Interaction Ontology |
| MONDO | Disease Ontology |
| ORDO | Orphanet Rare Disease Ontology |
| PATO | Phenotype and Trait Ontology |
| PR | Protein Ontology |
| RO | Relation Ontology |
| TAXSLIM | Taxonomic subset |
| UBERON | Anatomy Ontology |


These ontologies are specified in

    yaml/ont-load-inventory.yaml

# External Data Sources

Non-ontology sources are specified in

    yaml/source-load-inventory.yaml

The pipeline ingests the following structured biomedical data sources:

| Source | Description |
|------|-------------|
| ChEMBL | Bioactive drug-like small molecules and drug–target interaction data |
| DrugBank | Curated drug database linking drugs, targets, and mechanisms |
| DrugCentral | Drug information resource integrating approvals, indications, and targets |
| Guide to Pharmacology (IUPHAR/BPS) | Expert-curated pharmacology targets and ligands |
| Therapeutic Target Database (TTD) | Known and explored therapeutic protein and nucleic acid targets |
| PharmGKB | Pharmacogenomics knowledge linking genes, drugs, and disease |
| SIDER | Drug side effect resource extracted from public drug labels |
| Open Targets Platform | Integrated evidence linking targets, diseases, and drugs |
| NCBI Gene | Gene-centric biological information from NCBI |
| Ensembl | Genome annotation database for vertebrate genomes |
| UniProtKB | Comprehensive protein sequence and functional annotation database |
| GOA | Gene Ontology annotations linking genes to GO terms |
| miRBase | MicroRNA sequence and annotation database |
| RefSeq | Curated reference sequences for genes, transcripts, and proteins |
| DisGeNET | Integrated gene–disease association database |
| JensenLab DISEASES | Text-mined and curated disease–gene association database |
| ClinVar | Clinically relevant genetic variants and their interpretations |
| GWAS Catalog | Genome-wide association study variant–trait associations |
| OMIM | Online Mendelian Inheritance in Man genetic disease database |
| IntAct | Molecular interaction database maintained by EMBL-EBI |
| STRING | Protein–protein interaction network database |
| BioGRID | Biological interaction repository for proteins and genes |
| DIP | Database of experimentally determined protein interactions |
| MINT | Molecular interaction database curated from literature |
| Reactome | Curated biological pathway knowledgebase |
| SMPDB | Small Molecule Pathway Database |
| PathWhiz | Pathway diagram and modeling database |
| WikiPathways | Community-curated biological pathway database |
| KEGG | Kyoto Encyclopedia of Genes and Genomes pathway database |
| UniChem | Cross-reference mapping between chemical structure identifiers |
| HMDB | Human Metabolome Database |
| PubChem | Chemical structures, compounds, and bioactivity data |
| CTD | Comparative Toxicogenomics Database linking chemicals, genes, and disease |
| SemMedDB | Semantic predications extracted from biomedical literature |
| ClinicalTrials.gov | Registry of clinical studies and trial metadata |



These sources contribute structured biomedical relationships including:

-   gene--disease associations
-   drug--target interactions
-   pathway relationships
-   phenotype associations

# Graph Output Format

The final graph is stored in JSON Lines format.

## Nodes

    jsonl/nodes.jsonl

Example node record:

    {
    "id": "MONDO:0005148",
    "name": "type 2 diabetes mellitus",
    "category": "biolink:Disease"
    }

## Edges

    jsonl/edges.jsonl

Example edge record:

    {
    "subject": "CHEBI:15377",
    "predicate": "biolink:related_to",
    "object": "MONDO:0005148"
    }

# Running the Pipeline with Snakemake

Install Snakemake:

    pip install snakemake

Execute the pipeline from the repository root:

    snakemake --cores 8

Recommended command with logging:

    snakemake --cores 8 --printshellcmds --reason --rerun-incomplete

Snakemake will automatically execute all steps required to produce the
final normalized graph.

# Running the Pipeline Manually

The pipeline can also be executed without Snakemake.

## Extract Ontologies

    python extract/owl_parser.py \
    yaml/ont-load-inventory.yaml \
    owl_files/ \
    jsonl/ontologies.jsonl

## Extract Sources

    python extract/source_parser.py \
    yaml/source-load-inventory.yaml \
    jsonl/ \
    jsonl/sources.jsonl

## Convert Ontologies

    python transform/convert_ontologies.py \
    jsonl/ontologies.jsonl \
    yaml/curies-to-categories.yaml \
    yaml/curies-to-urls-map.yaml \
    4.2.5 \
    jsonl/ontology_nodes.jsonl \
    jsonl/ontology_edges.jsonl

## Convert Sources

    python transform/convert_sources.py \
    jsonl/sources.jsonl \
    yaml/curies-to-categories.yaml \
    yaml/curies-to-urls-map.yaml \
    jsonl/source_nodes.jsonl \
    jsonl/source_edges.jsonl

## Merge Graphs

    python transform/merge_graphs.py \
    --nodes jsonl/ontology_nodes.jsonl jsonl/source_nodes.jsonl \
    --edges jsonl/ontology_edges.jsonl jsonl/source_edges.jsonl \
    --outputNodes jsonl/nodes.jsonl \
    --outputEdges jsonl/edges.jsonl

## Normalize Graph

    python transform/filter_kg_and_remap_predicates.py \
    yaml/predicate-remap.yaml \
    yaml/kg2-provided-by-curie-to-infores-curie.yaml \
    yaml/knowledge-level-agent-type-map.yaml \
    yaml/edge-blocklist.yaml \
    jsonl/nodes.jsonl \
    jsonl/edges.jsonl \
    jsonl/nodes-simplified.jsonl \
    jsonl/edges-simplified.jsonl \
    versions.md

# Configuration Files

The configuration directory contains YAML files controlling graph
conversion and normalization.

## curies-to-categories.yaml

Maps identifier prefixes to Biolink node categories.

## curies-to-urls-map.yaml

Defines how IRIs are converted to CURIE identifiers.

## predicate-remap.yaml

Defines predicate normalization rules.

## kg2-provided-by-curie-to-infores-curie.yaml

Maps source identifiers to Translator `infores` identifiers.

## knowledge-level-agent-type-map.yaml

Defines knowledge-level metadata used in the Translator ecosystem.

## edge-blocklist.yaml

Defines edges that should be removed during normalization.

# Versioning

The file

    versions.md

stores the graph build version identifier.

This value is embedded into the graph metadata.

# Notes

-   JSON Lines is used to support streaming large graphs.

-   The pipeline supports graphs with tens to hundreds of millions of
    edges.

-   Snakemake ensures reproducible builds.

# Future Work

Planned additions include:

-   node canonicalization

-   identifier normalization

-   equivalence resolution

-   graph statistics generation

-   export to Neo4j or Parquet

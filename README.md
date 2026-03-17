# Rare Disease Knowledge Graph (RDKG)

## Overview

This repository contains a biomedical knowledge graph focused on rare diseases. It integrates multiple curated sources into a unified Biolink-style schema for downstream tasks such as drug repurposing, molecular target discovery, and clinical decision support.

The pipeline is fully reproducible and designed for HPC environments. Raw data is **not versioned in Git** and is instead downloaded programmatically.

---

## System Requirements

### Minimum (Observed)

* **Disk**: ~25 GB (end-to-end pipeline)
* **RAM**: ~6 GB peak observed (5.46 GB max RSS)
* **CPU**: 10+ cores recommended (pipeline parallelism limited but benefits from I/O concurrency)
* **Runtime**: ~10 minutes total

### Tested Environment - macOS

* **System**: Apple MacBook Pro with M5 chip
* **CPU**: 10 cores
* **RAM**: 32 GB unified memory
* **Storage**: 1 TB SSD
* **OS**: macOS Tahoe 26.3.1
* **Python**: 3.13+

### Tested Environment - HPC

* **System**: NVIDIA DGX-h node
* **CPU**: 16 cores
* **RAM**: 128 GB
* **Storage**: 1 TB SSD
* **OS**: Rocky Linux 9.7 (Blue Onyx)
* **Python**: 3.13+

### Prerequisites

Before running the pipeline, you must install:

* **zstd** - Required for decompressing `.tar.zst` archives
  * **macOS**: `brew install zstd`
  * **Linux**: `apt-get install zstd` (Ubuntu/Debian) or `yum install zstd` (CentOS/RHEL)
  * **HPC**: Usually available in module system: `module load zstd` (check with `module avail`)

### S3 Access

All data sources (except Orphanet) are downloaded from a **public S3 bucket**:

```
https://translator-ingests.s3.us-east-1.amazonaws.com/
```

No AWS credentials required. If downloads fail, verify:
* Network connectivity and firewall rules
* `curl` or `wget` are available in your shell

---

## Installation

### Quick Start

Build the entire graph with a single command:

```bash
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

### Manual Installation

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r setup/requirements.txt

# Run individual pipeline steps
bash process/ingest_data.sh
bash process/unzip.sh
python process/merge_graphs.py --help
python process/filter_graph.py
python stats/stats.py
```

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
│   ├── ingest_data.sh          # downloads standard sources from S3
│   ├── ingest_orphanet.sh      # downloads Orphanet XML files
│   ├── unzip.sh                # extracts .tar.zst archives
│   ├── transform_orphanet.py   # transforms Orphanet XML to JSONL
│   ├── merge_graphs.py         # graph merge
│   ├── filter_graph.py         # filtering
│   ├── orphanet_ingest.py      # Orphanet ingestion utilities (from translator ingest)
│   └── biolink_util.py         # Biolink utilities (from translator ingest)
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

#### Standard Sources

Downloads from the public Translator ingest S3 bucket:

```
https://translator-ingests.s3.us-east-1.amazonaws.com/releases/<source>/latest/<source>.tar.zst
```

#### Orphanet

Downloads directly from Orphanet:

```
https://www.orphadata.com/data/xml/en_product<N>.xml
```

Files downloaded:
- `en_product6.xml`: Disease-gene associations
- `en_product1.xml`: Disease metadata and external identifiers
- `en_product4.xml`: Disease-phenotype (HPO) associations
- `en_funct_consequences.xml`: Disease-disability associations

### 2. Extraction

Standard source archives (`.tar.zst`) are extracted into per-source directories.

### 3. Transformation

**Orphanet XML files** are transformed into KGX JSONL format via [process/transform_orphanet.py](process/transform_orphanet.py):
- Extracts Disease and Gene nodes
- Creates GeneToDiseaseAssociation edges
- Maps external disease identifiers (MONDO, ICD-11, OMIM, UMLS)
- Extracts HPO phenotype associations
- Extracts disability/functional consequence associations

### 4. Merge

Combines all source graphs:

* deduplicates nodes
* removes orphan edges

Outputs:

* `files/all_nodes.jsonl`
* `files/all_edges.jsonl`
* `files/orphan_edges.jsonl`

### 5. Filtering

Removes unwanted predicates (e.g., `biolink:subclass_of`) and prunes unused nodes.

Outputs:

* `files/nodes_filtered.jsonl`
* `files/edges_filtered.jsonl`

### 6. Statistics

Computes summary metrics and distributions.

Outputs:

* `stats/stats_all.txt`
* `stats/stats_filtered.txt`

---

## Data Format

### Nodes

```json
{
  "id": "MONDO:0005300",
  "name": "schizophrenia",
  "category": ["biolink:Disease"],
  "attributes": {
    "xrefs": ["DOID:5419"],
    "description": "..."
  }
}
```

* `id` (CURIE): Unique identifier (e.g., `MONDO:`, `NCBI_GENE:`, `CHEMBL:`)
* `name`: Human-readable label
* `category`: List of Biolink semantic types
* `attributes`: Additional metadata (xrefs, descriptions, source info)

### Edges

```json
{
  "subject": "MONDO:0005300",
  "predicate": "biolink:associated_with",
  "object": "HP:0000716",
  "category": ["biolink:Association"],
  "provided_by": "hpoa"
}
```

* `subject`: CURIE of source node
* `predicate`: Biolink predicate (e.g., `biolink:associated_with`)
* `object`: CURIE of target node
* `category`: Edge semantic types
* `provided_by`: Source database name

---

## Dependency Versions

See [setup/versions.md](setup/versions.md) for tested dependency versions. Install with:

```bash
pip install -r setup/requirements.txt
```

**Note**: The pipeline is tested with the versions in `setup/versions.md`. Newer versions of dependencies may work but are not guaranteed.

---

## Advanced Usage

### Run Individual Pipeline Steps

You can run steps independently (ensure earlier steps are completed first):

```bash
# Download data only
bash process/ingest_data.sh

# Extract existing downloads
bash process/unzip.sh

# Merge graphs (requires extracted data)
python process/merge_graphs.py

# Filter edges/nodes
python process/filter_graph.py

# Compute statistics
python stats/stats.py
```

### Customize Filtering Rules

Edit [process/filter_graph.py](process/filter_graph.py) to modify which predicates/nodes are kept. By default, `biolink:subclass_of` edges are removed.

### Customize Orphanet Processing

Edit [process/transform_orphanet.py](process/transform_orphanet.py) to:
- Change which Orphanet files are processed
- Modify predicate mappings for gene-disease associations
- Adjust disease/disability association handling
- Filter specific association types

Example modifications:
- Comment out XML file processing functions to skip them
- Modify `ASSOCIATION_TYPE_PREDICATE_MAPPING` to customize edge predicates
- Adjust heuristics for disability ID generation

### On HPC Clusters

For large-scale deployments, the pipeline can be adapted to distributed systems. Contact the maintainer for guidance.

---

## Troubleshooting

### Download Failures

**Problem**: S3 download fails or times out.

**Solutions**:
* Check internet connectivity: `curl -I https://translator-ingests.s3.us-east-1.amazonaws.com/`
* Try re-running `process/ingest_data.sh` (many sources can resume partial downloads)
* Ensure adequate disk space: `df -h`
* For transient issues, wait and retry

### Orphanet Download Failures

**Problem**: Orphanet XML files fail to download or `transform_orphanet.py` reports missing files.

**Solutions**:
* Verify Orphanet website is accessible: `curl -I https://www.orphadata.com/data/xml/en_product6.xml`
* Check `files/data/orphanet/` directory exists and has `.xml` files
* Re-run: `bash process/ingest_orphanet.sh`
* If files missing, the transformation script will continue with available files (non-fatal warnings)

### Out of Disk Space

**Problem**: "No space left on device" error during extraction.

**Solutions**:
* Check available space: `df -h /path/to/RDKG`
* Typical full pipeline footprint: ~25–30 GB
* Size varies depending on source versions and filtering
* Remove intermediate archives after extraction: `rm -rf files/data/*/**.tar.zst`
* Or use a larger disk partition and rerun

### Memory Errors

**Problem**: "Killed" or "out of memory" errors during merge/filter steps.

**Solutions**:
* Ensure 8+ GB RAM available
* Close other applications
* If on HPC, request more memory in job submission
* Increase virtual memory (not recommended; use physical RAM)

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'X'`

**Solutions**:
* Verify venv is activated: `which python` should show `venv/bin/python`
* Reinstall dependencies: `pip install -r setup/requirements.txt`
* Check Python version: `python --version` (should be 3.11+)

### Data Inconsistencies

If output statistics don't match [Graph Statistics](#graph-statistics):
* Filtering rules may have changed; check [process/filter_graph.py](process/filter_graph.py)
* Source data may be updated on S3; re-run full pipeline
* Recompute: `python stats/stats.py`

---

## Important Notes

* Large datasets (`.tar.zst`, JSONL outputs) are **not tracked in Git**
* All data is downloaded at runtime from public S3 (no credentials needed)
* Designed for HPC usage (disk + memory intensive)
* Pipeline is deterministic and reproducible
* Output statistics are computed fresh each run; see `stats/stats_all.txt` and `stats/stats_filtered.txt`

---

## Use Cases

* Rare disease target discovery
* Drug repurposing
* Biomedical knowledge graph embeddings
* RAG pipelines for LLMs
* Clinical decision support

---

## Code Attribution

### Orphanet Ingestion

The Orphanet ingestion code ([process/orphanet_ingest.py](process/orphanet_ingest.py) and [process/biolink_util.py](process/biolink_util.py)) was adapted from the **Translator Phase 3 Data Ingest Pipeline** (formerly maintained separately). These utilities have been streamlined for standalone use in RDKG without the full Koza/Translator framework.

The custom transformation script [process/transform_orphanet.py](process/transform_orphanet.py) is a simplified standalone implementation designed specifically for RDKG's pipeline.

---

## Contributing

Contributions are welcome! Please:

1. Open an issue to discuss proposed changes
2. Fork the repository
3. Create a feature branch
4. Submit a pull request with clear descriptions

For questions or bug reports, contact the maintainer.

---

## Maintainer

**Frankie Hodges**  
Ramsey Lab, Oregon State University  
[Contact](mailto:frankie.hodges@oregonstate.edu)

---

## Citation

If you use RDKG in your research, please cite:

```
Rare Disease Knowledge Graph (RDKG). Frankie Hodges, Ramsey Lab, Oregon State University, 2026.
Available at: https://github.com/hodgesf/RDKG
```

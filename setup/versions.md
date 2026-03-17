# Dependency Versions

This document specifies the tested Python package versions for RDKG.

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| jsonlines | 3.1.0+ | JSONL file handling |
| PyYAML | 6.0+ | Configuration parsing |
| pandas | 2.0.0+ | Data manipulation |
| numpy | 1.24.0+ | Numerical operations |
| requests | 2.31.0+ | HTTP requests |
| tqdm | 4.65.0+ | Progress bars |

## Graph & Parsing

| Package | Version | Purpose |
|---------|---------|---------|
| rdflib | 6.3.0+ | RDF graph handling |
| lxml | 4.9.0+ | XML parsing |
| xmltodict | 0.13.0+ | XML-to-dict conversion |

## Biolink & Knowledge Graph Utilities

| Package | Version | Purpose |
|---------|---------|---------|
| bmt | 1.3.0+ | Biolink model toolkit |
| linkml-runtime | 1.7.0+ | LinkML runtime support |
| curies | 0.6.0+ | CURIE handling |
| prefixcommons | 0.2.0+ | Prefix commons utilities |

## Application

| Package | Version | Purpose |
|---------|---------|---------|
| kg2-util | 2.4.0+ | KG2 utilities |

## Workflow

| Package | Version | Purpose |
|---------|---------|---------|
| snakemake | 7.32.0+ | Workflow management (optional) |

---

## Python Version

- **Minimum**: Python 3.9
- **Tested**: Python 3.9, 3.10, 3.11
- **Recommended**: Python 3.11+

## Installation

Install all dependencies with pinned versions:

```bash
pip install -r requirements.txt
```

Or upgrade to latest compatible versions:

```bash
pip install --upgrade -r requirements.txt
```

## Notes

- Versions listed are minimum tested versions; newer patch versions should be compatible
- `snakemake` is optional and only needed if using workflow orchestration
- All packages should be compatible with Python 3.9+
- For conda environments, equivalent conda packages are available with the same versions

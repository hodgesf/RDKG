#!/usr/bin/env python3

"""
Orphanet XML to KGX JSONL transformer.

This script transforms Orphanet XML files into KGX-format nodes and edges files.
It's adapted from the Translator ingest pipeline but simplified to work standalone
without the full Koza framework.

Processed files:
- en_product6.xml: Disease-gene associations
- en_product1.xml: Disease metadata and external identifiers
- en_product4.xml: Disease-phenotype (HPO) associations
- en_funct_consequences.xml: Disease-disability associations
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict
import xmltodict
import hashlib

# resolve repo root
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "files" / "data" / "orphanet"
OUTPUT_DIR = DATA_DIR

NODES_OUT = OUTPUT_DIR / "nodes.jsonl"
EDGES_OUT = OUTPUT_DIR / "edges.jsonl"

# Constants
INFORES_ORPHANET = "infores:orphanet"


def _normalize_xml_value(value: Any) -> Optional[str]:
    """Extract and normalize a value from XML, handling dictionaries with text content."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("#text", "").strip() or None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _get_gene_id(gene_dict: dict[str, Any]) -> Optional[str]:
    """Extract the HGNC-based gene ID from a gene dictionary."""
    if not gene_dict:
        return None

    external_refs = gene_dict.get("ExternalReferenceList", {}).get("ExternalReference", [])
    if not isinstance(external_refs, list):
        external_refs = [external_refs] if external_refs else []

    # Look for HGNC reference
    for ref in external_refs:
        source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        if source == "HGNC" and reference:
            return f"HGNC:{reference}"

    # Fallback: try Ensembl ID
    for ref in external_refs:
        source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        if source == "Ensembl" and reference:
            return f"ENSEMBL:{reference}"

    return None


def _get_disorder_id(disorder_dict: dict[str, Any]) -> Optional[str]:
    """Extract the Orphanet disorder ID as ORPHA CURIE."""
    orpha_code = _normalize_xml_value(disorder_dict.get("OrphaCode"))
    if orpha_code:
        return f"ORPHA:{orpha_code}"
    return None


def _get_gene_symbol(gene_dict: dict[str, Any]) -> Optional[str]:
    """Extract gene symbol from gene dictionary."""
    return _normalize_xml_value(gene_dict.get("Symbol"))


def _get_disorder_name(disorder_dict: dict[str, Any]) -> Optional[str]:
    """Extract disorder name from disorder dictionary."""
    name_dict = disorder_dict.get("Name")
    return _normalize_xml_value(name_dict)


def _extract_pmid(source_str: str) -> Optional[str]:
    """Extract PMID from source string like '22587682[PMID]'."""
    if not source_str:
        return None
    if "[PMID]" in source_str:
        pmid = source_str.replace("[PMID]", "").strip()
        if pmid and pmid.isdigit():
            return f"PMID:{pmid}"
    return None


def process_product6(nodes: dict, edges: list, xml_file: Path) -> None:
    """Process en_product6.xml (Disease-gene associations)."""
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        data = xmltodict.parse(f.read())

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    for disorder in disorder_list:
        disorder_id = _get_disorder_id(disorder)
        disorder_name = _get_disorder_name(disorder)

        if not disorder_id or not disorder_name:
            continue

        # Create disease node
        disease_node = {
            "id": disorder_id,
            "name": disorder_name,
            "category": ["biolink:Disease"],
            "provided_by": INFORES_ORPHANET
        }
        if disorder_id not in nodes:
            nodes[disorder_id] = disease_node

        # Process gene associations
        gene_list = disorder.get("GeneList", {}).get("Gene", [])
        if isinstance(gene_list, dict):
            gene_list = [gene_list]

        for gene in gene_list:
            gene_id = _get_gene_id(gene)
            gene_symbol = _get_gene_symbol(gene)

            if not gene_id or not gene_symbol:
                continue

            # Create gene node
            gene_node = {
                "id": gene_id,
                "name": gene_symbol,
                "category": ["biolink:Gene"],
                "provided_by": INFORES_ORPHANET
            }
            if gene_id not in nodes:
                nodes[gene_id] = gene_node

            # Extract association type
            gene_association_list = gene.get("GeneAssociationList", {}).get("GeneAssociation", [])
            if isinstance(gene_association_list, dict):
                gene_association_list = [gene_association_list]

            for association in gene_association_list:
                assoc_type = _normalize_xml_value(association.get("AssociationType"))
                
                # Map association types to predicates
                predicate = "biolink:contributes_to"  # Default predicate
                if assoc_type == "Disease-causing germline mutation(s) in":
                    predicate = "biolink:contributes_to"
                elif assoc_type == "Disease-causing somatic mutation(s) in":
                    predicate = "biolink:contributes_to"
                elif assoc_type == "Genetic susceptibility to":
                    predicate = "biolink:contributes_to"
                elif assoc_type == "Major susceptibility factor in":
                    predicate = "biolink:contributes_to"
                elif assoc_type == "Role in the phenotype of":
                    predicate = "biolink:contributes_to"

                # Create edge
                edge = {
                    "subject": gene_id,
                    "predicate": predicate,
                    "object": disorder_id,
                    "category": ["biolink:Association"],
                    "provided_by": INFORES_ORPHANET,
                    "attributes": {
                        "association_type": assoc_type
                    }
                }
                edges.append(edge)


def process_product1(nodes: dict, edges: list, xml_file: Path) -> None:
    """Process en_product1.xml (Disease metadata and external identifiers)."""
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        data = xmltodict.parse(f.read())

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    for disorder in disorder_list:
        disorder_id = _get_disorder_id(disorder)
        disorder_name = _get_disorder_name(disorder)

        if not disorder_id or not disorder_name:
            continue

        # Update disease node with external identifiers
        attributes = {}
        
        # Extract external identifiers (MONDO, ICD-11, OMIM, UMLS)
        external_refs = disorder.get("ExternalReferenceList", {}).get("ExternalReference", [])
        if isinstance(external_refs, dict):
            external_refs = [external_refs]

        xrefs = []
        for ref in external_refs:
            source = _normalize_xml_value(ref.get("Source"))
            ref_id = _normalize_xml_value(ref.get("Reference"))
            if source and ref_id:
                xrefs.append(f"{source.upper()}:{ref_id}")

        if xrefs:
            attributes["xrefs"] = xrefs

        # Update or create disease node with attributes
        if disorder_id in nodes:
            if "attributes" not in nodes[disorder_id]:
                nodes[disorder_id]["attributes"] = {}
            nodes[disorder_id]["attributes"].update(attributes)
        else:
            disease_node = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET,
                "attributes": attributes
            }
            nodes[disorder_id] = disease_node


def process_product4(nodes: dict, edges: list, xml_file: Path) -> None:
    """Process en_product4.xml (Disease-phenotype HPO associations)."""
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        data = xmltodict.parse(f.read())

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    for disorder in disorder_list:
        disorder_id = _get_disorder_id(disorder)
        disorder_name = _get_disorder_name(disorder)

        if not disorder_id or not disorder_name:
            continue

        # Create disease node if not exists
        if disorder_id not in nodes:
            disease_node = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET
            }
            nodes[disorder_id] = disease_node

        # Extract HPO phenotypes
        hpo_list = disorder.get("HPODisorderAssociationList", {}).get("HPODisorderAssociation", [])
        if isinstance(hpo_list, dict):
            hpo_list = [hpo_list]

        for hpo_assoc in hpo_list:
            hpo_dict = hpo_assoc.get("HPO", {})
            if not hpo_dict:
                continue

            hpo_id = _normalize_xml_value(hpo_dict.get("HPOId"))
            hpo_term = _normalize_xml_value(hpo_dict.get("HPOTerm"))

            if not hpo_id or not hpo_term:
                continue

            # Create phenotype node
            phenotype_node = {
                "id": hpo_id,
                "name": hpo_term,
                "category": ["biolink:PhenotypicFeature"],
                "provided_by": INFORES_ORPHANET
            }
            if hpo_id not in nodes:
                nodes[hpo_id] = phenotype_node

            # Create association edge
            edge = {
                "subject": disorder_id,
                "predicate": "biolink:has_phenotype",
                "object": hpo_id,
                "category": ["biolink:Association"],
                "provided_by": INFORES_ORPHANET
            }
            edges.append(edge)


def process_funct_consequences(nodes: dict, edges: list, xml_file: Path) -> None:
    """Process en_funct_consequences.xml (Disease-disability associations)."""
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        data = xmltodict.parse(f.read())

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    for disorder in disorder_list:
        disorder_id = _get_disorder_id(disorder)
        disorder_name = _get_disorder_name(disorder)

        if not disorder_id or not disorder_name:
            continue

        # Create disease node if not exists
        if disorder_id not in nodes:
            disease_node = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET
            }
            nodes[disorder_id] = disease_node

        # Extract disability associations
        disability_list = disorder.get("DisabilityDisorderAssociationList", {}).get("DisabilityDisorderAssociation", [])
        if isinstance(disability_list, dict):
            disability_list = [disability_list]

        for disability_assoc in disability_list:
            disability_entry = disability_assoc.get("Disability", {})
            if not disability_entry:
                continue

            disability_name = _normalize_xml_value(disability_entry.get("Name"))
            if not disability_name:
                continue

            # Create disability identifier using hashed name
            disability_hash = hashlib.md5(disability_name.encode()).hexdigest()[:8]
            disability_id = f"ORPHANET-DISABILITY:{disability_hash}"

            # Extract frequency, severity, and temporality
            frequency_dict = disability_assoc.get("FrequenceDisability", {})
            frequency = _normalize_xml_value(frequency_dict.get("Name"))

            severity_dict = disability_assoc.get("SeverityDisability", {})
            severity = _normalize_xml_value(severity_dict.get("Name"))

            temporality_dict = disability_assoc.get("TemporalityDisability", {})
            temporality = _normalize_xml_value(temporality_dict.get("Name"))

            # Create association edge
            edge_attributes = {"description": disability_name}
            if frequency:
                edge_attributes["frequency"] = frequency
            if severity:
                edge_attributes["severity"] = severity
            if temporality:
                edge_attributes["temporality"] = temporality

            edge = {
                "subject": disorder_id,
                "predicate": "biolink:has_disability",
                "object": disability_id,
                "category": ["biolink:Association"],
                "provided_by": INFORES_ORPHANET,
                "attributes": edge_attributes
            }
            edges.append(edge)


def main():
    """Main processing function."""
    nodes = {}
    edges = []

    print(f"Processing Orphanet XML files from {DATA_DIR}...")

    # Process each XML file
    process_product6(nodes, edges, DATA_DIR / "en_product6.xml")
    process_product1(nodes, edges, DATA_DIR / "en_product1.xml")
    process_product4(nodes, edges, DATA_DIR / "en_product4.xml")
    process_funct_consequences(nodes, edges, DATA_DIR / "en_funct_consequences.xml")

    # Write nodes to JSONL
    print(f"Writing {len(nodes)} nodes to {NODES_OUT}...")
    with open(NODES_OUT, 'w') as f:
        for node in nodes.values():
            f.write(json.dumps(node) + "\n")

    # Write edges to JSONL
    print(f"Writing {len(edges)} edges to {EDGES_OUT}...")
    with open(EDGES_OUT, 'w') as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    print(f"Orphanet transformation complete!")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")


if __name__ == "__main__":
    main()

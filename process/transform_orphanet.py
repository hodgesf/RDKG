#!/usr/bin/env python3

"""
Orphanet XML to KGX JSONL transformer.

This script transforms Orphanet XML files into KGX-format nodes and edges files.
Directly adapted from the Translator ingest pipeline's orphanet_ingest.py
but simplified to work standalone without the Koza framework.

Processed files:
- en_product6.xml: Disease-gene associations
- en_product1.xml: Disease metadata and external identifiers
- en_product4.xml: Disease-phenotype (HPO) associations
- en_funct_consequences.xml: Disease-disability associations

Based on the official Translator ingest pipeline for Orphanet.
"""

import json
import sys
import uuid
import hashlib
from pathlib import Path
from typing import Any, Optional, List, Dict
import xmltodict

# resolve repo root
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "files" / "data" / "orphanet"
OUTPUT_DIR = DATA_DIR

NODES_OUT = OUTPUT_DIR / "nodes.jsonl"
EDGES_OUT = OUTPUT_DIR / "edges.jsonl"

# Constants
INFORES_ORPHANET = "infores:orphanet"

# Mapping of association types to Biolink predicates
ASSOCIATION_TYPE_PREDICATE_MAPPING = {
    "Disease-causing germline mutation(s) in": "biolink:contributes_to",
    "Disease-causing somatic mutation(s) in": "biolink:contributes_to",
    "Genetic susceptibility to": "biolink:contributes_to",
    "Major susceptibility factor in": "biolink:contributes_to",
    "Role in the phenotype of": "biolink:contributes_to",
}

DEFAULT_PREDICATE = "biolink:contributes_to"

# Map external sources to cross-reference predicates
XREF_PREDICATES = {
    "MONDO": "biolink:equivalent_to",
    "ICD-11": "biolink:mapped_to",
    "ICD-10": "biolink:mapped_to",
    "OMIM": "biolink:equivalent_to",
    "UMLS": "biolink:equivalent_to",
    "MeSH": "biolink:mapped_to",
    "GARD": "biolink:mapped_to",
}


def _normalize_xml_value(value: Any) -> Optional[str]:
    """
    Extract and normalize a value from XML, handling dictionaries with text content.
    XML parsed by xmltodict sometimes represents simple text elements as dicts
    with '#text' key when they have attributes.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        text = value.get("#text", "").strip() or None
        return text
    if isinstance(value, str):
        return value.strip() or None
    return None


def _get_gene_id(gene_dict: Dict[str, Any]) -> Optional[str]:
    """Extract the HGNC-based gene ID from a gene dictionary."""
    if not gene_dict:
        return None

    external_refs = gene_dict.get("ExternalReferenceList", {}).get("ExternalReference", [])
    if not isinstance(external_refs, list):
        external_refs = [external_refs] if external_refs else []

    # Look for HGNC reference in external references
    for ref in external_refs:
        source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        if source == "HGNC" and reference:
            return f"HGNC:{reference}"

    # Fallback: try to use Ensembl ID
    for ref in external_refs:
        source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        if source == "Ensembl" and reference:
            return f"ENSEMBL:{reference}"

    return None


def _get_disorder_id(disorder_dict: Dict[str, Any]) -> Optional[str]:
    """Extract the Orphanet disorder ID as ORPHA CURIE."""
    orpha_code = _normalize_xml_value(disorder_dict.get("OrphaCode"))
    if orpha_code:
        return f"ORPHA:{orpha_code}"
    return None


def _get_gene_symbol(gene_dict: Dict[str, Any]) -> Optional[str]:
    """Extract gene symbol from gene dictionary."""
    return _normalize_xml_value(gene_dict.get("Symbol"))


def _get_disorder_name(disorder_dict: Dict[str, Any]) -> Optional[str]:
    """Extract disorder name from disorder dictionary."""
    name_dict = disorder_dict.get("Name")
    return _normalize_xml_value(name_dict)


def _extract_pmid(source_str: str) -> Optional[str]:
    """Extract PMID from source string like '22587682[PMID]'."""
    if not source_str:
        return None
    # Handle format like "22587682[PMID]"
    if "[PMID]" in source_str:
        pmid = source_str.replace("[PMID]", "").strip()
        return f"PMID:{pmid}" if pmid else None
    return None


def _get_publications(source_of_validation: str) -> Optional[List[str]]:
    """Extract publications from source of validation field."""
    if not source_of_validation:
        return None

    publications = []
    # Handle multiple PMIDs separated by pipe
    sources = source_of_validation.split("|")
    for source in sources:
        pmid = _extract_pmid(source.strip())
        if pmid:
            publications.append(pmid)

    return publications if publications else None


def _get_external_identifier(disorder_dict: Dict[str, Any], source: str) -> Optional[str]:
    """Extract a specific external identifier from a disorder dictionary."""
    ext_ref_list = disorder_dict.get("ExternalReferenceList", {}).get("ExternalReference", [])
    if not isinstance(ext_ref_list, list):
        ext_ref_list = [ext_ref_list] if ext_ref_list else []

    for ref in ext_ref_list:
        ref_source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        if ref_source == source and reference:
            return reference
    return None


def process_product6(nodes: Dict, edges: List, xml_file: Path) -> None:
    """
    Process en_product6.xml (Disease-gene associations).
    
    Creates gene and disease nodes, plus GeneToDiseaseAssociation edges
    with appropriate relationship types based on the association classification.
    """
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            data = xmltodict.parse(f.read())
    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    print(f"  Found {len(disorder_list)} disorders")
    
    edges_created = 0
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

        # Process disorder-gene associations
        disorder_gene_list = disorder.get("DisorderGeneAssociationList", {})
        if not disorder_gene_list:
            continue
            
        gene_associations = disorder_gene_list.get("DisorderGeneAssociation", [])
        if isinstance(gene_associations, dict):
            gene_associations = [gene_associations]

        for gene_assoc in gene_associations:
            gene_dict = gene_assoc.get("Gene", {})
            if not gene_dict:
                continue

            gene_id = _get_gene_id(gene_dict)
            gene_symbol = _get_gene_symbol(gene_dict)

            if not gene_id:
                print(f"  Warning: Could not extract gene ID for disorder {disorder_id}")
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

            # Extract association details
            assoc_type_dict = gene_assoc.get("DisorderGeneAssociationType", {})
            assoc_type = _normalize_xml_value(assoc_type_dict.get("Name"))

            # Get predicate from mapping, or use default
            predicate = ASSOCIATION_TYPE_PREDICATE_MAPPING.get(assoc_type, DEFAULT_PREDICATE)

            # Extract publications
            source_of_validation = _normalize_xml_value(gene_assoc.get("SourceOfValidation"))
            publications = _get_publications(source_of_validation)

            # Create edge
            edge = {
                "id": str(uuid.uuid4()),
                "subject": gene_id,
                "predicate": predicate,
                "object": disorder_id,
                "category": ["biolink:Association"],
                "provided_by": INFORES_ORPHANET,
                "knowledge_level": "assertion",
                "agent_type": "manual_agent"
            }
            
            # Add attributes
            attributes = {}
            if assoc_type:
                attributes["association_type"] = assoc_type
            if publications:
                attributes["publications"] = publications
            
            if attributes:
                edge["attributes"] = attributes
                
            edges.append(edge)
            edges_created += 1
    
    print(f"  Created {edges_created} gene-disease edges")


def process_product1(nodes: Dict, edges: List, xml_file: Path) -> None:
    """
    Process en_product1.xml (Disease metadata with external references).
    
    Maps external disease identifiers (MONDO, ICD-11, OMIM, UMLS, etc.) to disease nodes
    by creating cross-reference edges or adding attributes.
    """
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            data = xmltodict.parse(f.read())
    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return

    disorder_list = data.get("JDBOR", {}).get("DisorderList", {}).get("Disorder", [])
    if isinstance(disorder_list, dict):
        disorder_list = [disorder_list]

    print(f"  Found {len(disorder_list)} disorders")
    
    xref_edges_created = 0
    for disorder in disorder_list:
        disorder_id = _get_disorder_id(disorder)
        disorder_name = _get_disorder_name(disorder)

        if not disorder_id or not disorder_name:
            continue

        # Create or update disease node
        if disorder_id not in nodes:
            nodes[disorder_id] = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET
            }

        # Extract external references and create cross-reference information
        ext_ref_list = disorder.get("ExternalReferenceList", {}).get("ExternalReference", [])
        if not isinstance(ext_ref_list, list):
            ext_ref_list = [ext_ref_list] if ext_ref_list else []

        xrefs = []
        for ref in ext_ref_list:
            source = _normalize_xml_value(ref.get("Source"))
            reference = _normalize_xml_value(ref.get("Reference"))
            
            if not source or not reference:
                continue

            xref_id = f"{source}:{reference}"
            xrefs.append(xref_id)

            # Create optional cross-reference edge (only for key sources)
            if source in XREF_PREDICATES:
                predicate = XREF_PREDICATES[source]
                xref_edge = {
                    "id": str(uuid.uuid4()),
                    "subject": disorder_id,
                    "predicate": predicate,
                    "object": xref_id,
                    "category": ["biolink:Association"],
                    "provided_by": INFORES_ORPHANET,
                    "knowledge_level": "assertion",
                    "agent_type": "manual_agent"
                }
                edges.append(xref_edge)
                xref_edges_created += 1

        # Add xrefs as node attributes
        if xrefs:
            if "attributes" not in nodes[disorder_id]:
                nodes[disorder_id]["attributes"] = {}
            nodes[disorder_id]["attributes"]["xrefs"] = xrefs
    
    print(f"  Created {xref_edges_created} cross-reference edges")


def process_product4(nodes: Dict, edges: List, xml_file: Path) -> None:
    """
    Process en_product4.xml (Disease-phenotype HPO associations).
    
    Creates DiseaseToPhenotypicFeatureAssociation edges between diseases and HPO terms.
    Includes frequency information if available.
    """
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            data = xmltodict.parse(f.read())
    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return

    hpo_status_list = data.get("JDBOR", {}).get("HPODisorderSetStatusList", {}).get("HPODisorderSetStatus", [])
    if isinstance(hpo_status_list, dict):
        hpo_status_list = [hpo_status_list]

    print(f"  Found {len(hpo_status_list)} disease-phenotype entries")
    
    phenotype_edges_created = 0
    for hpo_entry in hpo_status_list:
        disorder_entry = hpo_entry.get("Disorder", {})
        if not disorder_entry:
            continue

        disorder_id = _get_disorder_id(disorder_entry)
        disorder_name = _get_disorder_name(disorder_entry)

        if not disorder_id or not disorder_name:
            continue

        # Create disease node if not exists
        if disorder_id not in nodes:
            nodes[disorder_id] = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET
            }

        # Extract HPO associations
        hpo_assoc_list = hpo_entry.get("HPODisorderAssociationList", {})
        if not hpo_assoc_list:
            continue

        hpo_assocs = hpo_assoc_list.get("HPODisorderAssociation", [])
        if isinstance(hpo_assocs, dict):
            hpo_assocs = [hpo_assocs]

        for hpo_assoc in hpo_assocs:
            hpo_dict = hpo_assoc.get("HPO", {})
            if not hpo_dict:
                continue

            hpo_id = _normalize_xml_value(hpo_dict.get("HPOId"))
            hpo_term = _normalize_xml_value(hpo_dict.get("HPOTerm"))

            if not hpo_id:
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

            # Extract frequency information
            frequency_dict = hpo_assoc.get("HPOFrequency", {})
            frequency = _normalize_xml_value(frequency_dict.get("Name"))

            # Create disease-phenotype association
            phenotype_edge = {
                "id": str(uuid.uuid4()),
                "subject": disorder_id,
                "predicate": "biolink:has_phenotype",
                "object": hpo_id,
                "category": ["biolink:Association"],
                "provided_by": INFORES_ORPHANET,
                "knowledge_level": "assertion",
                "agent_type": "manual_agent"
            }

            if frequency:
                phenotype_edge["attributes"] = {
                    "frequency": frequency
                }

            edges.append(phenotype_edge)
            phenotype_edges_created += 1
    
    print(f"  Created {phenotype_edges_created} disease-phenotype edges")


def process_funct_consequences(nodes: Dict, edges: List, xml_file: Path) -> None:
    """
    Process en_funct_consequences.xml (Disease-disability associations).
    
    Creates edges linking diseases to functional consequences/disabilities,
    with frequency, severity, and temporality information.
    """
    if not xml_file.exists():
        print(f"Warning: {xml_file} not found, skipping")
        return

    print(f"Processing {xml_file.name}...")
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            data = xmltodict.parse(f.read())
    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return

    disability_list = data.get("JDBOR", {}).get("DisorderDisabilityRelevanceList", {}).get("DisorderDisabilityRelevance", [])
    if isinstance(disability_list, dict):
        disability_list = [disability_list]

    print(f"  Found {len(disability_list)} disease-disability entries")
    
    disability_edges_created = 0
    for disability_entry in disability_list:
        disorder_entry = disability_entry.get("Disorder", {})
        if not disorder_entry:
            continue

        disorder_id = _get_disorder_id(disorder_entry)
        disorder_name = _get_disorder_name(disorder_entry)

        if not disorder_id or not disorder_name:
            continue

        # Create disease node if not exists
        if disorder_id not in nodes:
            nodes[disorder_id] = {
                "id": disorder_id,
                "name": disorder_name,
                "category": ["biolink:Disease"],
                "provided_by": INFORES_ORPHANET
            }

        # Extract disability associations
        disability_list_assoc = disability_entry.get("DisabilityDisorderAssociationList", {}).get("DisabilityDisorderAssociation", [])
        if isinstance(disability_list_assoc, dict):
            disability_list_assoc = [disability_list_assoc]

        for disability_assoc in disability_list_assoc:
            disability_entry_item = disability_assoc.get("Disability", {})
            if not disability_entry_item:
                continue

            disability_name = _normalize_xml_value(disability_entry_item.get("Name"))
            if not disability_name:
                continue

            # Create a disability identifier using the name (hashed to avoid long URIs)
            disability_hash = hashlib.md5(disability_name.encode()).hexdigest()[:8]
            disability_id = f"ORPHANET-DISABILITY:{disability_hash}"

            # Extract severity, frequency, and temporality
            frequency_dict = disability_assoc.get("FrequenceDisability", {})
            frequency = _normalize_xml_value(frequency_dict.get("Name"))

            severity_dict = disability_assoc.get("SeverityDisability", {})
            severity = _normalize_xml_value(severity_dict.get("Name"))

            temporality_dict = disability_assoc.get("TemporalityDisability", {})
            temporality = _normalize_xml_value(temporality_dict.get("Name"))

            # Create association edge linking disease to disability
            disability_edge = {
                "id": str(uuid.uuid4()),
                "subject": disorder_id,
                "predicate": "biolink:has_disability",
                "object": disability_id,
                "category": ["biolink:Association"],
                "provided_by": INFORES_ORPHANET,
                "knowledge_level": "assertion",
                "agent_type": "manual_agent"
            }

            # Add attributes for disability details
            attributes = {"description": disability_name}
            if frequency:
                attributes["frequency"] = frequency
            if severity:
                attributes["severity"] = severity
            if temporality:
                attributes["temporality"] = temporality

            disability_edge["attributes"] = attributes
            edges.append(disability_edge)
            disability_edges_created += 1
    
    print(f"  Created {disability_edges_created} disease-disability edges")


def main():
    """Main processing function."""
    nodes: Dict = {}
    edges: List = []

    print(f"\nProcessing Orphanet XML files from {DATA_DIR}...\n")

    # Process each XML file
    process_product6(nodes, edges, DATA_DIR / "en_product6.xml")
    process_product1(nodes, edges, DATA_DIR / "en_product1.xml")
    process_product4(nodes, edges, DATA_DIR / "en_product4.xml")
    process_funct_consequences(nodes, edges, DATA_DIR / "en_funct_consequences.xml")

    # Write nodes to JSONL
    print(f"\nWriting {len(nodes)} nodes to {NODES_OUT}...")
    with open(NODES_OUT, 'w') as f:
        for node in nodes.values():
            f.write(json.dumps(node) + "\n")

    # Write edges to JSONL
    print(f"Writing {len(edges)} edges to {EDGES_OUT}...")
    with open(EDGES_OUT, 'w') as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    print(f"\nOrphanet transformation complete!")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}\n")


if __name__ == "__main__":
    main()

"""
Orphanet ingest: transforms Orphanet XML disease data into KGX format.

This ingest processes multiple Orphanet XML product files, which contain rare disease
information including disease-gene associations, phenotypes, and functional consequences.

Supported files:
- en_product6.xml: Disease-gene associations
- en_product1.xml: Disease metadata and external identifiers
- en_product4.xml: Disease-phenotype (HPO) associations
- en_funct_consequences.xml: Disease-disability associations

Key features:
- Extracts Disease and Gene nodes from Orphanet XML
- Creates GeneToDiseaseAssociation edges with appropriate relationship types
- Maps external disease identifiers (MONDO, ICD-11, OMIM, UMLS) to disease nodes
- Extracts HPO phenotype associations
- Extracts disability/functional consequence associations
- Associates publications and validation information with edges
"""

from typing import Any, Iterable
from pathlib import Path
import xmltodict
import requests

import koza
from koza.model.graphs import KnowledgeGraph

from biolink_model.datamodel.pydanticmodel_v2 import (
    Disease,
    Gene,
    GeneToDiseaseAssociation,
    PhenotypicFeature,
    DiseaseToPhenotypicFeatureAssociation,
    Association,
    KnowledgeLevelEnum,
    AgentTypeEnum,
)
from bmt.pydantic import entity_id, build_association_knowledge_sources
from translator_ingest.util.biolink import INFORES_ORPHANET

# Mapping of association types to Biolink predicates
# GeneToDiseaseAssociation only allows: biolink:contributes_to or biolink:associated_with
# We use contributes_to for disease-causing mutations and susceptibility factors
ASSOCIATION_TYPE_PREDICATE_MAPPING = {
    "Disease-causing germline mutation(s) in": "biolink:contributes_to",
    "Disease-causing somatic mutation(s) in": "biolink:contributes_to",
    "Genetic susceptibility to": "biolink:contributes_to",
    "Major susceptibility factor in": "biolink:contributes_to",
    "Role in the phenotype of": "biolink:contributes_to",
}

# Default predicate if association type is not in mapping
DEFAULT_PREDICATE = "biolink:contributes_to"


def get_latest_version() -> str:
    """
    Fetch the version from Orphanet data file metadata.

    Attempts to fetch the file and extract version information from HTTP headers
    or fallback to current date in YYYY-MM-DD format.
    """
    try:
        response = requests.head(
            "https://www.orphadata.com/data/xml/en_product6.xml",
            timeout=10,
            allow_redirects=True,
        )
        response.raise_for_status()
        # Use Last-Modified header if available
        if "Last-Modified" in response.headers:
            from email.utils import parsedate_to_datetime
            modified_date = parsedate_to_datetime(response.headers["Last-Modified"])
            return modified_date.strftime("%Y-%m-%d")
    except requests.RequestException:
        pass

    # Fallback: use current date
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_xml_value(value: Any) -> str | None:
    """
    Extract and normalize a value from XML, handling dictionaries with text content.

    XML parsed by xmltodict sometimes represents simple text elements as dicts
    with '#text' key when they have attributes.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("#text", "").strip() or None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _get_gene_id(gene_dict: dict[str, Any]) -> str | None:
    """Extract the HGNC-based gene ID from a gene dictionary."""
    if not gene_dict:
        return None

    # Look for HGNC reference in external references
    external_refs = gene_dict.get("ExternalReferenceList", {}).get("ExternalReference", [])
    if not isinstance(external_refs, list):
        external_refs = [external_refs] if external_refs else []

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


def _get_disorder_id(disorder_dict: dict[str, Any]) -> str | None:
    """Extract the Orphanet disorder ID as ORPHA CURIE."""
    orpha_code = _normalize_xml_value(disorder_dict.get("OrphaCode"))
    if orpha_code:
        return f"ORPHA:{orpha_code}"
    return None


def _get_gene_symbol(gene_dict: dict[str, Any]) -> str | None:
    """Extract gene symbol from gene dictionary."""
    return _normalize_xml_value(gene_dict.get("Symbol"))


def _get_disorder_name(disorder_dict: dict[str, Any]) -> str | None:
    """Extract disorder name from disorder dictionary."""
    name_dict = disorder_dict.get("Name")
    return _normalize_xml_value(name_dict)


def _extract_pmid(source_str: str) -> str | None:
    """Extract PMID from source string like '22587682[PMID]'."""
    if not source_str:
        return None
    # Handle format like "22587682[PMID]"
    if "[PMID]" in source_str:
        pmid = source_str.replace("[PMID]", "").strip()
        return f"PMID:{pmid}" if pmid else None
    return None


def _get_publications(source_of_validation: str) -> list[str] | None:
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


def _get_external_identifier(disorder_dict: dict[str, Any], source: str) -> str | None:
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


@koza.transform_record()
def transform_orphanet_record(koza: koza.KozaTransform, record: dict[str, Any]) -> KnowledgeGraph | None:
    """
    Route records to appropriate transform function based on file type.
    """
    file_type = record.get("file_type")
    data = record.get("data")

    if file_type == "product6":
        return transform_product6_disease_gene(koza, data)
    elif file_type == "product1":
        return transform_product1_disease_metadata(koza, data)
    elif file_type == "product4":
        return transform_product4_hpo(koza, data)
    elif file_type == "funct_consequences":
        return transform_funct_consequences(koza, data)

    return None


@koza.prepare_data()
def prepare_orphanet_data(
    koza: koza.KozaTransform, data: Iterable[dict[str, Any]]
) -> Iterable[dict[str, Any]]:
    """
    Prepare Orphanet XML data by parsing all available XML files and yielding records.

    This function handles multiple Orphanet product XML formats:
    - Product6: Disease-gene associations
    - Product1: Disease metadata with external references
    - Product4: Disease-HPO phenotype associations
    - FunctConsequences: Disease-disability associations
    """
    input_dir = Path(koza.input_files_dir)

    # Process en_product6.xml - Disease-Gene associations
    product6_path = input_dir / "en_product6.xml"
    if product6_path.exists():
        koza.log(f"Processing Product6 (Disease-Gene) from {product6_path}")
        try:
            with open(product6_path, "r", encoding="utf-8") as f:
                xml_dict = xmltodict.parse(f.read())
            root = xml_dict.get("JDBOR", {})
            disorder_list = root.get("DisorderList", {}).get("Disorder", [])
            if isinstance(disorder_list, dict):
                disorder_list = [disorder_list]
            koza.log(f"Found {len(disorder_list)} disorders in Product6")
            for disorder in disorder_list:
                yield {"file_type": "product6", "data": disorder}
        except Exception as e:
            koza.log(f"Error parsing Product6: {e}", level="ERROR")

    # Process en_product1.xml - Disease metadata with external references
    product1_path = input_dir / "en_product1.xml"
    if product1_path.exists():
        koza.log(f"Processing Product1 (Disease metadata) from {product1_path}")
        try:
            with open(product1_path, "r", encoding="utf-8") as f:
                xml_dict = xmltodict.parse(f.read())
            root = xml_dict.get("JDBOR", {})
            disorder_list = root.get("DisorderList", {}).get("Disorder", [])
            if isinstance(disorder_list, dict):
                disorder_list = [disorder_list]
            koza.log(f"Found {len(disorder_list)} disorders in Product1")
            for disorder in disorder_list:
                yield {"file_type": "product1", "data": disorder}
        except Exception as e:
            koza.log(f"Error parsing Product1: {e}", level="ERROR")

    # Process en_product4.xml - Disease-HPO phenotype associations
    product4_path = input_dir / "en_product4.xml"
    if product4_path.exists():
        koza.log(f"Processing Product4 (HPO associations) from {product4_path}")
        try:
            with open(product4_path, "r", encoding="utf-8") as f:
                xml_dict = xmltodict.parse(f.read())
            root = xml_dict.get("JDBOR", {})
            hpo_status_list = root.get("HPODisorderSetStatusList", {}).get("HPODisorderSetStatus", [])
            if isinstance(hpo_status_list, dict):
                hpo_status_list = [hpo_status_list]
            koza.log(f"Found {len(hpo_status_list)} disease-phenotype entries in Product4")
            for hpo_entry in hpo_status_list:
                yield {"file_type": "product4", "data": hpo_entry}
        except Exception as e:
            koza.log(f"Error parsing Product4: {e}", level="ERROR")

    # Process en_funct_consequences.xml - Disease-disability associations
    funct_path = input_dir / "en_funct_consequences.xml"
    if funct_path.exists():
        koza.log(f"Processing FunctConsequences (Disability associations) from {funct_path}")
        try:
            with open(funct_path, "r", encoding="utf-8") as f:
                xml_dict = xmltodict.parse(f.read())
            root = xml_dict.get("JDBOR", {})
            disability_list = root.get("DisorderDisabilityRelevanceList", {}).get("DisorderDisabilityRelevance", [])
            if isinstance(disability_list, dict):
                disability_list = [disability_list]
            koza.log(f"Found {len(disability_list)} disease-disability entries in FunctConsequences")
            for disability_entry in disability_list:
                yield {"file_type": "funct_consequences", "data": disability_entry}
        except Exception as e:
            koza.log(f"Error parsing FunctConsequences: {e}", level="ERROR")


def transform_product6_disease_gene(koza: koza.KozaTransform, record: dict[str, Any]) -> KnowledgeGraph | None:
    """
    Transform Product6 disorder record into disease-gene associations.

    Each disorder may have multiple gene associations, so we create one KnowledgeGraph
    containing the disease node and multiple gene nodes with association edges.
    """
    # Extract disease information
    disorder_id = _get_disorder_id(record)
    disorder_name = _get_disorder_name(record)

    if not disorder_id or not disorder_name:
        return None

    disease_node = Disease(id=disorder_id, name=disorder_name)
    nodes = [disease_node]
    edges = []

    # Extract gene associations
    gene_assoc_list = record.get("DisorderGeneAssociationList", {})
    if not gene_assoc_list:
        # No gene associations, return just the disease node
        return KnowledgeGraph(nodes=nodes, edges=[])

    associations = gene_assoc_list.get("DisorderGeneAssociation", [])
    # Ensure associations is a list
    if isinstance(associations, dict):
        associations = [associations]

    for assoc in associations:
        gene_dict = assoc.get("Gene")
        if not gene_dict:
            continue

        gene_id = _get_gene_id(gene_dict)
        gene_symbol = _get_gene_symbol(gene_dict)

        if not gene_id:
            koza.log(f"Could not extract gene ID for disorder {disorder_id}", level="WARNING")
            continue

        # Create gene node
        gene_node = Gene(id=gene_id, name=gene_symbol)
        nodes.append(gene_node)

        # Extract association details
        assoc_type_dict = assoc.get("DisorderGeneAssociationType", {})
        assoc_type = _normalize_xml_value(assoc_type_dict.get("Name"))

        # Get predicate from mapping, or use default
        predicate = ASSOCIATION_TYPE_PREDICATE_MAPPING.get(assoc_type, DEFAULT_PREDICATE)

        # Extract publications
        source_of_validation = _normalize_xml_value(assoc.get("SourceOfValidation"))
        publications = _get_publications(source_of_validation)

        # Create association edge
        gene_assoc = GeneToDiseaseAssociation(
            id=entity_id(),
            subject=gene_id,
            predicate=predicate,
            object=disorder_id,
            sources=build_association_knowledge_sources(primary=INFORES_ORPHANET),
            knowledge_level=KnowledgeLevelEnum.knowledge_assertion,
            agent_type=AgentTypeEnum.manual_agent,
        )

        if publications:
            gene_assoc.publications = publications

        edges.append(gene_assoc)

    if edges:
        return KnowledgeGraph(nodes=nodes, edges=edges)

    # Return just disease node if no valid gene associations
    return KnowledgeGraph(nodes=nodes, edges=[])


def transform_product1_disease_metadata(koza: koza.KozaTransform, record: dict[str, Any]) -> KnowledgeGraph | None:
    """
    Transform Product1 disorder record to create disease nodes with cross-reference edges.

    Product1 contains disease metadata including mappings to external resources
    like MONDO, ICD-11, ICD-10, OMIM, UMLS, and MeSH.
    
    Creates edges to external database identifiers.
    """
    disorder_id = _get_disorder_id(record)
    disorder_name = _get_disorder_name(record)

    if not disorder_id or not disorder_name:
        return None

    # Create disease node
    disease_node = Disease(id=disorder_id, name=disorder_name)
    nodes = [disease_node]
    edges = []

    # Extract external references and create edges
    ext_ref_list = record.get("ExternalReferenceList", {}).get("ExternalReference", [])
    if not isinstance(ext_ref_list, list):
        ext_ref_list = [ext_ref_list] if ext_ref_list else []

    # Map external sources to predicates
    xref_predicates = {
        "MONDO": "biolink:equivalent_to",
        "ICD-11": "biolink:mapped_to",
        "ICD-10": "biolink:mapped_to",
        "OMIM": "biolink:equivalent_to",
        "UMLS": "biolink:equivalent_to",
        "MeSH": "biolink:mapped_to",
        "GARD": "biolink:mapped_to",
    }

    for ref in ext_ref_list:
        source = _normalize_xml_value(ref.get("Source"))
        reference = _normalize_xml_value(ref.get("Reference"))
        
        if not source or not reference:
            continue

        # Create external identifier node
        ext_id = f"{source}:{reference}"
        ext_node_id = ext_id  # Use the full CURIE as the ID

        # Get predicate from mapping
        predicate = xref_predicates.get(source, "biolink:mapped_to")

        # Create cross-reference edge
        xref_edge = Association(
            id=entity_id(),
            subject=disorder_id,
            predicate=predicate,
            object=ext_node_id,
            sources=build_association_knowledge_sources(primary=INFORES_ORPHANET),
            knowledge_level=KnowledgeLevelEnum.knowledge_assertion,
            agent_type=AgentTypeEnum.manual_agent,
        )
        edges.append(xref_edge)

    if edges:
        return KnowledgeGraph(nodes=nodes, edges=edges)
    
    return KnowledgeGraph(nodes=nodes, edges=[])


def transform_product4_hpo(koza: koza.KozaTransform, record: dict[str, Any]) -> KnowledgeGraph | None:
    """
    Transform Product4 HPO-disorder associations into disease-phenotype edges.

    Creates DiseaseToPhenotypicFeatureAssociation edges between diseases and HPO terms.
    """
    # Extract disorder information from the entry
    disorder_entry = record.get("Disorder", {})
    if not disorder_entry:
        return None

    disorder_id = _get_disorder_id(disorder_entry)
    disorder_name = _get_disorder_name(disorder_entry)

    if not disorder_id or not disorder_name:
        return None

    disease_node = Disease(id=disorder_id, name=disorder_name)
    nodes = [disease_node]
    edges = []

    # Extract HPO associations
    hpo_assoc_list = record.get("HPODisorderAssociationList", {})
    if not hpo_assoc_list:
        return KnowledgeGraph(nodes=nodes, edges=[])

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
        phenotype_node = PhenotypicFeature(id=hpo_id, name=hpo_term)
        nodes.append(phenotype_node)

        # Extract frequency information
        frequency_dict = hpo_assoc.get("HPOFrequency", {})
        frequency = _normalize_xml_value(frequency_dict.get("Name"))

        # Create disease-phenotype association
        hpo_assoc_edge = DiseaseToPhenotypicFeatureAssociation(
            id=entity_id(),
            subject=disorder_id,
            predicate="biolink:has_phenotype",
            object=hpo_id,
            sources=build_association_knowledge_sources(primary=INFORES_ORPHANET),
            knowledge_level=KnowledgeLevelEnum.knowledge_assertion,
            agent_type=AgentTypeEnum.manual_agent,
        )

        if frequency:
            # Store frequency as an attribute
            if not hpo_assoc_edge.attributes:
                hpo_assoc_edge.attributes = []
            hpo_assoc_edge.attributes.append({
                "attribute_type_id": "biolink:frequency",
                "value": frequency
            })

        edges.append(hpo_assoc_edge)

    if edges:
        return KnowledgeGraph(nodes=nodes, edges=edges)

    return KnowledgeGraph(nodes=nodes, edges=[])


def transform_funct_consequences(koza: koza.KozaTransform, record: dict[str, Any]) -> KnowledgeGraph | None:
    """
    Transform FunctConsequences disability-disorder associations.

    Creates edges linking diseases to functional consequences/disabilities.
    """
    disorder_entry = record.get("Disorder", {})
    if not disorder_entry:
        return None

    disorder_id = _get_disorder_id(disorder_entry)
    disorder_name = _get_disorder_name(disorder_entry)

    if not disorder_id or not disorder_name:
        return None

    disease_node = Disease(id=disorder_id, name=disorder_name)
    nodes = [disease_node]
    edges = []

    # Extract disability associations
    disability_list = record.get("DisabilityDisorderAssociationList", {}).get("DisabilityDisorderAssociation", [])
    if isinstance(disability_list, dict):
        disability_list = [disability_list]

    for disability_assoc in disability_list:
        disability_entry = disability_assoc.get("Disability", {})
        if not disability_entry:
            continue

        disability_name = _normalize_xml_value(disability_entry.get("Name"))
        if not disability_name:
            continue

        # Create a disability identifier using the name (hashed to avoid long URIs)
        import hashlib
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
        disability_edge = Association(
            id=entity_id(),
            subject=disorder_id,
            predicate="biolink:has_disability",  # Custom predicate for disability
            object=disability_id,
            sources=build_association_knowledge_sources(primary=INFORES_ORPHANET),
            knowledge_level=KnowledgeLevelEnum.knowledge_assertion,
            agent_type=AgentTypeEnum.manual_agent,
        )

        # Add attributes for disability details
        if not disability_edge.attributes:
            disability_edge.attributes = []
        
        if frequency:
            disability_edge.attributes.append({
                "attribute_type_id": "biolink:frequency",
                "value": frequency
            })
        if severity:
            disability_edge.attributes.append({
                "attribute_type_id": "biolink:severity",
                "value": severity
            })
        if temporality:
            disability_edge.attributes.append({
                "attribute_type_id": "biolink:temporality",
                "value": temporality
            })

        # Store disability name in edge
        disability_edge.attributes.append({
            "attribute_type_id": "biolink:description",
            "value": disability_name
        })

        edges.append(disability_edge)

    if edges:
        return KnowledgeGraph(nodes=nodes, edges=edges)

    return KnowledgeGraph(nodes=nodes, edges=[])

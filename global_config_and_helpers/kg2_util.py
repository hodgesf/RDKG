import pathlib
import ssl
import tempfile
import urllib.request
import shutil
import yaml
import os
import jsonlines
import datetime

CURIE_PREFIX_BIOLINK_SOURCE = 'biolink_download_source'
SOURCE_NODE_CATEGORY = 'retrieval source'
BIOLINK_CATEGORY_NAMED_THING = 'named thing'
CURIE_PREFIX_BIOLINK_SOURCE = 'biolink_download_source'
CURIE_PREFIX_OBO = 'OBO'
CURIE_PREFIX_BIOLINK = 'biolink'
NODE_ID_SLOT = 'id'
NODE_IRI_SLOT = 'iri'
NODE_NAME_SLOT = 'name'
NODE_PUBLICATIONS_SLOT = 'publications'
NODE_DESCRIPTION_SLOT = 'description'
NODE_NAME_SLOT = 'name'
NODE_CATEGORY_SLOT = 'category'
NODE_SYNONYM_SLOT = 'synonym'
NODE_SAME_AS_SLOT = 'same_as' # NOTE: to align with current KGX compliace, see issue #494 
NODE_TAXON_SLOT = 'in_taxon' # NOTE: Not yet in Biolink, see issue #468
NODE_FULL_NAME_SLOT = 'full_name'
NODE_CATEGORY_LABEL_SLOT = 'category_label'
NODE_CREATION_DATE_SLOT = 'creation_date'
NODE_UPDATE_DATE_SLOT = 'update_date'
NODE_DEPRECATED_SLOT = 'deprecated'
NODE_REPLACED_BY_SLOT = 'replaced_by'
NODE_PROVIDED_BY_SLOT = 'provided_by'
NODE_HAS_BIOLOGICAL_SEQUENCE_SLOT = 'has_biological_sequence'
NODE_ALL_NAMES_SLOT = 'all_names'
NODE_ALL_CATEGORIES_SLOT = 'all_categories'

EDGE_ID_SLOT = 'id'
EDGE_KG2_IDS_SLOT = 'kg2_ids'
EDGE_SUBJECT_SLOT = 'subject'
EDGE_OBJECT_SLOT = 'object'
EDGE_PREDICATE_SLOT = 'predicate'
EDGE_AGENT_TYPE_SLOT = 'agent_type'
EDGE_KNOWLEDGE_LEVEL_SLOT = 'knowledge_level'
EDGE_PRIMARY_KNOWLEDGE_SOURCE_SLOT = 'primary_knowledge_source'
EDGE_DOMAIN_RANGE_EXCLUSION_SLOT = 'domain_range_exclusion'
EDGE_QUALIFIED_PREDICATE_SLOT = 'qualified_predicate'
EDGE_OBJECT_DIRECTION_QUALIFIER_SLOT = 'object_direction_qualifier'
EDGE_OBJECT_ASPECT_QUALIFIER_SLOT = 'object_aspect_qualifier'
EDGE_PUBLICATIONS_SLOT = 'publications'
EDGE_PUBLICATIONS_INFO_SLOT = 'publications_info'
EDGE_RELATION_LABEL_SLOT = 'relation_label'
EDGE_SOURCE_PREDICATE_SLOT = 'source_predicate'
EDGE_NEGATED_SLOT = 'negated'
EDGE_UPDATE_DATE_SLOT = 'update_date'
CURIE_PREFIX_RTX = 'RTX'
BASE_URL_RTX = 'http://rtx.ai/identifiers#'
BIOLINK_CATEGORY_RETRIEVAL_SOURCE = 'retrieval source'
SOURCE_NODE_CATEGORY = BIOLINK_CATEGORY_RETRIEVAL_SOURCE

def end_read_jsonlines(read_jsonlines_info):
    (_, jsonlines_reader, file) = read_jsonlines_info
    file.close()
    jsonlines_reader.close()

def cap(word):
    return word[0].upper() + word[1:]

def title_preserving_caps(string):
    return " ".join(map(cap, string.split(' ')))

def convert_space_case_to_camel_case(name: str):
    return title_preserving_caps(name).replace(' ', '')
    
def download_file_if_not_exist_locally(url: str, local_file_name: str):
    if url is None:
        return local_file_name

    path = pathlib.Path(local_file_name)
    if path.exists():
        return local_file_name

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    fd, tmp = tempfile.mkstemp(prefix="kg2-")

    with urllib.request.urlopen(req, context=ctx) as r, os.fdopen(fd, "wb") as f:
        shutil.copyfileobj(r, f)

    shutil.move(tmp, local_file_name)

    return local_file_name

def read_file_to_string(path: str):
    with open(path) as f:
        return f.read()


def safe_load_yaml_from_string(yaml_string: str):
    return yaml.safe_load(yaml_string)



def create_single_jsonlines(test_mode: bool = False):
    sort_keys = not test_mode

    fd, path = tempfile.mkstemp(prefix="kg2-")
    file = os.fdopen(fd, "w")

    writer = jsonlines.Writer(file, sort_keys=sort_keys)

    return writer, file, path


def close_single_jsonlines(info, output_file_name):
    writer, file, path = info

    writer.close()
    file.close()

    shutil.move(path, output_file_name)


def make_edge_key(edge_dict: dict):
    return edge_dict['subject'] + '---' + \
           edge_dict['source_predicate'] + '---' + \
           (edge_dict['qualified_predicate'] if edge_dict['qualified_predicate'] is not None else 'None') + \
           '---' + \
           (edge_dict['object_aspect_qualifier'] if edge_dict['object_aspect_qualifier'] is not None else 'None') + \
           '---' + \
           (edge_dict['object_direction_qualifier'] if edge_dict['object_direction_qualifier'] is not None else 'None') + \
           '---' + \
           edge_dict['object'] + '---' + \
           edge_dict['primary_knowledge_source']


def make_edge(subject_id: str,
              object_id: str,
              relation_curie: str,
              relation_label: str,
              primary_knowledge_source: str,
              update_date: str = None):

    edge = {
        EDGE_SUBJECT_SLOT: subject_id,
        EDGE_OBJECT_SLOT: object_id,
        EDGE_RELATION_LABEL_SLOT: relation_label,
        EDGE_SOURCE_PREDICATE_SLOT: relation_curie,
        EDGE_PREDICATE_SLOT: relation_curie,   # <-- change here
        EDGE_QUALIFIED_PREDICATE_SLOT: None,
        EDGE_OBJECT_ASPECT_QUALIFIER_SLOT: None,
        EDGE_OBJECT_DIRECTION_QUALIFIER_SLOT: None,
        EDGE_NEGATED_SLOT: False,
        EDGE_PUBLICATIONS_SLOT: [],
        EDGE_PUBLICATIONS_INFO_SLOT: {},
        EDGE_UPDATE_DATE_SLOT: update_date,
        EDGE_PRIMARY_KNOWLEDGE_SOURCE_SLOT: primary_knowledge_source,
        EDGE_DOMAIN_RANGE_EXCLUSION_SLOT: False
    }

    edge_id = make_edge_key(edge)
    edge[EDGE_ID_SLOT] = edge_id

    return edge


def convert_biolink_category_to_curie(biolink_category_label: str):
    if '_' in biolink_category_label:
        raise ValueError("invalid category_label: " + biolink_category_label)
    return CURIE_PREFIX_BIOLINK + ':' + convert_space_case_to_camel_case(biolink_category_label)

def start_read_jsonlines(file_name: str, type=dict):
    file = open(file_name, 'r')
    jsonlines_reader = jsonlines.Reader(file)
    return (jsonlines_reader.iter(type=type), jsonlines_reader, file)

def close_kg2_jsonlines(nodes_info: tuple, edges_info: tuple,
                        output_nodes_file_name: str, output_edges_file_name: str):
    close_single_jsonlines(nodes_info, output_nodes_file_name)
    if edges_info is not None:
        close_single_jsonlines(edges_info, output_edges_file_name)


def date():
    return datetime.datetime.now().isoformat()

def make_node(id: str,
              iri: str,
              name: str,
              category_label: str,
              update_date: str,
              provided_by: str):

    if '-' in category_label:
        raise ValueError(
            'hyphen detected in category_label argument to make_node: ' + category_label
        )

    category_curie = convert_biolink_category_to_curie(category_label)
    category_label_norm = category_label.replace(' ', '_')

    return {
        NODE_ID_SLOT: id,
        NODE_IRI_SLOT: iri,
        NODE_NAME_SLOT: name,
        NODE_FULL_NAME_SLOT: name,
        NODE_CATEGORY_SLOT: category_curie,
        NODE_CATEGORY_LABEL_SLOT: category_label_norm,
        NODE_DESCRIPTION_SLOT: None,
        NODE_SYNONYM_SLOT: [],
        NODE_PUBLICATIONS_SLOT: [],
        NODE_CREATION_DATE_SLOT: None,
        NODE_UPDATE_DATE_SLOT: update_date,
        NODE_DEPRECATED_SLOT: False,
        NODE_REPLACED_BY_SLOT: None,
        NODE_PROVIDED_BY_SLOT: [provided_by],
        NODE_HAS_BIOLOGICAL_SEQUENCE_SLOT: None
    }

def create_kg2_jsonlines(test_mode: bool = False, include_edges: bool = True):
    nodes = create_single_jsonlines(test_mode)
    edges = create_single_jsonlines(test_mode) if include_edges else None
    return nodes, edges
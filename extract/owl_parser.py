#!/usr/bin/env python3
''' owlparser.py: Converts OWL (XML) Files into JSON Lines Representations

    Usage: owlparser.py [--test] <inputFile.yaml> <owlFilePath> <outputFile.jsonl>
'''

import json
import argparse
import datetime
import kg2_util
from lxml import etree


__author__ = 'Frankie Hodges'
__copyright__ = 'Oregon State University'
__credits__ = ['Stephen Ramsey', 'Frankie Hodges']
__license__ = 'MIT'
__version__ = '0.1.0'
__maintainer__ = 'Frankie Hodges'
__email__ = 'hodgesf@oregonstate.edu'
__status__ = 'Prototype'


def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('inputFile', type=str)
    arg_parser.add_argument('owlFilePath', type=str)
    arg_parser.add_argument('outputFile', type=str)
    return arg_parser.parse_args()


def date():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

from lxml import etree
import io

class XMLParser:
    """
    LXML-based XML to JSON Lines parser.
    Handles streaming large files by processing top-level nests as they close.
    """
    def __init__(self, skip_tags, ignored_attributes, processing_func):
        self.OUTMOST_TAGS_SKIP = set(skip_tags)
        self.IGNORED_ATTRIBUTES = set(ignored_attributes)
        self.processing_func = processing_func

        # Labels for internal logic
        self.LINE_TYPE_IGNORE = "ignore"
        self.LINE_TYPE_START_NEST = "start nest"
        self.LINE_TYPE_START_NEST_WITH_ATTR = "start nest with attributes"
        self.LINE_TYPE_ENTRY = "entry"
        self.LINE_TYPE_ENTRY_WITH_ATTR = "entry with attributes"
        self.LINE_TYPE_ENTRY_ONLY_ATTR = "entry with only attributes"
        self.LINE_TYPE_END_NEST = "end nest"

        self.KEY_TAG = "tag"
        self.KEY_ATTRIBUTES = "attributes"
        self.KEY_TEXT = "ENTRY_TEXT"
        self.KEY_TYPE = "type"

    def element_to_dict(self, element):
        """
        Recursively converts an lxml element into a dictionary matching your nested structure.
        """
        out = {}
        
        # Add filtered attributes
        attrs = {k: v for k, v in element.attrib.items() if k not in self.IGNORED_ATTRIBUTES}
        for k, v in attrs.items():
            out[k] = v

        # Add text if it exists
        text = (element.text or "").strip()
        if text:
            out[self.KEY_TEXT] = text

        # Process children
        for child in element:
            child_tag = child.tag
            if child_tag not in out:
                out[child_tag] = []
            
            # Recurse
            out[child_tag].append(self.element_to_dict(child))
            
        return out

    def divide_into_lines(self, input_file_name):
        """
        Uses etree.iterparse to stream through the file and identify top-level nests.
        This replaces the manual bracket counting and stack management.
        """
        # 'start' to catch tags to skip, 'end' to process completed nests
        context = etree.iterparse(input_file_name, events=('start', 'end'))
        
        # Track depth so we only process the first level of nests after the skipped tags
        depth = 0
        skip_depth = 0

        for event, elem in context:
            if event == 'start':
                if elem.tag in self.OUTMOST_TAGS_SKIP and depth == skip_depth:
                    skip_depth += 1
                depth += 1
            
            elif event == 'end':
                depth -= 1
                
                # If we are at the level just below our skipped tags
                if depth == skip_depth and elem.tag not in self.OUTMOST_TAGS_SKIP:
                    # Convert this complete nest to a dictionary
                    nest_dict = {elem.tag: [self.element_to_dict(elem)]}
                    
                    # Process the result
                    self.processing_func(nest_dict)
                    
                    # Clear the element from memory to keep RAM usage low
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                
                if elem.tag in self.OUTMOST_TAGS_SKIP:
                    skip_depth -= 1

    # --- Legacy Compatibility Methods (Simplified) ---
    
    def categorize_element(self, element):
        """
        If you still need the specific 'LINE_TYPE' labels for other logic.
        """
        has_attrs = len(element.attrib) > 0
        has_text = bool((element.text or "").strip())
        has_children = len(element) > 0

        if has_attrs:
            if has_text or has_children:
                return self.LINE_TYPE_ENTRY_WITH_ATTR
            return self.LINE_TYPE_ENTRY_ONLY_ATTR
        return self.LINE_TYPE_ENTRY if has_text else self.LINE_TYPE_START_NEST


from lxml import etree
import kg2_util

class OWLParser:
    def __init__(self, input_files, input_file_names, owl_file_path, output_file_name):
        # Configuration
        self.skip_tags = ["?xml", "rdf:RDF", "!DOCTYPE"]
        self.ignored_attributes = ["{http://www.w3.org/XML/1998/namespace}lang"] # lxml uses namespaced attributes
        
        # XML Parser initialization (using the lxml version we built)
        self.xml_parser = XMLParser(self.skip_tags, self.ignored_attributes, self.triage_nest_dict)

        # State management for Blank Nodes (genids)
        self.GENID_REMAINING_NESTS = {}
        self.GENID_TO_ID = {}
        self.ID_TO_GENIDS = {}

        self.input_files = input_files
        self.input_file_names = input_file_names
        self.owl_file_path = owl_file_path
        
        # Setup output
        self.output_info = kg2_util.create_single_jsonlines()
        self.output = self.output_info[0]

    def triage_nest_dict(self, nest_dict):
        """
        The processing function called by the lxml XMLParser.
        """
        # 1. Identify what we are looking at
        # Your XMLParser output uses the tag as the top-level key
        tag = next(iter(nest_dict))
        content = nest_dict[tag][0] # Get the first (and likely only) item in the list

        # 2. Extract identifiers and genids using the keys created by XMLParser
        # Note: XMLParser maps owl:Class to 'owl:Class' and rdf:about to 'rdf:about'
        class_id = content.get("rdf:about")
        
        # Find genids in subclasses
        subclasses = content.get("rdfs:subClassOf", [])
        genids = [s.get("rdf:nodeID") for s in subclasses if s.get("rdf:nodeID", "").startswith("genid")]

        # Find genid in restrictions
        restrictions = content.get("owl:Restriction", [])
        restriction_genid = None
        for r in restrictions:
            if r.get("rdf:nodeID", "").startswith("genid"):
                restriction_genid = r.get("rdf:nodeID")

        # 3. Triage Logic (The "Wait-and-Link" Algorithm)
        if genids:
            # This is a class definition waiting for its restrictions
            self.ID_TO_GENIDS[class_id] = genids
            for gid in genids:
                self.GENID_TO_ID[gid] = class_id
            self.GENID_REMAINING_NESTS[class_id] = nest_dict
            
        elif restriction_genid:
            # This is a restriction definition meant to fill a hole in a class
            target_class_id = self.GENID_TO_ID.get(restriction_genid)

            if not target_class_id:
                # Orphaned restriction, just output it
                self.write_to_output(nest_dict, self.input_file)
                return

            # Link the restriction content into the saved class nest
            # We look for the subclass entry with the matching nodeID and swap it
            class_nest = self.GENID_REMAINING_NESTS[target_class_id]
            class_content = class_nest["owl:Class"][0]
            
            for i, sub in enumerate(class_content.get("rdfs:subClassOf", [])):
                if sub.get("rdf:nodeID") == restriction_genid:
                    # Update the entry with the full restriction data
                    class_content["rdfs:subClassOf"][i] = content
                    break

            self.ID_TO_GENIDS[target_class_id].remove(restriction_genid)

            # If no more genids are pending for this class, output it
            if not self.ID_TO_GENIDS[target_class_id]:
                self.write_to_output(class_nest, self.input_file)
                self.GENID_REMAINING_NESTS[target_class_id] = None
        else:
            # Normal tag with no genid complications
            self.write_to_output(nest_dict, self.input_file)

    def write_to_output(self, output_dict, source_file):
        output_dict["owl_source"] = source_file
        output_dict["owl_source_name"] = self.input_file_names[source_file]
        self.output.write(output_dict)

    def parse_OWL_file(self):
        for input_file in self.input_files:
            self.input_file = input_file
            print(f"Reading: {input_file}")
            
            # Start the lxml-based streaming parse
            self.xml_parser.divide_into_lines(self.owl_file_path + input_file)

            # Flush any classes that were waiting for genids that never arrived
            for class_id, nest in self.GENID_REMAINING_NESTS.items():
                if nest:
                    self.write_to_output(nest, self.input_file)

            # Reset state for next file
            self.GENID_REMAINING_NESTS.clear()
            self.GENID_TO_ID.clear()
            self.ID_TO_GENIDS.clear()

        kg2_util.close_single_jsonlines(self.output_info, self.output_file_name)

def identify_and_download_input_files(ont_load_inventory, path_to_owl_files):
    """
    Download all of the input files in ont-load-inventory.yaml
    """
    input_files = []
    input_file_names = {}
    # Ensure the path ends with a single slash
    owl_file_path = path_to_owl_files.rstrip('/') + "/"

    for item in ont_load_inventory:
        file_name = item['file']
        url = item['url']
        input_files.append(file_name)
        input_file_names[file_name] = item['title']
        
        # Use your utility to pull the files
        print(f"Downloading: {file_name} starting at {date()}")
        kg2_util.download_file_if_not_exist_locally(url, owl_file_path + file_name)
        print(f"Download of: {file_name} finished at {date()}")

    return input_files, input_file_names, owl_file_path

if __name__ == '__main__':
    print(f"Start Time: {date()}")
    args = get_args()

    # Configuration from CLI
    inventory_path = args.inputFile
    owl_path = args.owlFilePath
    output_file_name = args.outputFile

    # Load YAML configuration
    # Assuming kg2_util.safe_load_yaml_from_string is your standard loader
    inventory_data = kg2_util.safe_load_yaml_from_string(kg2_util.read_file_to_string(inventory_path))
    
    # 1. Prepare Data: Download files and map names
    input_files, input_file_names, owl_file_path = identify_and_download_input_files(inventory_data, owl_path)

    print(f"Files to process: {input_files}")

    # 2. Initialize Parser: This now uses the lxml-optimized XMLParser internally
    owl_parser = OWLParser(input_files, input_file_names, owl_file_path, output_file_name)

    # 3. Execute: Process the 27GB+ graph in a memory-efficient stream
    owl_parser.parse_OWL_file()
    
    print(f"End Time: {date()}")
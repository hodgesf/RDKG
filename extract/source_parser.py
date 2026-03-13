#!/usr/bin/env python3
"""
source_parser.py: Converts non-ontology sources into JSON Lines.

Usage:
    source_parser.py <inventory_yaml> <data_dir> <output_jsonl>
"""

import argparse
import datetime
import gzip
import csv
import json
import os
import kg2_util


__author__ = "Frankie Hodges"
__license__ = "MIT"


def date():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=str)
    parser.add_argument("data_dir", type=str)
    parser.add_argument("output_file", type=str)
    return parser.parse_args()


class SourceParser:

    def __init__(self, inventory, data_dir, output_file):

        self.inventory = inventory
        self.data_dir = data_dir.rstrip("/") + "/"
        self.output_file = output_file

        self.output_info = kg2_util.create_single_jsonlines()
        self.output = self.output_info[0]

    def download_sources(self):

        sources = []

        for item in self.inventory:

            file_name = item["file"]
            url = item["url"]

            local_path = self.data_dir + file_name
            sources.append((item, local_path))

            print(f"Downloading: {file_name} starting at {date()}")
            kg2_util.download_file_if_not_exist_locally(url, local_path)
            print(f"Download finished: {file_name} at {date()}")

        return sources

    def open_file(self, path):

        if path.endswith(".gz"):
            return gzip.open(path, "rt")

        return open(path)

    def process_tsv(self, item, path):

        with self.open_file(path) as f:

            reader = csv.DictReader(f, delimiter="\t")

            for row in reader:

                row["source"] = item["id"]
                row["source_name"] = item["title"]

                self.output.write(row)

    def process_csv(self, item, path):

        with self.open_file(path) as f:

            reader = csv.DictReader(f)

            for row in reader:

                row["source"] = item["id"]
                row["source_name"] = item["title"]

                self.output.write(row)

    def process_json(self, item, path):

        with self.open_file(path) as f:

            data = json.load(f)

            if isinstance(data, list):

                for record in data:

                    record["source"] = item["id"]
                    record["source_name"] = item["title"]

                    self.output.write(record)

            else:

                data["source"] = item["id"]
                data["source_name"] = item["title"]

                self.output.write(data)

    def process_file(self, item, path):

        fmt = item.get("format")

        if fmt == "tsv":
            self.process_tsv(item, path)

        elif fmt == "csv":
            self.process_csv(item, path)

        elif fmt == "json":
            self.process_json(item, path)

        else:
            print(f"Skipping unsupported format: {path}")

    def run(self):

        sources = self.download_sources()

        for item, path in sources:

            print(f"Processing: {path}")
            self.process_file(item, path)

        kg2_util.close_single_jsonlines(self.output_info, self.output_file)


if __name__ == "__main__":

    print(f"Start Time: {date()}")

    args = get_args()

    inventory = kg2_util.safe_load_yaml_from_string(
        kg2_util.read_file_to_string(args.inventory)
    )

    parser = SourceParser(
        inventory,
        args.data_dir,
        args.output_file,
    )

    parser.run()

    print(f"End Time: {date()}")
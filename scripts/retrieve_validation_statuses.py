#!/usr/bin/env python
"""
This script retrieves fastq validation event status and results for all files in an upload area id
"""

import argparse
import os
import requests


def main(args):
    data_dir_path = "/data/{0}".format(args.dataset_name)
    for file in os.listdir(data_dir_path):
        if "fastq" in file:
            upload_url = "https://upload.{0}.data.humancellatlas.org/v1/area/{1}/{2}/validate".format(args.environment, args.upload_area_id, file)
            headers = {'Api-Key': args.api_key}
            message = {"validator_image": "quay.io/humancellatlas/fastq_utils:master"}
            response = requests.get(upload_url, headers=headers, json=message)
            print("{0}: Event Status: {1} Results: {2}".format(file, response.validation_status, response.validation_results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='schedule validation jobs')
    parser.add_argument('--dataset-name', help='dataset directory name')
    parser.add_argument('--upload-area-id', help='upload area id')
    parser.add_argument('--environment', help="upload environment", default="staging")
    parser.add_argument('--api-key', help="upload api key", required=True)
    args = parser.parse_args()
    main(args)

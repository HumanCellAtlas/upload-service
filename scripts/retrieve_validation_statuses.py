#!/usr/bin/env python
"""
This script retrieves fastq validation job statuses and results for all files in an upload area id
"""

import argparse
import os
import requests
import json
try:
    import urllib.parse as urlparse
except ImportError:
    import urllib as urlparse


def main(args):
    data_dir_path = "/data/{0}".format(args.dataset_name)
    for file in os.listdir(data_dir_path):
        if "fastq" in file:
            filename = urlparse.quote(file)
            upload_url = "https://upload.{0}.data.humancellatlas.org/v1/area/{1}/{2}/validate".format(args.environment, args.upload_area_id, filename)
            headers = {'Api-Key': args.api_key}
            response = requests.get(upload_url, headers=headers)
            json_response = json.loads(response.text)
            status = json_response["validation_status"]
            if status == "VALIDATED":
                validation_results = json.loads(json_response["validation_results"])
                validation_state = validation_results['validation_state']
                print("{0}: File Validation Status: {1}".format(file, validation_state))
            else:
                print("{0}: File Validation Status: {1}".format(file, status))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='retrieve validation jobs')
    parser.add_argument('--dataset-name', help='dataset directory name')
    parser.add_argument('--upload-area-id', help='upload area id')
    parser.add_argument('--environment', help="upload environment", default="staging")
    parser.add_argument('--api-key', help="upload api key", required=True)
    args = parser.parse_args()
    main(args)

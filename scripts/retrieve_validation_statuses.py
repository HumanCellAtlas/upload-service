#!/usr/bin/env python
"""
This script schedules fastq validation for all files in an upload area id
"""

import argparse
import json
import requests
try:
    import urllib.parse as urlparse
except ImportError:
    import urllib as urlparse

import boto3

s3_client = boto3.client('s3')


def _parse_s3_path(s3_path):
    s3_path = s3_path.replace("s3://", "")
    s3_path_split = s3_path.split("/", 1)

    bucket = s3_path_split[0]
    prefix = ''
    if len(s3_path_split) > 1:
        prefix = s3_path_split[1]
    return bucket, prefix


def _retrieve_files_list_and_size_sum_tuple_from_s3_path(s3_path):
        s3_file_obj_paths = []
        bucket, prefix = _parse_s3_path(s3_path)

        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
        for page in page_iterator:
            if "Contents" in page:
                for key in page["Contents"]:
                    s3_obj = {'uuid': key['Key'].split('/')[0], 'name': key['Key'].split('/')[1]}
                    s3_file_obj_paths.append(s3_obj)
        return s3_file_obj_paths


def main(args):
    files = _retrieve_files_list_and_size_sum_tuple_from_s3_path(args.s3_path)
    for file in files:
        if "fastq" in file['name']:
            filename = urlparse.quote(file['name'])
            upload_url = "https://upload.{0}.data.humancellatlas.org/v1/area/{1}/{2}/validate".format(args.environment, file["uuid"], filename)
            headers = {'Api-Key': args.api_key}
            response = requests.get(upload_url, headers=headers)
            json_response = json.loads(response.text)
            status = json_response["validation_status"]
            if status == "VALIDATED":
                validation_results = json.loads(json_response['validation_results'])
                validation_state = validation_results['validation_state']
                print("{0}: File Validation Status: {1}".format(file["name"], validation_state))
            else:
                print("{0}: File Validation Status: {1}".format(file["name"], status))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='schedule validation jobs')
    parser.add_argument('--s3-path', help='upload area uri', required=True)
    parser.add_argument('--environment', help="upload environment", default="staging")
    parser.add_argument('--api-key', help="upload api key", required=True)
    args = parser.parse_args()
    main(args)

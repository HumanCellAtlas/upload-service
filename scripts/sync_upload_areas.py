#!/usr/bin/env python
"""
This script syncs data from s3 buckets into data directories.
"""

import argparse
import os
from subprocess import call


def main(args):
    if not os.path.isdir(args.data_dir_path):
        print("\nThe data directory path passed in does not exist. The default is '/data'. Please pass in a valid directory path or 'mkdir /data'\n")
        return
    credentials_dir_path = "{0}/credentials".format(args.data_dir_path)
    credentials_file_path = "{0}/upload_area_creds.txt".format(credentials_dir_path)
    if not os.path.exists(credentials_file_path):
        print("\nThe credentials file (which stores dataset names and s3 bucket URNs) does not exist. Exiting as there is nothing to sync.\n")
        return
    with open(credentials_file_path) as f:
        lines = f.read()
        lines = lines.replace("\n", ",")
        lines = lines.replace("Dataset name:", "")
        lines = lines.replace(",CLI URN to copy for HCA Upload Select", "")
        areas = lines.split(",")
        for area in areas:
            if area:
                sync_s3_bucket_with_local_dir(area)


def sync_s3_bucket_with_local_dir(area_parsed_list):
    area_id_parts = area_parsed_list.split(":")
    dir_name = area_id_parts[0]
    environment = area_id_parts[4]
    upload_area_id = area_id_parts[5]
    data_dir_path = "{0}/{1}".format(args.data_dir_path, dir_name)
    s3_bucket_uri = "s3://org-humancellatlas-upload-{0}/{1}".format(environment, upload_area_id)
    print("Starting aws s3 sync of {0}".format(upload_area_id))
    call(["aws", "s3", "sync", s3_bucket_uri, data_dir_path])
    print("Completed aws s3 sync of {0}".format(upload_area_id))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create upload areas')
    parser.add_argument('--data-dir-path', help='data root directory', default='/data')
    args = parser.parse_args()
    main(args)

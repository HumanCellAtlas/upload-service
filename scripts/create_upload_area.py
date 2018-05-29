#!/usr/bin/env python
"""
This script allows users to create upload areas in a specific environment.
"""

import argparse
import json
import requests
import uuid
import os

from pathlib import Path


def main(args):
    credential_dir_path = "{0}/credentials".format(args.data_dir_path)
    credential_file_path = "{0}/upload_area_creds.txt".format(credential_dir_path)
    dataset_dir_path = "{0}/{1}".format(args.data_dir_path, args.dataset_name)
    check_and_create_directories(args, credential_dir_path, credential_file_path, dataset_dir_path)
    urn = create_upload_area_and_fetch_credentials(args, dataset_dir_path)
    write_credentials_to_disk(args, urn, credential_file_path)


def create_upload_area_and_fetch_credentials(args, dataset_dir_path):
    upload_area_id = 'aaaaaaaa-bbbb-cccc-dddd-' + str(uuid.uuid4()).split("-")[-1]
    url = "https://upload.{0}.data.humancellatlas.org/v1/area/{1}".format(args.environment, upload_area_id)
    headers = {'Api-Key': args.api_key}
    response = requests.post(url, headers=headers)
    if response.status_code == 401:
        os.rmdir(dataset_dir_path)
        raise Exception("\n Invalid Upload Service API Key. Please retry with the correct key.\n")
    urn = json.loads(response.text)["urn"]
    return urn


def check_and_create_directories(args, credential_dir_path, credential_file_path, dataset_dir_path):
    if not os.path.isdir(args.data_dir_path):
        raise Exception("\nThe data directory path passed in does not exist. The default is '/data'. Please pass in a valid directory path or 'mkdir /data'\n")
        return
    credential_dir_path = "{0}/credentials".format(args.data_dir_path)
    credential_file_path = "{0}/upload_area_creds.txt".format(credential_dir_path)
    dataset_dir_path = "{0}/{1}".format(args.data_dir_path, args.dataset_name)
    try:
        os.mkdir(dataset_dir_path)
        if not os.path.isdir(credential_dir_path):
            os.mkdir(credential_dir_path)
        if not os.path.exists(credential_file_path):
            Path(credential_file_path).touch()
    except OSError as e:
        print("\n")
        print(e)
        raise Exception("\nFailed to create directory in /data. Please correct error above and retry. The dataset name must be unique.\n")


def write_credentials_to_disk(args, urn, credential_file_path):
    proj_cred_line = "Dataset name:{0}\nCLI URN to copy for HCA Upload Select:{1}\n".format(args.dataset_name, urn)
    with open(credential_file_path, "a") as myfile:
        myfile.write(proj_cred_line)
    print("\nDataset name: {0}\n".format(args.dataset_name))
    print("CLI URN to copy for HCA Upload Select:")
    print("{0}\n".format(urn))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create upload areas')
    parser.add_argument('--api-key', help='upload service api key', required=True)
    parser.add_argument('--dataset-name', help='unique name of dataset', required=True)
    parser.add_argument('--environment', help='upload service environment', required=True, choices=["dev", "integration", "staging"])
    parser.add_argument('--data-dir-path', help='data root directory', default='/data')
    args = parser.parse_args()
    main(args)

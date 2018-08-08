#!/usr/bin/env python

import argparse

import boto3
client = boto3.client('lambda')


def get_lambda_env_vars(function_name):
    response = client.get_function_configuration(
        FunctionName=function_name,
    )
    return response['Environment']['Variables']


def update_version_for_lambda(function_name, upload_service_version):
    curr_vars = get_lambda_env_vars(function_name)
    curr_vars['UPLOAD_SERVICE_VERSION'] = upload_service_version
    response = client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            'Variables': curr_vars
        }
    )

    print("{} env vars are: {}".format(function_name, response['Environment']['Variables']))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='update lambda env vars')
    parser.add_argument('--function-name', help='lambda function name (including environment)')
    parser.add_argument('--upload-service-version', help='upload service version')

    args = parser.parse_args()
    update_version_for_lambda(args.function_name, args.upload_service_version)

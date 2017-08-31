
import logging

import boto3
from botocore.exceptions import ClientError
from connexion.lifecycle import ConnexionResponse

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('nose').setLevel(logging.WARNING)

STAGING_BUCKET_NAME_PREFIX = 'org-humancellatlas-staging-'


def create(staging_area_id: str):
    s3 = boto3.resource('s3')
    bucket_name = f"{STAGING_BUCKET_NAME_PREFIX}{staging_area_id}"
    bucket = s3.Bucket(bucket_name)
    try:
        bucket.load()
        return rfc7807error_response(title="Staging Area Already Exists",
                                     status=409,
                                     detail=f"Staging area {staging_area_id} already exists.")
    except ClientError as e:
        if e.response['Error']['Code'] != '404':
            return rfc7807error_response(title="Unexpected Error",
                                         status=500,
                                         detail=f"bucket.load() returned {e.response}")
    bucket.create()
    return {'url': f"s3://{bucket.name}"}, 201


def delete(staging_area_id: str):
    s3 = boto3.resource('s3')
    bucket_name = f"{STAGING_BUCKET_NAME_PREFIX}{staging_area_id}"
    bucket = s3.Bucket(bucket_name)
    try:
        bucket.load()
        bucket.delete()
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return rfc7807error_response(title="Staging Area Not Found", status=404)
        else:
            return rfc7807error_response(title="Unexpected Error",
                                         status=500,
                                         detail=e.response)
    return None, 204


RFC7807_MIMETYPE = 'application/problem+json'


def rfc7807error_response(title, status, detail=None):
    body = {
        'title': title,
        'status': status,
        'detail': detail
    }
    if detail:
        body['detail'] = detail

    return ConnexionResponse(
        status_code=status,
        mimetype=RFC7807_MIMETYPE,
        content_type=RFC7807_MIMETYPE,
        body=body
    )

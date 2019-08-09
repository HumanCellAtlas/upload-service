"""usage: python /scripts/fix_upload_tags.py --upload-area s3://org-humancellatlas-upload-prod/40972c5f-295a-4e39-9ac8-a1aaca89798f/."""
import argparse
import boto3
import requests

from hca.util.pool import ThreadPool

client = boto3.client('s3')
okay_files = []
fixed_files = []


def file_upload_notification(area_uuid, filename):
    url = "https://upload.data.humancellatlas.org/v1/area/{area_uuid}/{filename}".format(area_uuid=area_uuid,filename=filename)
    response = requests.post(url)
    if not response.status_code == requests.codes.accepted:
        raise RuntimeError(
            "POST {url} returned {status}".format(
                url=url,
                status=response.status_code))
    return response


def _check_tags(upload_bucket, upload_area_uuid, keyString):
    tags = client.get_object_tagging(Bucket=upload_bucket, Key=keyString).get('TagSet')
    if tags and len(tags) == 4:
        okay_files.append(keyString)
        if len(okay_files) % 100 == 0:
            print(len(okay_files))
    else:
        fixed_files.append(keyString)
        file_name = keyString.split('/')[1]
        file_upload_notification(upload_area_uuid, file_name)


def main(upload_bucket, upload_area_uuid):
    paginator = client.get_paginator("list_objects")
    pool = ThreadPool()
    page_iterator = paginator.paginate(Bucket=upload_bucket, Prefix=upload_area_uuid)
    for page in page_iterator:
        if "Contents" in page:
            for key in page["Contents"]:
                keyString = key["Key"]
                pool.add_task(_check_tags, upload_bucket, upload_area_uuid, keyString)
    pool.wait_for_completion()
    print('Following files fixed: ')
    print(fixed_files)
    print('Please re-kick bundle export')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload-area", required=True)
    args = parser.parse_args()
    upload_area = args.upload_area.replace('s3://', '')
    upload_area = upload_area[:-1]
    upload_bucket = upload_area.split('/')[0]
    upload_area_uuid = upload_area.split('/')[1]
    main(upload_bucket, upload_area_uuid)

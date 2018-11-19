import os
from functools import reduce
import boto3
from botocore.exceptions import ClientError

from tenacity import retry, wait_fixed, stop_after_attempt

from .exceptions import UploadException
if not os.environ.get("CONTAINER"):
    from .database import create_pg_record, get_pg_record, run_query_with_params

s3 = boto3.resource('s3')
s3client = boto3.client('s3')


class UploadedFile:

    """
    The UploadedFile class represents newly-uploaded or previously uploaded files.

    If the parameters to __init__() include 'name', 'data', 'content_type': a new file will be created.
    """

    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')

    @classmethod
    def from_s3_key(cls, upload_area, s3_key):
        s3object = s3.Bucket(upload_area.bucket_name).Object(s3_key)
        return cls(upload_area, s3object=s3object)

    def __init__(self, upload_area, name=None, content_type=None, data=None, s3object=None):
        self.content_size = None
        self.upload_area = upload_area
        self.s3obj = None
        self.name = name
        self.content_type = content_type
        self.checksums = {}
        if name and data and content_type:
            self.content_size = len(data)
            self._create(data)
        elif s3object:
            self._load_s3_object(s3object)
        else:
            raise RuntimeError("you must provide s3object, or name, content_type and data")

    def _create(self, data):
        self.s3obj = self.upload_area.s3_object_for_file(self.name)
        self.fetch_or_create_db_record()
        self.s3obj.put(Body=data, ContentType=self.content_type)

    def _load_s3_object(self, s3object):
        self.s3obj = s3object
        self.name = s3object.key[self.upload_area.key_prefix_length:]  # cut off upload-area-id/
        self.checksums = self._dcp_tags_of_file()
        self.content_type = self.s3obj.content_type

    def info(self):
        return {
            'upload_area_id': self.upload_area.uuid,
            'name': self.name,
            'size': self.size,
            'content_type': self.content_type,
            'url': f"s3://{self.upload_area.bucket_name}/{self.s3obj.key}",
            'checksums': self.checksums,
            'last_modified': self.s3obj.last_modified.isoformat()
        }

    def refresh(self):
        self.s3obj.reload()
        self.content_type = self.s3obj.content_type

    @property
    def s3key(self):
        return f"{self.upload_area.uuid}/{self.name}"

    @property
    def s3url(self):
        return f"s3://{self.upload_area.bucket_name}/{self.s3key}"

    @property
    def size(self):
        if self.content_size:
            return self.content_size
        else:
            return self.s3obj.content_length

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def save_tags(self):
        tags = {f"hca-dss-{csum}": self.checksums[csum] for csum in self.checksums.keys()}
        tagging = dict(TagSet=self._encode_tags(tags))
        s3client.put_object_tagging(Bucket=self.upload_area.bucket_name, Key=self.s3obj.key, Tagging=tagging)
        self.checksums = self._dcp_tags_of_file()
        if len(self.CHECKSUM_TAGS) != len(self.checksums.keys()):
            raise UploadException(status=500,
                                  detail="Tags {tags} did not stick to {self.s3obj.key}")
        return self.checksums

    def _dcp_tags_of_file(self):
        try:
            tagging = s3client.get_object_tagging(Bucket=self.upload_area.bucket_name, Key=self.s3obj.key)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise UploadException(status=404, title="No such file",
                                      detail=f"No such file in that upload area")
            else:
                raise e
        tags = {}
        if 'TagSet' in tagging:
            tag_set = self._decode_tags(tagging['TagSet'])
            # k[8:] = cut off "hca-dss-" in tag name
            tags = {k[8:]: v for k, v in tag_set.items() if k in self.CHECKSUM_TAGS}
        return tags

    @staticmethod
    def _encode_tags(tags: dict) -> list:
        return [dict(Key=k, Value=v) for k, v in tags.items()]

    @staticmethod
    def _decode_tags(tags: list) -> dict:
        if not tags:
            return {}
        simplified_dicts = list({tag['Key']: tag['Value']} for tag in tags)
        return reduce(lambda x, y: dict(x, **y), simplified_dicts)

    def _format_prop_vals_dict(self):
        return {
            "id": self.s3obj.key,
            "upload_area_id": self.upload_area.uuid,
            "name": self.name,
            "size": self.size
        }

    def create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("file", prop_vals_dict)

    def fetch_or_create_db_record(self):
        existing_file = get_pg_record("file", self.s3obj.key)
        if not existing_file:
            self.create_record()

    def retrieve_latest_file_validation_status_and_results(self):
        status = "UNSCHEDULED"
        results = None
        query_results = run_query_with_params("SELECT status, results->>'stdout' FROM validation \
            WHERE file_id = %s order by created_at desc limit 1;", (self.s3obj.key,))
        rows = query_results.fetchall()
        if len(rows) > 0:
            status = rows[0][0]
            results = rows[0][1]
        return status, results

    def retrieve_latest_file_checksum_status_and_values(self):
        status = "UNSCHEDULED"
        checksums = None
        query_results = run_query_with_params("SELECT status, checksums FROM checksum \
            WHERE file_id = %s order by created_at desc limit 1;", (self.s3obj.key,))
        rows = query_results.fetchall()
        if len(rows) > 0:
            status = rows[0][0]
            checksums = rows[0][1]
        return status, checksums

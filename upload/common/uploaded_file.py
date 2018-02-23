from functools import reduce

import boto3
from botocore.exceptions import ClientError

from .exceptions import UploadException

s3 = boto3.resource('s3')
s3client = boto3.client('s3')


class UploadedFile:

    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')

    @classmethod
    def from_s3_key(cls, upload_area, s3_key):
        s3object = s3.Bucket(upload_area.bucket_name).Object(s3_key)
        return cls(upload_area, s3object)

    def __init__(self, upload_area, s3object):
        self.upload_area = upload_area
        self.s3obj = s3object
        self.name = s3object.key[upload_area.key_prefix_length:]  # cut off upload-area-id/
        self.content_type_tag = None
        tags = self._dcp_tags_of_file()
        if 'content-type' in tags:
            self.content_type_tag = tags['content-type']
            del tags['content-type']
        self.checksums = tags

    def info(self):
        return {
            'upload_area_id': self.upload_area.uuid,
            'name': self.name,
            'size': self.size,
            'content_type': self.content_type_tag or self.s3obj.content_type,
            'url': f"s3://{self.upload_area.bucket_name}/{self.s3obj.key}",
            'checksums': self.checksums,
            'last_modified': self.s3obj.last_modified.isoformat()
        }

    @property
    def s3url(self):
        return f"s3://{self.upload_area.bucket_name}/{self.upload_area.uuid}/{self.name}"

    @property
    def size(self):
        return self.s3obj.content_length

    def save_tags(self):
        tags = {f"hca-dss-{csum}": self.checksums[csum] for csum in self.checksums.keys()}
        tagging = dict(TagSet=self._encode_tags(tags))
        s3client.put_object_tagging(Bucket=self.upload_area.bucket_name, Key=self.s3obj.key, Tagging=tagging)
        return tags

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

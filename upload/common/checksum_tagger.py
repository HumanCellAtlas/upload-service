from functools import reduce

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, wait_fixed, stop_after_attempt

from .exceptions import UploadException

s3client = boto3.client('s3')


class ChecksumTagger:
    TAG_PREFIX = 'hca-dss-'
    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')

    def __init__(self, s3object):
        self._s3obj = s3object

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def save_checksums_as_tags_on_s3_object(self, checksums: dict):
        tags = {f"{self.TAG_PREFIX}{csum_name}": csum for csum_name, csum in checksums.items()}

        tagging = dict(TagSet=self._encode_s3_tagset(tags))
        s3client.put_object_tagging(Bucket=self._s3obj.bucket_name, Key=self._s3obj.key, Tagging=tagging)

        saved_checksums = self._read_tags()
        if len(saved_checksums) != len(checksums):
            raise UploadException(status=500,
                                  title=f"Tags {tags} did not stick to {self._s3obj.key}",
                                  detail=f"tried to apply tags {tags}")

    def read_checksums(self):
        tags_dict = self._read_tags()
        return self._cut_off_tag_prefix_for_dss_tags(tags_dict)

    def _read_tags(self):
        try:
            tagging = s3client.get_object_tagging(Bucket=self._s3obj.bucket_name, Key=self._s3obj.key)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise UploadException(status=404, title="No such file",
                                      detail=f"No such file in that upload area")
            else:
                raise e
        tags_dict = {}
        if 'TagSet' in tagging:
            tags_dict = self._decode_s3_tagset(tagging['TagSet'])
        return tags_dict

    def _cut_off_tag_prefix_for_dss_tags(self, tags_dict):
        return {k[len(self.TAG_PREFIX):]: v for k, v in tags_dict.items() if k in self.CHECKSUM_TAGS}

    @staticmethod
    def _encode_s3_tagset(tags: dict) -> list:
        # { 'a':'b', 'c':'d'} -> [ { 'Key':'a', 'Value':'b'}, {'Key':'c', 'Value':'d'} ]
        return [dict(Key=k, Value=v) for k, v in tags.items()]

    @staticmethod
    def _decode_s3_tagset(tags: list) -> dict:
        # [ { 'Key':'a', 'Value':'b'}, {'Key':'c', 'Value':'d'} ] -> { 'a':'b', 'c':'d'}
        if not tags:
            return {}
        simplified_dicts = list({tag['Key']: tag['Value']} for tag in tags)
        return reduce(lambda x, y: dict(x, **y), simplified_dicts)

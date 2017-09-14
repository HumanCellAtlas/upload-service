from functools import reduce

import boto3
from boto3.s3.transfer import TransferConfig

from checksumming_io.checksumming_io import ChecksummingSink

s3client = boto3.client('s3')

KB = 1024
MB = KB * KB


class StagedFile:

    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')
    MIME_TAG = 'hca-dss-content-type'
    HCA_TAGS = CHECKSUM_TAGS + (MIME_TAG,)

    @classmethod
    def from_listobject_dict(cls, staging_area, object_dict):
        return cls(staging_area, s3_key=object_dict['Key'], size=object_dict['Size'])

    @classmethod
    def from_s3object(cls, staging_area, s3obj):
        return cls(staging_area, s3_key=s3obj.key, size=s3obj.content_length)

    def __init__(self, staging_area, s3_key=None, size=None):
        self.s3_key = s3_key
        self.name = s3_key[staging_area.key_prefix_length:]  # cut off staging-area-id/
        self.staging_area = staging_area
        self.size = size
        tags = self._hca_tags_of_file()
        self.content_type = tags.get('content-type', 'unknown')
        if 'content-type' in tags:
            del tags['content-type']
        self.checksums = tags

    def info(self):
        return {
            'staging_area_id': self.staging_area.uuid,
            'name': self.name,
            'size': self.size,
            'content_type': self.content_type,
            'url': f"s3://{self.staging_area.bucket_name}/{self.s3_key}",
            'checksums': self.checksums
        }

    def compute_checksums(self):
        with ChecksummingSink() as sink:
            s3client.download_fileobj(self.staging_area.bucket_name, self.s3_key, sink, Config=self._transfer_config())
            self.checksums = sink.get_checksums()

    def save_tags(self):
        tags = {
            'hca-dss-content-type': self.content_type,
            'hca-dss-s3_etag': self.checksums['s3_etag'],
            'hca-dss-sha1': self.checksums['sha1'],
            'hca-dss-sha256': self.checksums['sha256'],
            'hca-dss-crc32c': self.checksums['crc32c'],
        }
        tagging = dict(TagSet=self._encode_tags(tags))
        s3client.put_object_tagging(Bucket=self.staging_area.bucket_name, Key=self.s3_key, Tagging=tagging)

    def _hca_tags_of_file(self):
        tagging = s3client.get_object_tagging(Bucket=self.staging_area.bucket_name, Key=self.s3_key)
        tags = {}
        if 'TagSet' in tagging:
            tag_set = self._decode_tags(tagging['TagSet'])
            # k[8:] = cut off "hca-dss-" in tag name
            tags = {k[8:]: v for k, v in tag_set.items() if k in self.HCA_TAGS}
        return tags

    def _transfer_config(self) -> TransferConfig:
        etag_stride = self._s3_chunk_size(self.size)
        return TransferConfig(multipart_threshold=etag_stride,
                              multipart_chunksize=etag_stride)

    @staticmethod
    def _encode_tags(tags: dict) -> list:
        return [dict(Key=k, Value=v) for k, v in tags.items()]

    @staticmethod
    def _decode_tags(tags: list) -> dict:
        if not tags:
            return {}
        simplified_dicts = list({tag['Key']: tag['Value']} for tag in tags)
        return reduce(lambda x, y: dict(x, **y), simplified_dicts)

    @staticmethod
    def _s3_chunk_size(file_size: int) -> int:
        if file_size <= 10000 * 64 * MB:
            return 64 * MB
        else:
            div = file_size // 10000
            if div * 10000 < file_size:
                div += 1
            return ((div + (MB - 1)) // MB) * MB

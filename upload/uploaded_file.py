from functools import reduce

import boto3
from boto3.s3.transfer import TransferConfig

from checksumming_io.checksumming_io import ChecksummingSink

s3 = boto3.resource('s3')
s3client = boto3.client('s3')

KB = 1024
MB = KB * KB


class UploadedFile:

    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')

    @classmethod
    def from_listobject_dict(cls, upload_area, object_dict):
        return cls(upload_area, s3_key=object_dict['Key'], size=object_dict['Size'])

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
            'size': self.s3obj.content_length,
            'content_type': self.content_type_tag or self.s3obj.content_type,
            'url': f"s3://{self.upload_area.bucket_name}/{self.s3obj.key}",
            'checksums': self.checksums,
            'last_modified': self.s3obj.last_modified
        }

    def compute_checksums(self, progress_callback=None):
        with ChecksummingSink() as sink:
            s3client.download_fileobj(self.upload_area.bucket_name, self.s3obj.key, sink,
                                      Callback=progress_callback, Config=self._transfer_config())
            self.checksums = sink.get_checksums()

    def save_tags(self):
        tags = {
            'hca-dss-s3_etag': self.checksums['s3_etag'],
            'hca-dss-sha1': self.checksums['sha1'],
            'hca-dss-sha256': self.checksums['sha256'],
            'hca-dss-crc32c': self.checksums['crc32c'],
        }
        tagging = dict(TagSet=self._encode_tags(tags))
        s3client.put_object_tagging(Bucket=self.upload_area.bucket_name, Key=self.s3obj.key, Tagging=tagging)
        return tags

    def _dcp_tags_of_file(self):
        tagging = s3client.get_object_tagging(Bucket=self.upload_area.bucket_name, Key=self.s3obj.key)
        tags = {}
        if 'TagSet' in tagging:
            tag_set = self._decode_tags(tagging['TagSet'])
            # k[8:] = cut off "hca-dss-" in tag name
            tags = {k[8:]: v for k, v in tag_set.items() if k in self.CHECKSUM_TAGS}
        return tags

    def _transfer_config(self) -> TransferConfig:
        etag_stride = self._s3_chunk_size(self.s3obj.content_length)
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
        if file_size <= 10000 * 64 * MB:  # 640 GB
            return 64 * MB
        else:
            div = file_size // 10000
            if div * 10000 < file_size:
                div += 1
            return ((div + (MB - 1)) // MB) * MB

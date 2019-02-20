import collections.abc
import logging
import time
from functools import reduce

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from dcplib.checksumming_io import ChecksummingSink
from dcplib.s3_multipart import get_s3_multipart_chunk_size, MULTIPART_THRESHOLD
from tenacity import retry, wait_fixed, stop_after_attempt

from .exceptions import UploadException

logger = logging.getLogger(__name__)


class DssChecksums(collections.abc.MutableMapping):
    """
    Encapsulates code for dealing with DSS checksums:
    - retrieving them from an S3 object
    - computing them from an s3 object
    - writing them to s3 object tags
    - acts like a dict()

    checksums = DssChecksums(s3object=object)
    if not checksums.are_present():
        checksums.compute()
        checksums.save_as_tags_on_s3_object()
    """

    TAG_PREFIX = 'hca-dss-'
    CHECKSUM_NAMES = ('sha1', 'sha256', 'crc32c', 's3_etag')
    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')

    def __init__(self, s3_object,
                 checksums=None  # only used during testing
                 ):
        self._s3obj = s3_object
        self._s3client = boto3.client('s3')
        self.tagger = self.Tagger(s3_object)
        self._checksums = self.tagger.read_checksums_from_object() or checksums or {}

    def __getitem__(self, name):
        return self._checksums[name]

    def __setitem__(self, name, value):
        raise NotImplemented

    def __delitem__(self, name):
        raise NotImplemented

    def __iter__(self):
        return iter(self._checksums)

    def __len__(self):
        return len(self._checksums)

    def keys(self):
        return self._checksums.keys()

    def refresh(self):
        self._checksums = self.tagger.read_checksums_from_object() or {}

    def are_present(self):
        return sorted(self.keys()) == sorted(self.CHECKSUM_NAMES)

    def compute(self, report_progress=False):
        computer = self.ChecksumComputer(s3obj=self._s3obj)
        self._checksums = computer.compute(report_progress)
        return self

    def save_as_tags_on_s3_object(self):
        self.tagger.save_tags(self)

    class Tagger:

        def __init__(self, s3obj):
            self._s3obj = s3obj
            self._s3client = boto3.client('s3')

        def read_checksums_from_object(self):
            if not self._s3obj:
                return None
            tags_dict = self._read_tags()
            return self._cut_off_tag_prefix_for_dss_tags(tags_dict)

        @retry(reraise=True, wait=wait_fixed(2), stop=stop_after_attempt(5))
        def _read_tags(self):
            try:
                tagging = self._s3client.get_object_tagging(Bucket=self._s3obj.bucket_name, Key=self._s3obj.key)
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

        @retry(reraise=True, wait=wait_fixed(2), stop=stop_after_attempt(5))
        def save_tags(self, checksums):
            tags = {f"{DssChecksums.TAG_PREFIX}{csum_name}": csum for csum_name, csum in checksums.items()}

            tagging = dict(TagSet=self._encode_s3_tagset(tags))
            self._s3client.put_object_tagging(Bucket=self._s3obj.bucket_name, Key=self._s3obj.key, Tagging=tagging)

            saved_checksums = self._read_tags()
            if len(saved_checksums) != len(checksums):
                raise UploadException(status=500,
                                      title=f"Tags {tags} did not stick to {self._s3obj.key}",
                                      detail=f"tried to apply tags {tags}")

        @staticmethod
        def _cut_off_tag_prefix_for_dss_tags(tags_dict):
            return {
                k[len(DssChecksums.TAG_PREFIX):]: v for k, v in tags_dict.items() if k in DssChecksums.CHECKSUM_TAGS
            }

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

    class ChecksumComputer:

        def __init__(self, s3obj):
            self._s3obj = s3obj
            self._s3client = boto3.client('s3')
            self.bytes_checksummed = 0
            self.start_time = None
            self.last_diag_output_time = None

        def compute(self, report_progress=False):
            if report_progress:
                self.bytes_checksummed = 0
                self.start_time = time.time()
                self.last_diag_output_time = self.start_time
                progress_callback = self._compute_checksums_progress_callback
            else:
                progress_callback = None

            return self._compute_checksums(progress_callback=progress_callback)

        def _compute_checksums(self, progress_callback=None):
            multipart_chunksize = get_s3_multipart_chunk_size(self._s3obj.content_length)
            with ChecksummingSink(multipart_chunksize) as sink:
                self._s3client.download_fileobj(self._s3obj.bucket_name,
                                                self._s3obj.key, sink,
                                                Callback=progress_callback,
                                                Config=self._transfer_config())
                checksums = sink.get_checksums()
                if len(DssChecksums.CHECKSUM_NAMES) != len(checksums):
                    error = f"checksums {checksums} for {self._s3obj.key} do not meet requirements"
                    raise UploadException(status=500, title=error, detail=str(checksums))
                return checksums

        def _compute_checksums_progress_callback(self, bytes_transferred):
            self.bytes_checksummed += bytes_transferred
            if time.time() - self.last_diag_output_time > 1:
                logger.info("elapsed=%0.1f bytes_checksummed=%d" %
                            (time.time() - self.start_time, self.bytes_checksummed))
                self.last_diag_output_time = time.time()

        def _transfer_config(self) -> TransferConfig:
            multipart_chunksize = get_s3_multipart_chunk_size(self._s3obj.content_length)
            return TransferConfig(multipart_threshold=MULTIPART_THRESHOLD,
                                  multipart_chunksize=multipart_chunksize)

import time
import boto3
from boto3.s3.transfer import TransferConfig
from dcplib.checksumming_io import ChecksummingSink
from dcplib.s3_multipart import get_s3_multipart_chunk_size, MULTIPART_THRESHOLD

from .logging import get_logger
from .exceptions import UploadException

logger = get_logger(__name__)
KB = 1024
MB = KB * KB
s3client = boto3.client('s3')


class UploadedFileChecksummer:

    CHECKSUM_NAMES = ('sha1', 'sha256', 'crc32c', 's3_etag')

    def __init__(self, uploaded_file):
        self.uploaded_file = uploaded_file
        self.bytes_checksummed = 0
        self.start_time = None
        self.last_diag_output_time = None
        self.multipart_chunksize = get_s3_multipart_chunk_size(self.uploaded_file.s3obj.content_length)

    def has_checksums(self):
        return sorted(tuple(self.uploaded_file.checksums.keys())) == sorted(self.CHECKSUM_NAMES)

    def checksum(self, report_progress=False):
        if report_progress:
            self.bytes_checksummed = 0
            self.start_time = time.time()
            self.last_diag_output_time = self.start_time
            progress_callback = self._compute_checksums_progress_callback
        else:
            progress_callback = None

        self.checksums = self._compute_checksums(progress_callback=progress_callback)
        return self.checksums

    def _compute_checksums(self, progress_callback=None):
        with ChecksummingSink(self.multipart_chunksize) as sink:
            s3client.download_fileobj(self.uploaded_file.upload_area.bucket_name,
                                      self.uploaded_file.s3obj.key, sink,
                                      Callback=progress_callback,
                                      Config=self._transfer_config())
            checksums = sink.get_checksums()
            if len(self.CHECKSUM_NAMES) != len(checksums):
                error = f"checksums {checksums} for {self.uploaded_file.s3obj.key} do not meet requirements"
                raise UploadException(status=500,
                                      details=error)
            return checksums

    def _compute_checksums_progress_callback(self, bytes_transferred):
        self.bytes_checksummed += bytes_transferred
        if time.time() - self.last_diag_output_time > 1:
            logger.info("elapsed=%0.1f bytes_checksummed=%d" % (time.time() - self.start_time, self.bytes_checksummed))
            self.last_diag_output_time = time.time()

    def _transfer_config(self) -> TransferConfig:
        return TransferConfig(multipart_threshold=MULTIPART_THRESHOLD,
                              multipart_chunksize=self.multipart_chunksize)

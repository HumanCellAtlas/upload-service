import time

import boto3
from boto3.s3.transfer import TransferConfig

from dcplib.checksumming_io import ChecksummingSink

KB = 1024
MB = KB * KB
s3client = boto3.client('s3')


class UploadedFileChecksummer:

    CHECKSUM_NAMES = ('sha1', 'sha256', 'crc32c', 's3_etag')

    def __init__(self, uploaded_file, logger=None):
        self.logger = logger
        self.uploaded_file = uploaded_file
        self.bytes_checksummed = 0
        self.start_time = None
        self.last_diag_output_time = None

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

        return self._compute_checksums(progress_callback=progress_callback)

    def _compute_checksums(self, progress_callback=None):
        with ChecksummingSink() as sink:
            s3client.download_fileobj(self.uploaded_file.upload_area.bucket_name,
                                      self.uploaded_file.s3obj.key, sink,
                                      Callback=progress_callback,
                                      Config=self._transfer_config())
            return sink.get_checksums()

    def _compute_checksums_progress_callback(self, bytes_transferred):
        self.bytes_checksummed += bytes_transferred
        if time.time() - self.last_diag_output_time > 1:
            self._log("elapsed=%0.1f bytes_checksummed=%d" % (time.time() - self.start_time, self.bytes_checksummed))
            self.last_diag_output_time = time.time()

    def _transfer_config(self) -> TransferConfig:
        etag_stride = self._s3_chunk_size(self.uploaded_file.s3obj.content_length)
        return TransferConfig(multipart_threshold=etag_stride,
                              multipart_chunksize=etag_stride)

    def _log(self, message):
        if self.logger:
            self.logger.info(message)

    @staticmethod
    def _s3_chunk_size(file_size: int) -> int:
        if file_size <= 10000 * 64 * MB:  # 640 GB
            return 64 * MB
        else:
            div = file_size // 10000
            if div * 10000 < file_size:
                div += 1
            return ((div + (MB - 1)) // MB) * MB

import os
import sys
import time

from dcplib.checksumming_io import ChecksummingSink
from dcplib.s3_multipart import get_s3_multipart_chunk_size

from .logging import get_logger

logger = get_logger(__name__)

# Checksum(s) to compute for file; current options: crc32c, sha1, sha256, s3_etag
CHECKSUM_NAMES = ['crc32c']


class ClientSideChecksumHandler:
    """ The ClientSideChecksumHandler takes in a file as a parameter and handles any behavior related to
    check-summing the file on the client-side, returning a tag that can be used as metadata when the file is uploaded
    to S3."""

    def __init__(self, filename=None, data=None):
        self._filename = filename
        self._data = data
        self._checksums = {}

        self._compute_checksum()

    def get_checksum_metadata_tag(self):
        """ Returns a map of checksum values by the name of the hashing function that produced it."""
        if not self._checksums:
            logger.warning("No checksums have been computed for this file.")
            return {}
        return {str(_hash_name): str(_hash_value) for _hash_name, _hash_value in self._checksums.items()}

    def _compute_checksum(self):
        """ Calculates checksums for a given file. """
        if self._filename is not None and self._filename.startswith("s3://"):
            logger.warning("Did not perform client-side checksumming for file in S3. To be implemented.")
            pass
        elif self._filename is None and self._data is None:
            logger.warning("Did not perform client-side checksumming because no data was provided.")
            pass
        elif self._filename is not None and self._data is not None:
            logger.warning(
                f"Did not perform client-side checksumming because both a file and raw data was provided. "
                f"Only one may be provided.")
            pass
        else:
            if self._filename is not None:
                checksumCalculator = self.ChecksumCalculator(os.path.getsize(self._filename), filename=self._filename)
                self._checksums = checksumCalculator.compute()
            else:
                checksumCalculator = self.ChecksumCalculator(
                    sys.getsizeof(self._data),
                    data=self._data if isinstance(self._data, (bytes, bytearray)) else self._data.encode())
                self._checksums = checksumCalculator.compute()

    class ChecksumCalculator:
        """ The ChecksumCalculator encapsulates calling various library functions based on the required checksum to
        be calculated on a file."""

        def __init__(self, data_size, data=None, filename=None, checksums=CHECKSUM_NAMES):
            self._data = data
            self._filename = filename
            self._data_size = data_size
            self._checksums = checksums

        def compute(self):
            """ Compute the checksum(s) for the given file and return a map of the value by the hash function name. """
            start_time = time.time()
            if self._data:
                with ChecksummingSink(self._data_size, hash_functions=self._checksums) as sink:
                    sink.write(self._data)
                    checksums = sink.get_checksums()
            elif self._filename:
                _multipart_chunksize = get_s3_multipart_chunk_size(self._data_size)
                with ChecksummingSink(_multipart_chunksize, hash_functions=self._checksums) as sink:
                    with open(self._filename, 'rb') as _file_object:
                        sink.write(_file_object.read(_multipart_chunksize))
                    checksums = sink.get_checksums()

            logger.info("Checksumming took %.2f milliseconds to compute" % ((time.time() - start_time) * 1000))
            return checksums

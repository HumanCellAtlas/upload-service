#!/usr/bin/env python

import argparse
import os
import sys

from urllib3.util import parse_url

from upload.common.upload_area import UploadArea
from upload.common.logging import get_logger
from upload.common.checksum import UploadedFileChecksummer
from upload.common.ingest_notifier import IngestNotifier

logger = get_logger(f"CHECKSUMMER [{os.environ.get('AWS_BATCH_JOB_ID')}]")


class Checksummer:

    def __init__(self, argv):
        self._parse_args(argv)
        upload_area, uploaded_file = self._find_file()
        checksummer = UploadedFileChecksummer(uploaded_file)
        if checksummer.has_checksums():
            logger.info(f"File {uploaded_file.name} is already checksummed.")
        else:
            logger.info(f"Checksumming {uploaded_file.name}...")
            checksums = self._checksum_file(checksummer, uploaded_file)
            logger.info(f"Checksums {checksums} used to tag file {upload_area.uuid}/{uploaded_file.name}")
            self._notify_ingest(uploaded_file)

    def _parse_args(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument('s3_url', metavar="S3_URL", help="S3 URL of file to checksum")
        self.args = parser.parse_args(args=argv)
        url_bits = parse_url(self.args.s3_url)
        self.bucket_name = url_bits.netloc
        self.s3_object_key = url_bits.path.lstrip('/')
        logger.debug(f"bucket_name {self.bucket_name}")
        logger.debug(f"s3_object_key {self.s3_object_key}")

    def _find_file(self):
        key_parts = self.s3_object_key.split('/')
        upload_area_id = key_parts.pop(0)
        filename = "/".join(key_parts)
        logger.debug(f"upload_area_id {upload_area_id}")
        logger.debug(f"filename {filename}")
        upload_area = UploadArea(upload_area_id)
        return upload_area, upload_area.uploaded_file(filename)

    def _checksum_file(self, checksummer, uploaded_file):
        checksums = checksummer.checksum(report_progress=True)
        uploaded_file.checksums = checksums
        uploaded_file.save_tags()
        return checksums

    def _notify_ingest(self, uploaded_file):
        payload = uploaded_file.info()
        status = IngestNotifier().file_was_uploaded(payload)
        logger.info(f"Notified Ingest: payload={payload}, status={status}")


if __name__ == '__main__':
    logger.info(f"STARTED with argv: {sys.argv}")
    Checksummer(sys.argv[1:])

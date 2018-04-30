#!/usr/bin/env python

import argparse
import os
import sys
from urllib3.util import parse_url
from upload.common.upload_area import UploadArea
from upload.common.logging import get_logger
from upload.common.logging import format_logger_with_id
from upload.common.checksum import UploadedFileChecksummer
from upload.common.checksum_event import UploadedFileChecksumEvent
from upload.common.upload_api_client import update_event


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
            checksum_event = UploadedFileChecksumEvent(file_id=uploaded_file.s3obj.key,
                                                       checksum_id=self.checksum_id,
                                                       job_id=os.environ['AWS_BATCH_JOB_ID'],
                                                       status="CHECKSUMMING")
            update_event(checksum_event, uploaded_file.info())
            checksums = self._checksum_file(checksummer, uploaded_file)
            logger.info(f"Checksums {checksums} used to tag file {upload_area.uuid}/{uploaded_file.name}")
            checksum_event.status = "CHECKSUMMED"
            update_event(checksum_event, uploaded_file.info())

    def _parse_args(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument('s3_url', metavar="S3_URL", help="S3 URL of file to checksum")
        parser.add_argument('checksum_id', metavar="CHECKSUM_ID")
        self.args = parser.parse_args(args=argv)
        url_bits = parse_url(self.args.s3_url)
        self.bucket_name = url_bits.netloc
        self.s3_object_key = url_bits.path.lstrip('/')
        self.checksum_id = self.args.checksum_id
        format_logger_with_id(logger, "file_key", self.s3_object_key)
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


if __name__ == '__main__':
    logger.info(f"STARTED with argv: {sys.argv}")
    Checksummer(sys.argv[1:])

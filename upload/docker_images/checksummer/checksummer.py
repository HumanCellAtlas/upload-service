#!/usr/bin/env python

import argparse
import os
import sys
from urllib3.util import parse_url

import boto3

from upload.common.logging import get_logger
from upload.common.dss_checksums import DssChecksums
from upload.common.checksum_event import ChecksumEvent
from upload.common.upload_api_client import update_event
from upload.common.upload_config import UploadConfig

logger = get_logger(f"CHECKSUMMER [{os.environ.get('AWS_BATCH_JOB_ID')}]")


class Checksummer:

    def __init__(self, argv):
        self.bucket_name = None
        self.s3_object_key = None
        self.upload_area_id = None
        self.file_name = None
        UploadConfig.use_env = True  # AWS Secrets are not available to batch jobs, use environment
        self._parse_args(argv)
        s3 = boto3.resource('s3')
        s3obj = s3.Bucket(self.bucket_name).Object(self.s3_object_key)
        self.checksums = DssChecksums(s3obj)

        self.checksum_event = ChecksumEvent(checksum_id=os.environ['CHECKSUM_ID'],
                                            job_id=os.environ['AWS_BATCH_JOB_ID'])
        if self.checksums.are_present():
            logger.info(f"File {self.s3_object_key} is already checksummed.")
            self._update_checksum_event(status="CHECKSUMMED")
        else:
            logger.info(f"Checksumming {self.s3_object_key}...")
            self._update_checksum_event(status="CHECKSUMMING")
            self.checksums.compute(report_progress=True)
            self.checksums.save_as_tags_on_s3_object()
            self._update_checksum_event(status="CHECKSUMMED")
            logger.info(f"Checksums {dict(self.checksums)} used to tag file {self.s3_object_key}")

    def _parse_args(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument('s3_url', metavar="S3_URL", help="S3 URL of file to checksum")
        parser.add_argument('-t', '--test', action='store_true', help="Test only, do not submit results to Upload API")
        self.args = parser.parse_args(args=argv)
        url_bits = parse_url(self.args.s3_url)
        if url_bits.scheme != 's3':
            raise RuntimeError(f"This is not an S3 URL: {self.args.s3_url}")
        self.bucket_name = url_bits.netloc
        self.s3_object_key = url_bits.path.lstrip('/')
        path_parts = self.s3_object_key.split('/')
        self.upload_area_id = path_parts.pop(0)
        self.file_name = "/".join(path_parts)
        logger.debug("url={url} bucket={bucket} s3_key={key} area={area} file={filename}".format(
            url=self.args.s3_url, bucket=self.bucket_name, key=self.s3_object_key, area=self.upload_area_id,
            filename=self.file_name))

    def _update_checksum_event(self, status):
        self.checksum_event.status = status
        if not self.args.test:
            update_event(self.checksum_event, {'upload_area_id': self.upload_area_id,
                                               'name': self.file_name,
                                               'checksums': dict(self.checksums)})


if __name__ == '__main__':
    logger.info(f"STARTED with argv: {sys.argv}")
    Checksummer(sys.argv[1:])

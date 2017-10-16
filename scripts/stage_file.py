#!/usr/bin/env python

"""
Stage files in the HCA Staging Area

Usage:

    stage_file cp <file> <urn>

"""

import argparse, base64, json, os, sys, re

try:
    import boto3
    from boto3.s3.transfer import TransferConfig
except ImportError:
    print("\nPlease install boto3 to use this script, e.g. \"pip install boto3\"\n")
    exit(1)

__version__ = "0.2.0"

KB = 1024
MB = KB * KB


def sizeof_fmt(num, suffix='B'):
    """
    From https://stackoverflow.com/a/1094933
    """
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%d %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


class Main:

    STAGING_BUCKET_TEMPLATE = "org-humancellatlas-staging-%s"
    CLEAR_TO_EOL = "\x1b[0K"

    def __init__(self):
        self._parse_args()
        self._parse_urn(self.args.urn)
        session = boto3.session.Session(**self.aws_credentials)
        self.s3 = session.resource('s3')
        self._stage_file(self.args.file_path, self.args.target_filename)

    def _parse_args(self):
        parser = argparse.ArgumentParser(description=__doc__,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('file_path', metavar="<file>",
                            help="name of file to stage")
        parser.add_argument('urn', metavar='<URN>',
                            help="URN of staging area (given to you by Ingest Broker)")
        parser.add_argument('-t', '--target_filename', metavar="<target_filename>", default=None)
        parser.add_argument('-v', '--version', action='version', version='%(prog)s version {}'.format(__version__),
                            help="show version and exit")
        self.args = parser.parse_args()

    def _parse_urn(self, urn):
        urnbits = urn.split(':')
        assert(urnbits[0:3] == ['hca', 'sta', 'aws'])
        if len(urnbits) == 6:
            self.deployment_stage = urnbits[3]
            self.area_uuid = urnbits[4]
            encoded_credentials = urnbits[5]
        elif len(urnbits) == 5:
            self.deployment_stage = 'dev'
            self.area_uuid = urnbits[3]
            encoded_credentials = urnbits[4]
        else:
            raise RuntimeError("Bad URN")
        uppercase_credentials = json.loads(base64.b64decode(encoded_credentials))
        self.aws_credentials = {k.lower(): v for k, v in uppercase_credentials.items()}

    def callback(self, bytes_transferred):
        self.cumulative_bytes_transferred += bytes_transferred
        percent_complete = (self.cumulative_bytes_transferred * 100) / self.file_size
        sys.stdout.write("\r%s of %s transferred (%.0f%%)%s" %
                         (sizeof_fmt(self.cumulative_bytes_transferred),
                          sizeof_fmt(self.file_size),
                          percent_complete,
                          self.CLEAR_TO_EOL))
        sys.stdout.flush()

    def _stage_file(self, file_path, target_filename=None):
        file_s3_key = "%s/%s" % (self.area_uuid, target_filename or os.path.basename(file_path))
        print("Uploading %s to staging area %s..." % (os.path.basename(file_path), file_s3_key))
        self.file_size = os.stat(file_path).st_size
        bucket_name = self.STAGING_BUCKET_TEMPLATE % (self.deployment_stage,)
        bucket = self.s3.Bucket(bucket_name)
        obj = bucket.Object(file_s3_key)
        content_type = 'application/json' if re.search('.json$', file_path) else 'hca-data-file'
        with open(file_path, 'rb') as fh:
            self.cumulative_bytes_transferred = 0
            obj.upload_fileobj(fh,
                               ExtraArgs={'ContentType': content_type,
                                          'ACL': 'bucket-owner-full-control'},
                               Callback=self.callback,
                               Config=self.transfer_config(self.file_size)
                               )
        print("\n")

    @classmethod
    def transfer_config(cls, file_size):
        etag_stride = cls._s3_chunk_size(file_size)
        return TransferConfig(multipart_threshold=etag_stride,
                              multipart_chunksize=etag_stride)

    @staticmethod
    def _s3_chunk_size(file_size):
        if file_size <= 10000 * 64 * MB:
            return 64 * MB
        else:
            div = file_size // 10000
            if div * 10000 < file_size:
                div += 1
            return ((div + (MB-1)) // MB) * MB


if __name__ == '__main__':
    runner = Main()